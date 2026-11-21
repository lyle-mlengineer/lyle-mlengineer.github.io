"""Platform-spec gate: the file must be the size, ratio and format the registry says."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.qa.provenance import Finding
from app.schemas.design import LayoutAST, PlatformSpec, Ratio

_EXPECTED_RATIO: dict[Ratio, float] = {
    "1:1": 1.0,
    "4:5": 4 / 5,
    "9:16": 9 / 16,
    "16:9": 16 / 9,
}


def check(
    layout: LayoutAST,
    spec: PlatformSpec,
    path: Path,
    *,
    ratio_tolerance: float = 0.02,
) -> tuple[list[Finding], dict[str, float | int | str]]:
    findings: list[Finding] = []
    metrics: dict[str, float | int | str] = {
        "expected_width": spec.size[0],
        "expected_height": spec.size[1],
    }
    if (layout.width, layout.height) != spec.size:
        findings.append(
            Finding(
                "canvas",
                "wrong_canvas",
                f"AST is {layout.width}x{layout.height}, registry says "
                f"{spec.size[0]}x{spec.size[1]}",
            )
        )
    if layout.spec != spec.id and layout.spec.split("_")[0] != spec.platform:
        findings.append(
            Finding(
                "spec",
                "wrong_spec",
                f"AST says spec {layout.spec!r}, expected {spec.id!r}",
            )
        )
    expected_ratio = _EXPECTED_RATIO[spec.ratio]
    actual_ratio = layout.width / layout.height if layout.height else 0.0
    if abs(actual_ratio - expected_ratio) > ratio_tolerance:
        findings.append(
            Finding(
                "ratio",
                "wrong_ratio",
                f"canvas ratio {actual_ratio:.3f} is not {spec.ratio}",
            )
        )

    if not path.exists():
        findings.append(Finding("file", "missing_file", str(path)))
        return findings, metrics

    with Image.open(path) as image:
        metrics["width"] = image.width
        metrics["height"] = image.height
        metrics["format"] = image.format or "unknown"
        if image.format != "PNG":
            findings.append(
                Finding("file", "wrong_format", f"expected PNG, got {image.format}")
            )
        if (image.width, image.height) != spec.size:
            findings.append(
                Finding(
                    "file",
                    "wrong_size",
                    f"PNG is {image.width}x{image.height}, "
                    f"expected {spec.size[0]}x{spec.size[1]}",
                )
            )
    return findings, metrics
