"""Candidate containers shared by the deterministic and LLM passes."""

import re
from dataclasses import dataclass, field

from app.pipeline.extract.ground import numbers
from app.schemas.content import Fact, Offering, Project, RejectedFact

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(value: str, limit: int = 60) -> str:
    cleaned = _SLUG.sub("-", value.lower()).strip("-")
    return cleaned[:limit] or "item"


def supported_numbers(text: str, facts: list[Fact]) -> bool:
    """True when every number in ``text`` has a fact to point at."""
    allowed: set[str] = set()
    for fact in facts:
        allowed |= numbers(fact.value)
        allowed |= numbers(fact.source_quote)
    return numbers(text) <= allowed


@dataclass
class QuoteCandidate:
    fact: Fact
    attribution: str | None = None
    role: str | None = None


@dataclass
class CandidateSet:
    facts: list[Fact] = field(default_factory=list)
    offerings: list[Offering] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    quote: QuoteCandidate | None = None
    rejected: list[RejectedFact] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    signals: dict[str, list[str]] = field(default_factory=dict)

    def reject(
        self,
        *,
        key: str | None,
        value: str,
        unit: str | None = None,
        source_id: str | None = None,
        source_quote: str = "",
        reason: str,
    ) -> None:
        self.rejected.append(
            RejectedFact(
                key=key,
                value=value[:600],
                unit=unit[:40] if unit else None,
                source_id=source_id,
                source_quote=source_quote[:2000],
                reason=reason,
            )
        )
