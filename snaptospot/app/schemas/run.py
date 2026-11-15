from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.run import Run
from app.schemas.content import ContentModel
from app.schemas.profile import SiteProfile


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    status: str
    error: str | None = None
    ai_generated: bool = False
    stats: dict[str, Any] = {}
    model_versions: dict[str, Any] = {}
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    profile: SiteProfile | None = None
    content_model: ContentModel | None = None


def run_to_out(run: Run) -> RunOut:
    profile = run.profile_json
    content_model = run.content_model_json
    return RunOut(
        id=run.id,
        site_id=run.site_id,
        status=run.status,
        error=run.error,
        ai_generated=run.ai_generated,
        stats=run.stats_json or {},
        model_versions=run.model_versions_json or {},
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        profile=SiteProfile.model_validate(profile) if profile else None,
        content_model=(
            ContentModel.model_validate(content_model) if content_model else None
        ),
    )
