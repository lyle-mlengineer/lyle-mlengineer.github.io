"""Persistence and orchestration for gap answers, facts and conflicts."""

import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, FactRecord, GapAnswer, Run
from app.models.base import new_id, utcnow
from app.pipeline.extract.candidates import slug, supported_numbers
from app.pipeline.extract.model import _PROOF_ORDER
from app.pipeline.extract.requirements import evaluate_gaps
from app.pipeline.resolve.conflicts import FactCandidate, resolve_conflict
from app.pipeline.resolve.questions import generate_questions, question_for_slot
from app.pipeline.resolve.schema import RequirementSlot, slot_for
from app.pipeline.resolve.tiers import assign_tier
from app.schemas.content import ContentModel, Fact, Offering, Proof, QuoteRef
from app.schemas.profile import Gap, ImageAsset, LogoAsset, SiteProfile
from app.schemas.resolve import (
    AnswerIn,
    FactActionIn,
    GapReport,
    RenderOut,
)

_NUMBER = re.compile(r"\d")
_MODEL_KEYS = {"proof.metrics", "proof.quote", "commerce.price"}
_SAFE_FREE_TEXT_DIGITS = {"proof.quote", "attribution.quote", "recency.metrics"}


class ResolveError(ValueError):
    """A request that cannot be applied to this run."""


class ConflictError(ResolveError):
    """A request that conflicts with an accepted fact."""


class NotFoundError(ResolveError):
    """A requested fact does not exist for this run."""


def _profile(run: Run) -> SiteProfile:
    if not run.profile_json:
        raise ResolveError("run has no profile; analyze the site first")
    return SiteProfile.model_validate(run.profile_json)


def _model(run: Run) -> ContentModel:
    if not run.content_model_json:
        raise ResolveError("run has no content model; analyze the site first")
    return ContentModel.model_validate(run.content_model_json)


def _accepted(db: Session, run: Run) -> list[FactRecord]:
    return list(
        db.scalars(
            select(FactRecord)
            .where(FactRecord.run_id == run.id, FactRecord.status == "accepted")
            .order_by(FactRecord.id)
        )
    )


def _all_facts(db: Session, run: Run) -> list[FactRecord]:
    return list(
        db.scalars(
            select(FactRecord)
            .where(FactRecord.run_id == run.id)
            .order_by(FactRecord.id)
        )
    )


def _new_fact_id(db: Session, run: Run, prefix: str = "u") -> str:
    for _ in range(20):
        candidate = f"{prefix}_{new_id()[:12]}"
        if db.get(FactRecord, (run.id, candidate)) is None:
            return candidate
    raise ResolveError("could not allocate a fact id")


def _audit(
    db: Session,
    run: Run,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    meta: dict[str, object],
) -> None:
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
        )
    )


def ensure_facts(db: Session, run: Run) -> None:
    """Backfill ``facts`` from an existing content model, once per run."""
    existing = db.scalar(
        select(func.count()).select_from(FactRecord).where(FactRecord.run_id == run.id)
    )
    if existing:
        return
    if not run.content_model_json:
        return
    model = ContentModel.model_validate(run.content_model_json)
    for fact in model.facts:
        db.add(
            FactRecord(
                run_id=run.id,
                id=fact.id,
                tenant_id=run.tenant_id,
                key=fact.key,
                value=fact.value,
                unit=fact.unit,
                label=fact.label,
                as_of=fact.as_of,
                source_type=fact.source_type,
                source=fact.source,
                source_id=fact.source_id,
                source_page=fact.source_page,
                source_quote=fact.source_quote,
                confidence=fact.confidence,
                tier=fact.tier,
                retrieved_at=fact.retrieved_at,
                published_at=fact.published_at,
                permission=fact.permission,
                status="accepted",
            )
        )
    db.flush()


def _fact_from_record(record: FactRecord) -> Fact:
    return Fact(
        id=record.id,
        key=record.key,
        value=record.value,
        unit=record.unit,
        label=record.label,
        as_of=record.as_of,
        source_type=record.source_type,
        source=record.source,
        source_id=record.source_id,
        source_page=record.source_page,
        source_quote=record.source_quote or record.value,
        confidence=record.confidence,
        tier=record.tier,
        retrieved_at=record.retrieved_at,
        published_at=record.published_at,
        permission=record.permission,
    )


def _quote_meta(
    db: Session, run: Run, model: ContentModel
) -> tuple[str | None, str | None]:
    row = db.scalar(
        select(GapAnswer)
        .where(
            GapAnswer.run_id == run.id,
            GapAnswer.gap_key == "proof.quote",
            GapAnswer.action == "answered",
        )
        .order_by(GapAnswer.created_at.desc())
    )
    if row:
        attribution = row.answer_json.get("attribution")
        role = row.answer_json.get("role")
        if attribution or role:
            return attribution, role
    if model.quote is not None:
        return model.quote.attribution, model.quote.role
    return None, None


def _rank_key(fact: Fact) -> tuple[int, str]:
    index = _PROOF_ORDER.index(fact.key) if fact.key in _PROOF_ORDER else len(_PROOF_ORDER)
    return index, fact.id


def _clean_text(text: str, facts: list[Fact], fallback: str = "") -> str:
    if not text:
        return fallback
    return text if supported_numbers(text, facts) else fallback


def _rebuild_model(
    db: Session,
    run: Run,
    model: ContentModel,
    accepted: list[FactRecord],
) -> ContentModel:
    all_records = _all_facts(db, run)
    record_keys = {record.key for record in all_records}
    accepted_by_key = {record.key: record for record in accepted}
    existing_keys = {fact.key for fact in model.facts}

    by_key: dict[str, Fact] = {}
    for fact in model.facts:
        # A rejected or quarantined fact with no accepted replacement must stop
        # rendering. Facts without a stored row predate the backfill and stay.
        if fact.key in accepted_by_key or fact.key in record_keys:
            continue
        by_key[fact.key] = fact
    for key, record in accepted_by_key.items():
        if key in existing_keys or key in _MODEL_KEYS or key.startswith("metric."):
            by_key[key] = _fact_from_record(record)
    facts = list(by_key.values())
    by_id = {fact.id: fact for fact in facts}
    available_ids = set(by_id)

    offerings = []
    for offering in model.offerings[:4]:
        if not supported_numbers(offering.title, facts):
            continue
        metric_id = offering.metric_fact_id
        if metric_id not in available_ids:
            metric_id = None
        offerings.append(
            offering.model_copy(
                update={
                    "metric_fact_id": metric_id,
                    "one_liner": _clean_text(offering.one_liner, facts, offering.title),
                }
            )
        )
    offer_fact = next((record for record in accepted if record.key == "offer.core"), None)
    if offer_fact is not None and len(offerings) < 4:
        value = offer_fact.value.strip()
        if value and not any(item.title.casefold() == value.casefold() for item in offerings):
            offerings.append(
                Offering(
                    key=f"offer.{slug(value, 40)}",
                    title=value[:120],
                    one_liner=value[:320],
                )
            )

    projects = []
    for project in model.projects[:8]:
        if not supported_numbers(project.name, facts):
            continue
        badge_id = project.badge_fact_id
        if badge_id not in available_ids:
            badge_id = None
        projects.append(
            project.model_copy(
                update={
                    "badge_fact_id": badge_id,
                    "blurb": _clean_text(project.blurb, facts),
                }
            )
        )

    proof_ids: list[str] = []
    for item in model.proof:
        fact = by_id.get(item.fact_id)
        if fact is not None and fact.tier in {"A", "B"} and fact.id not in proof_ids:
            proof_ids.append(fact.id)
    ranked = sorted(
        (
            fact
            for fact in facts
            if fact.key != "proof.quote" and fact.tier in {"A", "B"}
        ),
        key=_rank_key,
    )
    for fact in ranked:
        if len(proof_ids) >= 4:
            break
        if fact.id not in proof_ids:
            proof_ids.append(fact.id)
    proof = [
        Proof(fact_id=fact_id, emphasis="lead" if index == 0 else "normal")
        for index, fact_id in enumerate(proof_ids[:4])
    ]

    quote: QuoteRef | None = None
    quote_fact = next((fact for fact in facts if fact.key == "proof.quote"), None)
    if quote_fact is not None and quote_fact.permission in {
        "published_on_site",
        "attested",
        "brand_document",
    }:
        attribution, role = _quote_meta(db, run, model)
        attribution_fact = next(
            (record for record in accepted if record.key == "attribution.quote"), None
        )
        if attribution_fact is not None:
            value = attribution_fact.value.strip()
            if "," in value:
                name, rest = value.split(",", 1)
                attribution, role = name.strip(), rest.strip() or None
            else:
                attribution = value
        quote = QuoteRef(
            fact_id=quote_fact.id,
            attribution=attribution[:120] if attribution else None,
            role=role[:160] if role else None,
        )

    return ContentModel.model_validate(
        {
            "thesis": _clean_text(
                model.thesis, facts, fallback="Selected work and capabilities"
            ),
            "audience": _clean_text(model.audience, facts),
            "arc": model.arc,
            "facts": [fact.model_dump(mode="json") for fact in facts],
            "offerings": [item.model_dump(mode="json") for item in offerings],
            "projects": [item.model_dump(mode="json") for item in projects],
            "proof": [item.model_dump(mode="json") for item in proof],
            "quote": quote.model_dump(mode="json") if quote else None,
            "cta": model.cta.model_dump(mode="json"),
            "disclaimers": model.disclaimers,
        }
    )


def _apply_fact_to_profile(profile: SiteProfile, record: FactRecord) -> None:
    key = record.key
    value = record.value.strip()
    if not value:
        return
    if key == "identity.name":
        profile.entities.person.name = value
    elif key == "identity.role":
        profile.entities.person.role = value
    elif key == "identity.location":
        profile.entities.person.location = value
    elif key == "contact.email":
        profile.entities.contact.email = value
    elif key == "contact.url":
        profile.entities.contact.url = value
    elif key == "proof.client_logo":
        profile.brand.logo = LogoAsset(url=value)
    elif key in {"visual.project_shot", "identity.portrait"}:
        role = "product_shot" if key == "visual.project_shot" else "portrait"
        if not any(image.role == role and image.url == value for image in profile.images):
            profile.images.append(
                ImageAsset(
                    asset_id=f"user_{record.id}",
                    url=value,
                    role=role,
                )
            )


def _coverage(db: Session, run: Run) -> float:
    accepted = db.scalar(
        select(func.count())
        .select_from(FactRecord)
        .where(FactRecord.run_id == run.id, FactRecord.status == "accepted")
    ) or 0
    stats = run.stats_json or {}
    rejected = stats.get("rejected_facts") or []
    total = accepted + len(rejected)
    return round(accepted / total, 3) if total else 0.0


def _recompute_gaps(
    db: Session,
    run: Run,
    profile: SiteProfile,
    model: ContentModel,
) -> list[Gap]:
    accepted = {record.key: record for record in _accepted(db, run)}
    skipped = {
        row.gap_key
        for row in db.scalars(
            select(GapAnswer).where(
                GapAnswer.run_id == run.id, GapAnswer.action == "skip"
            )
        )
    }
    gaps = evaluate_gaps(profile, model, today=date.today())
    for gap in gaps:
        if gap.key in accepted:
            gap.status = "resolved"
            gap.resolved_by = accepted[gap.key].id
        elif gap.key in skipped:
            gap.status = "skipped"
            gap.resolved_by = "user_skip"
    profile.gaps = gaps
    return gaps


def _update_stats(
    db: Session,
    run: Run,
    gaps: list[Gap],
) -> float:
    accepted = db.scalar(
        select(func.count())
        .select_from(FactRecord)
        .where(FactRecord.run_id == run.id, FactRecord.status == "accepted")
    ) or 0
    stats = dict(run.stats_json or {})
    stats["facts"] = accepted
    stats["coverage"] = _coverage(db, run)
    stats["gaps"] = [
        {
            "key": gap.key,
            "class": gap.gap_class,
            "severity": gap.severity,
            "status": gap.status,
        }
        for gap in gaps
    ]
    stats["blocking_open"] = [
        gap.key
        for gap in gaps
        if gap.severity == "blocking" and gap.status == "open"
    ]
    run.stats_json = stats
    return stats["coverage"]


def rebuild(db: Session, run: Run) -> tuple[SiteProfile, ContentModel, list[Gap]]:
    """Reapply accepted facts to the profile, model, gaps and stats."""
    db.flush()
    ensure_facts(db, run)
    profile = _profile(run)
    model = _model(run)
    accepted = _accepted(db, run)
    for record in accepted:
        _apply_fact_to_profile(profile, record)
    model = _rebuild_model(db, run, model, accepted)
    gaps = _recompute_gaps(db, run, profile, model)
    run.profile_json = profile.model_dump(mode="json")
    run.content_model_json = model.model_dump(mode="json")
    _update_stats(db, run, gaps)
    db.flush()
    return profile, model, gaps


def build_gap_report(db: Session, run: Run) -> GapReport:
    ensure_facts(db, run)
    profile = _profile(run)
    facts = _all_facts(db, run)
    accepted = [fact for fact in facts if fact.status == "accepted"]
    questions = generate_questions(profile.gaps, facts)
    blocking = [
        gap.key
        for gap in profile.gaps
        if gap.severity == "blocking" and gap.status == "open"
    ]
    stats = run.stats_json or {}
    coverage = float(stats.get("coverage", 0.0))
    return GapReport(
        run_id=run.id,
        status=run.status,
        coverage=coverage,
        facts_count=len(accepted),
        gaps=profile.gaps,
        questions=questions,
        blocking_open=blocking,
        ready=not blocking,
    )


def _validate_answer(slot: RequirementSlot, answer: AnswerIn) -> str:
    value = (answer.value or "").strip()
    if slot.question_type == "number_unit":
        if not _NUMBER.search(value):
            raise ResolveError(f"{slot.key} needs a number")
    elif slot.question_type == "url":
        if not value.lower().startswith(("http://", "https://")):
            raise ResolveError(f"{slot.key} needs an http(s) URL")
    elif slot.key not in _SAFE_FREE_TEXT_DIGITS and _NUMBER.search(value):
        raise ResolveError(
            f"{slot.key} is free text; add numbers as a metric so they stay grounded"
        )
    if slot.requires_attestation and not answer.attest:
        raise ResolveError(f"{slot.key} requires attest=true")
    return value


def _answer_fact(
    db: Session,
    run: Run,
    actor_id: str,
    slot: RequirementSlot,
    answer: AnswerIn,
    value: str,
) -> tuple[FactRecord, str]:
    """Create an answer fact and reconcile it with any accepted same-key fact."""
    unit = answer.unit or slot.unit
    if slot.question_type == "number_unit" and unit:
        if value.startswith(unit):
            value = value[len(unit) :].strip()
        if value.endswith(unit):
            value = value[: -len(unit)].strip()
    source_quote = f"{slot.prompt} Answer: {value}"[:2000]
    permission = None
    if slot.key == "proof.quote" or slot.key == "proof.client_logo":
        permission = "attested" if answer.attest else None

    existing = db.scalar(
        select(FactRecord).where(
            FactRecord.run_id == run.id,
            FactRecord.key == slot.key,
            FactRecord.status == "accepted",
        )
    )
    new_id_value = _new_fact_id(db, run)
    candidate = FactCandidate(
        fact_id=new_id_value,
        key=slot.key,
        value=value,
        source_type="user_answer",
        tier=assign_tier("user_answer"),
        attested=answer.attest,
    )
    status = "accepted"
    note = "added"
    if existing is not None:
        resolution = resolve_conflict(
            FactCandidate(
                fact_id=existing.id,
                key=existing.key,
                value=existing.value,
                source_type=existing.source_type,
                tier=existing.tier,
                attested=existing.attested_by is not None,
            ),
            candidate,
        )
        note = resolution.reason
        if resolution.winner_id == existing.id:
            status = "quarantined"
        else:
            existing.status = "quarantined"
            db.flush()
            _audit(
                db,
                run,
                actor_id,
                "fact.quarantined",
                "fact",
                existing.id,
                {
                    "key": existing.key,
                    "reason": resolution.reason,
                    "replaced_by": new_id_value,
                },
            )

    record = FactRecord(
        run_id=run.id,
        id=new_id_value,
        tenant_id=run.tenant_id,
        key=slot.key,
        value=value[:600],
        unit=unit,
        label=slot.key,
        as_of=None,
        source_type="user_answer",
        source="user_answer",
        source_id=None,
        source_quote=source_quote,
        confidence=1.0,
        tier=assign_tier("user_answer"),
        retrieved_at=utcnow().date(),
        published_at=None,
        permission=permission,
        status=status,
        attested_by=actor_id if answer.attest else None,
    )
    db.add(record)
    db.flush()
    return record, note


def apply_answers(
    db: Session,
    run: Run,
    actor_id: str,
    answers: list[AnswerIn],
) -> GapReport:
    profile = _profile(run)
    current = {gap.key: gap for gap in profile.gaps}
    for answer in answers:
        slot = slot_for(answer.key)
        if slot is None:
            raise ResolveError(f"unknown gap key {answer.key!r}")
        gap = current.get(answer.key)
        if gap is not None and gap.status in {"resolved"}:
            continue

        question = question_for_slot(slot, severity=gap.severity if gap else None)
        if answer.skip:
            db.add(
                GapAnswer(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    gap_key=answer.key,
                    question_json=question.model_dump(mode="json", by_alias=True),
                    answer_json={"skip": True},
                    action="skip",
                    fact_id=None,
                )
            )
            _audit(
                db,
                run,
                actor_id,
                "gap.skipped",
                "run",
                run.id,
                {"key": answer.key, "question": question.prompt},
            )
            continue

        value = _validate_answer(slot, answer)
        record, note = _answer_fact(db, run, actor_id, slot, answer, value)
        db.add(
            GapAnswer(
                run_id=run.id,
                tenant_id=run.tenant_id,
                gap_key=answer.key,
                question_json=question.model_dump(mode="json", by_alias=True),
                answer_json={
                    "value": value,
                    "unit": answer.unit or slot.unit,
                    "attest": answer.attest,
                    "attribution": answer.attribution,
                    "role": answer.role,
                    "status": record.status,
                    "note": note,
                },
                action="answered",
                fact_id=record.id,
            )
        )
        _audit(
            db,
            run,
            actor_id,
            "gap.answered",
            "fact",
            record.id,
            {
                "key": answer.key,
                "value": record.value,
                "attested": answer.attest,
                "status": record.status,
                "note": note,
            },
        )

    rebuild(db, run)
    return build_gap_report(db, run)


def _fact_or_404(db: Session, run: Run, fact_id: str) -> FactRecord:
    fact = db.scalar(
        select(FactRecord).where(
            FactRecord.run_id == run.id,
            FactRecord.id == fact_id,
            FactRecord.tenant_id == run.tenant_id,
        )
    )
    if fact is None:
        raise NotFoundError("fact not found")
    return fact


def apply_fact_action(
    db: Session,
    run: Run,
    actor_id: str,
    fact_id: str,
    body: FactActionIn,
) -> FactRecord:
    if body.action == "override" and not body.attest:
        raise ResolveError("override requires attest=true")
    if body.action == "override" and not (body.value and body.value.strip()):
        raise ResolveError("override requires a value")

    record = _fact_or_404(db, run, fact_id)

    if body.action == "reject":
        record.status = "rejected"
        _audit(
            db,
            run,
            actor_id,
            "fact.rejected",
            "fact",
            record.id,
            {"key": record.key, "value": record.value, "reason": body.reason},
        )
        rebuild(db, run)
        return record

    if body.action == "accept":
        if record.status == "accepted":
            return record
        occupying = db.scalar(
            select(FactRecord).where(
                FactRecord.run_id == run.id,
                FactRecord.key == record.key,
                FactRecord.status == "accepted",
                FactRecord.id != record.id,
            )
        )
        if occupying is not None:
            raise ConflictError(
                f"another accepted fact already occupies {record.key!r}"
            )
        record.status = "accepted"
        _audit(
            db,
            run,
            actor_id,
            "fact.accepted",
            "fact",
            record.id,
            {"key": record.key, "value": record.value},
        )
        rebuild(db, run)
        return record

    # Override. Quarantine every accepted occupant of the key first so the
    # partial unique index never sees two accepted rows.
    value = (body.value or "").strip()
    new_id_value = _new_fact_id(db, run)
    occupants = list(
        db.scalars(
            select(FactRecord).where(
                FactRecord.run_id == run.id,
                FactRecord.key == record.key,
                FactRecord.status == "accepted",
            )
        )
    )
    for occupant in occupants:
        occupant.status = "quarantined"
        _audit(
            db,
            run,
            actor_id,
            "fact.quarantined",
            "fact",
            occupant.id,
            {
                "key": occupant.key,
                "reason": "user override",
                "replaced_by": new_id_value,
            },
        )
    db.flush()

    permission = record.permission or ("attested" if body.attest else None)
    replacement = FactRecord(
        run_id=run.id,
        id=new_id_value,
        tenant_id=run.tenant_id,
        key=record.key,
        value=value[:600],
        unit=body.unit or record.unit,
        label=record.label,
        as_of=body.as_of or record.as_of,
        source_type="user_answer",
        source="user_answer",
        source_id=None,
        source_quote=f"User override of {record.id}: {value}"[:2000],
        confidence=1.0,
        tier=assign_tier("user_answer"),
        retrieved_at=utcnow().date(),
        published_at=record.published_at,
        permission=permission,
        status="accepted",
        attested_by=actor_id,
    )
    db.add(replacement)
    db.flush()
    _audit(
        db,
        run,
        actor_id,
        "fact.overridden",
        "fact",
        replacement.id,
        {
            "key": record.key,
            "old_fact_id": record.id,
            "old_value": record.value,
            "new_value": replacement.value,
            "overrides": record.source_type,
            "attested": True,
        },
    )
    rebuild(db, run)
    return replacement


def render_report(db: Session, run: Run) -> RenderOut:
    report = build_gap_report(db, run)
    blocking = [
        gap
        for gap in report.gaps
        if gap.severity == "blocking" and gap.status == "open"
    ]
    open_gaps = [gap for gap in report.gaps if gap.status == "open"]
    return RenderOut(
        run_id=run.id,
        status="blocked" if blocking else "ready",
        coverage=report.coverage,
        blocking_gaps=blocking,
        open_gaps=open_gaps,
        questions=report.questions,
        ready=not blocking,
    )
