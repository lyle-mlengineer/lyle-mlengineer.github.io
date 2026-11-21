"""Build typed slots from the content model.

No value is typed here. Every number, badge and quote is copied from an accepted
fact with tier A or B, and keeps that fact's id. Copy that could introduce a
digit is rejected before it reaches a slot.
"""

import io
import math
import re
from datetime import date
from functools import lru_cache

from app.compose.layouts import CARD_ASSETS, plan_for
from app.design.platforms import ratio_class
from app.design.tokens import portrait_for
from app.schemas.content import ContentModel, Fact
from app.schemas.design import (
    CTASlot,
    DesignSystem,
    HeadlinePart,
    LayoutSlots,
    MediaSlot,
    PlatformSpec,
    QRSlot,
    QuoteSlot,
    StatSlot,
    TileSlot,
)
from app.schemas.profile import ImageAsset, SiteProfile

_WHITESPACE = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_ALLOWED_PERMISSIONS = {"published_on_site", "attested", "brand_document"}


def _clean(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def humanize_key(key: str) -> str:
    return key.replace(".", " ").replace("_", " ").strip().capitalize()


def renderable(fact: Fact, *, today: date | None = None) -> bool:
    """Tier A/B only, and an old metric without an as-of date cannot render."""
    if fact.tier not in {"A", "B"}:
        return False
    if fact.published_at is not None and not fact.as_of:
        age = ((today or date.today()) - fact.published_at).days
        if age > 90:
            return False
    return True


def headline_parts(text: str, *, max_parts: int = 2) -> list[HeadlinePart]:
    cleaned = _clean(text)
    if not cleaned:
        return []
    parts = [part for part in _SENTENCE.split(cleaned) if part]
    if len(parts) > max_parts:
        parts = [parts[0], " ".join(parts[1:])]
    return [HeadlinePart(text=part, emphasis="last_word") for part in parts]


def badge_text(fact: Fact) -> str:
    value = _clean(fact.value)
    if fact.unit and not value.casefold().endswith(fact.unit.casefold()):
        value = f"{value} {fact.unit}"
    return value


@lru_cache(maxsize=32)
def qr_svg(url: str) -> str | None:
    """Generate a deterministic local QR SVG. No external service is called."""
    try:
        import segno
    except ImportError:  # pragma: no cover - dependency is declared
        return None
    buffer = io.BytesIO()
    qr = segno.make(url, error="m", micro=False)
    qr.save(
        buffer,
        kind="svg",
        scale=4,
        border=1,
        dark="#000000",
        light="#ffffff",
        xmldecl=False,
        svgclass=None,
        lineclass=None,
    )
    return buffer.getvalue().decode()


def _media_slot(image: ImageAsset | None, treatment: str = "screenshot") -> MediaSlot | None:
    if image is None:
        return None
    return MediaSlot(
        asset_id=image.asset_id,
        url=image.url,
        role=image.role,
        alt=image.alt,
        object_position="50% 50%" if treatment == "screenshot" else "50% 22%",
        treatment=treatment,
    )


def _project_image(project_image: str | None, profile: SiteProfile) -> ImageAsset | None:
    if not project_image:
        return None
    if project_image.startswith(("http://", "https://", "data:")):
        return ImageAsset(
            asset_id=project_image,
            url=project_image,
            role="product_shot",
            alt="Project screenshot",
        )
    return next(
        (image for image in profile.images if image.asset_id == project_image),
        None,
    )


def _tiles(
    card: str,
    density: int,
    model: ContentModel,
    profile: SiteProfile,
    facts: dict[str, Fact],
) -> list[TileSlot]:
    if card == "capabilities":
        tiles: list[TileSlot] = []
        for offering in model.offerings[:density]:
            metric = facts.get(offering.metric_fact_id or "")
            tiles.append(
                TileSlot(
                    title=_clean(offering.title),
                    blurb=_clean(offering.one_liner),
                    badge=badge_text(metric) if metric is not None else None,
                    badge_fact_id=metric.id if metric is not None else None,
                    badge_tier=metric.tier if metric is not None else None,  # type: ignore[arg-type]
                    tools=offering.tools,
                )
            )
        return tiles
    if card == "projects":
        tiles = []
        for project in model.projects[:density]:
            image = _project_image(project.image, profile)
            badge = facts.get(project.badge_fact_id or "")
            tiles.append(
                TileSlot(
                    title=_clean(project.name),
                    blurb=_clean(project.blurb),
                    image=image.url if image else None,
                    alt=image.alt if image and image.alt else project.name,
                    badge=badge_text(badge) if badge is not None else None,
                    badge_fact_id=badge.id if badge is not None else None,
                    badge_tier=badge.tier if badge is not None else None,  # type: ignore[arg-type]
                )
            )
        return tiles
    return []


def _stats(model: ContentModel, facts: dict[str, Fact]) -> list[StatSlot]:
    stats: list[StatSlot] = []
    for proof in model.proof:
        fact = facts.get(proof.fact_id)
        if fact is None:
            continue
        stats.append(
            StatSlot(
                value=_clean(fact.value),
                unit=fact.unit,
                label=_clean(fact.label) or humanize_key(fact.key),
                as_of=fact.as_of,
                fact_id=fact.id,
                tier=fact.tier,  # type: ignore[arg-type]
                source=fact.source,
            )
        )
    return stats


def _quote(model: ContentModel, facts: dict[str, Fact]) -> QuoteSlot | None:
    if model.quote is None:
        return None
    fact = facts.get(model.quote.fact_id)
    if fact is None or fact.permission not in _ALLOWED_PERMISSIONS:
        return None
    return QuoteSlot(
        text=_clean(fact.value),
        attribution=_clean(model.quote.attribution or "") or None,
        role=_clean(model.quote.role or "") or None,
        fact_id=fact.id,
        tier=fact.tier,  # type: ignore[arg-type]
        source=fact.source,
    )


def build_slots(
    card: str,
    density: int,
    model: ContentModel,
    profile: SiteProfile,
    design: DesignSystem,
    spec: PlatformSpec,
    *,
    today: date | None = None,
) -> LayoutSlots:
    facts = {
        fact.id: fact for fact in model.facts if renderable(fact, today=today)
    }
    role = profile.entities.person.role or profile.entities.org.name or "Portfolio"
    eyebrow = {
        "hero": role,
        "capabilities": "What I build",
        "projects": "Selected work",
        "proof": "Proof",
    }[card]
    headline = {
        "hero": model.thesis,
        "capabilities": "Capabilities with evidence.",
        "projects": "Work that speaks for itself.",
        "proof": "Proof, not promises.",
    }[card]
    subhead = {
        "hero": model.audience,
        "capabilities": model.thesis,
        "projects": model.audience or model.thesis,
        "proof": "Every number carries a source.",
    }[card]

    slots = LayoutSlots(
        eyebrow=eyebrow,
        headline=headline_parts(headline),
        subhead=_clean(subhead),
        tiles=_tiles(card, density, model, profile, facts),
        cta=CTASlot(url=model.cta.url, label=model.cta.label),
        footnotes=model.disclaimers,
    )
    if card == "hero":
        portrait = portrait_for(profile)
        media = _media_slot(portrait, "portrait")
        if media is not None:
            media = media.model_copy(
                update={"object_position": design.portrait_treatment.object_position}
            )
            slots.media = [media]
    if card == "proof":
        slots.stats = _stats(model, facts)[:density]
        slots.quote = _quote(model, facts)
        svg = qr_svg(model.cta.url)
        slots.qr = QRSlot(url=model.cta.url, svg=svg)
    return slots


def grid_shape(card: str, template: str, density: int) -> tuple[int, int]:
    if card == "capabilities":
        if template.endswith("columns"):
            return max(1, density), 1
        if template.endswith("rows"):
            return 1, max(1, density)
        return 2, max(1, math.ceil(density / 2))
    if card == "projects":
        if template.endswith("wide"):
            columns = {8: 4, 6: 3, 4: 4, 2: 2}.get(density, 4)
        else:
            columns = 2 if density > 1 else 1
        return columns, max(1, math.ceil(density / columns))
    return 2, 2


def build_context(
    card: str,
    density: int,
    model: ContentModel,
    profile: SiteProfile,
    design: DesignSystem,
    spec: PlatformSpec,
    *,
    today: date | None = None,
) -> dict[str, object]:
    plan = plan_for(spec, card)
    slots = build_slots(
        card, density, model, profile, design, spec, today=today
    )
    columns, rows = grid_shape(card, plan.template, density)
    return {
        "width": spec.size[0],
        "height": spec.size[1],
        "ratio_class": ratio_class(spec.ratio),
        "template": plan.template,
        "tokens": design.tokens.model_dump(mode="json"),
        "portrait_treatment": design.portrait_treatment.model_dump(mode="json"),
        "media_treatment": design.media_treatment.model_dump(mode="json"),
        "slots": slots.model_dump(mode="json"),
        "cols": columns,
        "rows": rows,
        "safe": spec.safe,
    }


def alt_text(
    card: str,
    slots: LayoutSlots,
    design: DesignSystem,
    profile: SiteProfile,
) -> str:
    who = profile.entities.person.name or profile.title or "This portfolio"
    if card == "hero":
        portrait = " A portrait is on the card." if slots.media else ""
        return f"{design.label} announcement card for {who}. {slots.subhead}.{portrait}".strip()
    if card == "capabilities":
        names = ", ".join(tile.title for tile in slots.tiles)
        return f"{design.label} capability card for {who}: {names}."
    if card == "projects":
        names = ", ".join(tile.title for tile in slots.tiles)
        return f"{design.label} selected-work card for {who}, showing {names}."
    values = "; ".join(
        f"{stat.value}{' ' + stat.unit if stat.unit else ''} {stat.label}"
        for stat in slots.stats
    )
    quote = f' Quote: "{slots.quote.text}"' if slots.quote else ""
    return f"{design.label} proof card for {who}: {values}.{quote}".strip()


def asset_name(spec: PlatformSpec, card: str) -> str:
    return f"{spec.platform}/{CARD_ASSETS[card]}"  # type: ignore[index]
