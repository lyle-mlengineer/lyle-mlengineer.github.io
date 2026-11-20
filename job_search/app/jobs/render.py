"""Render the small Markdown subset our skills emit, escaped first.

No Markdown library and no ``|safe`` on model output: text is HTML-escaped
before any tags are added, so a prompt-injected ``<script>`` stays literal.
Supported: headings, unordered lists, bold, paragraphs and line breaks.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HEADING = re.compile(r"^(#{1,4})\s+(.+)$")
_BULLET = re.compile(r"^[-*]\s+(.+)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
# A sentence boundary that only fires before a new sentence's capital or digit.
_SENTENCE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\u201c\"'(])")


def markdown_to_html(
    markdown: str, *, paragraph_chars: int = 0, collapsible_sections: bool = False
) -> str:
    """Render the supported Markdown subset.

    ``paragraph_chars`` is opt-in and splits long plain paragraphs at sentence
    boundaries, so a two-minute interview answer reads as a handful of short
    blocks instead of one wall of text. Lists, headings and short paragraphs are
    left alone.
    """
    lines = (markdown or "").replace("\r\n", "\n").split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    code: list[str] = []
    code_lang = ""
    in_code = False

    def flush_code() -> None:
        nonlocal code_lang, in_code
        if in_code or code:
            blocks.append(_code_block(code, code_lang))
            code.clear()
            code_lang = ""
            in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            text = " ".join(paragraph).strip()
            if text:
                blocks.extend(
                    f"<p>{_inline(piece)}</p>"
                    for piece in split_paragraphs(text, paragraph_chars)
                )
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{_inline(item)}</li>" for item in bullets)
            blocks.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw in lines:
        line = raw.strip()
        if in_code or line.startswith("```"):
            if line.startswith("```"):
                if in_code:
                    flush_code()
                else:
                    flush_paragraph()
                    flush_bullets()
                    code_lang = line[3:].strip()
                    in_code = True
                continue
            code.append(raw)
            continue
        if not line:
            flush_paragraph()
            flush_bullets()
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_bullets()
            level = min(6, len(heading.group(1)) + 1)
            blocks.append(f"<h{level}{_heading_class(heading.group(2))}>{_inline(heading.group(2))}</h{level}>")
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
    flush_code()
    if collapsible_sections:
        blocks = _collapse_sections(blocks)
    return "\n".join(blocks)


def _collapse_sections(blocks: list[str]) -> list[str]:
    """Turn every fourth-level heading into a closed ``details`` block.

    ``markdown_to_html`` renders ``###`` sections as ``h4`` because the document
    title starts at ``h2``. Design briefs are long, so each step (requirements,
    entities, API, data flow, high-level design, deep dives) becomes its own
    disclosure and the question stays visible while the reader chooses depth.
    """
    out: list[str] = []
    open_section = False
    for block in blocks:
        if block.startswith("<h4"):
            if open_section:
                out.append("</div></details>")
            match = re.match(r"<h4[^>]*>(.*?)</h4>", block)
            title = match.group(1) if match else ""
            out.append(
                '<details class="design-section">'
                f'<summary class="design-section__title">{title}</summary>'
                '<div class="design-section__body">'
            )
            open_section = True
            continue
        if block.startswith(("<h1", "<h2", "<h3")):
            if open_section:
                out.append("</div></details>")
                open_section = False
        out.append(block)
    if open_section:
        out.append("</div></details>")
    return out


def split_paragraphs(text: str, limit: int) -> list[str]:
    """Group whole sentences into blocks no longer than ``limit`` characters."""
    if limit <= 0 or len(text) <= limit:
        return [text]
    sentences = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    if len(sentences) <= 1:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _heading_class(text: str) -> str:
    """A slug class per heading so CSS can style known sections (Delivery, Anchors)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return f' class="prose-h prose-h--{slug}"' if slug else ""


def _code_block(lines: list[str], language: str) -> str:
    """A fenced code block, escaped and never passed through inline Markdown."""
    lang = re.sub(r"[^a-z0-9_+#-]", "", language.lower())[:20]
    class_attr = f' class="language-{lang}"' if lang else ""
    escaped = html.escape("\n".join(lines))
    return f'<pre class="prose-code"><code{class_attr}>{escaped}</code></pre>'


def _inline(value: str) -> str:
    """Bold and http(s) links, with everything else escaped first."""
    links: list[str] = []

    def stash(match: re.Match[str]) -> str:
        label, href = match.group(1), match.group(2)
        if not _safe_url(href):
            return match.group(0)
        safe_href = html.escape(href, quote=True)
        links.append(
            f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">{_bold(html.escape(label, quote=True))}</a>'
        )
        return f"\x00{len(links) - 1}\x00"

    text = _LINK.sub(stash, value)
    text = _bold(html.escape(text, quote=True))
    for index, markup in enumerate(links):
        text = text.replace(f"\x00{index}\x00", markup)
    return text


def _bold(value: str) -> str:
    return _BOLD.sub(r"<strong>\1</strong>", value)


def _safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
