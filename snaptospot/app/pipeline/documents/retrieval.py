"""Hybrid retrieval: BM25 + vector, reciprocal rank fusion, rerank to top 8.

Every query starts with tenant, run and site equality filters, so a document
uploaded to one account can never surface in another account's run. On Postgres
the lexical and vector legs use the ``tsvector`` and pgvector indexes; on SQLite
both legs run in Python over the same tenant-filtered candidate set.
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document, Run
from app.models.base import utcnow
from app.pipeline.documents.embeddings import cosine, embed_query, tokenize
from app.pipeline.resolve.schema import slot_for

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_RRF_K = 60
_MIN_SCORE = 0.05
_LEXICAL_LIMIT = 60
_VECTOR_LIMIT = 60
_MAX_CANDIDATES = 2000

_GAP_QUERIES = {
    "proof.metrics": (
        "metric result number percentage improvement impact outcome measure "
        "achievement growth"
    ),
    "commerce.price": "price cost pricing fee amount dollars entry",
    "proof.quote": "client testimonial quote feedback said review",
    "attribution.quote": "client name role title attribution author founder",
    "identity.name": "name founder owner author person",
    "identity.role": "role job title position works as founder engineer designer",
    "identity.location": "based located city country remote",
    "contact.email": "email contact reach address",
    "contact.url": "contact link booking website url",
    "offer.core": "offering service product what we do help build design create",
    "visual.project_shot": "project screenshot product image photo",
    "identity.portrait": "portrait headshot photo profile image",
    "proof.client_logo": "client brand logo mark image",
    "recency.metrics": "date month year measured as of updated",
}
_NUMERIC_KEYS = {"proof.metrics", "commerce.price", "recency.metrics"}


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document: Document
    score: float
    lexical_rank: int | None = None
    vector_rank: int | None = None


def query_for_gap(key: str) -> str:
    slot = slot_for(key)
    base = slot.prompt if slot else key.replace(".", " ").replace("_", " ")
    extra = _GAP_QUERIES.get(key, "")
    if not extra and slot is not None:
        extra = _GAP_QUERIES.get(slot.gap_class, "")
    return f"{base} {extra}".strip()


def _eligible(run: Run, document_ids: list[str] | None = None):
    conditions = [
        Chunk.tenant_id == run.tenant_id,
        Chunk.run_id == run.id,
        Chunk.site_id == run.site_id,
        Document.tenant_id == run.tenant_id,
        Document.run_id == run.id,
        Document.site_id == run.site_id,
        Document.status == "ready",
        or_(
            Document.pinned_to_brand.is_(True),
            Document.expires_at.is_(None),
            Document.expires_at > utcnow(),
        ),
    ]
    if document_ids:
        conditions.append(Chunk.document_id.in_(document_ids))
    return conditions


def _load_rows(
    db: Session, run: Run, document_ids: list[str] | None = None
) -> list[tuple[Chunk, Document]]:
    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(*_eligible(run, document_ids))
        .order_by(Chunk.document_id, Chunk.ordinal)
        .limit(_MAX_CANDIDATES)
    )
    return list(db.execute(statement).all())


def _bm25_ranking(query: str, rows: list[tuple[Chunk, Document]], limit: int) -> list[str]:
    query_terms = list(dict.fromkeys(tokenize(query)))
    if not query_terms or not rows:
        return []

    corpus = [tokenize(chunk.text) for chunk, _ in rows]
    lengths = [len(tokens) for tokens in corpus]
    average = (sum(lengths) / len(lengths)) or 1.0
    document_frequency = Counter()
    for tokens in corpus:
        for term in set(tokens):
            document_frequency[term] += 1

    total = len(corpus)
    scores: list[tuple[float, str]] = []
    for index, tokens in enumerate(corpus):
        if not tokens:
            continue
        counts = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            idf = math.log(1.0 + (total - df + 0.5) / (df + 0.5))
            denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * lengths[index] / average)
            score += idf * (frequency * 2.5) / denominator
        if score > 0:
            scores.append((score, rows[index][0].id))

    scores.sort(key=lambda item: (-item[0], item[1]))
    return [chunk_id for _, chunk_id in scores[:limit]]


def _vector_ranking(
    db: Session,
    run: Run,
    rows: list[tuple[Chunk, Document]],
    query_vector: list[float],
    limit: int,
    document_ids: list[str] | None = None,
) -> list[tuple[str, float]]:
    if db.get_bind().dialect.name == "postgresql":
        try:
            distance = Chunk.embedding.cosine_distance(query_vector)
            statement = (
                select(Chunk.id, distance.label("distance"))
                .join(Document, Chunk.document_id == Document.id)
                .where(*_eligible(run, document_ids), Chunk.embedding.is_not(None))
                .order_by(distance)
                .limit(limit)
            )
            return [
                (row.id, 1.0 - float(row.distance))
                for row in db.execute(statement).all()
            ]
        except Exception as exc:  # pragma: no cover - requires Postgres
            logger.warning("pgvector ordering failed; scoring in Python: %s", exc)

    scored = []
    for chunk, _ in rows:
        similarity = cosine(chunk.embedding, query_vector)
        scored.append((similarity, chunk.id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(chunk_id, similarity) for similarity, chunk_id in scored[:limit]]


def _rerank(query: str, text: str, similarity: float, *, wants_numbers: bool) -> float:
    query_terms = set(tokenize(query))
    text_terms = set(tokenize(text))
    coverage = (
        len(query_terms & text_terms) / len(query_terms) if query_terms else 0.0
    )
    phrase = 1.0 if query.strip().lower() in text.lower() else 0.0
    density = min(len(_NUMBER.findall(text)), 4) / 4
    score = 0.35 * max(similarity, 0.0) + 0.25 * coverage + 0.10 * phrase
    if wants_numbers:
        score += 0.30 * density
    return score


def search_chunks(
    db: Session,
    run: Run,
    query: str,
    *,
    top_k: int | None = None,
    document_ids: list[str] | None = None,
    gap_key: str | None = None,
) -> list[RetrievedChunk]:
    settings = get_settings()
    limit = top_k or settings.retrieval_top_k
    rows = _load_rows(db, run, document_ids)
    if not rows:
        return []

    query_vector = embed_query(query)
    lexical = _bm25_ranking(query, rows, _LEXICAL_LIMIT)
    vector = _vector_ranking(db, run, rows, query_vector, _VECTOR_LIMIT, document_ids)
    vector_scores = dict(vector)

    fused: dict[str, float] = {}
    lexical_rank = {chunk_id: index for index, chunk_id in enumerate(lexical)}
    vector_rank = {chunk_id: index for index, chunk_id in enumerate(vector_scores)}
    for chunk_id, index in lexical_rank.items():
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (_RRF_K + index + 1)
    for chunk_id, index in vector_rank.items():
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (_RRF_K + index + 1)

    by_id = {chunk.id: (chunk, document) for chunk, document in rows}
    wants_numbers = gap_key in _NUMERIC_KEYS if gap_key else False
    if wants_numbers:
        # A metric query may share no words with the winning slide. Numbers are
        # the signal, so numeric chunks enter the rerank pool even at rank zero.
        for chunk, _document in rows:
            if _NUMBER.search(chunk.text):
                fused.setdefault(chunk.id, 0.0)
    pool = sorted(fused.items(), key=lambda item: (-item[1], item[0]))[
        : max(limit * 4, 64)
    ]

    ranked: list[RetrievedChunk] = []
    for chunk_id, _fused_score in pool:
        chunk, document = by_id[chunk_id]
        score = _rerank(
            query,
            chunk.text,
            vector_scores.get(chunk_id, 0.0),
            wants_numbers=wants_numbers,
        )
        if score < _MIN_SCORE:
            continue
        ranked.append(
            RetrievedChunk(
                chunk=chunk,
                document=document,
                score=round(score, 6),
                lexical_rank=lexical_rank.get(chunk_id),
                vector_rank=vector_rank.get(chunk_id),
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.chunk.ordinal))
    return ranked[:limit]


def search_for_gap(
    db: Session,
    run: Run,
    gap_key: str,
    *,
    top_k: int | None = None,
    document_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    return search_chunks(
        db,
        run,
        query_for_gap(gap_key),
        top_k=top_k,
        document_ids=document_ids,
        gap_key=gap_key,
    )
