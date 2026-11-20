"""Small text normalisers shared by the writing skills."""

from __future__ import annotations

import re
from typing import Any

CLICHES = (
    "passionate",
    "rockstar",
    "synergy",
    "dynamic self-starter",
    "think outside the box",
    "hit the ground running",
)


def text(value: Any, limit: int = 2000) -> str:
    return " ".join(str(value or "").split())[:limit]


def prose_text(value: Any, limit: int = 20_000) -> str:
    """Like :func:`text`, but blank lines survive as paragraph breaks."""
    raw = str(value or "").replace("\r\n", "\n")
    cleaned = "\n".join(" ".join(line.split()) for line in raw.split("\n"))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:limit]


def clip_chars(value: Any, limit: int) -> str:
    """Collapse whitespace, then cut at a word boundary near ``limit``.

    Unlike a plain slice this never leaves half a word (or a dangling comma) at
    the end of a greeting or closing.
    """
    cleaned = text(value, limit + 1)
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-")


def items(value: Any, limit: int, *, item_limit: int = 400) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for raw in value:
        clean = text(raw, item_limit)
        if clean and clean not in out:
            out.append(clean)
    return out[:limit]


def word_count(value: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", value or ""))


def clip_words(value: str, maximum: int) -> str:
    """Trim to a sentence boundary near the limit, never below half of it."""
    value = prose_text(value)
    words = value.split()
    if len(words) <= maximum:
        return value
    cut = " ".join(words[:maximum])
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary >= int(len(cut) * 0.5):
        return cut[: boundary + 1]
    return cut.rstrip(" ,;:-") + "."


def strip_cliches(value: str) -> str:
    cleaned = value
    for phrase in CLICHES:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    paragraphs = (" ".join(part.split()) for part in cleaned.split("\n\n"))
    return "\n\n".join(part for part in paragraphs if part)


def drop_placeholders(values: list[str]) -> list[str]:
    return [value for value in values if not re.search(r"\[[^\]]{1,40}\]", value)]
