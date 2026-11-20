"""Uploaded interview sources: extraction, chunking, FTS5 search and payloads.

A source is whatever the candidate wants to study from — a PDF of interview
notes, a DOCX of system-design prompts, an article, or text pasted into the page.
The extracted text is stored once, chunked heading-aware, and indexed in
``interview_source_fts`` so practice questions can be grounded in it and a
question can be answered with citations back to the exact source.

Everything in here is untrusted: extraction normalises control characters and
the prompt builder wraps the result in a tag, exactly like the job page.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import InterviewQuestion, InterviewSource, InterviewSourceChunk, utcnow
from ..rag.ingest import chunk_markdown
from ..rag.retrieve import query_terms
from ..utils import clean_text, slugify

MAX_TITLE_CHARS = 240
MIN_SOURCE_CHARS = 80
MAX_EXCERPT_CHARS = 700
MAX_QUERY_TERMS = 18

TEXT_SUFFIXES = {".txt", ".text", ".csv", ".log"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}
HTML_SUFFIXES = {".html", ".htm"}
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_BLANKS = re.compile(r"\n{3,}")


class SourceError(ValueError):
    """A source could not be read, stored, or is a duplicate."""


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: int
    source_id: int
    source_title: str
    heading: str | None
    text: str
    score: float = 0.0

    @property
    def citation(self) -> str:
        return f"{self.source_title} › {self.heading}" if self.heading else self.source_title


# ------------------------------------------------------------------ extraction


def clean_source_text(value: str, *, limit: int | None = None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub(" ", text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = _BLANKS.sub("\n\n", text).strip()
    if limit is not None:
        text = text[:limit]
    return text


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - the dependency ships with the app
        raise SourceError(
            "PDF support needs pypdf. Install it with 'pip install pypdf' and try again."
        ) from exc
    try:
        reader = PdfReader(BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise SourceError(f"That PDF could not be read: {exc}") from exc
    return "\n\n".join(page for page in pages if page)


def _docx_text(data: bytes) -> str:
    from docx import Document

    try:
        document = Document(BytesIO(data))
    except Exception as exc:
        raise SourceError(f"That DOCX could not be read: {exc}") from exc

    parts: list[str] = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(part for part in parts if part.strip())


def _html_text(data: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(data.decode("utf-8", errors="replace"), "html.parser")
    title = ""
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(" ", strip=True)
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "form", "button"]):
        tag.decompose()
    for tag in soup.find_all(["nav", "footer", "header", "aside"]):
        tag.decompose()
    blocks: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "td"]):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name in {"h1", "h2", "h3", "h4"}:
            blocks.append("#" * min(4, int(node.name[1])) + " " + text)
        elif node.name == "li":
            blocks.append("- " + text)
        else:
            blocks.append(text)
    if not blocks:
        body = soup.body or soup
        blocks = [body.get_text(" ", strip=True)]
    return "\n\n".join(blocks), title


def extract_upload(
    filename: str,
    *,
    mime: str = "",
    data: bytes,
    max_chars: int = 400_000,
) -> tuple[str, str, str]:
    """Return ``(text, kind, inferred_title)`` for an uploaded file."""
    if not data:
        raise SourceError("That file is empty.")
    suffix = Path(filename or "").suffix.lower()
    inferred_title = Path(filename or "").stem.replace("_", " ").replace("-", " ").strip()

    if suffix in PDF_SUFFIXES or mime == "application/pdf":
        text, kind = _pdf_text(data), "pdf"
    elif suffix in DOCX_SUFFIXES or mime.endswith("wordprocessingml.document"):
        text, kind = _docx_text(data), "docx"
    elif suffix in HTML_SUFFIXES or mime in {"text/html", "application/xhtml+xml"}:
        text, title = _html_text(data)
        kind = "article"
        inferred_title = inferred_title or title
    else:
        decoded = data.decode("utf-8", errors="replace")
        text = decoded
        kind = "markdown" if suffix in MARKDOWN_SUFFIXES else "text"

    text = clean_source_text(text, limit=max_chars)
    if len(text) < MIN_SOURCE_CHARS:
        raise SourceError(
            "That source has too little readable text. Scanned PDFs need OCR before upload."
        )
    return text, kind, inferred_title


# ------------------------------------------------------------------ storage


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def add_source(
    db: Session,
    settings: Settings,
    *,
    title: str,
    text: str,
    kind: str,
    filename: str | None = None,
    mime: str | None = None,
    source_url: str | None = None,
    data: bytes | None = None,
) -> InterviewSource:
    """Store one source and its chunks, rejecting exact duplicates."""
    cleaned = clean_source_text(text, limit=settings.interview_max_source_chars)
    if len(cleaned) < MIN_SOURCE_CHARS:
        raise SourceError("That source has too little readable text to study from.")

    digest = _digest(cleaned)
    existing = db.scalar(select(InterviewSource).where(InterviewSource.sha256 == digest))
    if existing is not None:
        raise SourceError(f"“{existing.title}” is already saved.")

    label = clean_text(title or filename or "Interview source")[:MAX_TITLE_CHARS]
    source = InterviewSource(
        title=label or "Interview source",
        kind=kind,
        filename=(filename or None),
        mime=(mime or None),
        source_url=source_url or None,
        sha256=digest,
        bytes=len(data) if data else len(cleaned.encode("utf-8")),
        char_count=len(cleaned),
        text=cleaned,
    )
    db.add(source)
    db.flush()

    if data is not None and filename:
        suffix = Path(filename).suffix.lower()[:10]
        name = f"source-{source.id}-{slugify(source.title, fallback='source')}{suffix}"
        path = settings.interview_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        source.path = str(path)

    chunks = chunk_markdown(cleaned, fallback_title=source.title)
    for chunk in chunks:
        db.add(
            InterviewSourceChunk(
                source_id=source.id,
                ordinal=chunk.ordinal,
                heading=(chunk.heading or source.title)[:240],
                text=chunk.text,
                est_tokens=max(1, len(chunk.text) // 4),
            )
        )
    db.flush()

    stored = db.scalars(
        select(InterviewSourceChunk)
        .where(InterviewSourceChunk.source_id == source.id)
        .order_by(InterviewSourceChunk.ordinal)
    ).all()
    for row, chunk in zip(stored, chunks, strict=True):
        db.execute(
            sql_text(
                "INSERT INTO interview_source_fts(rowid, text, heading, source_title) "
                "VALUES (:rowid, :text, :heading, :source_title)"
            ),
            {
                "rowid": row.id,
                "text": chunk.text,
                "heading": row.heading or "",
                "source_title": source.title,
            },
        )
    source.chunk_count = len(stored)
    source.updated_at = utcnow()
    db.flush()
    return source


def add_from_upload(
    db: Session,
    settings: Settings,
    *,
    filename: str,
    mime: str,
    data: bytes,
    title: str = "",
) -> InterviewSource:
    if len(data) > settings.interview_max_upload_bytes:
        raise SourceError(
            f"That file is larger than the {settings.interview_max_upload_bytes // 1_000_000} MB limit."
        )
    text, kind, inferred = extract_upload(
        filename,
        mime=mime,
        data=data,
        max_chars=settings.interview_max_source_chars,
    )
    return add_source(
        db,
        settings,
        title=title or inferred or Path(filename).stem,
        text=text,
        kind=kind,
        filename=Path(filename).name[:255],
        mime=(mime or "")[:120] or None,
        data=data,
    )


def delete_source(db: Session, source: InterviewSource) -> None:
    ids = db.scalars(
        select(InterviewSourceChunk.id).where(InterviewSourceChunk.source_id == source.id)
    ).all()
    if ids:
        placeholders = ",".join(str(int(chunk_id)) for chunk_id in ids)
        db.execute(sql_text(f"DELETE FROM interview_source_fts WHERE rowid IN ({placeholders})"))
    db.execute(delete(InterviewSourceChunk).where(InterviewSourceChunk.source_id == source.id))
    if source.path:
        try:
            Path(source.path).unlink(missing_ok=True)
        except OSError:  # a missing file must not block deleting the row
            pass
    db.delete(source)


# ------------------------------------------------------------------ search


def _fts_query(value: str) -> str:
    terms = query_terms(value, limit=MAX_QUERY_TERMS)
    if not terms:
        return ""
    return " OR ".join(f'"{term}"' for term in terms)


def search_source_chunks(
    db: Session,
    query: str,
    *,
    source_ids: Iterable[int] | None = None,
    limit: int = 8,
    max_chars: int = 6_000,
) -> list[SourceChunk]:
    match = _fts_query(query)
    if not match:
        return []
    ids = [int(source_id) for source_id in (source_ids or []) if source_id]
    filter_sql = ""
    params: dict[str, Any] = {"query": match, "limit": limit}
    if ids:
        filter_sql = " AND c.source_id IN (" + ",".join(f":s{index}" for index in range(len(ids))) + ")"
        params.update({f"s{index}": source_id for index, source_id in enumerate(ids)})

    rows = db.execute(
        sql_text(
            f"""
            SELECT c.id AS chunk_id, c.source_id, s.title AS source_title, c.heading, c.text,
                   bm25(interview_source_fts, 1.0, 2.0, 0.5) AS rank
            FROM interview_source_fts
            JOIN interview_source_chunks c ON c.id = interview_source_fts.rowid
            JOIN interview_sources s ON s.id = c.source_id
            WHERE interview_source_fts MATCH :query{filter_sql}
            ORDER BY rank
            LIMIT :limit
            """
        ),
        params,
    ).all()

    chunks: list[SourceChunk] = []
    total = 0
    for row in rows:
        text = row.text or ""
        if chunks and total + len(text) > max_chars:
            continue
        chunks.append(
            SourceChunk(
                chunk_id=row.chunk_id,
                source_id=row.source_id,
                source_title=row.source_title or "",
                heading=row.heading,
                text=text,
                score=round(-float(row.rank), 4),
            )
        )
        total += len(text)
    return chunks


def sample_source_chunks(
    db: Session,
    source_ids: Iterable[int] | None,
    *,
    count: int = 8,
    max_chars: int = 6_000,
    rng=None,
) -> list[SourceChunk]:
    """Pick chunks at random so two practice sets do not read the same."""
    ids = [int(source_id) for source_id in (source_ids or []) if source_id]
    stmt = select(InterviewSourceChunk)
    if ids:
        stmt = stmt.where(InterviewSourceChunk.source_id.in_(ids))
    rows = db.scalars(stmt.limit(2_000)).all()
    if not rows:
        return []
    picker = rng or random
    chosen = picker.sample(rows, k=min(count, len(rows))) if hasattr(picker, "sample") else rows[:count]

    sources = {
        row.id: row
        for row in db.scalars(
            select(InterviewSource).where(
                InterviewSource.id.in_({chunk.source_id for chunk in chosen})
            )
        ).all()
    }
    chunks: list[SourceChunk] = []
    total = 0
    for row in chosen:
        text = row.text or ""
        if chunks and total + len(text) > max_chars:
            continue
        source = sources.get(row.source_id)
        chunks.append(
            SourceChunk(
                chunk_id=row.id,
                source_id=row.source_id,
                source_title=source.title if source else "",
                heading=row.heading,
                text=text,
            )
        )
        total += len(text)
    return chunks


def as_context(chunks: Iterable[SourceChunk]) -> str:
    """Prompt-ready block with a stable citation line per chunk."""
    return "\n\n".join(f"[{chunk.citation}]\n{chunk.text}" for chunk in chunks)


# ------------------------------------------------------------------ payloads


def source_payload(source: InterviewSource, *, question_count: int | None = None) -> dict[str, Any]:
    excerpt = source.text[:MAX_EXCERPT_CHARS].strip()
    if len(source.text) > MAX_EXCERPT_CHARS:
        excerpt += "…"
    return {
        "id": source.id,
        "title": source.title,
        "kind": source.kind,
        "filename": source.filename,
        "mime": source.mime,
        "source_url": source.source_url,
        "chars": source.char_count,
        "chunks": source.chunk_count,
        "questions": question_count or 0,
        "created_at": source.created_at,
        "excerpt": excerpt,
    }


def question_payload(question: InterviewQuestion) -> dict[str, Any]:
    return {
        "id": question.id,
        "origin": question.origin,
        "topic": question.topic,
        "difficulty": question.difficulty,
        "role": question.role,
        "level": question.level,
        "question": question.question,
        "answer": question.answer,
        "follow_ups": list(question.follow_ups_json or []),
        "follow_up_answers": list(question.follow_up_answers_json or []),
        "citations": list(question.citations_json or []),
        "source_title": question.source.title if question.source else None,
        "created_at": question.created_at,
    }


def save_questions(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    job_id: int | None,
    source_id: int | None,
    origin: str,
    model: str | None = None,
    role: str | None = None,
    level: str | None = None,
) -> list[InterviewQuestion]:
    saved: list[InterviewQuestion] = []
    for row in rows:
        question = InterviewQuestion(
            job_id=job_id,
            source_id=source_id,
            origin=origin,
            topic=clean_text(str(row.get("topic") or "General"))[:120] or "General",
            difficulty=row.get("difficulty")
            if row.get("difficulty") in {"warm-up", "core", "deep"}
            else "core",
            role=role,
            level=level,
            question=clean_text(str(row.get("question") or ""))[:1_000],
            answer=(str(row.get("answer") or "")).strip()[:6_000],
            follow_ups_json=[clean_text(str(item))[:300] for item in (row.get("follow_ups") or [])][:4],
            citations_json=[clean_text(str(item))[:300] for item in (row.get("citations") or [])][:5],
            model=model,
        )
        if not question.question or not question.answer:
            continue
        db.add(question)
        saved.append(question)
    db.flush()
    return saved