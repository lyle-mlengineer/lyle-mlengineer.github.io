"""Alt text from the layout tree, never from a screenshot.

The AST already knows every visible string, so the description can be complete
by construction. A spatial hint is allowed only when the measured boxes agree
with it; otherwise it is dropped and reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.compose.layouts import CARD_ASSETS, CARD_LABELS
from app.schemas.design import LayoutAST, LayoutSlots
from app.schemas.profile import SiteProfile

_CARD_BY_ASSET = {name: card for card, name in CARD_ASSETS.items()}

_SLOT_LABEL = {
    "eyebrow": "eyebrow",
    "headline": "headline",
    "subhead": "subheading",
    "portrait": "portrait",
    "cta": "call to action",
    "qr": "QR code",
}


@dataclass
class AltResult:
    asset: str
    text: str
    warnings: list[str] = field(default_factory=list)


def _unit(value: str, unit: str | None) -> str:
    if not unit:
        return value
    if unit in {"%", "‰", "°", "×"} or unit.startswith("/"):
        return f"{value}{unit}"
    return f"{value} {unit}"


def visible_strings(slots: LayoutSlots) -> list[str]:
    """Every string the card template actually renders, in reading order."""
    strings: list[str] = []
    if slots.eyebrow:
        strings.append(slots.eyebrow)
    strings.extend(part.text for part in slots.headline if part.text)
    if slots.subhead:
        strings.append(slots.subhead)
    for tile in slots.tiles:
        strings.append(tile.title)
        if tile.blurb:
            strings.append(tile.blurb)
        if tile.badge:
            strings.append(tile.badge)
        if tile.alt:
            strings.append(tile.alt)
    for stat in slots.stats:
        strings.append(_unit(stat.value, stat.unit))
        if stat.label:
            strings.append(stat.label)
        if stat.as_of:
            strings.append(f"as of {stat.as_of}")
    if slots.quote:
        strings.append(slots.quote.text)
        if slots.quote.attribution:
            strings.append(slots.quote.attribution)
        if slots.quote.role:
            strings.append(slots.quote.role)
    for media in slots.media:
        if media.alt:
            strings.append(media.alt)
    if slots.cta:
        strings.append(slots.cta.label)
        strings.append(slots.cta.url)
    if slots.qr:
        strings.append(slots.qr.url)
    # ``tools`` and ``footnotes`` are in the model but not rendered by the
    # card template, so they are deliberately absent from alt text.
    return strings


def slot_position(layout: LayoutAST, slot: str) -> str | None:
    """Describe where a measured slot sits, relative to the canvas."""
    box = layout.measured.boxes.get(slot)
    if box is None:
        return None
    centre_x = box.x + box.w / 2
    centre_y = box.y + box.h / 2
    if centre_x < layout.width / 3:
        horizontal = "left"
    elif centre_x > layout.width * 2 / 3:
        horizontal = "right"
    else:
        horizontal = "middle"
    if centre_y < layout.height * 0.4:
        vertical = "top"
    elif centre_y > layout.height * 0.6:
        vertical = "bottom"
    else:
        vertical = "middle"
    if horizontal == "middle" and vertical == "middle":
        return "center"
    if horizontal == "middle":
        return vertical
    if vertical == "middle":
        return horizontal
    return f"{vertical} {horizontal}"


def hint_matches(position: str | None, hint: str) -> bool:
    if not position:
        return False
    normalised = position.casefold()
    words = hint.casefold().replace("_", " ").replace("-", " ").split()
    words = ["middle" if word == "center" else word for word in words]
    return bool(words) and all(word in normalised.split() for word in words)


def _who(layout: LayoutAST, profile: SiteProfile | None) -> str:
    if profile is not None:
        return (
            profile.entities.person.name
            or profile.entities.org.name
            or profile.title
            or "this portfolio"
        )
    return "this portfolio"


def _card_label(layout: LayoutAST) -> str:
    card = _CARD_BY_ASSET.get(layout.asset.split("/", 1)[-1])
    return CARD_LABELS.get(card, "campaign") if card else "campaign"


def _sentence(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[-1] not in ".!?":
        value += "."
    return value


def build_alt_text(
    layout: LayoutAST,
    *,
    profile: SiteProfile | None = None,
    hints: dict[str, str] | None = None,
) -> AltResult:
    """Describe every string in the AST, plus only verified spatial hints."""
    slots = layout.slots
    who = _who(layout, profile)
    parts: list[str] = [
        f"{layout.direction.replace('_', ' ').title()} {_card_label(layout)} "
        f"card for {who}."
    ]

    if slots.eyebrow:
        parts.append(f"Eyebrow: {slots.eyebrow}.")
    headline = " ".join(part.text for part in slots.headline if part.text)
    if headline:
        parts.append(_sentence(f"Headline: {headline}"))
    if slots.subhead:
        parts.append(_sentence(slots.subhead))

    if slots.tiles:
        tiles = []
        for tile in slots.tiles:
            detail = tile.title
            if tile.blurb:
                detail += f": {tile.blurb}"
            if tile.badge:
                detail += f" ({tile.badge})"
            if tile.alt:
                detail += f", image: {tile.alt}"
            tiles.append(detail)
        parts.append("Tiles: " + "; ".join(tiles) + ".")

    if slots.stats:
        stats = []
        for stat in slots.stats:
            detail = f"{_unit(stat.value, stat.unit)} {stat.label}".strip()
            if stat.as_of:
                detail += f" as of {stat.as_of}"
            stats.append(detail)
        parts.append("Statistics: " + "; ".join(stats) + ".")

    if slots.quote:
        quote = f'Quote: "{slots.quote.text}"'
        if slots.quote.attribution:
            quote += f" - {slots.quote.attribution}"
        if slots.quote.role:
            quote += f", {slots.quote.role}"
        parts.append(quote + ".")

    for media in slots.media:
        description = media.alt or media.role.replace("_", " ")
        parts.append(f"Image: {description}.")

    if slots.cta:
        parts.append(f"Call to action: {slots.cta.label} at {slots.cta.url}.")
    if slots.qr:
        parts.append(f"QR code for {slots.qr.url}.")

    warnings: list[str] = []
    for slot, hint in (hints or {}).items():
        position = slot_position(layout, slot)
        if hint_matches(position, hint):
            label = _SLOT_LABEL.get(slot, slot.replace("-", " "))
            parts.append(f"The {label} is at the {position}.")
        else:
            warnings.append(
                f"spatial hint for {slot!r} ({hint}) does not match the layout "
                f"({position or 'unmeasured'}); dropped"
            )

    return AltResult(asset=layout.asset, text=" ".join(parts), warnings=warnings)


def build_alts(
    layouts: list[LayoutAST],
    *,
    profile: SiteProfile | None = None,
    hints: dict[str, dict[str, str]] | None = None,
) -> list[AltResult]:
    """Alt text for a set of layouts, keyed by asset name for the manifest."""
    results: list[AltResult] = []
    for layout in layouts:
        results.append(
            build_alt_text(
                layout,
                profile=profile,
                hints=(hints or {}).get(layout.asset),
            )
        )
    return results
