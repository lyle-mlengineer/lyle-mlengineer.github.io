import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Tier = Literal["A", "B", "C", "D"]
RejectReason = Literal[
    "no_source",
    "number_mismatch",
    "unsupported_rounding",
    "conflict",
    "tier_not_renderable",
    "invalid",
]
SourceType = Literal["site", "user_answer", "document", "web", "inference"]

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    """Return normalised Arabic digit sequences (commas removed).

    Copy validation uses the same normalisation as the content model, so a
    figure that passed extraction is not rejected for a comma later.
    """
    return {match.group(0).replace(",", "") for match in _NUMBER.finditer(text)}


_numbers = numbers_in


class Fact(BaseModel):
    """One grounded number, date or quote.

    The renderer only reads facts. ``tier`` is assigned by the resolver, never
    by the extraction model, and is validated against ``source_type`` here.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=600)
    unit: str | None = Field(default=None, max_length=40)
    label: str = Field(default="", max_length=160)
    as_of: str | None = Field(default=None, max_length=40)
    source_type: SourceType
    source: str = Field(min_length=1, max_length=2048)
    source_id: str | None = Field(default=None, max_length=40)
    source_page: int | None = Field(default=None, ge=1)
    source_quote: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=0.99, ge=0, le=1)
    tier: Tier
    retrieved_at: date
    published_at: date | None = None
    permission: Literal[
        "published_on_site", "attested", "brand_document", "none"
    ] | None = None

    @model_validator(mode="after")
    def _tier_contract(self) -> "Fact":
        if self.tier in {"A", "B"} and not self.source_quote.strip():
            raise ValueError("tier A and B facts require a source_quote")
        expected = {
            "site": {"A"},
            "user_answer": {"A"},
            "document": {"A"},
            "web": {"B", "C"},
            "inference": {"D"},
        }[self.source_type]
        if self.tier not in expected:
            raise ValueError(f"{self.source_type} facts must be tier {sorted(expected)}")
        return self


class Offering(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    one_liner: str = Field(min_length=1, max_length=320)
    metric_fact_id: str | None = None
    tools: list[str] = Field(default_factory=list, max_length=12)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    blurb: str = Field(default="", max_length=240)
    badge_fact_id: str | None = None
    image: str | None = None
    status: Literal["shipped", "active", "wip", "archived"] = "shipped"


class Proof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    emphasis: Literal["lead", "normal"] = "normal"


class QuoteRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    attribution: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=160)


class CTA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    label: str = Field(min_length=1, max_length=120)


class RejectedFact(BaseModel):
    """A candidate the extractor refused to promote into ``facts[]``."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, max_length=120)
    value: str = Field(min_length=1, max_length=600)
    unit: str | None = Field(default=None, max_length=40)
    source_id: str | None = Field(default=None, max_length=40)
    source_quote: str = Field(default="", max_length=2000)
    reason: RejectReason


class ContentModel(BaseModel):
    """The contract between extraction and the renderer.

    Metrics, badges and quotes are pointers into ``facts[]``. Free text may not
    introduce a number that no fact supports.
    """

    model_config = ConfigDict(extra="forbid")

    thesis: str = Field(min_length=1, max_length=320)
    audience: str = Field(default="", max_length=200)
    arc: list[str] = Field(default_factory=list, max_length=8)
    facts: list[Fact] = Field(default_factory=list)
    offerings: list[Offering] = Field(default_factory=list, max_length=4)
    projects: list[Project] = Field(default_factory=list, max_length=8)
    proof: list[Proof] = Field(default_factory=list, max_length=4)
    quote: QuoteRef | None = None
    cta: CTA
    disclaimers: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _cross_references(self) -> "ContentModel":
        by_id = {fact.id: fact for fact in self.facts}
        if len(by_id) != len(self.facts):
            raise ValueError("fact ids must be unique")
        keys = [fact.key for fact in self.facts]
        if len(set(keys)) != len(keys):
            raise ValueError("only one accepted fact per key is allowed")

        for item in self.proof:
            fact = by_id.get(item.fact_id)
            if fact is None:
                raise ValueError(f"proof references unknown fact {item.fact_id!r}")
            if fact.tier not in {"A", "B"}:
                raise ValueError(f"proof fact {item.fact_id!r} must be tier A or B")

        if self.quote is not None:
            fact = by_id.get(self.quote.fact_id)
            if fact is None:
                raise ValueError(f"quote references unknown fact {self.quote.fact_id!r}")
            if fact.permission not in {"published_on_site", "attested"}:
                raise ValueError("quote fact needs published_on_site or attested permission")

        for offering in self.offerings:
            if offering.metric_fact_id and offering.metric_fact_id not in by_id:
                raise ValueError(f"offering references unknown fact {offering.metric_fact_id!r}")
        for project in self.projects:
            if project.badge_fact_id and project.badge_fact_id not in by_id:
                raise ValueError(f"project references unknown fact {project.badge_fact_id!r}")

        supported = set()
        for fact in self.facts:
            supported |= _numbers(fact.value)
            supported |= _numbers(fact.source_quote)

        free_text = [self.thesis, self.audience]
        free_text.extend(item.title for item in self.offerings)
        free_text.extend(item.one_liner for item in self.offerings)
        free_text.extend(item.name for item in self.projects)
        free_text.extend(item.blurb for item in self.projects)
        for text in free_text:
            unsupported = _numbers(text) - supported
            if unsupported:
                raise ValueError(f"digit(s) {sorted(unsupported)} have no supporting fact")
        return self
