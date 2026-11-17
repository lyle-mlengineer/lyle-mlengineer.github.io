"""Turn a site's brand into a deterministic design system.

Colour work happens in OKLab, not RGB. The site's own palette seeds the accent:
near-black, near-white and grey clusters are dropped, then the highest area ×
chroma cluster wins if it reaches 4.5:1 against the direction's background. When
it does not, the direction's stock accent is used instead of shipping an
unreadable brand colour.
"""

import colorsys
import hashlib
import json
import math
import re
from typing import Any

from app.design.directions import DIRECTIONS, direction_for
from app.schemas.design import (
    DesignSystem,
    DesignTokens,
    Direction,
    MediaTreatment,
    PortraitTreatment,
)
from app.schemas.profile import FontToken, ImageAsset, SiteProfile

_HEX = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$", re.IGNORECASE)
_MIN_CONTRAST = 4.5

# Families that are expected to exist on the supported render machines. A brand
# family outside this list is not silently loaded over the network; the
# direction's pinned family is the fallback.
_PINNED_FAMILIES = {
    "bahnschrift",
    "segoe ui",
    "consolas",
    "arial",
    "arial narrow",
    "helvetica",
    "helvetica neue",
    "georgia",
    "times new roman",
    "courier new",
    "inter",
    "ibm plex mono",
    "jetbrains mono",
    "iowan old style",
    "sf pro",
    "system-ui",
}


def parse_hex(value: str) -> tuple[int, int, int] | None:
    match = _HEX.match(value.strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    return tuple(int(digits[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(channel))):02x}" for channel in rgb)


def _linear(channel: int | float) -> float:
    value = channel / 255 if channel > 1 else channel
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_value: str) -> float:
    parsed = parse_hex(hex_value)
    if parsed is None:
        return 0.0
    r, g, b = (_linear(channel) for channel in parsed)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    first = relative_luminance(fg)
    second = relative_luminance(bg)
    high, low = max(first, second), min(first, second)
    return round((high + 0.05) / (low + 0.05), 3)


def rgb_to_oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_linear(channel) for channel in rgb)
    long_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    medium = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    short = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (
        math.copysign(abs(value) ** (1 / 3), value)
        for value in (long_, medium, short)
    )
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklch(hex_value: str) -> tuple[float, float, float]:
    parsed = parse_hex(hex_value)
    if parsed is None:
        return (0.0, 0.0, 0.0)
    lightness, a, b = rgb_to_oklab(parsed)
    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a)) % 360
    return lightness, chroma, hue


def mix(first: str, second: str, amount: float) -> str:
    """Linear-ish blend in sRGB, clamped to a valid hex value."""
    left = parse_hex(first) or (0, 0, 0)
    right = parse_hex(second) or (255, 255, 255)
    amount = max(0.0, min(1.0, amount))
    return to_hex(tuple(left[i] * (1 - amount) + right[i] * amount for i in range(3)))


def _hue_shift(hex_value: str, degrees: float, *, lightness: float | None = None) -> str:
    parsed = parse_hex(hex_value)
    if parsed is None:
        return hex_value
    r, g, b = (channel / 255 for channel in parsed)
    hue, lightness_value, saturation = colorsys.rgb_to_hls(r, g, b)
    hue = ((hue * 360 + degrees) % 360) / 360
    if lightness is not None:
        lightness_value = max(0.0, min(1.0, lightness))
    return to_hex(
        tuple(
            channel * 255
            for channel in colorsys.hls_to_rgb(hue, lightness_value, saturation)
        )
    )


def _accent_from_brand(profile: SiteProfile, background: str) -> tuple[str, str]:
    candidates: list[tuple[float, str]] = []
    for color in profile.brand.colors:
        parsed = parse_hex(color.hex)
        if parsed is None:
            continue
        lightness, chroma, _ = oklch(color.hex)
        if lightness < 0.16 or lightness > 0.92 or chroma < 0.035:
            continue
        area = max(0.0, min(1.0, color.area if color.area is not None else 0.01))
        candidates.append((area * chroma, color.hex.strip()))
    for _, candidate in sorted(candidates, reverse=True):
        if contrast_ratio(candidate, background) >= _MIN_CONTRAST:
            return candidate, "site"
    return "", "direction"


def _font_family(token: FontToken | None, fallback: str) -> str:
    if token is None:
        return fallback
    family = token.family.strip()
    if family.casefold() in _PINNED_FAMILIES:
        return family
    return fallback


def _fonts(profile: SiteProfile, tokens: DesignTokens) -> tuple[str, str, str]:
    display_token = next(
        (font for font in profile.brand.fonts if font.role == "display"), None
    )
    body_token = next((font for font in profile.brand.fonts if font.role == "body"), None)
    if body_token is None and profile.brand.fonts:
        body_token = profile.brand.fonts[0]
    return (
        _font_family(display_token, tokens.font_display),
        _font_family(body_token, tokens.font_body),
        tokens.font_mono,
    )


def _portrait(profile: SiteProfile, accent: str, accent_soft: str) -> PortraitTreatment:
    portrait = next(
        (image for image in profile.images if image.role == "portrait"), None
    )
    position = "50% 22%"
    crop = "face_center_upper"
    if portrait is not None and portrait.face_bbox and len(portrait.face_bbox) == 4:
        x, y, width, height = portrait.face_bbox
        center_x = max(0.0, min(1.0, x + width / 2))
        center_y = max(0.0, min(1.0, y + height / 2))
        position = f"{center_x * 100:.0f}% {max(8, center_y * 100 - 6):.0f}%"
        crop = "face_center_upper"
    return PortraitTreatment(
        ring="conic",
        ring_colors=[accent, accent_soft, _hue_shift(accent, 38, lightness=0.72)],
        crop=crop,
        glow=0.18,
        object_position=position,
        grade="grayscale_to_warm",
    )


def _tokens_for(profile: SiteProfile, direction: Direction) -> DesignTokens:
    stock = DIRECTIONS[direction][1]
    accent, source = _accent_from_brand(profile, stock.bg)
    if not accent:
        accent = stock.accent
    dark = relative_luminance(stock.bg) < 0.2
    accent_soft = mix(accent, "#ffffff", 0.42 if dark else 0.72)
    display, body, mono = _fonts(profile, stock)
    return stock.model_copy(
        update={
            "accent": accent,
            "accent_soft": accent_soft,
            "font_display": display,
            "font_body": body,
            "font_mono": mono,
            "accent_source": source,
            # Keep the button readable even when the sampled accent is light.
            "text_on_accent": (
                "#111111"
                if contrast_ratio("#111111", accent) >= contrast_ratio("#ffffff", accent)
                else "#ffffff"
            ),
        }
    )


def design_system_hash(system: DesignSystem) -> str:
    payload: dict[str, Any] = system.model_dump(mode="json", exclude={"hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_design_system(
    profile: SiteProfile,
    direction: Direction | str = "auto",
    *,
    persisted: dict[str, Any] | None = None,
) -> DesignSystem:
    """Return the pinned design system for this site and direction.

    An ``auto`` request reuses a persisted system, which keeps a second run
    months later visually identical. An explicit different direction rebuilds.
    """
    if persisted:
        try:
            existing = DesignSystem.model_validate(persisted)
        except ValueError:
            existing = None
        if existing is not None and direction in {"auto", existing.direction}:
            if not existing.hash:
                existing = existing.model_copy(update={"hash": design_system_hash(existing)})
            return existing

    chosen: Direction = direction_for(profile) if direction == "auto" else direction  # type: ignore[assignment]
    tokens = _tokens_for(profile, chosen)
    system = DesignSystem(
        direction=chosen,
        label=DIRECTIONS[chosen][0],
        tokens=tokens,
        portrait_treatment=_portrait(profile, tokens.accent, tokens.accent_soft),
        media_treatment=MediaTreatment(),
        version=1,
    )
    return system.model_copy(update={"hash": design_system_hash(system)})


def portrait_for(profile: SiteProfile) -> ImageAsset | None:
    return next((image for image in profile.images if image.role == "portrait"), None)
