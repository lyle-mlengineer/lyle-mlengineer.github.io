"""Orchestrate web search: plan queries, fetch, score, extract and cite.

Search is a rung, not a dependency. A missing key, an unreachable provider or a
page that tries to give the model instructions all end in the same honest place:
the gap stays open and the run is labelled with what happened.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditLog, FactRecord, Run, WebQuery
from app.models.base import new_id, utcnow
from app.pipeline.extract.deterministic import metric_facts_for_text
from app.pipeline.extract.ground import ground_fact
from app.pipeline.resolve import search as search_mod
from app.pipeline.resolve.conflicts import FactCandidate, resolve_conflict
from app.pipeline.resolve.schema import slot_for
from app.pipeline.resolve.service import build_gap_report, rebuild
from app.pipeline.resolve.tiers import assign_tier
from app.schemas.profile import SiteProfile
from app.schemas.resolve import FactOut
from app.schemas.search import SearchOut, SearchQueryOut

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "web_extract_v1.md"
PROMPT_VERSION = "web_extract_v1"

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PRICE = re.compile(r"[$€£]\s?(\d[\d,]*(?:\.\d+)?)")
_ROLE_LABEL = re.compile(r"\b(?:role|title|position)\s*[:\-—]\s*([^\n]{3,80})", re.I)
_NAME_LABEL = re.compile(r"\bname\s*[:\-—]\s*([^\n]{2,80})", re.I)
_ROLE_SENTENCE = re.compile(
    r"\b(?:is|works?|worked|serves?)\s+(?:as\s+)?(?:a|an)\s+([^.\n]{3,60})",
    re.I,
)
_BASED = re.compile(r"\b(?:based in|located in|lives in)\s+([A-Z][^.\n]{1,60})", re.I)
_OFFER = re.compile(
    r"\b(?:we|i|[A-Z][\w&.'-]+(?:\s+[A-Z][\w&.'-]+){0,3})\s+"
    r"(?:build|builds|help|helps|design|designs|make|makes|create|creates|"
    r"provide|provides|deliver|delivers|offer|offers)\b[^.\n]{0,200}",
)
_MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)[a-z]*\s+(\d{4})\b",
    re.I,
)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_ROLE_WORDS = {
    "engineer",
    "designer",
    "founder",
    "developer",
    "manager",
    "scientist",
    "consultant",
    "director",
    "lead",
    "architect",
    "researcher",
    "analyst",
    "strategist",
    "producer",
    "editor",
    "writer",
    "ceo",
    "cto",
    "coo",
    "head",
}
_METRIC_KEYS = {"proof.metrics", "commerce.price", "recency.metrics"}


@dataclass(frozen=True)
class WebCandidate:
    key: str
    value: str
    quote: str
    published_at: date | None
    tier: str
    confidence: float
    unit: str | None = None
    label: str = ""
    as_of: str | None = None
    method: str = "heuristic"


@dataclass
class WebSearchReport:
    status: str
    label: str
    queries: list[WebQuery] = field(default_factory=list)
    facts: list[FactRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolved_gaps: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _profile(run: Run) -> SiteProfile:
    if not run.profile_json:
        raise ValueError("run has no site profile; analyze the site first")
    return SiteProfile.model_validate(run.profile_json)


def _accepted(db: Session, run: Run) -> list[FactRecord]:
    return list(
        db.scalars(
            select(FactRecord)
            .where(FactRecord.run_id == run.id, FactRecord.status == "accepted")
            .order_by(FactRecord.id)
        )
    )


def _set_status(run: Run, status: str) -> None:
    stats = dict(run.stats_json or {})
    stats["web_search"] = status
    run.stats_json = stats


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    stops = [index for index in (text.find(".", end), text.find("\n", end)) if index != -1]
    right = min(stops) + 1 if stops else len(text)
    return text[left:right].strip(" .\n") or text[start:end].strip()


def _title_name(title: str) -> str | None:
    for separator in (" | ", " — ", " – ", " - "):
        first = title.split(separator)[0].strip()
        if 2 <= len(first.split()) <= 4 and first[0].isupper():
            return first
    return None


def _identity(gap_key: str, source: search_mod.FetchedSource) -> WebCandidate | None:
    text = source.text
    if gap_key == "identity.name":
        match = _NAME_LABEL.search(text)
        value = match.group(1).strip(" .,-") if match else _title_name(source.title)
        if not value:
            return None
        quote = match.group(0).strip() if match else source.title
        if value not in quote:
            quote = _sentence_around(text, text.find(value), text.find(value) + len(value))
        if not quote:
            return None
        return WebCandidate(
            key=gap_key,
            value=value[:600],
            quote=quote[:2000],
            published_at=source.published_at,
            tier="C",
            confidence=0.7,
            label="person name",
        )
    if gap_key == "identity.role":
        match = _ROLE_LABEL.search(text) or _ROLE_SENTENCE.search(text)
        value = match.group(1).strip(" .,-") if match else None
        if value and not any(word in value.lower() for word in _ROLE_WORDS):
            value = None
        if value is None:
            title_name = _title_name(source.title)
            if title_name and title_name != source.title:
                tail = source.title.split(title_name, 1)[-1].strip(" |—-–")
                if tail and any(word in tail.lower() for word in _ROLE_WORDS):
                    value, match = tail, None
        if not value:
            return None
        start = text.find(value)
        quote = (
            match.group(0).strip()
            if match
            else _sentence_around(text, start, start + len(value))
        )
        return WebCandidate(
            key=gap_key,
            value=value[:600],
            quote=quote[:2000],
            published_at=source.published_at,
            tier="C",
            confidence=0.7,
            label="role",
        )
    if gap_key == "identity.location":
        match = _BASED.search(text)
        if not match:
            return None
        return WebCandidate(
            key=gap_key,
            value=match.group(1).strip(" .,-")[:600],
            quote=match.group(0).strip()[:2000],
            published_at=source.published_at,
            tier="C",
            confidence=0.7,
            label="location",
        )
    return None


def _offer(gap_key: str, source: search_mod.FetchedSource) -> WebCandidate | None:
    match = _OFFER.search(source.text)
    if not match:
        return None
    value = match.group(0).strip(" .,-")
    if len(value) < 8:
        return None
    quote = _sentence_around(source.text, match.start(), match.end())
    return WebCandidate(
        key=gap_key,
        value=value[:600],
        quote=quote[:2000],
        published_at=source.published_at,
        tier="C",
        confidence=0.7,
        label="offering",
    )


def _metric(gap_key: str, source: search_mod.FetchedSource) -> WebCandidate | None:
    facts = metric_facts_for_text(
        source.text,
        source=source.url,
        source_id=source.url,
        retrieved_at=date.today(),
    )
    if not facts:
        return None
    fact = facts[0]
    return WebCandidate(
        key=gap_key,
        value=fact.value,
        quote=fact.source_quote or source.text[:600],
        published_at=source.published_at,
        tier="C",
        confidence=0.75,
        unit=fact.unit,
        label=fact.label,
        as_of=fact.as_of,
    )


def _price(gap_key: str, source: search_mod.FetchedSource) -> WebCandidate | None:
    match = _PRICE.search(source.text)
    if not match:
        return None
    quote = _sentence_around(source.text, match.start(), match.end())
    currency = match.group(0)[0]
    return WebCandidate(
        key=gap_key,
        value=match.group(1).replace(",", ""),
        quote=quote[:2000],
        published_at=source.published_at,
        tier="C",
        confidence=0.75,
        unit=currency,
        label="entry price",
    )


def _recency(gap_key: str, source: search_mod.FetchedSource) -> WebCandidate | None:
    match = _MONTH.search(source.text)
    if not match:
        return None
    as_of = f"{match.group(2)}-{_MONTHS[match.group(1).lower()]:02d}"
    return WebCandidate(
        key=gap_key,
        value=match.group(0)[:600],
        quote=_sentence_around(source.text, match.start(), match.end())[:2000],
        published_at=source.published_at,
        tier="C",
        confidence=0.75,
        label="measured",
        as_of=as_of,
    )


def _heuristic(gap_key: str, source: search_mod.FetchedSource) -> WebCandidate | None:
    if gap_key.startswith("identity."):
        return _identity(gap_key, source)
    if gap_key == "offer.core":
        return _offer(gap_key, source)
    if gap_key in {"proof.metrics", "recency.metrics"}:
        return _metric(gap_key, source) if gap_key == "proof.metrics" else _recency(
            gap_key, source
        )
    if gap_key == "commerce.price":
        return _price(gap_key, source)
    if gap_key == "contact.email":
        match = _EMAIL.search(source.text)
        if match:
            return WebCandidate(
                key=gap_key,
                value=match.group(0),
                quote=_sentence_around(source.text, match.start(), match.end())[:2000],
                published_at=source.published_at,
                tier="C",
                confidence=0.7,
                label="email",
            )
    return None


def _llm(
    gap_key: str,
    source: search_mod.FetchedSource,
    *,
    gap_class: str,
) -> WebCandidate | None:
    from app.pipeline.understand.llm import LLMClient, LLMError

    client = LLMClient()
    if not client.available:
        return None
    slot = slot_for(gap_key)
    payload = {
        "gap": {
            "key": gap_key,
            "class": gap_class,
            "question": slot.prompt if slot else gap_key,
        },
        "source": {
            "url": source.url,
            "published_at": source.published_at.isoformat()
            if source.published_at
            else None,
            "content": search_mod.wrap_untrusted(source.text[:12000]),
        },
    }
    try:
        answer = client.complete_json(
            load_prompt(), json.dumps(payload, ensure_ascii=False), temperature=0.0
        )
    except (LLMError, ValueError) as exc:
        logger.warning("web extraction LLM failed for %s: %s", gap_key, exc)
        return None

    value = answer.get("value")
    quote = answer.get("source_quote")
    if not isinstance(value, str) or not value.strip():
        return None
    if not isinstance(quote, str) or not quote.strip():
        return None
    accepted, reason = ground_fact(value, quote, source.text)
    if not accepted:
        logger.info("web LLM answer rejected for %s: %s", gap_key, reason)
        return None

    unit = answer.get("unit") if isinstance(answer.get("unit"), str) else None
    try:
        confidence = float(answer.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7
    return WebCandidate(
        key=gap_key,
        value=value.strip()[:600],
        quote=quote.strip()[:2000],
        published_at=source.published_at,
        tier="C",
        unit=unit[:40] if unit else None,
        label=gap_key,
        confidence=max(0.0, min(confidence, 1.0)),
        method="llm",
    )


def _tier_for(score: search_mod.ScoreBreakdown, published_at: date | None) -> str:
    if published_at is None:
        # A number without a publication date may be attributed prose at most.
        return "C"
    effective = max(score.total, 0.9) if score.first_party else score.total
    return assign_tier(
        "web",
        score=effective,
        corroborated=bool(score.first_party) or score.corroboration >= 0.5,
    )


def _audit(
    db: Session,
    run: Run,
    actor_id: str,
    action: str,
    target_id: str,
    meta: dict[str, object],
) -> None:
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action=action,
            target_type="fact" if action.startswith("web.fact") else "web_query",
            target_id=target_id,
            meta=meta,
        )
    )


def _persist(
    db: Session,
    run: Run,
    actor_id: str,
    candidate: WebCandidate,
    query: WebQuery,
) -> tuple[FactRecord, bool]:
    existing = db.scalar(
        select(FactRecord).where(
            FactRecord.run_id == run.id,
            FactRecord.key == candidate.key,
            FactRecord.status == "accepted",
        )
    )
    if (
        existing is not None
        and existing.source_id == query.id
        and existing.value == candidate.value
    ):
        return existing, False

    fact_id = f"w_{new_id()[:12]}"
    status = "accepted"
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
            FactCandidate(
                fact_id=fact_id,
                key=candidate.key,
                value=candidate.value,
                source_type="web",
                tier=candidate.tier,
            ),
        )
        if resolution.winner_id == existing.id:
            status = "quarantined"
        elif resolution.winner_id is None:
            existing.status = "quarantined"
            status = "quarantined"
            db.flush()
            _audit(
                db,
                run,
                actor_id,
                "fact.quarantined",
                existing.id,
                {
                    "key": existing.key,
                    "reason": resolution.reason,
                    "replaced_by": fact_id,
                },
            )
        else:
            existing.status = "quarantined"
            db.flush()
            _audit(
                db,
                run,
                actor_id,
                "fact.quarantined",
                existing.id,
                {
                    "key": existing.key,
                    "reason": resolution.reason,
                    "replaced_by": fact_id,
                },
            )

    published = candidate.published_at
    as_of = candidate.as_of
    if as_of is None and published is not None:
        as_of = f"{published.year}-{published.month:02d}"
    record = FactRecord(
        run_id=run.id,
        id=fact_id,
        tenant_id=run.tenant_id,
        key=candidate.key,
        value=candidate.value[:600],
        unit=candidate.unit,
        label=candidate.label[:160],
        as_of=as_of,
        source_type="web",
        source=query.chosen_url or query.query[:2048],
        source_id=query.id,
        source_page=None,
        source_quote=candidate.quote[:2000],
        confidence=candidate.confidence,
        tier=candidate.tier,
        retrieved_at=utcnow().date(),
        published_at=published,
        permission=None,
        status=status,
    )
    db.add(record)
    db.flush()
    _audit(
        db,
        run,
        actor_id,
        "web.fact_extracted",
        record.id,
        {
            "key": candidate.key,
            "value": candidate.value,
            "tier": candidate.tier,
            "url": query.chosen_url,
            "query_id": query.id,
            "method": candidate.method,
            "status": status,
        },
    )
    return record, status == "accepted"


def _new_query(
    run: Run,
    plan: search_mod.SearchQueryPlan,
    engine: str,
    settings: object,
) -> WebQuery:
    from datetime import timedelta

    cache_days = getattr(settings, "web_search_cache_days", 7)
    return WebQuery(
        tenant_id=run.tenant_id,
        run_id=run.id,
        gap_key=plan.gap_key,
        gap_class=plan.gap_class,
        query=plan.query,
        query_hash=search_mod.query_hash(engine, plan.query),
        domain=plan.domain,
        engine=engine,
        result_count=0,
        results_json=[],
        status="pending",
        cache_hit=False,
        expires_at=utcnow() + timedelta(days=cache_days),
    )


def _hits_from_cache(cached: WebQuery) -> list[search_mod.SearchHit]:
    hits: list[search_mod.SearchHit] = []
    for item in cached.results_json or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        published = item.get("published_at")
        hits.append(
            search_mod.SearchHit(
                title=str(item.get("title") or url)[:300],
                url=url,
                published_at=date.fromisoformat(published)
                if isinstance(published, str)
                else None,
            )
        )
    return hits


def _source_meta(
    source: search_mod.FetchedSource, score: search_mod.ScoreBreakdown
) -> dict[str, object]:
    return {
        "title": source.title,
        "url": source.url,
        "published_at": source.published_at.isoformat()
        if source.published_at
        else None,
        **score.as_dict(),
    }


def _fetch_hits(
    hits: list[search_mod.SearchHit],
    *,
    engine: str,
    query: str,
) -> list[search_mod.FetchedSource]:
    sources: list[search_mod.FetchedSource] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.url in seen:
            continue
        seen.add(hit.url)
        domain = search_mod.registered_domain(hit.url)
        key = search_mod.query_hash(engine, f"{query}|{hit.url}")
        cached = search_mod.cached_source(domain, key)
        if cached is not None:
            sources.append(cached)
            continue
        try:
            fetched = search_mod.fetch_source(hit.url)
        except (search_mod.PageFetchError, ValueError) as exc:
            logger.info("could not fetch search result %s: %s", hit.url, exc)
            continue
        search_mod.remember_source(domain, key, fetched)
        sources.append(fetched)
    return sources


def _attempted_classes(db: Session, run: Run) -> set[str]:
    rows = db.scalars(select(WebQuery.gap_class).where(WebQuery.run_id == run.id))
    return {row for row in rows}


def _external_queries(db: Session, run: Run) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(WebQuery)
            .where(
                WebQuery.run_id == run.id,
                WebQuery.cache_hit.is_(False),
                WebQuery.status != "pending",
            )
        )
        or 0
    )


def _disabled(reason: str, run: Run, db: Session) -> SearchOut:
    _set_status(run, "disabled")
    gaps = build_gap_report(db, run)
    return SearchOut(
        run_id=run.id,
        status="disabled",
        label=reason,
        gaps=gaps,
    )


def run_web_search(db: Session, run: Run, actor_id: str) -> SearchOut:
    """Run one bounded web-search pass and return facts plus a status label."""
    settings = get_settings()
    profile = _profile(run)

    if not search_mod.is_enabled(settings):
        return _disabled(
            "Web search is disabled (set SNAP_SEARCH_PROVIDER and "
            "SNAP_SEARCH_API_KEY); gaps still need answers or documents.",
            run,
            db,
        )

    provider = search_mod.build_provider(settings)
    if provider is None:
        return _disabled(
            "Web search has no usable provider; gaps still need answers or documents.",
            run,
            db,
        )

    attempted = _attempted_classes(db, run)
    remaining = max(
        0,
        settings.web_search_max_queries - _external_queries(db, run),
    )
    if remaining == 0:
        _set_status(run, "exhausted")
        gaps = build_gap_report(db, run)
        return SearchOut(
            run_id=run.id,
            status="exhausted",
            label=(
                f"Web search already used its {settings.web_search_max_queries}-"
                "query budget; open gaps need answers or documents."
            ),
            gaps=gaps,
        )

    plans = search_mod.build_queries(
        profile,
        list(profile.gaps),
        limit=min(remaining, settings.web_search_max_queries),
        already_tried=attempted,
    )
    if not plans:
        _set_status(run, "searched")
        gaps = build_gap_report(db, run)
        return SearchOut(
            run_id=run.id,
            status="searched",
            label=(
                "No open gap needs a web search; answers or documents are the "
                "next rung."
            ),
            gaps=gaps,
        )

    accepted = _accepted(db, run)
    accepted_values = [fact.value for fact in accepted]
    entity_names = [
        value
        for value in (
            profile.entities.person.name,
            profile.entities.org.name,
            profile.title,
        )
        if value
    ]

    report = WebSearchReport(status="searched", label="")
    for plan in plans:
        cached_row = search_mod.find_cached_query(
            db,
            tenant_id=run.tenant_id,
            domain=plan.domain,
            query_hash_value=search_mod.query_hash(provider.name, plan.query),
            days=settings.web_search_cache_days,
        )
        engine = provider.name
        cache_hit = cached_row is not None
        row = _new_query(run, plan, engine, settings)
        db.add(row)
        db.flush()
        report.queries.append(row)

        if cache_hit and cached_row is not None:
            row.cache_hit = True
            row.engine = cached_row.engine
            hits = _hits_from_cache(cached_row)
            row.result_count = len(hits)
            row.status = "cached"
            _audit(
                db,
                run,
                actor_id,
                "web.query.cached",
                row.id,
                {
                    "gap_key": plan.gap_key,
                    "query": plan.query,
                    "domain": plan.domain,
                    "cached_from": cached_row.id,
                },
            )
        else:
            try:
                hits = provider.search(plan.query, settings.web_search_results)
            except search_mod.SearchProviderError as exc:
                row.status = "failed"
                report.warnings.append(str(exc))
                report.status = "degraded"
                logger.warning("web search provider failed: %s", exc)
                break
            row.result_count = len(hits)
            _audit(
                db,
                run,
                actor_id,
                "web.query",
                row.id,
                {
                    "gap_key": plan.gap_key,
                    "query": plan.query,
                    "domain": plan.domain,
                    "result_count": len(hits),
                    "engine": provider.name,
                },
            )

        if not hits:
            row.status = "no_fact"
            continue

        sources = _fetch_hits(
            hits[: settings.web_search_results],
            engine=row.engine,
            query=plan.query,
        )
        if not sources:
            row.status = "failed"
            continue

        ranked: list[tuple[search_mod.FetchedSource, search_mod.ScoreBreakdown]] = []
        for source in sources:
            score = search_mod.score_for_source(
                source,
                site_url=profile.url,
                accepted_values=accepted_values,
                entity_names=entity_names,
                metric=plan.gap_key in _METRIC_KEYS,
            )
            ranked.append((source, score))
        ranked.sort(key=lambda item: (-item[1].total, item[0].url))
        row.results_json = [_source_meta(source, score) for source, score in ranked]

        viable = [
            (source, score)
            for source, score in ranked
            if score.total >= settings.web_search_min_score
        ]
        if not viable:
            row.status = "discarded"
            row.score = ranked[0][1].total if ranked else None
            continue

        row.score = viable[0][1].total
        chosen = False
        for source, score in viable:
            injection = search_mod.detect_injection(source.text)
            if injection:
                logger.warning(
                    "prompt injection ignored at %s: %s",
                    source.url,
                    ", ".join(injection),
                )
                report.warnings.append(
                    f"Prompt injection ignored at {source.url}: "
                    f"{', '.join(injection)}."
                )
                row.status = "injection"
                continue

            candidate = _heuristic(plan.gap_key, source) or _llm(
                plan.gap_key,
                source,
                gap_class=plan.gap_class,
            )
            if candidate is None:
                continue

            candidate = WebCandidate(
                key=candidate.key,
                value=candidate.value,
                quote=candidate.quote,
                published_at=source.published_at,
                tier=_tier_for(score, source.published_at),
                confidence=candidate.confidence,
                unit=candidate.unit,
                label=candidate.label,
                as_of=candidate.as_of,
                method=candidate.method,
            )
            row.chosen_url = source.url
            row.score = score.total
            row.status = "completed"
            record, is_accepted = _persist(db, run, actor_id, candidate, row)
            report.facts.append(record)
            if is_accepted and candidate.key == plan.gap_key:
                report.resolved_gaps.append(candidate.key)
            chosen = True
            break

        if not chosen and row.status == "completed":
            row.status = "no_fact"

    if report.facts:
        rebuild(db, run)

    if report.status == "degraded":
        _set_status(run, "degraded")
        label = (
            "Web search provider was unavailable; gaps still need answers or "
            "documents."
        )
    else:
        _set_status(run, "searched")
        if report.resolved_gaps:
            sources_used = len({row.chosen_url for row in report.queries if row.chosen_url})
            label = (
                f"Web search resolved {len(set(report.resolved_gaps))} gap(s) "
                f"from {sources_used} source(s); every fact carries a URL."
            )
        else:
            label = (
                "Web search found no quotable answer above the source threshold; "
                "gaps remain open for answers or documents."
            )

    gaps = build_gap_report(db, run)
    return SearchOut(
        run_id=run.id,
        status=report.status,  # type: ignore[arg-type]
        label=label,
        queries=[SearchQueryOut.model_validate(row) for row in report.queries],
        facts=[FactOut.model_validate(record) for record in report.facts],
        gaps=gaps,
        warnings=report.warnings,
    )
