from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import IdMixin, utcnow


class GapAnswer(Base, IdMixin):
    """One answer to one generated question.

    The question is stored next to the answer because a fact that came from a
    question needs the question for context later. ``action`` is ``answered`` or
    ``skip``; a skipped question is a decision, not a missing value.
    """

    __tablename__ = "gap_answers"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(index=True)
    gap_key: Mapped[str] = mapped_column(String(120), index=True)
    question_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    answer_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    action: Mapped[str] = mapped_column(String(20), default="answered")
    fact_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
