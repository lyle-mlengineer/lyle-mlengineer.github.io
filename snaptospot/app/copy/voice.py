"""Derive the site's voice card without asking a model.

The card is a constraint, not prose: it tells the copy call whether to write in
the first person, which tense the site uses, how formal it sounds and how long
its sentences run. Samples are verbatim strings from the site so the writer has
a concrete register to match.
"""

from __future__ import annotations

import re

from app.schemas.content import ContentModel
from app.schemas.copy import VoiceCard
from app.schemas.profile import SiteProfile

_WHITESPACE = re.compile(r"\s+")
_FIRST_PERSON = re.compile(r"\b(I|I'm|I've|I'd|my|me|we|we're|our|us)\b", re.IGNORECASE)
_PAST = re.compile(
    r"\b(built|shipped|led|worked|ran|made|launched|created|designed)\b", re.IGNORECASE
)
_PRESENT = re.compile(r"\b(build|ships?|lead|work|run|make|launch|create|design)\b", re.IGNORECASE)
_FORMAL = {"formal", "corporate", "professional", "enterprise", "institutional"}


def _clean(text: str | None) -> str:
    return _WHITESPACE.sub(" ", (text or "")).strip()


def _samples(profile: SiteProfile, model: ContentModel) -> list[str]:
    candidates: list[str] = [
        profile.understanding.value_proposition.text
        if profile.understanding.value_proposition
        else "",
        model.thesis,
        model.offerings[0].one_liner if model.offerings else "",
        model.projects[0].blurb if model.projects else "",
        profile.understanding.audience or "",
        profile.title,
    ]
    seen: set[str] = set()
    samples: list[str] = []
    for candidate in candidates:
        text = _clean(candidate)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        samples.append(text)
        if len(samples) == 3:
            break
    return samples


def build_voice_card(profile: SiteProfile, model: ContentModel) -> VoiceCard:
    """Return a stable voice card for this profile and content model."""
    thesis = _clean(model.thesis)
    tone = {item.casefold() for item in profile.understanding.tone}
    samples = _samples(profile, model)

    person = "first" if _FIRST_PERSON.search(thesis) else "third"
    if _FIRST_PERSON.search(thesis) and not profile.entities.person.name:
        person = "third"

    tense = "past" if _PAST.search(thesis) and not _PRESENT.search(thesis) else "present"

    formality = "formal" if tone & _FORMAL else "plain"

    corpus = " ".join([thesis, *samples])
    average = len(corpus.split()) / max(1, len(samples) + 1)
    if average <= 12:
        sentence_length = "short"
    elif average <= 22:
        sentence_length = "medium"
    else:
        sentence_length = "long"

    return VoiceCard(
        person=person,
        tense=tense,
        formality=formality,
        sentence_length=sentence_length,
        samples=samples,
    )
