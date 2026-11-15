import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import AuditLog, Run, Site
from app.models.base import utcnow
from app.pipeline.analyze import analyze_site
from app.pipeline.ingest.errors import CrawlError
from app.schemas.content import ContentModel
from app.schemas.profile import SiteProfile
from app.schemas.run import RunOut, run_to_out
from app.schemas.site import SiteCreate, SiteOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/sites", tags=["sites"])


def _site_or_404(site_id: str, user: CurrentUser, db: DbSession) -> Site:
    site = db.scalar(select(Site).where(Site.id == site_id, Site.tenant_id == user.tenant_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(body: SiteCreate, user: CurrentUser, db: DbSession) -> Site:
    url = str(body.url)
    site = Site(
        tenant_id=user.tenant_id,
        url=url,
        domain=Site.domain_from(url),
        title=body.title,
    )
    db.add(site)
    db.flush()
    db.add(
        AuditLog(
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            action="site.created",
            target_type="site",
            target_id=site.id,
            meta={"url": url},
        )
    )
    db.commit()
    db.refresh(site)
    return site


@router.get("", response_model=list[SiteOut])
def list_sites(user: CurrentUser, db: DbSession) -> list[Site]:
    return list(
        db.scalars(
            select(Site)
            .where(Site.tenant_id == user.tenant_id)
            .order_by(Site.created_at.desc())
        )
    )


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site_id: str, user: CurrentUser, db: DbSession) -> Site:
    return _site_or_404(site_id, user, db)


@router.post("/{site_id}/analyze", response_model=RunOut)
def analyze(site_id: str, user: CurrentUser, db: DbSession) -> RunOut:
    """Crawl and profile a site.

    Runs inline for now, so the response already contains the profile. The run
    row exists either way, which keeps the failure visible to the client and
    ready for the Celery worker added in a later phase.
    """
    site = _site_or_404(site_id, user, db)
    run = Run(
        tenant_id=user.tenant_id,
        site_id=site.id,
        status="running",
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    action = "site.analyzed"
    try:
        profile, crawl, extraction = analyze_site(site, run)
        content_model = extraction.content_model
        run.profile_json = profile.model_dump(mode="json")
        run.content_model_json = content_model.model_dump(mode="json")
        run.model_versions_json = extraction.model_versions
        run.status = "succeeded"
        run.ai_generated = profile.understanding.ai_generated or extraction.llm_used
        total_candidates = len(content_model.facts) + len(extraction.rejected)
        run.stats_json = {
            "page_count": profile.observed.page_count,
            "asset_count": profile.observed.asset_count,
            "site_hash": profile.observed.site_hash,
            "robots_status": crawl.robots_status,
            "skipped": crawl.skipped,
            "llm_used": extraction.llm_used,
            "understanding_llm": profile.understanding.ai_generated,
            "facts": len(content_model.facts),
            "rejected_facts": [
                rejected.model_dump(mode="json") for rejected in extraction.rejected
            ],
            "coverage": (
                round(len(content_model.facts) / total_candidates, 3)
                if total_candidates
                else 1.0
            ),
            "signals": extraction.signals,
            "gaps": [
                {
                    "key": gap.key,
                    "class": gap.gap_class,
                    "severity": gap.severity,
                }
                for gap in profile.gaps
            ],
        }
        site.status = "analyzed"
        if not site.title:
            site.title = profile.title[:300]
    except CrawlError as exc:
        run.status = "failed"
        run.error = str(exc)[:1000]
        site.status = "failed"
        action = "site.analyze_failed"
    except Exception as exc:  # noqa: BLE001 - the run row records every failure
        logger.exception("Analysis failed for site %s", site.id)
        run.status = "failed"
        run.error = f"{exc.__class__.__name__}: {exc}"[:1000]
        site.status = "failed"
        action = "site.analyze_failed"
    finally:
        run.finished_at = utcnow()
        db.add(
            AuditLog(
                tenant_id=user.tenant_id,
                actor_user_id=user.id,
                action=action,
                target_type="run",
                target_id=run.id,
                meta={"site_id": site.id, "status": run.status},
            )
        )
        db.commit()
        db.refresh(run)

    return run_to_out(run)


@router.get("/{site_id}/profile", response_model=SiteProfile)
def get_profile(site_id: str, user: CurrentUser, db: DbSession) -> SiteProfile:
    _site_or_404(site_id, user, db)
    run = db.scalar(
        select(Run)
        .where(
            Run.site_id == site_id,
            Run.tenant_id == user.tenant_id,
            Run.status == "succeeded",
        )
        .order_by(Run.created_at.desc())
    )
    if run is None or run.profile_json is None:
        raise HTTPException(status_code=404, detail="This site has not been analyzed yet")
    return SiteProfile.model_validate(run.profile_json)


@router.get("/{site_id}/content-model", response_model=ContentModel)
def get_content_model(site_id: str, user: CurrentUser, db: DbSession) -> ContentModel:
    _site_or_404(site_id, user, db)
    run = db.scalar(
        select(Run)
        .where(
            Run.site_id == site_id,
            Run.tenant_id == user.tenant_id,
            Run.status == "succeeded",
        )
        .order_by(Run.created_at.desc())
    )
    if run is None or run.content_model_json is None:
        raise HTTPException(status_code=404, detail="This site has not been analyzed yet")
    return ContentModel.model_validate(run.content_model_json)
