"""The run executor.

One SQLite-backed state machine, deliberately boring: claim the run atomically,
walk the steps in a fixed order, persist each output, recompute progress. A
failure is recorded, never swallowed. Cancellation is checked between steps, and
a restart leaves an `interrupted` run for a human to retry rather than a
half-finished success.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import session_scope
from ..domain import SKILL_LABELS
from ..models import Artifact, Company, Job, JobEvent, Run, RunStep, utcnow
from ..providers.call_context import call_context
from ..providers.llm.base import LLMProvider, LLMProviderError, SkillValidationError
from ..providers.llm.pricing import estimate_cost
from ..skills.base import SkillContext
from ..skills.registry import get_skill
from ..utils import slugify

logger = logging.getLogger("skipper.jobs")

PIPELINE_ORDER: tuple[str, ...] = (
    "job_extraction",
    "job_summary",
    "company_research",
    "cv_writing",
    "cover_letter",
    "email_writing",
    "tell_me_about_yourself",
    "work_history",
    "proud_project",
    "technical_interview",
    "behavioral_interview",
)
RUN_KIND = "prepare"


class RunError(RuntimeError):
    pass


def create_run(
    db: Session,
    job: Job,
    *,
    seed_prior: bool = False,
    skills: tuple[str, ...] | None = None,
    kind: str = RUN_KIND,
) -> Run:
    """Create a queued run and its steps; caller commits and schedules it."""
    active = db.scalar(
        select(Run.id).where(Run.job_id == job.id, Run.status.in_(("queued", "running"))).limit(1)
    )
    if active:
        raise RunError("This job already has a run in flight.")

    steps = [get_skill(name) for name in (skills or PIPELINE_ORDER)]
    run = Run(
        job_id=job.id,
        kind=kind,
        status="queued",
        total_steps=len(steps),
        completed_steps=0,
        progress_pct=0,
    )
    db.add(run)
    db.flush()
    for ordinal, skill in enumerate(steps):
        db.add(
            RunStep(
                run_id=run.id,
                ordinal=ordinal,
                skill=skill.name,
                weight=skill.weight,
                status="pending",
            )
        )
    previous_status = job.status
    if job.status in {"discovered", "reviewing", "ready"}:
        job.status = "preparing"
    job.updated_at = utcnow()
    db.add(
        JobEvent(
            job_id=job.id,
            event_type="run",
            from_status=previous_status,
            to_status=job.status,
            note=(
                "Regeneration queued" if kind == "regenerate"
                else "Run queued" + (" (resuming earlier outputs)" if seed_prior else "")
            ),
            run_id=run.id,
        )
    )
    db.flush()
    return run


def execute_run(run_id: int, settings: Settings, llm: LLMProvider, search=None, fetcher=None) -> None:
    """Run a queued pipeline. Safe to call twice: only one caller wins the claim."""
    try:
        with session_scope(settings) as db:
            claimed = db.execute(
                update(Run)
                .where(Run.id == run_id, Run.status == "queued")
                .values(
                    status="running",
                    started_at=utcnow(),
                    provider=llm.name,
                    model_large=llm.model_for("large"),
                    model_small=llm.model_for("small"),
                )
            )
            db.commit()
            if claimed.rowcount == 0:
                logger.info("run %s was already claimed", run_id)
                return
            _run_steps(db, run_id, settings, llm, search=search, fetcher=fetcher)
    except Exception:
        logger.exception("run %s crashed before it could record a failure", run_id)
        with session_scope(settings) as db:
            run = db.get(Run, run_id)
            if run and run.status not in {"succeeded", "failed", "cancelled", "interrupted"}:
                _fail(db, run, "The worker stopped unexpectedly. Retry the run.")
                db.commit()


def _run_steps(db: Session, run_id: int, settings: Settings, llm: LLMProvider, *, search=None, fetcher=None) -> None:
    run = db.get(Run, run_id)
    if run is None:
        return
    job = db.get(Job, run.job_id)
    if job is None:
        _fail(db, run, "The job was deleted before the run started.")
        db.commit()
        return

    steps = db.scalars(select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.ordinal)).all()
    prior = _prior_outputs(db, job.id, exclude_run=run.id)
    if run.kind == "regenerate":
        # Keep dependency outputs, but never skip the artifacts being regenerated.
        for target in {step.skill for step in steps}:
            prior.pop(target, None)

    for step in steps:
        skill = get_skill(step.skill)
        db.refresh(run)
        if run.cancel_requested:
            _cancel(db, run, steps, step)
            db.commit()
            return
        if _elapsed_minutes(run.started_at) > settings.run_max_minutes:
            _fail(db, run, f"Stopped after the {settings.run_max_minutes}-minute run limit.")
            db.commit()
            return
        if run.tokens_in + run.tokens_out >= settings.run_token_budget:
            _fail(db, run, "Stopped at the run token budget.")
            db.commit()
            return

        # A retry resumes from the latest successful outputs instead of paying for them twice.
        if step.skill in prior:
            db.refresh(job)
            step.status = "succeeded"
            step.output_json = prior[step.skill]
            step.finished_at = utcnow()
            step.duration_ms = 0
            step.attempt = 0
            run.completed_steps += 1
            _recompute_progress(db, run)
            _apply_prior(db, job, step.skill, prior[step.skill])
            db.commit()
            continue

        step.status = "running"
        step.started_at = utcnow()
        step.attempt += 1
        run.current_step = step.skill
        job.updated_at = utcnow()
        db.commit()

        company = db.get(Company, job.company_id) if job.company_id else None
        ctx = SkillContext(
            job=job,
            company=company,
            settings=settings,
            llm=llm,
            prior=prior,
            run_id=run.id,
            portfolio_text="\n\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in sorted(settings.portfolio_dir.glob("*.md"))
            ),
            search=search,
            fetcher=fetcher,
        )

        try:
            with call_context(job_id=job.id, run_id=run.id, skill=skill.name):
                result = skill.execute(ctx)
            if skill.name == "cv_writing":
                from ..documents.storage import save_cv_bundle

                save_cv_bundle(db, job, run, result.payload, settings)
            elif skill.name == "cover_letter":
                from ..documents.storage import save_letter_bundle

                save_letter_bundle(db, job, run, result.payload, settings)
        except (SkillValidationError, LLMProviderError) as exc:
            message = _human_error(skill.name, exc)
            _finish_step(db, run, step, "failed", error=message)
            if skill.optional:
                db.add(
                    JobEvent(
                        job_id=job.id,
                        event_type="run",
                        note=f"Optional step failed: {message}"[:1000],
                        run_id=run.id,
                    )
                )
                db.commit()
                logger.warning("optional skill %s failed: %s", skill.name, message)
                continue
            _fail(db, run, message)
            db.commit()
            logger.warning("run %s failed at %s: %s", run.id, skill.name, message)
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("run %s failed at %s", run.id, skill.name)
            message = f"{SKILL_LABELS.get(skill.name, skill.name)} failed unexpectedly."
            _finish_step(db, run, step, "failed", error=message)
            _fail(db, run, message)
            db.commit()
            return

        _finish_step(db, run, step, "succeeded", result=result)
        run.tokens_in += result.response.tokens_in
        run.tokens_out += result.response.tokens_out
        run.cost_usd = round(
            run.cost_usd + estimate_cost(result.response.model, result.response.tokens_in, result.response.tokens_out),
            6,
        )
        prior[skill.name] = result.payload

        if skill.name == "job_extraction":
            _apply_extraction(db, job, result.payload)
            ctx.company = db.get(Company, job.company_id) if job.company_id else None
        elif result.markdown and skill.output_kind not in {"cv_pdf", "cv_docx", "cover_letter_pdf", "cover_letter_docx"}:
            _save_markdown(db, job, run, skill.output_kind, result.markdown, result.payload)
            if skill.name == "job_summary":
                job.summary_md = result.markdown

        run.completed_steps += 1
        _recompute_progress(db, run)
        db.commit()

    run.status = "succeeded"
    run.finished_at = utcnow()
    run.current_step = None
    run.progress_pct = 100
    job.updated_at = utcnow()
    previous = job.status
    kinds = set(
        db.scalars(
            select(Artifact.kind).where(Artifact.job_id == job.id, Artifact.is_current.is_(True))
        ).all()
    )
    full_pack = {"cv_pdf", "cover_letter_pdf", "email"} <= kinds
    job.status = "ready" if full_pack else "reviewing"
    job.next_action = (
        "Review the pack and apply"
        if full_pack
        else "Review the brief and retry the missing artifacts"
    )
    db.add(
        JobEvent(
            job_id=job.id,
            event_type="status",
            from_status=previous,
            to_status=job.status,
            note="Application pack ready" if full_pack else "Brief finished; some artifacts are missing",
            run_id=run.id,
        )
    )
    db.commit()


def _finish_step(db: Session, run: Run, step: RunStep, status: str, *, result=None, error: str | None = None) -> None:
    step.status = status
    step.finished_at = utcnow()
    step.duration_ms = _duration_ms(step.started_at)
    step.error = error
    if result is not None:
        step.output_json = result.payload
        step.tokens_in = result.response.tokens_in
        step.tokens_out = result.response.tokens_out
        step.prompt_hash = result.prompt_hash
    db.flush()


def _recompute_progress(db: Session, run: Run) -> None:
    total = db.scalar(select(func.coalesce(func.sum(RunStep.weight), 0.0)).where(RunStep.run_id == run.id)) or 0.0
    done = (
        db.scalar(
            select(func.coalesce(func.sum(RunStep.weight), 0.0)).where(
                RunStep.run_id == run.id, RunStep.status == "succeeded"
            )
        )
        or 0.0
    )
    run.progress_pct = max(0, min(100, round(100 * done / total))) if total else 0


def _fail(db: Session, run: Run, message: str) -> None:
    run.status = "failed"
    run.error = message
    run.current_step = None
    run.finished_at = utcnow()
    db.execute(
        update(RunStep)
        .where(RunStep.run_id == run.id, RunStep.status == "pending")
        .values(status="skipped", finished_at=utcnow())
    )
    job = db.get(Job, run.job_id)
    if job:
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="run",
                note=message[:1000],
                run_id=run.id,
            )
        )


def _cancel(db: Session, run: Run, steps: list[RunStep], current: RunStep) -> None:
    if current.status in {"pending", "running"}:
        current.status = "skipped"
        current.finished_at = utcnow()
    for step in steps:
        if step.status == "pending":
            step.status = "skipped"
            step.finished_at = utcnow()
    run.status = "cancelled"
    run.error = "Cancelled by the user."
    run.current_step = None
    run.finished_at = utcnow()


def _save_markdown(
    db: Session,
    job: Job,
    run: Run,
    kind: str,
    content: str,
    payload: dict[str, Any],
) -> None:
    latest = db.scalar(select(func.max(Artifact.version)).where(Artifact.job_id == job.id, Artifact.kind == kind))
    version = (latest or 0) + 1
    db.execute(
        update(Artifact).where(Artifact.job_id == job.id, Artifact.kind == kind).values(is_current=False)
    )
    db.add(
        Artifact(
            job_id=job.id,
            run_id=run.id,
            kind=kind,
            version=version,
            is_current=True,
            format="md",
            content_md=content,
            meta_json={"extraction": payload, "payload": payload},
        )
    )
    db.add(JobEvent(job_id=job.id, event_type="artifact", note=f"Created {kind} v{version}", run_id=run.id))


def _apply_extraction(db: Session, job: Job, payload: dict[str, Any]) -> None:
    company = _resolve_company(db, payload)
    job.company_id = company.id
    job.title = payload["title"]
    job.location = payload.get("location")
    job.work_mode = payload.get("work_mode")
    job.employment_type = payload.get("employment_type")
    job.seniority = payload.get("seniority")
    salary = payload.get("salary") or {}
    job.salary_min = salary.get("min")
    job.salary_max = salary.get("max")
    job.salary_currency = salary.get("currency")
    job.salary_period = salary.get("period")
    job.deadline = payload.get("deadline")
    job.extract_json = payload
    job.keywords_json = payload.get("keywords") or []
    job.updated_at = utcnow()


def _resolve_company(db: Session, payload: dict[str, Any]) -> Company:
    from ..utils import normalize_company

    name = normalize_company(str(payload.get("company_name") or "Unknown company"))
    domain = payload.get("company_domain")
    company = None
    if domain:
        company = db.scalar(select(Company).where(Company.domain == domain))
    if company is None:
        company = db.scalar(select(Company).where(Company.name == name))
    if company is not None:
        if domain and not company.domain:
            company.domain = domain
        return company

    base = slugify(name, fallback="company")
    slug = base
    counter = 2
    while db.scalar(select(Company.id).where(Company.slug == slug)):
        slug = f"{base}-{counter}"
        counter += 1
    company = Company(
        name=name,
        slug=slug,
        domain=domain,
        website=f"https://{domain}" if domain else None,
    )
    db.add(company)
    try:
        db.flush()
    except IntegrityError:  # a concurrent creation of the same domain
        db.rollback()
        company = db.scalar(select(Company).where(Company.domain == domain)) if domain else None
        if company is None:
            raise
    return company


def _apply_prior(db: Session, job: Job, skill_name: str, payload: dict[str, Any]) -> None:
    if skill_name == "job_extraction":
        _apply_extraction(db, job, payload)


def _prior_outputs(db: Session, job_id: int, *, exclude_run: int) -> dict[str, dict[str, Any]]:
    run = db.scalar(
        select(Run)
        .where(Run.job_id == job_id, Run.id != exclude_run, Run.status == "succeeded")
        .order_by(Run.created_at.desc())
        .limit(1)
    )
    if run is None:
        return {}
    rows = db.scalars(
        select(RunStep).where(RunStep.run_id == run.id, RunStep.status == "succeeded")
    ).all()
    return {row.skill: row.output_json for row in rows if row.output_json}


def _human_error(skill_name: str, exc: Exception) -> str:
    label = SKILL_LABELS.get(skill_name, skill_name)
    if isinstance(exc, SkillValidationError):
        detail = exc.errors[0] if exc.errors else "the model returned the wrong shape"
        return f"{label} failed: {detail}. The run can be retried."
    return f"{label} failed: {exc}. The run can be retried."


def _duration_ms(started_at: str | None) -> int | None:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((datetime.now(UTC) - start).total_seconds() * 1000))


def _elapsed_minutes(started_at: str | None) -> float:
    if not started_at:
        return 0.0
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return (datetime.now(UTC) - start).total_seconds() / 60
