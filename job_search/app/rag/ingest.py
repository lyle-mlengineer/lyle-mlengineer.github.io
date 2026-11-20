"""Portfolio → chunks → FTS5.

The corpus is plain Markdown in ``data/portfolio``. Ingestion is incremental:
a SHA-256 per file decides whether it needs re-chunking, so restarting the app or
pressing "reindex" twice writes nothing on the second pass.

Chunks are heading-aware. A section is packed from paragraph blocks into
700–900 character windows with a ~120 character overlap, so a bullet keeps its
heading and a sentence is never cut mid-word.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import session_scope
from ..models import PortfolioChunk, PortfolioDoc, utcnow

MAX_CHARS = 860
OVERLAP_CHARS = 120
MIN_CHUNK_CHARS = 40

_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_BLANKS = re.compile(r"\n{3,}")


@dataclass
class Chunk:
    heading: str
    text: str
    ordinal: int


@dataclass
class IngestReport:
    docs_indexed: int = 0
    docs_skipped: int = 0
    docs_removed: int = 0
    chunks_written: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.docs_indexed or self.docs_removed)


def doc_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    return fallback


def chunk_markdown(markdown: str, *, fallback_title: str = "Portfolio") -> list[Chunk]:
    title = doc_title(markdown, fallback_title)
    sections = _sections(markdown, title)

    chunks: list[Chunk] = []
    for heading, body in sections:
        for text in _pack(_blocks(body)):
            if len(text) < MIN_CHUNK_CHARS:
                continue
            chunks.append(Chunk(heading=heading, text=text, ordinal=len(chunks)))
    return chunks


def _sections(markdown: str, title: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = title
    buffer: list[str] = []
    seen_title = False

    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            level, text = len(match.group(1)), match.group(2).strip()
            if level == 1 and not seen_title:
                seen_title = True
                title = text
                heading = title
                continue
            if buffer:
                body = "\n".join(buffer).strip()
                if body:
                    sections.append((heading, body))
                buffer = []
            heading = text
        else:
            buffer.append(line)

    body = "\n".join(buffer).strip()
    if body:
        sections.append((heading, body))
    return sections


def _blocks(body: str) -> list[str]:
    body = _BLANKS.sub("\n\n", body.strip())
    blocks: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block:
            continue
        blocks.extend(_split_long(block))
    return blocks


def _split_long(block: str) -> list[str]:
    if len(block) <= MAX_CHARS:
        return [block]
    parts, buffer = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+|\n(?=- )", block):
        sentence = sentence.strip()
        if not sentence:
            continue
        if buffer and len(buffer) + 1 + len(sentence) > MAX_CHARS:
            parts.append(buffer)
            buffer = sentence
        else:
            buffer = f"{buffer} {sentence}".strip()
    if buffer:
        parts.extend([buffer] if len(buffer) <= MAX_CHARS * 2 else _hard_split(buffer))
    return parts


def _hard_split(text: str) -> list[str]:
    words = text.split()
    parts, buffer = [], ""
    for word in words:
        if buffer and len(buffer) + 1 + len(word) > MAX_CHARS:
            parts.append(buffer)
            buffer = word
        else:
            buffer = f"{buffer} {word}".strip()
    if buffer:
        parts.append(buffer)
    return parts


def _pack(blocks: list[str]) -> list[str]:
    chunks: list[str] = []
    buffer = ""
    for block in blocks:
        if buffer and len(buffer) + 2 + len(block) > MAX_CHARS:
            chunks.append(buffer.strip())
            buffer = _tail(buffer)
        buffer = f"{buffer}\n\n{block}".strip() if buffer else block
    if buffer.strip():
        chunks.append(buffer.strip())
    return chunks


def _tail(text: str) -> str:
    if len(text) <= OVERLAP_CHARS:
        return text
    tail = text[-OVERLAP_CHARS:]
    space = tail.find(" ")
    return tail[space + 1 :] if space >= 0 else tail


def sync_portfolio(session: Session, settings: Settings) -> IngestReport:
    """Bring the database in line with the Markdown corpus."""
    report = IngestReport()
    seen: set[str] = set()

    paths = sorted(Path(settings.portfolio_dir).glob("*.md"))
    for path in paths:
        relative = str(path.relative_to(settings.portfolio_dir)).replace("\\", "/")
        seen.add(relative)
        raw = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        existing = session.scalar(select(PortfolioDoc).where(PortfolioDoc.path == relative))
        chunk_count = (
            session.scalar(select(PortfolioChunk.id).where(PortfolioChunk.doc_id == existing.id).limit(1))
            if existing
            else None
        )
        if existing and existing.sha256 == digest and chunk_count is not None:
            report.docs_skipped += 1
            continue

        title = doc_title(raw, path.stem.replace("-", " ").title())
        chunks = chunk_markdown(raw, fallback_title=title)

        if existing:
            _delete_fts_for(session, existing.id)
            session.execute(delete(PortfolioChunk).where(PortfolioChunk.doc_id == existing.id))
            doc = existing
            doc.title = title
            doc.sha256 = digest
            doc.updated_at = utcnow()
        else:
            doc = PortfolioDoc(path=relative, title=title, sha256=digest)
            session.add(doc)

        session.flush()
        for chunk in chunks:
            row = PortfolioChunk(
                doc_id=doc.id,
                ordinal=chunk.ordinal,
                heading=chunk.heading[:240] if chunk.heading else None,
                doc_title=title,
                text=chunk.text,
                est_tokens=max(1, len(chunk.text) // 4),
            )
            session.add(row)
        session.flush()

        stored = session.scalars(
            select(PortfolioChunk)
            .where(PortfolioChunk.doc_id == doc.id)
            .order_by(PortfolioChunk.ordinal)
        ).all()
        for stored_chunk, chunk in zip(stored, chunks, strict=True):
            session.execute(
                sql_text(
                    "INSERT INTO portfolio_fts(rowid, text, heading, doc_title) "
                    "VALUES (:rowid, :text, :heading, :doc_title)"
                ),
                {
                    "rowid": stored_chunk.id,
                    "text": chunk.text,
                    "heading": chunk.heading,
                    "doc_title": title,
                },
            )
        report.docs_indexed += 1
        report.chunks_written += len(chunks)

    for doc in session.scalars(select(PortfolioDoc)).all():
        if doc.path not in seen:
            _delete_fts_for(session, doc.id)
            session.execute(delete(PortfolioChunk).where(PortfolioChunk.doc_id == doc.id))
            session.delete(doc)
            report.docs_removed += 1

    # The index is derived, so reconcile it once per sync: this repairs rows
    # written before ``doc_title`` existed and drops entries for deleted chunks.
    session.execute(
        sql_text(
            "UPDATE portfolio_chunks SET doc_title = "
            "(SELECT title FROM portfolio_docs WHERE portfolio_docs.id = portfolio_chunks.doc_id) "
            "WHERE doc_title IS NULL"
        )
    )
    session.execute(sql_text("INSERT INTO portfolio_fts(portfolio_fts) VALUES('rebuild')"))
    session.commit()
    return report


def _delete_fts_for(session: Session, doc_id: int) -> None:
    ids = session.scalars(select(PortfolioChunk.id).where(PortfolioChunk.doc_id == doc_id)).all()
    if not ids:
        return
    placeholders = ",".join(str(int(chunk_id)) for chunk_id in ids)
    session.execute(sql_text(f"DELETE FROM portfolio_fts WHERE rowid IN ({placeholders})"))


def reindex(settings: Settings) -> IngestReport:
    with session_scope(settings) as session:
        return sync_portfolio(session, settings)
