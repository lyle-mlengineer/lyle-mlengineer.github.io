from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import AuditLog, Site
from app.schemas.site import SiteCreate, SiteOut

router = APIRouter(prefix="/v1/sites", tags=["sites"])


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
    site = db.scalar(select(Site).where(Site.id == site_id, Site.tenant_id == user.tenant_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site
