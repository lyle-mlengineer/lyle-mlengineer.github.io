"""Generate and validate five platform-native copy decks.

The deterministic builder always exists and always passes the validator. A model
may improve the prose, but it gets one correction attempt and then falls back to
the deterministic deck. Hard limits are re-counted here; the prompt is never
trusted with them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.compose.ast import humanize_key, renderable
from app.config import get_settings
from app.copy.counts import (
    count_for,
    count_graphemes,
    count_x,
    hashtags_in,
    spec_for_copy,
    strip_urls,
)
from app.copy.voice import build_voice_card
from app.pipeline.understand.llm import LLMClient, LLMError
from app.schemas.content import ContentModel, Fact, numbers_in
from app.schemas.copy import CopyDeck, CopyIssue, PostSpec, VoiceCard
from app.schemas.profile import SiteProfile

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "copy_v1.md"
PROMPT_VERSION = "copy_v1"

_WHITESPACE = re.compile(r"\s+")
_THREAD_PREFIX = re.compile(r"^\s*\d+\s*/\s*")
_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "you",
    "your",
}


class CopyValidationError(ValueError):
    """A deck failed a rule after the allowed regeneration attempt."""

    def __init__(self, issues: list[CopyIssue]) -> None:
        self.issues = issues
        detail = "; ".join(f"{item.field}: {item.detail}" for item in issues) or "invalid deck"
        super().__init__(detail)


@lru_cache(maxsize=1)
def load_prompt() -> tuple[str, str]:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_hash() -> str:
    return load_prompt()[1]


# ---------------------------------------------------------------------------
# Shared deterministic helpers
# ---------------------------------------------------------------------------


def _clean(text: str | None) -> str:
    return _WHITESPACE.sub(" ", (text or "")).strip()


def _plain(text: str) -> str:
    """Remove typographic dashes so the deterministic deck cannot overuse them."""
    return _clean(text).replace("—", " - ").replace("–", " - ")


def _banned(banned: list[str] | None) -> list[str]:
    return banned if banned is not None else list(get_settings().copy_banned_phrases)


def _safe(text: str, banned: list[str]) -> str:
    lowered = text.casefold()
    return "" if any(phrase.casefold() in lowered for phrase in banned) else text


def _unit(value: str, unit: str | None) -> str:
    if not unit:
        return value
    if unit.startswith(("%", "‰", "°", "×")) or unit.startswith("/"):
        return f"{value}{unit}"
    return f"{value} {unit}"


def fact_text(fact: Fact, *, with_label: bool = True) -> str:
    value = _unit(_clean(fact.value), fact.unit)
    label = _clean(fact.label) or humanize_key(fact.key)
    return f"{value} {label}" if with_label and label else value


def usable_facts(model: ContentModel, *, today: date | None = None) -> list[Fact]:
    return [
        fact
        for fact in model.facts
        if fact.tier in {"A", "B"} and renderable(fact, today=today)
    ]


def proof_facts(model: ContentModel, facts: list[Fact]) -> list[Fact]:
    """Facts in the content model's proof order, then the rest."""
    by_id = {fact.id: fact for fact in facts}
    ordered = [
        by_id[proof.fact_id]
        for proof in model.proof
        if proof.fact_id in by_id
    ]
    seen = {fact.id for fact in ordered}
    return ordered + [fact for fact in facts if fact.id not in seen]


def supported_numbers(model: ContentModel) -> set[str]:
    """Digits a caption may contain: values, labels and quotes in tier A/B facts."""
    supported: set[str] = set()
    for fact in model.facts:
        if fact.tier not in {"A", "B"}:
            continue
        for text in (fact.value, fact.unit, fact.label, fact.as_of, fact.source_quote):
            if text:
                supported |= numbers_in(text)
    return supported


def _name(profile: SiteProfile) -> str:
    return profile.entities.person.name or profile.entities.org.name or ""


def _role(profile: SiteProfile) -> str:
    role = profile.entities.person.role or profile.entities.org.name
    if role:
        return role
    value = profile.understanding.value_proposition
    return value.text if value is not None else ""


def _location(profile: SiteProfile) -> str:
    return profile.entities.person.location or ""


def _thesis(model: ContentModel, banned: list[str]) -> str:
    thesis = _safe(_plain(model.thesis), banned)
    if thesis:
        return thesis
    if model.offerings:
        title = _plain(model.offerings[0].title)
        if _safe(title, banned):
            return f"{title} that ships."
    return "Work that ships, with the evidence behind it."


def _audience(model: ContentModel, banned: list[str]) -> str:
    audience = _safe(_plain(model.audience), banned)
    return audience


def _offering_lines(model: ContentModel, banned: list[str], limit: int = 4) -> list[str]:
    lines: list[str] = []
    for offering in model.offerings[:limit]:
        title = _safe(_plain(offering.title), banned)
        summary = _safe(_plain(offering.one_liner), banned)
        if not title:
            continue
        lines.append(f"{title}: {summary}" if summary else title)
    return lines


def _project_lines(model: ContentModel, banned: list[str], limit: int = 6) -> list[str]:
    lines: list[str] = []
    for project in model.projects[:limit]:
        name = _safe(_plain(project.name), banned)
        blurb = _safe(_plain(project.blurb), banned)
        if not name:
            continue
        lines.append(f"{name}: {blurb}" if blurb else name)
    return lines


def _proof_lines(facts: list[Fact], banned: list[str], limit: int = 4) -> list[str]:
    lines: list[str] = []
    for fact in facts[:limit]:
        text = _safe(fact_text(fact), banned)
        if text:
            lines.append(text)
    return lines


def _quote_line(model: ContentModel, facts: list[Fact], banned: list[str]) -> str:
    if model.quote is None:
        return ""
    fact = next((item for item in facts if item.id == model.quote.fact_id), None)
    if fact is None:
        return ""
    said = _safe(_plain(fact.value), banned)
    if not said:
        return ""
    attribution = _plain(model.quote.attribution or "")
    return f'"{said}" - {attribution}' if attribution else f'"{said}"'


def _hashtags(
    model: ContentModel,
    profile: SiteProfile,
    banned: list[str],
    count: int,
) -> list[str]:
    phrases = [
        _role(profile),
        *[offering.title for offering in model.offerings],
        *[project.name for project in model.projects],
        model.audience,
        *[fact.label for fact in model.facts if fact.tier in {"A", "B"}],
    ]
    blocked = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9'’]*", _name(profile))
    }
    seen: set[str] = set()
    tags: list[str] = []
    for phrase in phrases:
        tokens = [
            token.strip("'’")
            for token in re.findall(r"[A-Za-z][A-Za-z0-9'’]*", phrase or "")
        ]
        tokens = [
            token
            for token in tokens
            if (len(token) >= 3 or (len(token) == 2 and token.isupper()))
            and token.casefold() not in _STOP
            and token.casefold() not in blocked
        ]
        if not tokens:
            continue
        for width in (2, 1, 3):
            if len(tokens) < width:
                continue
            candidate = "".join(token[:1].upper() + token[1:] for token in tokens[:width])
            key = candidate.casefold()
            if key in seen or len(candidate) > 30:
                continue
            if any(word.casefold() in candidate.casefold() for word in banned):
                continue
            seen.add(key)
            tags.append(f"#{candidate}")
            break
        if len(tags) == count:
            break
    for fallback in ("Portfolio", "Build", "Shipping", "Proof", "Work"):
        if len(tags) == count:
            break
        if fallback.casefold() not in seen:
            seen.add(fallback.casefold())
            tags.append(f"#{fallback}")
    return tags[:count]


def _url(model: ContentModel) -> str:
    return model.cta.url


def _cta_label(model: ContentModel) -> str:
    label = _clean(model.cta.label)
    if not label or numbers_in(label):
        # A CTA label is interface text, not a claim. If it carries a port,
        # phone number or version, fall back rather than inventing provenance.
        return "Portfolio"
    return label


def _join(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line is not None).strip()


def _fit_x(candidates: list[str], banned: list[str], limit: int = 280) -> str:
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        if not _safe(text, banned):
            continue
        if count_x(text) <= limit:
            return text
    # Last resort: trim the first candidate to a word boundary. This only runs
    # when the site's own thesis is unusually long.
    for candidate in candidates:
        text = candidate.strip()
        if not text or not _safe(text, banned):
            continue
        words = text.split()
        while words:
            shortened = " ".join(words)
            if count_x(shortened) <= limit:
                return shortened
            words.pop()
    return ""


def _fit_graphemes(candidates: list[str], banned: list[str], limit: int) -> str:
    for candidate in candidates:
        text = candidate.strip()
        if not text or not _safe(text, banned):
            continue
        if count_graphemes(text) <= limit:
            return text
    for candidate in candidates:
        text = candidate.strip()
        if not text or not _safe(text, banned):
            continue
        words = text.split()
        while words:
            shortened = " ".join(words)
            if count_graphemes(shortened) <= limit:
                return shortened
            words.pop()
    return ""


# ---------------------------------------------------------------------------
# Deterministic builders
# ---------------------------------------------------------------------------


def _build_linkedin(
    model: ContentModel,
    profile: SiteProfile,
    voice: VoiceCard,
    banned: list[str],
    facts: list[Fact],
) -> CopyDeck:
    thesis = _thesis(model, banned)
    audience = _audience(model, banned)
    offerings = _offering_lines(model, banned)
    projects = _project_lines(model, banned)
    proof = _proof_lines(facts, banned)
    quote = _quote_line(model, facts, banned)
    tags = _hashtags(model, profile, banned, 4)
    url = _url(model)
    label = _cta_label(model)

    def assemble(
        project_items: list[str],
        offering_items: list[str],
        proof_items: list[str],
    ) -> str:
        lines = [thesis]
        if audience:
            lines += ["", audience]
        if offering_items:
            lines += ["", "What I build:"]
            lines += [f"- {item}" for item in offering_items]
        if project_items:
            lines += ["", "Selected work:"]
            lines += [f"- {item}" for item in project_items]
        if proof_items:
            lines += ["", "The numbers:"]
            lines += [f"- {item}" for item in proof_items]
        if quote:
            lines += ["", quote]
        lines += ["", f"{label}: {url}"]
        if tags:
            lines += ["", " ".join(tags)]
        return _join(lines)

    primary = assemble(projects, offerings, proof)
    while count_graphemes(primary) > 3000 and projects:
        projects.pop()
        primary = assemble(projects, offerings, proof)
    while count_graphemes(primary) > 3000 and offerings:
        offerings.pop()
        primary = assemble(projects, offerings, proof)
    while count_graphemes(primary) > 3000 and proof:
        proof.pop()
        primary = assemble(projects, offerings, proof)

    short = _fit_graphemes(
        [f"{thesis}\n\n{url}", f"{_audience(model, banned) or thesis}\n\n{url}", url],
        banned,
        3000,
    )

    alternatives = [
        _fit_graphemes(
            [
                "The numbers first:\n\n"
                + "\n".join(f"- {item}" for item in proof)
                + f"\n\n{thesis}\n\n{url}",
                f"{thesis}\n\n{url}",
                url,
            ],
            banned,
            3000,
        ),
        _fit_graphemes(
            [
                f"{audience}\n\n{thesis}\n\n{label}: {url}",
                f"{thesis}\n\n{label}: {url}",
                url,
            ],
            banned,
            3000,
        ),
        short,
    ]
    return CopyDeck(
        platform="linkedin",
        primary=primary,
        alternatives=alternatives,
        short_variant=short,
        hashtags=tags,
    )


def _build_x(
    model: ContentModel,
    profile: SiteProfile,
    voice: VoiceCard,
    banned: list[str],
    facts: list[Fact],
) -> CopyDeck:
    thesis = _thesis(model, banned)
    audience = _audience(model, banned)
    offerings = _offering_lines(model, banned)
    proof = _proof_lines(facts, banned)
    url = _url(model)
    label = _cta_label(model)
    tags = _hashtags(model, profile, banned, 1)

    proof_line = "; ".join(proof[:3])
    primary = _fit_x(
        [
            f"{thesis}\n\n{proof_line}.",
            f"{thesis}\n\n{proof[0]}." if proof else "",
            thesis,
        ],
        banned,
    )

    short = _fit_x([f"{thesis} {url}", f"{thesis}", url], banned)

    alternatives = [
        _fit_x(
            [
                f"{proof_line}.\n\n{thesis}",
                f"{proof[0]}.\n\n{thesis}" if proof else "",
                thesis,
            ],
            banned,
        ),
        _fit_x([f"{audience}\n\n{thesis}", thesis, proof_line], banned),
        short,
    ]

    problem = _fit_x(
        [f"1/ {audience}\n\nThat gap is the work.", f"1/ {thesis}", "1/"],
        banned,
    )
    work = _fit_x(
        ["2/ What I build:\n\n" + "\n".join(f"- {item}" for item in offerings), "2/ " + thesis],
        banned,
    )
    numbers = _fit_x(
        ["3/ The numbers:\n\n" + "\n".join(f"- {item}" for item in proof), "3/ " + proof_line],
        banned,
    )
    closing = _fit_x(
        [
            f"4/ {label}:\n{url}\n\n{' '.join(tags)}",
            f"4/ {label}:\n{url}",
            f"4/ {url}",
        ],
        banned,
    )

    return CopyDeck(
        platform="x",
        primary=primary,
        alternatives=alternatives,
        thread=[problem, work, numbers, closing],
        short_variant=short,
        hashtags=tags,
    )


def _build_instagram(
    model: ContentModel,
    profile: SiteProfile,
    voice: VoiceCard,
    banned: list[str],
    facts: list[Fact],
) -> CopyDeck:
    thesis = _thesis(model, banned)
    audience = _audience(model, banned)
    offerings = _offering_lines(model, banned)
    proof = _proof_lines(facts, banned)
    tags = _hashtags(model, profile, banned, 5)
    label = _cta_label(model)

    primary = _fit_graphemes(
        [
            _join(
                [
                    thesis,
                    "",
                    audience,
                    "",
                    "What I build:",
                    *[f"- {item}" for item in offerings],
                    "",
                    "The numbers:",
                    *[f"- {item}" for item in proof],
                    "",
                    f"{label} - link in bio.",
                    "",
                    " ".join(tags),
                ]
            ),
            _join(
                [
                    thesis,
                    "",
                    *[f"- {item}" for item in proof],
                    "",
                    "Case studies are in the link in bio.",
                    "",
                    " ".join(tags),
                ]
            ),
            f"{thesis}\n\nLink in bio.",
        ],
        banned,
        2200,
    )

    short = _fit_graphemes(
        [
            f"{thesis}\n\nCase studies in the link in bio.",
            f"{thesis}\n\nLink in bio.",
            "Link in bio.",
        ],
        banned,
        2200,
    )

    alternatives = [
        _fit_graphemes(
            [
                _join(
                    [
                        "The numbers first:",
                        *[f"- {item}" for item in proof],
                        "",
                        thesis,
                        "",
                        "Case studies in the link in bio.",
                        "",
                        " ".join(tags),
                    ]
                ),
                short,
            ],
            banned,
            2200,
        ),
        _fit_graphemes(
            [
                _join([audience or thesis, "", thesis, "", "Link in bio.", "", " ".join(tags)]),
                short,
            ],
            banned,
            2200,
        ),
        short,
    ]
    return CopyDeck(
        platform="instagram",
        primary=primary,
        alternatives=alternatives,
        short_variant=short,
        hashtags=tags,
    )


def _build_tiktok(
    model: ContentModel,
    profile: SiteProfile,
    voice: VoiceCard,
    banned: list[str],
    facts: list[Fact],
) -> CopyDeck:
    thesis = _thesis(model, banned)
    audience = _audience(model, banned)
    offerings = _offering_lines(model, banned)
    proof = _proof_lines(facts, banned)
    tags = _hashtags(model, profile, banned, 3)
    label = _cta_label(model)

    primary = _fit_graphemes(
        [
            _join(
                [
                    thesis,
                    "",
                    audience,
                    "",
                    "What I build:",
                    *[f"- {item}" for item in offerings],
                    "",
                    "The numbers:",
                    *[f"- {item}" for item in proof],
                    "",
                    f"{label} - link in bio. Follow for more.",
                    "",
                    " ".join(tags),
                ]
            ),
            _join(
                [
                    thesis,
                    "",
                    *[f"- {item}" for item in proof],
                    "",
                    "Link in bio.",
                    " ".join(tags),
                ]
            ),
            f"{thesis}\n\nLink in bio.",
        ],
        banned,
        2200,
    )
    short = _fit_graphemes(
        [f"{thesis}\n\nLink in bio.", f"{thesis}", "Link in bio."],
        banned,
        2200,
    )
    alternatives = [
        _fit_graphemes(
            [
                _join(
                    [
                        "The numbers first:",
                        *[f"- {item}" for item in proof],
                        "",
                        thesis,
                        "",
                        " ".join(tags),
                    ]
                ),
                short,
            ],
            banned,
            2200,
        ),
        _fit_graphemes(
            [_join([audience or thesis, "", thesis, "", "Link in bio.", " ".join(tags)]), short],
            banned,
            2200,
        ),
        short,
    ]
    return CopyDeck(
        platform="tiktok",
        primary=primary,
        alternatives=alternatives,
        short_variant=short,
        hashtags=tags,
    )


def _build_whatsapp(
    model: ContentModel,
    profile: SiteProfile,
    voice: VoiceCard,
    banned: list[str],
    facts: list[Fact],
) -> CopyDeck:
    thesis = _thesis(model, banned)
    audience = _audience(model, banned)
    offerings = _offering_lines(model, banned)
    proof = _proof_lines(facts, banned, limit=3)
    url = _url(model)
    name = _name(profile)
    role = _role(profile)
    location = _location(profile)

    status = _fit_graphemes(
        [
            _join([thesis, "", audience, "", *proof, "", "The portfolio is live."]),
            _join([thesis, "", *proof, "", "The portfolio is live."]),
            f"{thesis} The portfolio is live.",
        ],
        banned,
        700,
    )

    individual = _fit_graphemes(
        [
            _join(
                [
                    "Hi [Name] - I have finally put my portfolio together and thought of you.",
                    "",
                    f"{thesis} {audience}".strip(),
                    "",
                    " ".join(proof),
                    "",
                    "The site has the case studies and the numbers behind each one:",
                    url,
                    "",
                    "Would value your take.",
                ]
            ),
            _join(["Hi [Name] - my portfolio is live.", "", thesis, "", url]),
        ],
        banned,
        700,
    )

    group = _fit_graphemes(
        [
            _join(
                [
                    "Sharing my portfolio in case it is useful to anyone here.",
                    "",
                    thesis,
                    "",
                    " ".join(proof),
                    "",
                    url,
                    "",
                    "Happy to answer questions on any of it.",
                ]
            ),
            _join(["Sharing my portfolio:", thesis, url]),
        ],
        banned,
        700,
    )

    heading = ", ".join(part for part in (name, role, location) if part)
    broadcast = _fit_graphemes(
        [
            _join(
                [
                    heading,
                    "",
                    thesis,
                    "",
                    "What is in it:",
                    *[f"- {item}" for item in offerings],
                    *[f"- {item}" for item in proof],
                    "",
                    url,
                ]
            ),
            _join([heading, "", thesis, "", url]),
        ],
        banned,
        700,
    )

    short = _fit_graphemes(
        [f"{thesis} The portfolio is live.", thesis, "The portfolio is live."],
        banned,
        700,
    )

    messages = {
        "status": status,
        "individual": individual,
        "group": group,
        "broadcast": broadcast,
    }
    return CopyDeck(
        platform="whatsapp",
        primary=status,
        alternatives=[individual, group, broadcast],
        short_variant=short,
        hashtags=[],
        messages=messages,
    )


_BUILDERS: dict[str, Callable[..., CopyDeck]] = {
    "linkedin": _build_linkedin,
    "x": _build_x,
    "instagram": _build_instagram,
    "tiktok": _build_tiktok,
    "whatsapp": _build_whatsapp,
}


def build_deck(
    platform: str,
    model: ContentModel,
    profile: SiteProfile,
    *,
    voice: VoiceCard | None = None,
    banned: list[str] | None = None,
    today: date | None = None,
) -> CopyDeck:
    """Build the deterministic deck for one platform."""
    spec = spec_for_copy(platform)
    phrases = _banned(banned)
    card = voice or build_voice_card(profile, model)
    facts = proof_facts(model, usable_facts(model, today=today))
    return _BUILDERS[spec.platform](model, profile, card, phrases, facts)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _texts(deck: CopyDeck) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = [("primary", deck.primary)]
    values.extend(
        (f"alternative-{index + 1}", text)
        for index, text in enumerate(deck.alternatives)
    )
    if deck.thread is not None:
        values.extend((f"thread-{index + 1}", text) for index, text in enumerate(deck.thread))
    if deck.short_variant:
        values.append(("short_variant", deck.short_variant))
    if deck.messages is not None:
        values.extend((f"messages.{key}", text) for key, text in deck.messages.items())
    return values


def _digit_issues(
    field: str,
    text: str,
    supported: set[str],
) -> CopyIssue | None:
    body = strip_urls(text)
    body = _THREAD_PREFIX.sub("", body)
    found = numbers_in(body)
    unsupported = sorted(found - supported)
    if not unsupported:
        return None
    return CopyIssue(
        field=field,
        reason="unsupported_number",
        detail=f"digit(s) {', '.join(unsupported)} have no tier A/B fact",
    )


def validate_deck(
    deck: CopyDeck,
    spec: PostSpec,
    model: ContentModel,
    *,
    banned: list[str] | None = None,
    supported: set[str] | None = None,
) -> list[CopyIssue]:
    """Return every hard-rule violation. An empty list means publishable."""
    phrases = _banned(banned)
    supported_numbers_set = supported if supported is not None else supported_numbers(model)
    max_em_dashes = get_settings().copy_max_em_dashes
    issues: list[CopyIssue] = []

    if deck.platform != spec.platform:
        issues.append(
            CopyIssue(
                field="platform",
                reason="shape",
                detail=f"deck is {deck.platform}, expected {spec.platform}",
            )
        )

    if len(deck.alternatives) != 3:
        issues.append(
            CopyIssue(
                field="alternatives",
                reason="shape",
                detail=f"expected exactly 3 alternatives, got {len(deck.alternatives)}",
            )
        )

    if spec.thread and not deck.thread:
        issues.append(
            CopyIssue(field="thread", reason="shape", detail="this platform needs a thread")
        )
    if not spec.thread and deck.thread:
        issues.append(
            CopyIssue(field="thread", reason="shape", detail="this platform does not use threads")
        )

    if spec.shapes == ["status", "individual", "group", "broadcast"]:
        if deck.messages is None:
            issues.append(
                CopyIssue(
                    field="messages",
                    reason="shape",
                    detail="WhatsApp needs status, individual, group and broadcast messages",
                )
            )
        else:
            missing = set(spec.shapes) - set(deck.messages)
            extra = set(deck.messages) - set(spec.shapes)
            if missing:
                issues.append(
                    CopyIssue(
                        field="messages",
                        reason="shape",
                        detail=f"missing message shape(s) {sorted(missing)}",
                    )
                )
            if extra:
                issues.append(
                    CopyIssue(
                        field="messages",
                        reason="shape",
                        detail=f"unknown message shape(s) {sorted(extra)}",
                    )
                )
            if deck.messages.get("status") != deck.primary:
                issues.append(
                    CopyIssue(
                        field="messages.status",
                        reason="shape",
                        detail="WhatsApp primary must equal the status message",
                    )
                )
    elif deck.messages is not None:
        issues.append(
            CopyIssue(
                field="messages",
                reason="shape",
                detail="only WhatsApp uses message shapes",
            )
        )

    for field, text in _texts(deck):
        length = count_for(spec, text)
        if length > spec.caption_max:
            issues.append(
                CopyIssue(
                    field=field,
                    reason="length",
                    detail=f"{length} > {spec.caption_max} characters",
                )
            )
        if not text.strip():
            issues.append(CopyIssue(field=field, reason="shape", detail="text is empty"))

    declared = deck.hashtags
    if not spec.hashtags_min <= len(declared) <= spec.hashtags_max:
        issues.append(
            CopyIssue(
                field="hashtags",
                reason="hashtags",
                detail=(
                    f"{len(declared)} hashtags, expected {spec.hashtags_min}-"
                    f"{spec.hashtags_max}"
                ),
            )
        )
    if len(set(declared)) != len(declared):
        issues.append(
            CopyIssue(field="hashtags", reason="hashtags", detail="duplicate hashtag")
        )
    for tag in declared:
        if not re.fullmatch(r"#[A-Za-z0-9_]+", tag):
            issues.append(
                CopyIssue(
                    field="hashtags",
                    reason="hashtags",
                    detail=f"{tag!r} is not a valid hashtag",
                )
            )
    in_text: set[str] = set()
    for _, text in _texts(deck):
        in_text.update(hashtags_in(text))
    undeclared = sorted(in_text - set(declared))
    if undeclared:
        issues.append(
            CopyIssue(
                field="hashtags",
                reason="hashtags",
                detail=f"hashtag(s) {undeclared} are not in hashtags[]",
            )
        )
    absent = sorted(set(declared) - in_text)
    if absent:
        issues.append(
            CopyIssue(
                field="hashtags",
                reason="hashtags",
                detail=f"hashtag(s) {absent} never appear in the copy",
            )
        )

    url = model.cta.url
    if spec.link_policy == "end":
        lines = [line.strip() for line in deck.primary.strip().splitlines() if line.strip()]
        body = [
            line
            for line in lines
            if not all(token.startswith("#") for token in line.split())
        ]
        last_body = body[-1] if body else ""
        if url not in deck.primary or url not in last_body:
            issues.append(
                CopyIssue(
                    field="primary",
                    reason="link",
                    detail="LinkedIn link must be the last line before the hashtags",
                )
            )
    elif spec.link_policy == "last_tweet":
        if url in deck.primary:
            issues.append(
                CopyIssue(
                    field="primary",
                    reason="link",
                    detail="the X hook must not contain the link",
                )
            )
        if deck.thread and url not in deck.thread[-1]:
            issues.append(
                CopyIssue(
                    field="thread",
                    reason="link",
                    detail="the link must be in the last tweet of the X thread",
                )
            )
        if deck.short_variant and url not in deck.short_variant:
            issues.append(
                CopyIssue(
                    field="short_variant",
                    reason="link",
                    detail="the X short variant must carry the link",
                )
            )
    elif spec.link_policy == "bio":
        for field, text in _texts(deck):
            if "http://" in text or "https://" in text:
                issues.append(
                    CopyIssue(
                        field=field,
                        reason="link",
                        detail="this platform cannot carry a clickable URL; use 'link in bio'",
                    )
                )
        if "link in bio" not in deck.primary.casefold():
            issues.append(
                CopyIssue(
                    field="primary",
                    reason="link",
                    detail="the caption must say 'link in bio'",
                )
            )
    elif spec.link_policy == "none":
        if deck.messages and "status" in deck.messages:
            status = deck.messages["status"]
            if "http://" in status or "https://" in status or "www." in status:
                issues.append(
                    CopyIssue(
                        field="messages.status",
                        reason="link",
                        detail="a WhatsApp status caption cannot contain a link",
                    )
                )

    em_dashes = sum(text.count("—") for _, text in _texts(deck))
    if em_dashes > max_em_dashes:
        issues.append(
            CopyIssue(
                field="copy",
                reason="banned_phrase",
                detail=f"{em_dashes} em dashes (max {max_em_dashes})",
            )
        )

    for field, text in _texts(deck):
        lowered = text.casefold()
        for phrase in phrases:
            if phrase.casefold() in lowered:
                issues.append(
                    CopyIssue(
                        field=field,
                        reason="banned_phrase",
                        detail=f"contains banned phrase {phrase!r}",
                    )
                )
        issue = _digit_issues(field, text, supported_numbers_set)
        if issue is not None:
            issues.append(issue)

    return issues


def validate_or_regenerate(
    generate: Callable[[list[CopyIssue]], CopyDeck],
    validate: Callable[[CopyDeck], list[CopyIssue]],
    *,
    attempts: int = 2,
) -> CopyDeck:
    """Generate, reject, regenerate once, then fail with the reasons."""
    issues: list[CopyIssue] = []
    for _ in range(attempts):
        deck = generate(issues)
        issues = validate(deck)
        if not issues:
            return deck
    raise CopyValidationError(issues)


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


def _deck_from_payload(platform: str, payload: dict[str, Any]) -> CopyDeck:
    def text(key: str) -> str:
        value = payload.get(key)
        return value.strip() if isinstance(value, str) else ""

    raw_alternatives = payload.get("alternatives")
    alternatives = [
        item.strip()
        for item in raw_alternatives
        if isinstance(item, str) and item.strip()
    ][:3] if isinstance(raw_alternatives, list) else []
    if len(alternatives) != 3:
        raise ValueError("copy payload needs exactly three alternatives")

    raw_thread = payload.get("thread")
    thread: list[str] | None = None
    if isinstance(raw_thread, list):
        thread = [item.strip() for item in raw_thread if isinstance(item, str) and item.strip()]
        if not thread:
            thread = None

    raw_messages = payload.get("messages")
    messages: dict[str, str] | None = None
    if isinstance(raw_messages, dict):
        messages = {
            key: value.strip()
            for key, value in raw_messages.items()
            if isinstance(key, str) and isinstance(value, str) and value.strip()
        }

    raw_tags = payload.get("hashtags")
    tags = [
        item.strip()
        for item in raw_tags
        if isinstance(item, str) and item.strip()
    ] if isinstance(raw_tags, list) else []

    return CopyDeck(
        platform=platform,  # type: ignore[arg-type]
        primary=text("primary"),
        alternatives=alternatives,
        thread=thread,
        short_variant=text("short_variant"),
        hashtags=tags,
        messages=messages,
        source="llm",
    )


def _llm_deck(
    spec: PostSpec,
    model: ContentModel,
    profile: SiteProfile,
    voice: VoiceCard,
    banned: list[str],
    client: LLMClient,
    issues: list[CopyIssue],
) -> CopyDeck:
    system, _ = load_prompt()
    facts = [
        {
            "id": fact.id,
            "key": fact.key,
            "value": fact.value,
            "unit": fact.unit,
            "label": fact.label,
            "tier": fact.tier,
        }
        for fact in usable_facts(model)
    ]
    request = {
        "platform": spec.platform,
        "post_spec": spec.model_dump(mode="json"),
        "voice_card": voice.model_dump(mode="json"),
        "thesis": model.thesis,
        "audience": model.audience,
        "offerings": [offering.model_dump(mode="json") for offering in model.offerings],
        "projects": [project.model_dump(mode="json") for project in model.projects],
        "facts": facts,
        "cta": model.cta.model_dump(mode="json"),
        "banned_phrases": banned,
        "previous_issues": [issue.model_dump(mode="json") for issue in issues],
        "response_keys": [
            "primary",
            "alternatives",
            "thread",
            "short_variant",
            "hashtags",
            "messages",
        ],
    }
    payload = client.complete_json(system, json.dumps(request, ensure_ascii=False))
    return _deck_from_payload(spec.platform, payload)


def generate_deck(
    platform: str,
    model: ContentModel,
    profile: SiteProfile,
    *,
    voice: VoiceCard | None = None,
    client: LLMClient | None = None,
    use_llm: bool = True,
    banned: list[str] | None = None,
    today: date | None = None,
) -> CopyDeck:
    """Return a valid deck, using the model when available and safe."""
    spec = spec_for_copy(platform)
    phrases = _banned(banned)
    card = voice or build_voice_card(profile, model)
    deterministic = build_deck(
        spec.platform, model, profile, voice=card, banned=phrases, today=today
    )
    issues = validate_deck(deterministic, spec, model, banned=phrases)
    if issues:
        # The heuristic is supposed to be valid by construction. If the site's
        # own text defeats it, fail loudly rather than writing a broken deck.
        raise CopyValidationError(issues)

    if not use_llm or client is None or not getattr(client, "available", True):
        return deterministic

    try:
        deck = validate_or_regenerate(
            lambda prior: _llm_deck(
                spec, model, profile, card, phrases, client, prior
            ),
            lambda candidate: validate_deck(
                candidate, spec, model, banned=phrases
            ),
        )
        return deck
    except (CopyValidationError, LLMError, ValueError, TypeError) as exc:
        deterministic.warnings.append(
            f"LLM copy was rejected; using the deterministic deck ({exc})"
        )
        return deterministic
