from typing import Any
from urllib.parse import urlparse

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, TimestampMixin


class Site(Base, IdMixin, TimestampMixin):
    __tablename__ = "sites"

    tenant_id: Mapped[str] = mapped_column(index=True)
    url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    # Pinned per site so a later run looks like the same brand. JSON keeps the
    # token contract forward-compatible while the hash makes it cacheable.
    design_system_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    design_system_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    @staticmethod
    def domain_from(url: str) -> str:
        return (urlparse(url).hostname or "").lower()
