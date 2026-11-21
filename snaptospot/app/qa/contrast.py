"""WCAG contrast on every text/background pair in the AST.

Pairs are semantic, not sampled from pixels: the card template maps a slot to a
token pair, and the ratio comes from the token hex values. That makes the gate
deterministic and explains itself in the report.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.compose.layouts import CARD_ASSETS
from app.design.tokens import contrast_ratio
from app.qa.provenance import Finding
from app.schemas.design import DesignSystem, LayoutAST

BODY_MIN = 4.5
DISPLAY_MIN = 3.0
_CARD_BY_ASSET = {name: card for card, name in CARD_ASSETS.items()}

# slot -> (foreground token, background token, display type?)
_PAIRS: dict[str, tuple[str, str, bool]] = {
    "eyebrow": ("muted", "bg", False),
    "headline": ("paper", "bg", True),
    "headline.accent": ("accent", "bg", True),
    "subhead": ("muted", "bg", False),
    "tile.title": ("paper", "bg", True),
    "tile.blurb": ("muted", "bg", False),
    "tile.metric": ("accent", "bg", False),
    "tile.badge": ("paper", "bg", False),
    "stat.value": ("paper", "bg", True),
    "stat.unit": ("muted", "bg", False),
    "stat.label": ("muted", "bg", False),
    "stat.date": ("muted_2", "bg", False),
    "quote.text": ("paper", "bg", True),
    "quote.attr": ("muted", "bg", False),
    "cta.label": ("muted", "bg", False),
    "cta.url": ("paper", "bg", False),
    "qr.url": ("muted", "bg", False),
}


@dataclass(frozen=True)
class Pair:
    slot: str
    foreground: str
    background: str
    display: bool


def pairs_for(layout: LayoutAST) -> list[Pair]:
    """Only the pairs the template actually draws for this card."""
    slots = layout.slots
    card = _CARD_BY_ASSET.get(layout.asset.split("/", 1)[-1], "")
    wanted: list[str] = []
    if slots.eyebrow:
        wanted.append("eyebrow")
    if any(part.text for part in slots.headline):
        wanted.append("headline")
        if any(part.emphasis in {"last_word", "accent"} for part in slots.headline):
            wanted.append("headline.accent")
    if slots.subhead:
        wanted.append("subhead")
    for tile in slots.tiles:
        wanted.append("tile.title")
        if tile.blurb:
            wanted.append("tile.blurb")
        if tile.badge:
            wanted.append("tile.metric" if card != "projects" else "tile.badge")
    for stat in slots.stats:
        wanted.append("stat.value")
        if stat.unit:
            wanted.append("stat.unit")
        if stat.label:
            wanted.append("stat.label")
        if stat.as_of:
            wanted.append("stat.date")
    if slots.quote is not None:
        wanted.append("quote.text")
        if slots.quote.attribution or slots.quote.role:
            wanted.append("quote.attr")
    if slots.cta is not None:
        wanted.append("cta.label")
        wanted.append("cta.url")
    if slots.qr is not None:
        wanted.append("qr.url")
    seen: set[str] = set()
    pairs: list[Pair] = []
    for name in wanted:
        if name in seen:
            continue
        seen.add(name)
        foreground, background, display = _PAIRS[name]
        pairs.append(Pair(name, foreground, background, display))
    return pairs


def check(
    layout: LayoutAST,
    design: DesignSystem,
    *,
    body_min: float = BODY_MIN,
    display_min: float = DISPLAY_MIN,
) -> tuple[list[Finding], dict[str, float | int | str]]:
    tokens = design.tokens
    findings: list[Finding] = []
    metrics: dict[str, float | int | str] = {}
    worst = 99.0
    for pair in pairs_for(layout):
        foreground = getattr(tokens, pair.foreground)
        background = getattr(tokens, pair.background)
        ratio = contrast_ratio(foreground, background)
        required = display_min if pair.display else body_min
        metrics[pair.slot] = ratio
        worst = min(worst, ratio)
        if ratio < required:
            findings.append(
                Finding(
                    pair.slot,
                    "low_contrast",
                    f"{pair.foreground} {foreground} on {pair.background} "
                    f"{background} is {ratio:.2f}:1, needs {required:.1f}:1",
                )
            )
    if metrics:
        metrics["worst_ratio"] = round(worst, 3)
    return findings, metrics
