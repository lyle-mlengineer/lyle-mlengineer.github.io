from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin


class FactRecord(Base, TimestampMixin):
    """A stored fact candidate for one run.

    ``(run_id, id)`` is the primary key so fact IDs stay short and stable inside
    a run. The partial unique index below enforces one accepted fact per key.
    """

    __tablename__ = "facts"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(index=True)
    key: Mapped[str] = mapped_column(String(120), index=True)
    value: Mapped[str] = mapped_column(String(600))
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    label: Mapped[str] = mapped_column(String(160), default="")
    as_of: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(2048))
    source_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_quote: Mapped[str] = mapped_column(String(2000), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.99)
    tier: Mapped[str] = mapped_column(String(1))
    retrieved_at: Mapped[date] = mapped_column(Date)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    permission: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="accepted", index=True)
    attested_by: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index(
            "facts_one_accepted",
            "run_id",
            "key",
            unique=True,
            sqlite_where=text("status = 'accepted'"),
            postgresql_where=text("status = 'accepted'"),
        ),
        Index("facts_by_run", "run_id", "tier", "status"),
    )
