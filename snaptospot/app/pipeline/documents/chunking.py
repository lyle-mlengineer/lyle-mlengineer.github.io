"""Structure-aware chunking (~700 tokens, 120-token overlap).

Chunks never cross a page or slide boundary. That constraint costs a little
context and buys an exact citation: a fact pulled from a chunk can always name
the page it came from.
"""

from dataclasses import dataclass

from app.pipeline.documents.parsers import ParsedPage

MAX_TOKENS = 700
OVERLAP_TOKENS = 120
_CHARS_PER_TOKEN = 4
MAX_CHARS = MAX_TOKENS * _CHARS_PER_TOKEN
_OVERLAP_CHARS = OVERLAP_TOKENS * _CHARS_PER_TOKEN


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    page: int
    kind: str
    text: str
    tokens: int


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate good enough for chunk boundaries."""
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


def _hard_split(text: str, limit: int = MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    pieces: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = max(window.rfind("\n"), window.rfind(". "), window.rfind(" "))
        if cut < limit // 2:
            cut = limit
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        pieces.append(remaining.strip())
    return [piece for piece in pieces if piece]


def _segments(page: ParsedPage) -> list[str]:
    pieces: list[str] = []
    for line in page.text.split("\n"):
        line = line.strip()
        if line:
            pieces.extend(_hard_split(line))
    return pieces


def _tail(text: str) -> str:
    tail = text[-_OVERLAP_CHARS:]
    space = tail.find(" ")
    if space != -1:
        tail = tail[space + 1 :]
    return tail.strip()


def chunk_pages(pages: list[ParsedPage]) -> list[ChunkDraft]:
    """Split parsed pages into overlapping chunks, preserving page metadata."""
    drafts: list[ChunkDraft] = []
    ordinal = 0

    for page in pages:
        current: list[str] = []
        for segment in _segments(page):
            candidate = "\n".join([*current, segment])
            if current and estimate_tokens(candidate) > MAX_TOKENS:
                text = "\n".join(current).strip()
                if text:
                    ordinal += 1
                    drafts.append(
                        ChunkDraft(
                            ordinal=ordinal,
                            page=page.number,
                            kind=page.kind,
                            text=text,
                            tokens=estimate_tokens(text),
                        )
                    )
                tail = _tail(text)
                if tail and estimate_tokens(tail) + estimate_tokens(segment) <= MAX_TOKENS:
                    current = [tail]
                else:
                    current = []
            current.append(segment)

        if current:
            text = "\n".join(current).strip()
            if text:
                ordinal += 1
                drafts.append(
                    ChunkDraft(
                        ordinal=ordinal,
                        page=page.number,
                        kind=page.kind,
                        text=text,
                        tokens=estimate_tokens(text),
                    )
                )

    return drafts
