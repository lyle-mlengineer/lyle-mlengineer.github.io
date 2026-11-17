from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, TimestampMixin


class WebQuery(Base, IdMixin, TimestampMixin):
    """One logged web search, including the source metadata that survived it.

    ``results_json`` stores result titles, URLs, snippets, dates and scores --
    never page bodies. A row is also the cache entry: a second run with the same
    ``(domain, query_hash)`` inside the retention window reuses the provider
    result list instead of calling the search API again.
    """

    __tablename__ = "web_queries"

    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str] = mapped_column(index=True)
    gap_key: Mapped[str] = mapped_column(String(120))
    gap_class: Mapped[str] = mapped_column(String(40), index=True)
    query: Mapped[str] = mapped_column(String(500))
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    engine: Mapped[str] = mapped_column(String(40))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    results_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    chosen_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "web_queries_cache",
            "tenant_id",
            "domain",
            "query_hash",
            "created_at",
        ),
        Index("web_queries_by_run", "run_id", "gap_class"),
    )
