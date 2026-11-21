"""Provenance, citation and injection gates.

The AST is the source of truth: every number and badge points at a fact id, so
this is a join, not an OCR guess. Free text may not introduce a digit that no
tier-A/B fact supports, and a tier-C/D fact may never be rendered even if a slot
claims otherwise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import httpx

from app.compose.ast import renderable
from app.schemas.content import ContentModel, Fact, numbers_in
from app.schemas.design import LayoutAST

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?previous"
    r"|system\s+prompt"
    r"|you\s+are\s+now"
    r"|<script"
    r"|javascript:"
    r"|\{\{|\}\}"
    r"|\bsk-[A-Za-z0-9]{8,}",
    re.IGNORECASE,
)
_QUOTE_PERMISSIONS = {"published_on_site", "attested"}


@dataclass(frozen=True)
class Finding:
    slot: str
    reason: str
    detail: str


def _string(row: str) -> str:
    return re.sub(r"\s+", " ", row).strip()


def rendered_text(slots: object) -> list[tuple[str, str]]:
    """Every string the card template draws, with a stable slot name."""
    rows: list[tuple[str, str]] = []
    eyebrow = getattr(slots, "eyebrow", "")
    if eyebrow:
        rows.append(("eyebrow", _string(eyebrow)))
    for index, part in enumerate(getattr(slots, "headline", [])):
        if part.text:
            rows.append((f"headline.{index}", _string(part.text)))
    subhead = getattr(slots, "subhead", "")
    if subhead:
        rows.append(("subhead", _string(subhead)))
    for index, tile in enumerate(getattr(slots, "tiles", [])):
        rows.append((f"tile-{index}.title", _string(tile.title)))
        if tile.blurb:
            rows.append((f"tile-{index}.blurb", _string(tile.blurb)))
        if tile.badge:
            rows.append((f"tile-{index}.badge", _string(tile.badge)))
    for index, stat in enumerate(getattr(slots, "stats", [])):
        value = f"{stat.value} {stat.unit}" if stat.unit else stat.value
        rows.append((f"stat-{index}.value", _string(value)))
        if stat.label:
            rows.append((f"stat-{index}.label", _string(stat.label)))
        if stat.as_of:
            rows.append((f"stat-{index}.as_of", _string(stat.as_of)))
    quote = getattr(slots, "quote", None)
    if quote is not None:
        rows.append(("quote.text", _string(quote.text)))
        if quote.attribution:
            rows.append(("quote.attribution", _string(quote.attribution)))
        if quote.role:
            rows.append(("quote.role", _string(quote.role)))
    cta = getattr(slots, "cta", None)
    if cta is not None:
        rows.append(("cta.label", _string(cta.label)))
        rows.append(("cta.url", _string(cta.url)))
    qr = getattr(slots, "qr", None)
    if qr is not None:
        rows.append(("qr.url", _string(qr.url)))
    # ``tools`` and ``footnotes`` are not drawn by the card template.
    return rows


def _references(layout: LayoutAST) -> list[tuple[str, str, str | None]]:
    refs: list[tuple[str, str, str | None]] = []
    for index, stat in enumerate(layout.slots.stats):
        refs.append((f"stat-{index}", stat.fact_id, stat.tier))
    if layout.slots.quote is not None:
        refs.append(("quote", layout.slots.quote.fact_id, layout.slots.quote.tier))
    for index, tile in enumerate(layout.slots.tiles):
        if tile.badge_fact_id:
            refs.append((f"tile-{index}.badge", tile.badge_fact_id, tile.badge_tier))
    return refs


def _supported_numbers(model: ContentModel, *, today: date | None) -> set[str]:
    supported: set[str] = set()
    for fact in model.facts:
        if fact.tier not in {"A", "B"} or not renderable(fact, today=today):
            continue
        for field in (
            fact.value,
            fact.label,
            fact.unit or "",
            fact.as_of or "",
            fact.source_quote,
        ):
            supported |= numbers_in(field)
    return supported


def check(
    layout: LayoutAST,
    model: ContentModel,
    *,
    today: date | None = None,
) -> list[Finding]:
    """Join every rendered number and reference back to a tier-A/B fact."""
    findings: list[Finding] = []
    by_id = {fact.id: fact for fact in model.facts}

    for slot, fact_id, declared_tier in _references(layout):
        fact = by_id.get(fact_id)
        if fact is None:
            findings.append(
                Finding(slot, "unknown_fact", f"{fact_id!r} is not in facts[]")
            )
            continue
        if fact.tier not in {"A", "B"}:
            findings.append(
                Finding(
                    slot,
                    "tier_not_renderable",
                    f"{fact_id} is tier {fact.tier}; only A and B may render",
                )
            )
        elif declared_tier is not None and declared_tier != fact.tier:
            findings.append(
                Finding(
                    slot,
                    "tier_mismatch",
                    f"{fact_id} is tier {fact.tier} but the slot declares {declared_tier}",
                )
            )
        if not renderable(fact, today=today):
            findings.append(
                Finding(
                    slot,
                    "stale_fact",
                    f"{fact_id} is not renderable (missing as-of date or unsupported)",
                )
            )

    supported = _supported_numbers(model, today=today)
    for slot, text in rendered_text(layout.slots):
        # A URL is navigation, not a claim: its digits are not provenance.
        missing = numbers_in(_URL.sub(" ", text)) - supported
        if missing:
            findings.append(
                Finding(
                    slot,
                    "unsupported_number",
                    f"digits {sorted(missing)} have no tier-A/B fact",
                )
            )
    return findings


def check_quote_permission(
    layout: LayoutAST, model: ContentModel
) -> list[Finding]:
    quote = layout.slots.quote
    if quote is None:
        return []
    fact = next((item for item in model.facts if item.id == quote.fact_id), None)
    if fact is None:
        return [Finding("quote", "unknown_fact", f"{quote.fact_id!r} is not in facts[]")]
    if fact.permission not in _QUOTE_PERMISSIONS:
        return [
            Finding(
                "quote",
                "quote_permission",
                f"{fact.id} has permission {fact.permission!r}; "
                "expected published_on_site or attested",
            )
        ]
    return []


def used_facts(layout: LayoutAST, model: ContentModel) -> list[Fact]:
    ids = {fact_id for _, fact_id, _ in _references(layout)}
    return [fact for fact in model.facts if fact.id in ids]


def check_citation(
    layout: LayoutAST,
    model: ContentModel,
    *,
    online: bool = False,
    timeout: float = 10.0,
) -> list[Finding]:
    """Every tier-B fact in the asset needs a publication date and a live URL."""
    findings: list[Finding] = []
    for fact in used_facts(layout, model):
        if fact.tier != "B":
            continue
        if fact.published_at is None:
            findings.append(
                Finding(fact.id, "missing_published_at", "tier-B fact has no publication date")
            )
        source = fact.source.strip()
        if not source.lower().startswith(("http://", "https://")):
            findings.append(
                Finding(fact.id, "no_source_url", f"source {source[:80]!r} is not a URL")
            )
            continue
        if not online:
            continue
        try:
            response = httpx.head(source, timeout=timeout, follow_redirects=True)
        except httpx.HTTPError as exc:
            findings.append(Finding(fact.id, "unreachable_source", str(exc)))
            continue
        if response.status_code >= 400:
            findings.append(
                Finding(
                    fact.id,
                    "unreachable_source",
                    f"HEAD {source} returned {response.status_code}",
                )
            )
    return findings


def check_injection(
    layout: LayoutAST, model: ContentModel
) -> list[Finding]:
    """Fetched text must not smuggle instructions or credentials into a card."""
    findings: list[Finding] = []
    rows = rendered_text(layout.slots)
    rows.extend(
        [
            ("thesis", model.thesis),
            ("audience", model.audience),
            ("cta.label", model.cta.label),
        ]
    )
    for slot, text in rows:
        match = _INJECTION.search(text)
        if match:
            findings.append(
                Finding(slot, "instruction_echo", f"suspicious text {match.group(0)!r}")
            )
    return findings
