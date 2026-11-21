"""Safe-area gate: measured text boxes versus the platform's overlay mask.

Masks live in the platform registry (``PlatformSpec.safe``) as pixels from each
edge. The gate works on the measured AST boxes, so it is exact and needs no
image processing.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.qa.provenance import Finding
from app.schemas.design import Box, LayoutAST, PlatformSpec

# Only text is authoritative. A decorative ring may reach into a mask.
_TEXT_SLOTS = (
    "eyebrow",
    "headline",
    "subhead",
    "cta",
    "quote",
    "stat",
    "tile",
    "footnote",
)


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


def mask_rects(
    width: int, height: int, safe: dict[str, int]
) -> list[tuple[str, Rect]]:
    rects: list[tuple[str, Rect]] = []
    top = int(safe.get("top", 0) or 0)
    bottom = int(safe.get("bottom", 0) or 0)
    left = int(safe.get("left", 0) or 0)
    right = int(safe.get("right", 0) or 0)
    if top > 0:
        rects.append(("top", Rect(0, 0, width, top)))
    if bottom > 0:
        rects.append(("bottom", Rect(0, height - bottom, width, bottom)))
    if left > 0:
        rects.append(("left", Rect(0, 0, left, height)))
    if right > 0:
        rects.append(("right", Rect(width - right, 0, right, height)))
    return rects


def _intersection(first: Rect, second: Rect) -> tuple[float, float]:
    x = max(first.x, second.x)
    y = max(first.y, second.y)
    right = min(first.x + first.w, second.x + second.w)
    bottom = min(first.y + first.h, second.y + second.h)
    return max(0.0, right - x), max(0.0, bottom - y)


def _is_text(slot: str) -> bool:
    return slot.startswith(_TEXT_SLOTS)


def check(
    layout: LayoutAST,
    spec: PlatformSpec,
    *,
    tolerance: float = 0.5,
) -> tuple[list[Finding], dict[str, float | int | str]]:
    safe = {key: int(value) for key, value in (spec.safe or {}).items()}
    metrics: dict[str, float | int | str] = {"mask_edges": len(safe)}
    if not safe:
        return [], metrics

    masks = mask_rects(layout.width, layout.height, safe)
    findings: list[Finding] = []
    checked = 0
    for slot, box in layout.measured.boxes.items():
        if not _is_text(slot):
            continue
        checked += 1
        measured = Rect(box.x, box.y, box.w, box.h)
        for edge, mask in masks:
            overlap_w, overlap_h = _intersection(measured, mask)
            if overlap_w > tolerance and overlap_h > tolerance:
                findings.append(
                    Finding(
                        slot,
                        "safe_area",
                        f"{slot} overlaps the {edge} mask by "
                        f"{overlap_w:.1f}x{overlap_h:.1f}px",
                    )
                )
    metrics["text_boxes"] = checked
    return findings, metrics


def within_canvas(layout: LayoutAST, *, tolerance: float = 0.5) -> list[Finding]:
    findings: list[Finding] = []
    for slot, box in layout.measured.boxes.items():
        if not _is_text(slot):
            continue
        if (
            box.x < -tolerance
            or box.y < -tolerance
            or box.x + box.w > layout.width + tolerance
            or box.y + box.h > layout.height + tolerance
        ):
            findings.append(
                Finding(
                    slot,
                    "outside_canvas",
                    f"{slot} box {box.x:.0f},{box.y:.0f} "
                    f"{box.w:.0f}x{box.h:.0f} leaves the "
                    f"{layout.width}x{layout.height} canvas",
                )
            )
    return findings


def box_of(layout: LayoutAST, slot: str) -> Box | None:
    return layout.measured.boxes.get(slot)
