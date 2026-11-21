"""Brand drift: compare a token with the colour that actually rendered.

The check paints one solid swatch per hex token, captures it through the same
Chromium pipeline as the cards, samples the centre pixel, and reports the CIEDE2000
difference. Anything above 2 means the render no longer matches the design system
(colour profile, theme override, a stale stylesheet).
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

from PIL import Image

from app.design.tokens import parse_hex
from app.qa.provenance import Finding
from app.schemas.design import DesignSystem

SWATCH = 48
# ``line`` and ``shadow`` are rgba/box-shadow values, not flat fills.
_FLAT_TOKENS = (
    "bg",
    "bg_alt",
    "surface",
    "paper",
    "muted",
    "muted_2",
    "accent",
    "accent_soft",
    "text_on_accent",
)


@dataclass(frozen=True)
class Swatch:
    name: str
    hex: str


def swatches(design: DesignSystem) -> list[Swatch]:
    tokens = design.tokens
    rows: list[Swatch] = []
    for name in _FLAT_TOKENS:
        value = getattr(tokens, name)
        if parse_hex(value) is None:
            continue
        rows.append(Swatch(name, value))
    return rows


def swatch_html(rows: list[Swatch]) -> str:
    cells = "".join(
        f'<div style="width:{SWATCH}px;height:{SWATCH}px;background:{row.hex}"></div>'
        for row in rows
    )
    width = SWATCH * len(rows)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<style>html,body{{margin:0;padding:0;background:#000;}}"
        f".row{{display:flex;width:{width}px;height:{SWATCH}px}}</style></head>"
        f"<body><div class=\"row\">{cells}</div></body></html>"
    )


def sample_swatches(png: bytes, rows: list[Swatch]) -> dict[str, tuple[int, int, int]]:
    with Image.open(io.BytesIO(png)) as source:
        image = source.convert("RGB")
        samples: dict[str, tuple[int, int, int]] = {}
        for index, row in enumerate(rows):
            x = min(image.width - 1, index * SWATCH + SWATCH // 2)
            y = min(image.height - 1, SWATCH // 2)
            samples[row.name] = image.getpixel((x, y))  # type: ignore[assignment]
        return samples


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(channel) for channel in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(value: float) -> float:
        return value ** (1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e_2000(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> float:
    """CIEDE2000 colour difference between two Lab triples."""
    l1, a1, b1 = first
    l2, a2, b2 = second
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7))) if c_bar else 0.0
    a1p = (1 + g) * a1
    a2p = (1 + g) * a2
    c1p = math.hypot(a1p, b1)
    c2p = math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0

    dl = l2 - l1
    dc = c2p - c1p
    if c1p * c2p == 0:
        dh = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
    dh_arc = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh) / 2)

    l_bar = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar = (h1p + h2p + 360) / 2
    else:
        h_bar = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    delta_theta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    rc = 2 * math.sqrt(c_bar_p**7 / (c_bar_p**7 + 25**7)) if c_bar_p else 0.0
    sl = 1 + (0.015 * (l_bar - 50) ** 2) / math.sqrt(20 + (l_bar - 50) ** 2)
    sc = 1 + 0.045 * c_bar_p
    sh = 1 + 0.015 * c_bar_p * t
    rt = -math.sin(math.radians(2 * delta_theta)) * rc

    return math.sqrt(
        (dl / sl) ** 2
        + (dc / sc) ** 2
        + (dh_arc / sh) ** 2
        + rt * (dc / sc) * (dh_arc / sh)
    )


def compare(
    rows: list[Swatch],
    samples: dict[str, tuple[int, int, int]],
    *,
    max_delta: float = 2.0,
) -> tuple[list[Finding], dict[str, float | int | str]]:
    findings: list[Finding] = []
    metrics: dict[str, float | int | str] = {}
    worst = 0.0
    for row in rows:
        sample = samples.get(row.name)
        token = parse_hex(row.hex)
        if sample is None or token is None:
            continue
        delta = delta_e_2000(rgb_to_lab(token), rgb_to_lab(sample))
        metrics[row.name] = round(delta, 3)
        worst = max(worst, delta)
        if delta > max_delta:
            findings.append(
                Finding(
                    row.name,
                    "brand_drift",
                    f"{row.hex} rendered as #{sample[0]:02x}{sample[1]:02x}{sample[2]:02x} "
                    f"(dE {delta:.2f} > {max_delta:.1f})",
                )
            )
    metrics["worst_delta_e"] = round(worst, 3)
    return findings, metrics


def check(
    design: DesignSystem,
    *,
    worker: object | None = None,
    max_delta: float = 2.0,
) -> tuple[str, list[Finding], dict[str, float | int | str]]:
    rows = swatches(design)
    if not rows:
        return "skipped", [], {"swatches": 0}
    if worker is None:
        return "skipped", [], {"swatches": len(rows), "reason": "no browser"}
    html = swatch_html(rows)
    captured = worker.capture(html, SWATCH * len(rows), SWATCH)  # type: ignore[attr-defined]
    samples = sample_swatches(captured.data, rows)
    findings, metrics = compare(rows, samples, max_delta=max_delta)
    metrics["swatches"] = len(rows)
    return "browser", findings, metrics
