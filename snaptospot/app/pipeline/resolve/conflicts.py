"""Resolve disagreements between facts using the fixed precedence table.

The loser is recorded, never deleted. The table mirrors design §8.7.6:

* an attested user answer beats the site;
* the site beats a document (unless the user confirms a newer document);
* the site beats the web;
* a document beats the web;
* two web sources have no winner, so neither can render a number.
"""

from dataclasses import dataclass

# Higher wins. An unattested user answer is deliberately below the site: the
# site is still first-party, and the user has not confirmed the value.
_RANK = {
    "user_answer_attested": 5,
    "site": 4,
    "document": 3,
    "user_answer": 2,
    "web": 1,
    "inference": 0,
}


@dataclass(frozen=True)
class FactCandidate:
    fact_id: str
    key: str
    value: str
    source_type: str
    tier: str
    attested: bool = False


@dataclass(frozen=True)
class ConflictResolution:
    winner_id: str | None
    quarantined_ids: tuple[str, ...]
    reason: str
    overrides: str | None = None


def _rank(candidate: FactCandidate) -> int:
    if candidate.source_type == "user_answer" and candidate.attested:
        return _RANK["user_answer_attested"]
    return _RANK.get(candidate.source_type, 0)


def _agree(left: FactCandidate, right: FactCandidate) -> bool:
    return left.value.strip().casefold() == right.value.strip().casefold()


def resolve_conflict(
    existing: FactCandidate,
    candidate: FactCandidate,
) -> ConflictResolution:
    """Compare an accepted fact with a competing candidate."""
    if _agree(existing, candidate):
        return ConflictResolution(
            winner_id=existing.fact_id,
            quarantined_ids=(),
            reason="sources agree",
        )

    existing_rank = _rank(existing)
    candidate_rank = _rank(candidate)

    if existing.source_type == "web" and candidate.source_type == "web":
        return ConflictResolution(
            winner_id=None,
            quarantined_ids=(existing.fact_id, candidate.fact_id),
            reason="two web sources disagree; neither may render a number",
        )

    if candidate_rank > existing_rank:
        overrides = (
            existing.source_type if candidate.source_type == "user_answer" else None
        )
        return ConflictResolution(
            winner_id=candidate.fact_id,
            quarantined_ids=(existing.fact_id,),
            reason=f"{candidate.source_type} outranks {existing.source_type}",
            overrides=overrides,
        )

    if candidate_rank == existing_rank and candidate.source_type == "site":
        return ConflictResolution(
            winner_id=existing.fact_id,
            quarantined_ids=(candidate.fact_id,),
            reason="two site sentences disagree; the earlier specific value wins",
        )

    return ConflictResolution(
        winner_id=existing.fact_id,
        quarantined_ids=(candidate.fact_id,),
        reason=f"{existing.source_type} outranks {candidate.source_type}",
        overrides=existing.source_type if candidate.source_type == "user_answer" else None,
    )


def group_by_key(candidates: list[FactCandidate]) -> dict[str, list[FactCandidate]]:
    grouped: dict[str, list[FactCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.key, []).append(candidate)
    return grouped
