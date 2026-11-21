"""Duplicate detection: a 64-bit perceptual hash across the whole kit.

Two cards that are more than 90% similar are almost always the same layout with
the same copy, which means the kit would post the same image twice.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.qa.provenance import Finding

HASH_SIZE = 8


def dhash(image: Image.Image, size: int = HASH_SIZE) -> int:
    """Difference hash: 1 when a pixel is brighter than its right neighbour."""
    small = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    width = size + 1
    for row in range(size):
        offset = row * width
        for column in range(size):
            bits = (bits << 1) | (
                1 if pixels[offset + column] > pixels[offset + column + 1] else 0
            )
    return bits


def similarity(first: int, second: int, *, bits: int = HASH_SIZE * HASH_SIZE) -> float:
    return 1.0 - (first ^ second).bit_count() / bits


def hashes(paths: list[tuple[str, Path]]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for asset, path in paths:
        with Image.open(path) as image:
            rows[asset] = dhash(image)
    return rows


def check(
    items: list[tuple[str, Path]],
    *,
    threshold: float = 0.9,
) -> tuple[list[Finding], dict[str, float | int | str]]:
    computed = hashes(items)
    names = list(computed)
    findings: list[Finding] = []
    worst = 0.0
    pairs = 0
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            pairs += 1
            score = similarity(computed[first], computed[second])
            worst = max(worst, score)
            if score > threshold:
                findings.append(
                    Finding(
                        first,
                        "duplicate",
                        f"{first} and {second} are {score:.3f} similar "
                        f"(limit {threshold:.2f})",
                    )
                )
    return findings, {"pairs": pairs, "worst_similarity": round(worst, 3)}
