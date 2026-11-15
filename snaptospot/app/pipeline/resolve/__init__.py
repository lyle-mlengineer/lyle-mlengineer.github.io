"""Gap resolution: requirement slots, questions, tiers and conflicts."""

from app.pipeline.resolve.conflicts import (
    ConflictResolution,
    FactCandidate,
    group_by_key,
    resolve_conflict,
)
from app.pipeline.resolve.questions import generate_questions, question_for_slot
from app.pipeline.resolve.schema import (
    SLOT_BY_KEY,
    SLOTS,
    RequirementSlot,
    slot_for,
)
from app.pipeline.resolve.tiers import assign_tier, reject_client_tier

__all__ = [
    "SLOTS",
    "SLOT_BY_KEY",
    "ConflictResolution",
    "FactCandidate",
    "RequirementSlot",
    "assign_tier",
    "generate_questions",
    "group_by_key",
    "question_for_slot",
    "reject_client_tier",
    "resolve_conflict",
    "slot_for",
]
