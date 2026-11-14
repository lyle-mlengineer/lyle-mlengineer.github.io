import hashlib
import re

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.schemas.profile import Block, Heading, Page

_NOISE_TAGS = ("script", "style", "noscript", "template", "svg", "canvas", "iframe")
_BLOCK_TAGS = (
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "li",
    "blockquote",
    "figcaption",
    "td",
    "th",
    "dt",
    "dd",
)
_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
_MAX_BLOCKS = 400
_MAX_TEXT = 4000


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_hidden(node: Tag) -> bool:
    if node.has_attr("hidden") or node.get("aria-hidden") == "true":
        return True
    style = str(node.get("style", "")).replace(" ", "").lower()
    return "display:none" in style or "visibility:hidden" in style


def _direct_text(node: Tag) -> str:
    """Text owned by this node, excluding nested block candidates and noise."""
    parts: list[str] = []
    for text in node.find_all(string=True):
        cleaned = str(text).strip()
        if not cleaned:
            continue
        parent = text.parent
        blocked = False
        while parent is not None and parent is not node:
            if parent.name in _BLOCK_TAGS or parent.name in _NOISE_TAGS:
                blocked = True
                break
            parent = parent.parent
        if not blocked:
            parts.append(cleaned)
    return clean_text(" ".join(parts))


def _stable_id(kind: str, text: str) -> str:
    digest = hashlib.sha1(f"{kind}|{text}".encode()).hexdigest()[:7]  # noqa: S324
    return f"b{digest}"


def _bbox_for(node: Tag, bboxes: dict[str, list[float]] | None) -> list[float] | None:
    if not bboxes:
        return None
    index = node.get("data-sts-box")
    if index is None:
        return None
    return bboxes.get(str(index))


def page_title(soup: BeautifulSoup) -> str:
    if soup.title and clean_text(soup.title.get_text()):
        return clean_text(soup.title.get_text())
    first = soup.find("h1")
    return clean_text(first.get_text()) if first else ""


def extract_page(
    html: str,
    url: str,
    page_id: str,
    bboxes: dict[str, list[float]] | None = None,
) -> Page:
    """Turn one HTML document into a deterministic block tree.

    Source IDs are content-addressed (``kind + text``) rather than positional, so
    two runs over the same page produce the same IDs even if unrelated nodes move.
    Duplicate text is disambiguated in document order, which is stable for a
    given HTML document.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    headings: list[Heading] = []
    blocks: list[Block] = []
    seen: dict[str, int] = {}
    seen_text: set[tuple[str, str]] = set()

    for node in soup.find_all(_BLOCK_TAGS):
        if len(blocks) >= _MAX_BLOCKS:
            break
        if _is_hidden(node):
            continue
        text = _direct_text(node)
        if not text:
            continue
        text = text[:_MAX_TEXT]
        kind = "heading" if node.name in _HEADING_TAGS else node.name
        if (kind, text) in seen_text:
            continue
        seen_text.add((kind, text))

        base = _stable_id(kind, text)
        seen[base] = seen.get(base, 0) + 1
        block_id = base if seen[base] == 1 else f"{base}-{seen[base]}"

        blocks.append(
            Block(
                id=block_id,
                kind=kind,
                text=text,
                bbox=_bbox_for(node, bboxes),
            )
        )
        if node.name in _HEADING_TAGS:
            headings.append(
                Heading(level=_HEADING_TAGS[node.name], text=text, block_id=block_id)
            )

    return Page(
        id=page_id,
        url=url,
        title=page_title(soup),
        headings=headings,
        blocks=blocks,
    )


def page_text(page: Page) -> str:
    return "\n".join(block.text for block in page.blocks)
