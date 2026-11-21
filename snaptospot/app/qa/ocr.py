"""OCR cross-check: PaddleOCR when installed, Tesseract as the fallback.

The AST is the source of truth. OCR only catches rendering bugs: a glyph that
did not paint, a clipped line, a dropped number. When neither engine is
available the gate is reported as ``skip`` with the install command, never as a
pass.
"""

from __future__ import annotations

import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

from app.qa.provenance import Finding

_TOKEN = re.compile(r"[a-z0-9]+")


class Engine(Protocol):
    name: str

    def extract(self, image: Image.Image) -> str: ...


@dataclass(frozen=True)
class OcrCheck:
    engine: str
    expected_tokens: int
    matched_tokens: int
    missing_numbers: tuple[str, ...]
    text: str = ""

    @property
    def token_match(self) -> float:
        if self.expected_tokens == 0:
            return 1.0
        return self.matched_tokens / self.expected_tokens


class PaddleEngine:
    name = "paddleocr"

    def __init__(self) -> None:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]

        try:
            self._ocr = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
        except (TypeError, ValueError):
            # PaddleOCR 3.x renamed several constructor arguments.
            self._ocr = PaddleOCR(lang="en")

    def extract(self, image: Image.Image) -> str:
        import numpy as np

        result = self._ocr.ocr(np.array(image.convert("RGB")), cls=False)
        lines: list[str] = []
        for page in result or []:
            for row in page or []:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    value = row[1]
                    if isinstance(value, (list, tuple)) and value:
                        lines.append(str(value[0]))
        return "\n".join(lines)


class TesseractEngine:
    name = "tesseract"

    def extract(self, image: Image.Image) -> str:
        import pytesseract  # type: ignore[import-not-found]

        return str(pytesseract.image_to_string(image))


def detect_engine(*, enabled: bool = True) -> Engine | None:
    if not enabled:
        return None
    try:
        return PaddleEngine()
    except Exception:  # noqa: BLE001 - optional dependency
        pass
    if shutil.which("tesseract") is None:
        return None
    try:
        return TesseractEngine()
    except Exception:  # noqa: BLE001 - optional dependency
        return None


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def _normalise_numbers(text: str) -> set[str]:
    return {match.replace(",", "") for match in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def compare(
    expected: list[str],
    actual: str,
    numbers: set[str],
    *,
    engine: str,
) -> OcrCheck:
    wanted = Counter(tokens(" ".join(expected)))
    found = Counter(tokens(actual))
    matched = sum(min(count, found[token]) for token, count in wanted.items())
    missing = tuple(sorted(numbers - _normalise_numbers(actual)))
    return OcrCheck(
        engine=engine,
        expected_tokens=sum(wanted.values()),
        matched_tokens=matched,
        missing_numbers=missing,
        text=actual,
    )


def run(
    path: Path,
    strings: list[str],
    numbers: set[str],
    *,
    engine: Engine,
    width: int | None = None,
) -> OcrCheck:
    with Image.open(path) as source:
        image = source.convert("RGB")
        if width is not None and image.width > width:
            height = max(1, round(image.height * width / image.width))
            image = image.resize((width, height), Image.Resampling.LANCZOS)
    text = engine.extract(image)
    return compare(strings, text, numbers, engine=engine.name)


def findings_for(
    check: OcrCheck,
    *,
    token_match: float,
    scope: str = "text",
) -> list[Finding]:
    rows: list[Finding] = []
    if check.token_match < token_match:
        rows.append(
            Finding(
                scope,
                "text_accuracy",
                f"OCR matched {check.token_match:.1%} of tokens "
                f"({check.matched_tokens}/{check.expected_tokens}), "
                f"needs {token_match:.0%}",
            )
        )
    if check.missing_numbers:
        rows.append(
            Finding(
                scope,
                "number_mismatch",
                f"OCR did not read {', '.join(check.missing_numbers)}",
            )
        )
    return rows
