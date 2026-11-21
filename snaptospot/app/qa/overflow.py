"""Overflow gate: DOM ``scrollHeight``/``clientHeight`` per text slot at 1x and 2x.

The composer already fits cards, but fitting happens before images, fonts and
the final CSS are in place. This re-check loads the exact render HTML in the
same browser and compares every text slot against its own box.

Without a browser the gate falls back to the measured AST from composition and
says so. That is a weaker check, never a silent pass.
"""

from __future__ import annotations

from app.qa.provenance import Finding
from app.render.stills import layout_html
from app.schemas.design import DesignSystem, LayoutAST

TEXT_SLOTS = (
    "eyebrow",
    "headline",
    "subhead",
    "cta",
    "quote",
    "stat",
    "tile",
    "footnote",
)

_SLOT_JS = """
() => {
  const rows = {};
  for (const el of document.querySelectorAll('[data-slot]')) {
    rows[el.getAttribute('data-slot')] = {
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    };
  }
  const root = document.documentElement;
  return {
    slots: rows,
    page: {
      scrollWidth: root.scrollWidth,
      clientWidth: root.clientWidth,
      scrollHeight: root.scrollHeight,
      clientHeight: root.clientHeight,
    },
  };
}
"""


def _is_text(slot: str) -> bool:
    return slot.startswith(TEXT_SLOTS)


def _ast_findings(layout: LayoutAST) -> list[Finding]:
    findings: list[Finding] = []
    measured = layout.measured
    if measured.overflow or measured.fit == "overflow":
        findings.append(
            Finding(
                "card",
                "ast_overflow",
                f"composition measured fit={measured.fit} "
                f"at {measured.headline_pt}px",
            )
        )
    for slot, box in measured.boxes.items():
        if not _is_text(slot):
            continue
        if (
            box.x < -0.5
            or box.y < -0.5
            or box.x + box.w > layout.width + 0.5
            or box.y + box.h > layout.height + 0.5
        ):
            findings.append(
                Finding(
                    slot,
                    "outside_canvas",
                    f"{slot} box leaves the {layout.width}x{layout.height} canvas",
                )
            )
    return findings


def check(
    layout: LayoutAST,
    design: DesignSystem,
    *,
    worker: object | None = None,
    scales: tuple[int, ...] = (1, 2),
) -> tuple[str, list[Finding], dict[str, float | int | str]]:
    """Return ``(method, findings, metrics)``."""
    if worker is None:
        findings = _ast_findings(layout)
        return "ast", findings, {"scales": 0, "slots": len(layout.measured.boxes)}

    html = layout_html(layout, design)
    findings: list[Finding] = []
    metrics: dict[str, float | int | str] = {}
    for scale in scales:
        payload = worker.evaluate_document(  # type: ignore[attr-defined]
            html, layout.width, layout.height, _SLOT_JS, scale=scale
        )
        rows = payload.get("slots") if isinstance(payload, dict) else {}
        page = payload.get("page") if isinstance(payload, dict) else {}
        overflow_slots = 0
        for slot, row in (rows or {}).items():
            if not _is_text(slot) or not isinstance(row, dict):
                continue
            overflow_slots += 1
            if int(row.get("scrollWidth", 0)) > int(row.get("clientWidth", 0)) + 1:
                findings.append(
                    Finding(
                        slot,
                        "horizontal_overflow",
                        f"{slot} is {row['scrollWidth']}px wide inside "
                        f"{row['clientWidth']}px at {scale}x",
                    )
                )
            if int(row.get("scrollHeight", 0)) > int(row.get("clientHeight", 0)) + 1:
                findings.append(
                    Finding(
                        slot,
                        "vertical_overflow",
                        f"{slot} is {row['scrollHeight']}px tall inside "
                        f"{row['clientHeight']}px at {scale}x",
                    )
                )
        metrics[f"text_slots@{scale}x"] = overflow_slots
        if isinstance(page, dict):
            if int(page.get("scrollHeight", 0)) > int(page.get("clientHeight", 0)) + 1:
                findings.append(
                    Finding(
                        "page",
                        "page_overflow",
                        f"document is {page['scrollHeight']}px tall in a "
                        f"{page['clientHeight']}px viewport at {scale}x",
                    )
                )
    return "dom", findings, metrics
