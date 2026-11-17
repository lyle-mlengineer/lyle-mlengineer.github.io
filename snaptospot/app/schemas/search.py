from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.resolve import FactOut, GapReport


class SearchQueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gap_key: str
    gap_class: str
    query: str
    engine: str
    result_count: int
    chosen_url: str | None = None
    score: float | None = None
    status: str
    cache_hit: bool = False
    created_at: datetime


class SearchOut(BaseModel):
    """Result of one web-search pass, including how it degraded."""

    run_id: str
    status: Literal["searched", "disabled", "degraded", "exhausted"]
    label: str
    queries: list[SearchQueryOut] = Field(default_factory=list)
    facts: list[FactOut] = Field(default_factory=list)
    gaps: GapReport
    warnings: list[str] = Field(default_factory=list)
