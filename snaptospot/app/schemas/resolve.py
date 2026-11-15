from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.profile import Gap

QuestionType = Literal["choice", "number_unit", "short_text", "url", "file", "skip"]
FactAction = Literal["accept", "override", "reject"]


class QuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class Question(BaseModel):
    """One question generated from an open requirement slot."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    key: str
    gap_class: str = Field(alias="class")
    severity: str
    prompt: str
    type: QuestionType
    options: list[QuestionOption] = Field(default_factory=list)
    default: str = "skip"
    default_label: str = "Skip — omit this card"
    unlocks: str = ""
    unit: str | None = None
    placeholder: str | None = None
    requires_attestation: bool = False


class GapReport(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)

    run_id: str
    status: str
    coverage: float
    facts_count: int
    gaps: list[Gap] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    blocking_open: list[str] = Field(default_factory=list)
    ready: bool = False


class RenderOut(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)

    run_id: str
    status: Literal["ready", "blocked"]
    coverage: float
    blocking_gaps: list[Gap] = Field(default_factory=list)
    open_gaps: list[Gap] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    ready: bool = False


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    value: str | None = Field(default=None, max_length=600)
    unit: str | None = Field(default=None, max_length=40)
    attest: bool = False
    skip: bool = False
    attribution: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def _value_required_unless_skipped(self) -> "AnswerIn":
        if not self.skip and not (self.value and self.value.strip()):
            raise ValueError("value is required unless skip=true")
        return self


class AnswersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[AnswerIn] = Field(min_length=1, max_length=5)


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    id: str
    key: str
    value: str
    unit: str | None = None
    label: str = ""
    as_of: str | None = None
    source_type: str
    source: str
    source_id: str | None = None
    source_quote: str = ""
    confidence: float = 0.99
    tier: str
    retrieved_at: date
    published_at: date | None = None
    permission: str | None = None
    status: str = "accepted"
    attested_by: str | None = None


class FactActionIn(BaseModel):
    """Accept, override or reject a stored fact.

    ``tier`` is intentionally absent and ``extra="forbid"`` turns any attempt to
    supply one into a 422. An override must carry ``attest: true``.
    """

    model_config = ConfigDict(extra="forbid")

    action: FactAction
    value: str | None = Field(default=None, max_length=600)
    unit: str | None = Field(default=None, max_length=40)
    as_of: str | None = Field(default=None, max_length=40)
    attest: bool = False
    reason: str | None = Field(default=None, max_length=300)
