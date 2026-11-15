"""Generate the short interview from open gaps.

Rules from design §8.7.3: at most five questions, every question has a safe
default, and a slot that is already filled is never asked again. Ordering is
deterministic: highest card impact first, then key.
"""

from collections.abc import Iterable

from app.pipeline.resolve.schema import RequirementSlot, slot_for
from app.schemas.profile import Gap
from app.schemas.resolve import Question, QuestionOption

MAX_QUESTIONS = 5


def question_for_slot(slot: RequirementSlot, *, severity: str | None = None) -> Question:
    return Question(
        key=slot.key,
        gap_class=slot.gap_class,
        severity=severity or slot.severity,
        prompt=slot.prompt,
        type=slot.question_type,
        options=[
            QuestionOption(value=value, label=label) for value, label in slot.options
        ],
        default=slot.default,
        default_label=slot.default_label,
        unlocks=slot.unlocks,
        unit=slot.unit,
        placeholder=slot.placeholder,
        requires_attestation=slot.requires_attestation,
    )


def _accepted_keys(facts: Iterable[object]) -> set[str]:
    keys: set[str] = set()
    for fact in facts:
        status = getattr(fact, "status", "accepted")
        if status == "accepted":
            key = getattr(fact, "key", None)
            if key:
                keys.add(str(key))
    return keys


def _consistency_question(
    gap: Gap,
    facts: Iterable[object],
    accepted_keys: set[str],
) -> Question | None:
    base_key = gap.key.removeprefix("consistency.")
    values: list[str] = []
    for fact in facts:
        if getattr(fact, "key", None) != base_key:
            continue
        status = getattr(fact, "status", "accepted")
        if status not in {"accepted", "quarantined"}:
            continue
        value = str(getattr(fact, "value", "")).strip()
        if value and value not in values:
            values.append(value)
    if len(values) < 2:
        return None
    return Question(
        key=gap.key,
        gap_class="consistency",
        severity=gap.severity,
        prompt=f"Which value is correct for {base_key}?",
        type="choice",
        options=[QuestionOption(value=value, label=value) for value in values],
        default="skip",
        default_label="Skip — keep the current value",
        unlocks="Removes the conflicting card from review.",
        requires_attestation=True,
    )


def generate_questions(
    gaps: Iterable[Gap],
    facts: Iterable[object],
    *,
    limit: int = MAX_QUESTIONS,
) -> list[Question]:
    """Return at most ``limit`` questions, never asking for an accepted fact."""
    fact_list = list(facts)
    accepted = _accepted_keys(fact_list)
    ranked: list[tuple[int, str, Gap, RequirementSlot | None]] = []
    seen: set[str] = set()

    for gap in gaps:
        if gap.status != "open" or gap.key in seen:
            continue
        slot = slot_for(gap.key)
        if slot is not None:
            if gap.key in accepted:
                continue
            seen.add(gap.key)
            ranked.append((-slot.impact, gap.key, gap, slot))
            continue
        if gap.gap_class == "consistency" and gap.key not in accepted:
            seen.add(gap.key)
            ranked.append((-90, gap.key, gap, None))

    ranked.sort(key=lambda item: (item[0], item[1]))
    questions: list[Question] = []
    for _, _, gap, slot in ranked:
        if len(questions) >= limit:
            break
        if slot is not None:
            questions.append(question_for_slot(slot, severity=gap.severity))
            continue
        question = _consistency_question(gap, fact_list, accepted)
        if question is not None:
            questions.append(question)
    return questions
