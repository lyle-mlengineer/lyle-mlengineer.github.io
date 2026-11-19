"""Turn a careers page into clean text and lightweight Markdown.

Job boards vary wildly, so the extractor is a scoring heuristic rather than
per-site selectors:

1. strip scripts, navigation, footers and forms;
2. score candidate containers by text length minus link density;
3. walk the winner's block elements into Markdown-ish lines.

A page that yields fewer than 400 characters is reported as `ok=False`. That is
usually a JavaScript-only shell, and the caller should ask for a pasted posting
instead of sending an empty page to the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

MIN_USEFUL_CHARS = 400

_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "p", "li", "blockquote", "td", "dd")
_HEADING_TAGS = {"h1", "h2", "h3", "h4"}
_STRIP_TAGS = ("script", "style", "noscript", "svg", "iframe", "template", "form", "button")
_CHROME_TAGS = ("nav", "footer", "header", "aside")
_CANDIDATE_SELECTORS = (
    "main",
    "article",
    "[role=main]",
    "#content",
    "#main",
    ".content",
    ".main-content",
    ".job",
    "[class*=job-description]",
    "[class*=jobDescription]",
    "[id*=job-description]",
    ".posting",
    ".description",
)
_WS = re.compile(r"[ \t\u00a0]+")
_BLANKS = re.compile(r"\n{3,}")


@dataclass
class ExtractedPage:
    url: str
    title: str
    text: str
    description_md: str
    char_count: int
    ok: bool
    reason: str = ""


def extract_page(html: str, url: str = "") -> ExtractedPage:
    soup = BeautifulSoup(html or "", "html.parser")
    title = _title(soup)
    meta_description = _meta_description(soup)

    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    for tag in soup(_CHROME_TAGS):
        tag.decompose()

    body = soup.body or soup
    best = _best_candidate(body)
    text = _blocks_to_text(best)

    if len(text) < MIN_USEFUL_CHARS:
        fallback = _blocks_to_text(body)
        if len(fallback) > len(text):
            text = fallback

    text = _BLANKS.sub("\n\n", text).strip()
    ok = len(text) >= MIN_USEFUL_CHARS
    reason = "" if ok else "page had too little readable text (likely JavaScript-rendered)"

    description = meta_description or _first_paragraph(text)
    return ExtractedPage(
        url=url,
        title=title,
        text=text,
        description_md=description,
        char_count=len(text),
        ok=ok,
        reason=reason,
    )


def _title(soup: BeautifulSoup) -> str:
    for selector, attr in (
        ("meta[property='og:title']", "content"),
        ("meta[name='twitter:title']", "content"),
    ):
        node = soup.select_one(selector)
        if node and node.get(attr):
            return node[attr].strip()
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    if soup.h1 and soup.h1.get_text(strip=True):
        return soup.h1.get_text(" ", strip=True)
    return ""


def _meta_description(soup: BeautifulSoup) -> str:
    for selector in ("meta[name='description']", "meta[property='og:description']"):
        node = soup.select_one(selector)
        if node and node.get("content"):
            return node["content"].strip()
    return ""


def _score(node) -> int:
    text = node.get_text(" ", strip=True)
    if not text:
        return 0
    link_text = sum(len(a.get_text(" ", strip=True)) for a in node.find_all("a"))
    return len(text) - 2 * link_text


def _best_candidate(body):
    candidates = []
    for selector in _CANDIDATE_SELECTORS:
        candidates.extend(body.select(selector))
    if not candidates:
        candidates = body.find_all(["div", "section"], recursive=True)
    if not candidates:
        return body
    return max(candidates, key=_score)


def _blocks_to_text(root) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for node in root.find_all(_BLOCK_TAGS):
        text = _WS.sub(" ", node.get_text(" ", strip=True)).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        if node.name in _HEADING_TAGS:
            level = 2 if node.name in {"h1", "h2"} else 3
            lines.append("#" * level + " " + text)
        elif node.name == "li":
            lines.append("- " + text)
        else:
            lines.append(text)

    if not lines:
        text = _WS.sub(" ", root.get_text(" ", strip=True)).strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines)


def _first_paragraph(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if len(cleaned) >= 40 and not cleaned.startswith("#"):
            return cleaned[:300]
    return ""


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()
