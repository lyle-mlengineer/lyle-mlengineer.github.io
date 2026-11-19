"""Render the small Markdown subset our skills emit, escaped first.

No Markdown library and no ``|safe`` on model output: text is HTML-escaped
before any tags are added, so a prompt-injected ``<script>`` stays literal.
Supported: headings, unordered lists, bold, paragraphs and line breaks.
"""

from __future__ import annotations

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HEADING = re.compile(r"^(#{1,4})\s+(.+)$")
_BULLET = re.compile(r"^[-*]\s+(.+)$")


def markdown_to_html(markdown: str) -> str:
    lines = (markdown or "").replace("\r\n", "\n").split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            text = " ".join(paragraph).strip()
            if text:
                blocks.append(f"<p>{_inline(text)}</p>")
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{_inline(item)}</li>" for item in bullets)
            blocks.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph()
            flush_bullets()
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_bullets()
            level = min(6, len(heading.group(1)) + 1)
            blocks.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        bullet = _BULLET.match(line)
        if bullet:
            flush_paragraph()
            bullets.append(bullet.group(1))
            continue
        flush_bullets()
        paragraph.append(line)

    flush_paragraph()
    flush_bullets()
    return "\n".join(blocks)


def _inline(value: str) -> str:
    return _BOLD.sub(r"<strong>\1</strong>", html.escape(value, quote=True))
