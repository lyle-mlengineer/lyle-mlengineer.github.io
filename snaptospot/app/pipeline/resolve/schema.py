"""Requirement slots for the resolver.

A slot is declared up front, so the application always knows what it is looking
for and what a missing value costs the layout. Gaps are produced by comparing a
slot with the extracted profile; questions are produced from the gaps that
remain.
"""

from dataclasses import dataclass, field

QuestionType = str  # one of the fixed types in questions.py

_BLOCKING = "blocking"
_SOFT = "soft"


@dataclass(frozen=True)
class RequirementSlot:
    key: str
    gap_class: str
    severity: str
    impact: int
    prompt: str
    question_type: str
    unlocks: str
    default: str = "skip"
    default_label: str = "Skip — omit this card"
    unit: str | None = None
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    placeholder: str | None = None
    requires_attestation: bool = False


SLOTS: tuple[RequirementSlot, ...] = (
    RequirementSlot(
        key="offer.core",
        gap_class="offer",
        severity=_BLOCKING,
        impact=100,
        prompt="In one line, what do you sell?",
        question_type="short_text",
        unlocks="Adds the capability card to all five platforms.",
        placeholder="e.g. Calm, accessible product design for small teams",
    ),
    RequirementSlot(
        key="identity.name",
        gap_class="identity",
        severity=_BLOCKING,
        impact=96,
        prompt="What name should appear on the kit?",
        question_type="short_text",
        unlocks="Adds the hero card and makes the copy third-person.",
        placeholder="e.g. Lyle Okoth",
    ),
    RequirementSlot(
        key="proof.metrics",
        gap_class="proof",
        severity=_SOFT,
        impact=85,
        prompt="Add one strong result we can put on a card.",
        question_type="number_unit",
        unlocks="Adds a proof point; three grounded numbers fill the proof card.",
        unit="%",
        placeholder="e.g. 11.8",
    ),
    RequirementSlot(
        key="proof.quote",
        gap_class="proof",
        severity=_SOFT,
        impact=75,
        prompt="Paste a short client quote.",
        question_type="short_text",
        unlocks="Adds the testimonial card with attribution.",
        placeholder="e.g. The narration pipeline cut our edit time in half.",
        requires_attestation=True,
    ),
    RequirementSlot(
        key="commerce.price",
        gap_class="commerce",
        severity=_SOFT,
        impact=65,
        prompt="What is the entry price?",
        question_type="number_unit",
        unlocks="Adds the offer card to commerce campaigns.",
        unit="$",
        placeholder="e.g. 49",
    ),
    RequirementSlot(
        key="identity.role",
        gap_class="identity",
        severity=_SOFT,
        impact=60,
        prompt="What is your role?",
        question_type="short_text",
        unlocks="Adds a role line to the hero card.",
        placeholder="e.g. Machine Learning Engineer",
    ),
    RequirementSlot(
        key="visual.project_shot",
        gap_class="visual",
        severity=_SOFT,
        impact=55,
        prompt="Paste a link to a product or project screenshot.",
        question_type="url",
        unlocks="Adds the project grid without substituting a stock image.",
        placeholder="https://…",
    ),
    RequirementSlot(
        key="contact.email",
        gap_class="contact",
        severity=_SOFT,
        impact=52,
        prompt="What email should the contact card use?",
        question_type="short_text",
        unlocks="Adds a contact route to the kit.",
        placeholder="you@example.com",
    ),
    RequirementSlot(
        key="attribution.quote",
        gap_class="attribution",
        severity=_SOFT,
        impact=50,
        prompt="Who said the quote, and what is their role?",
        question_type="short_text",
        unlocks="Makes the testimonial attributable instead of anonymous.",
        placeholder="e.g. Daniel Reyes, Founder — Kite Learning",
    ),
    RequirementSlot(
        key="identity.location",
        gap_class="identity",
        severity=_SOFT,
        impact=45,
        prompt="Where are you based?",
        question_type="short_text",
        unlocks="Adds a location line to the hero card.",
        placeholder="e.g. Nairobi, Kenya",
    ),
    RequirementSlot(
        key="contact.url",
        gap_class="contact",
        severity=_SOFT,
        impact=42,
        prompt="Paste a contact or booking link.",
        question_type="url",
        unlocks="Adds a working call to action.",
        placeholder="https://…",
    ),
    RequirementSlot(
        key="identity.portrait",
        gap_class="identity",
        severity=_SOFT,
        impact=40,
        prompt="Paste a link to your portrait.",
        question_type="url",
        unlocks="Adds your portrait to the hero and about cards.",
        placeholder="https://…",
    ),
    RequirementSlot(
        key="proof.client_logo",
        gap_class="visual",
        severity=_SOFT,
        impact=35,
        prompt="Paste a link to a client or brand logo.",
        question_type="url",
        unlocks="Adds a logo mark to the proof card.",
        placeholder="https://…",
    ),
    RequirementSlot(
        key="recency.metrics",
        gap_class="recency",
        severity=_SOFT,
        impact=30,
        prompt="When were these numbers measured?",
        question_type="short_text",
        unlocks="Lets the proof card label a date instead of implying the number is current.",
        placeholder="e.g. 2026-10",
    ),
)

SLOT_BY_KEY: dict[str, RequirementSlot] = {slot.key: slot for slot in SLOTS}

SLOTS_BY_CLASS: dict[str, tuple[RequirementSlot, ...]] = {}
for _slot in SLOTS:
    SLOTS_BY_CLASS.setdefault(_slot.gap_class, ())
    SLOTS_BY_CLASS[_slot.gap_class] += (_slot,)


def slot_for(key: str) -> RequirementSlot | None:
    return SLOT_BY_KEY.get(key)


def slots_for_class(gap_class: str) -> tuple[RequirementSlot, ...]:
    return SLOTS_BY_CLASS.get(gap_class, ())
