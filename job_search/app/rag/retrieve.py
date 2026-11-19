"""BM25 retrieval over the portfolio FTS5 index.

Queries are built from a job, not from prose: title words, must-have skills and
keywords. Terms are OR-joined for recall, then BM25 with a heading boost ranks
them. The caller receives whole chunks with provenance (doc title + heading) so
a CV bullet can be traced back to a line a human wrote.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

MAX_QUERY_TERMS = 24
MAX_CONTEXT_CHARS = 3_500

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "our", "that", "the", "their", "this", "to", "we",
    "will", "with", "you", "your", "role", "job", "work", "team", "who", "what",
    "experience", "years", "year", "using", "have", "has", "about", "into",
}
_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    doc_title: str
    heading: str | None
    text: str
    score: float

    @property
    def citation(self) -> str:
        return f"{self.doc_title} › {self.heading}" if self.heading else self.doc_title


def query_terms(text: str, *, limit: int = MAX_QUERY_TERMS) -> list[str]:
    terms: list[str] = []
    for match in _WORD.finditer(text.lower()):
        word = match.group(0).strip(".-")
        if len(word) < 2 or word in STOPWORDS or word in terms:
            continue
        terms.append(word)
        if len(terms) >= limit:
            break
    return terms


def build_query(job: dict[str, Any] | str) -> str:
    if isinstance(job, str):
        terms = query_terms(job)
    else:
        parts: list[str] = [str(job.get("title") or ""), str(job.get("seniority") or "")]
        for key in ("skills", "must_have", "keywords"):
            value = job.get(key) or []
            parts.extend(value if isinstance(value, (list, tuple)) else [str(value)])
        parts.append(str(job.get("description") or "")[:600])
        terms = query_terms(" ".join(parts))
    if not terms:
        return ""
    return " OR ".join(f'"{term}"' for term in terms)


def retrieve(
    session: Session,
    query: str,
    *,
    limit: int = 8,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> list[RetrievedChunk]:
    if not query.strip():
        return []

    rows = session.execute(
        sql_text(
            """
            SELECT c.id AS chunk_id, d.title AS doc_title, c.heading, c.text,
                   bm25(portfolio_fts, 1.0, 2.0, 0.5) AS rank
            FROM portfolio_fts
            JOIN portfolio_chunks c ON c.id = portfolio_fts.rowid
            JOIN portfolio_docs d ON d.id = c.doc_id
            WHERE portfolio_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
            """
        ),
        {"query": query, "limit": limit},
    ).all()

    chunks: list[RetrievedChunk] = []
    total = 0
    for row in rows:
        text = row.text or ""
        if chunks and total + len(text) > max_chars:
            continue
        chunks.append(
            RetrievedChunk(
                chunk_id=row.chunk_id,
                doc_title=row.doc_title or "",
                heading=row.heading,
                text=text,
                score=round(-float(row.rank), 4),
            )
        )
        total += len(text)
    return chunks


def retrieve_for_job(
    session: Session,
    job: dict[str, Any],
    *,
    limit: int = 8,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> list[RetrievedChunk]:
    return retrieve(session, build_query(job), limit=limit, max_chars=max_chars)


def as_context(chunks: Iterable[RetrievedChunk]) -> str:
    """Prompt-ready block with a stable citation line per chunk."""
    blocks = []
    for chunk in chunks:
        blocks.append(f"[{chunk.citation}]\n{chunk.text}")
    return "\n\n".join(blocks)
