from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, TimestampMixin


class Run(Base, IdMixin, TimestampMixin):
    """One analysis attempt for one site.

    ``profile_json`` holds the validated SiteProfile. It is JSON rather than a
    web of tables because the profile is a rendered contract, not a queryable
    entity: later phases add facts, gaps and kits with their own tables.
    """

    __tablename__ = "runs"

    tenant_id: Mapped[str] = mapped_column(index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    content_model_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_versions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
