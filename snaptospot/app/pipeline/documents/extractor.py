"""Turn retrieved document chunks into grounded facts.

Heuristics run first because they are deterministic and offline. A configured
LLM is a fallback: it sees the top three chunks for one gap, must return a
verbatim quote, and its answer is grounded against the cited chunk exactly like
a site fact. A null answer leaves the gap open for the next rung.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditLog, Document, FactRecord, Run
from app.models.base import new_id, utcnow
from app.pipeline.documents.errors import DocumentError
from app.pipeline.documents.retrieval import RetrievedChunk, search_for_gap
from app.pipeline.extract.deterministic import (
    metric_facts_for_text,
    parse_attribution,
)
from app.pipeline.extract.ground import ground_fact
from app.pipeline.resolve.conflicts import FactCandidate, resolve_conflict
from app.pipeline.resolve.schema import slot_for
from app.pipeline.resolve.service import rebuild
from app.pipeline.resolve.tiers import assign_tier
from app.schemas.profile import SiteProfile

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "document_extract_v1.md"
PROMPT_VERSION = "document_extract_v1"

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL = re.compile(r"https?://[^\s<>\"')]+")
_IMAGE_URL = re.compile(
    r"https?://[^\s<>\"')]+?\.(?:png|jpe?g|gif|webp)(?:\?[^\s<>\"')]*)?", re.IGNORECASE
)
_PRICE = re.compile(r"[$€£]\s?(\d[\d,]*(?:\.\d+)?)")
_ROLE_LABEL = re.compile(r"\b(?:role|title|position)\s*[:\-—]\s*([^\n]{3,80})", re.I)
_NAME_LABEL = re.compile(r"\bname\s*[:\-—]\s*([^\n]{2,80})", re.I)
_ROLE_SENTENCE = re.compile(
    r"\b(?:I am|I'm|works? as|worked as|serves? as)\s+(?:a|an)\s+([^.\n]{3,60})",
    re.I,
)
_LINE_ROLE = re.compile(
    r"^(?P<name>[A-Z][\w.'’-]+(?:\s+[A-Z][\w.'’-]+){0,3})\s*[—–|,-]\s*(?P<role>[^\n]{3,80})$"
)
_BASED = re.compile(
    r"\b(?:based in|located in|lives in)\s+([A-Z][^.\n]{1,60})", re.I
)
_OFFER = re.compile(
    r"\b(?:we|i)\s+(?:build|help|design|make|create|provide|deliver|offer)\b"
    r"[^.\n]{0,200}",
    re.I,
)
_QUOTED = re.compile(r"[\"“”]([^\"“”]{20,400})[\"“”]")
_ATTRIBUTION = re.compile(
    r"[—–-]\s*([A-Z][\w.'’-]+(?:\s+[A-Z][\w.'’-]+){0,3})(?:,\s*([^\n]{2,80}))?"
)
_MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)[a-z]*\s+(\d{4})\b",
    re.I,
)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_ROLE_WORDS = {
    "engineer",
    "designer",
    "founder",
    "developer",
    "manager",
    "scientist",
    "consultant",
    "director",
    "lead",
    "architect",
    "researcher",
    "analyst",
    "strategist",
    "producer",
    "editor",
    "writer",
    "ceo",
    "cto",
    "coo",
    "head",
}
_IMAGE_KEYS = {"visual.project_shot", "identity.portrait", "proof.client_logo"}


@dataclass(frozen=True)
class DocumentCandidate:
    key: str
    value: str
    quote: str
    chunk_id: str
    document_id: str
    filename: str
    page: int
    unit: str | None = None
    label: str = ""
    as_of: str | None = None
    permission: str | None = None
    confidence: float = 0.9
    method: str = "heuristic"


@dataclass
class ExtractionReport:
    facts_extracted: int = 0
    per_document: dict[str, int] = field(default_factory=dict)
    resolved_gaps: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _first_sentence(text: str, pattern: re.Pattern[str]) -> str | None:
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if pattern.search(sentence):
            return sentence.strip()
    for line in text.split("\n"):
        if pattern.search(line):
            return line.strip()
    return None


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:)]}\"'")


def _metric(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        facts = metric_facts_for_text(
            item.chunk.text,
            source=item.document.filename,
            source_id=item.chunk.id,
            retrieved_at=date.today(),
        )
        if not facts:
            continue
        fact = facts[0]
        return [
            DocumentCandidate(
                key=gap_key,
                value=fact.value,
                unit=fact.unit,
                label=fact.label,
                as_of=fact.as_of,
                quote=fact.source_quote or item.chunk.text[:600],
                chunk_id=item.chunk.id,
                document_id=item.document.id,
                filename=item.document.filename,
                page=item.chunk.page,
            )
        ]
    return []


def _quote(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        match = _QUOTED.search(item.chunk.text)
        if not match:
            continue
        quote = " ".join(match.group(1).split()).strip()
        if len(quote) < 20:
            continue
        context = item.chunk.text[match.end() : match.end() + 220]
        attribution = _ATTRIBUTION.search(context)
        name = role = None
        if attribution:
            name, role = attribution.group(1), attribution.group(2)
        else:
            for line in context.split("\n"):
                name, role = parse_attribution(line.strip())
                if name:
                    break
        candidates = [
            DocumentCandidate(
                key="proof.quote",
                value=quote[:600],
                label="client quote",
                quote=quote,
                chunk_id=item.chunk.id,
                document_id=item.document.id,
                filename=item.document.filename,
                page=item.chunk.page,
                permission="brand_document",
            )
        ]
        if name:
            combined = f"{name}, {role.strip(' -–—')}" if role else name
            candidates.append(
                DocumentCandidate(
                    key="attribution.quote",
                    value=combined[:600],
                    label="quote attribution",
                    quote=(attribution.group(0) if attribution else combined).strip(),
                    chunk_id=item.chunk.id,
                    document_id=item.document.id,
                    filename=item.document.filename,
                    page=item.chunk.page,
                )
            )
        return candidates
    return []


def _identity(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        text = item.chunk.text
        if gap_key == "identity.name":
            match = _NAME_LABEL.search(text)
            value = match.group(1).strip(" .,-") if match else None
            quote = match.group(0).strip() if match else None
            if not value:
                for line in text.split("\n"):
                    line_match = _LINE_ROLE.match(line.strip())
                    if not line_match:
                        continue
                    role = line_match.group("role").lower()
                    if any(word in role for word in _ROLE_WORDS):
                        value = line_match.group("name").strip()
                        quote = line.strip()
                        break
            if value:
                return [
                    DocumentCandidate(
                        key=gap_key,
                        value=value[:600],
                        label="person name",
                        quote=quote or value,
                        chunk_id=item.chunk.id,
                        document_id=item.document.id,
                        filename=item.document.filename,
                        page=item.chunk.page,
                    )
                ]
        elif gap_key == "identity.role":
            match = _ROLE_LABEL.search(text)
            value = match.group(1).strip(" .,-") if match else None
            quote = match.group(0).strip() if match else None
            if not value:
                for line in text.split("\n"):
                    line_match = _LINE_ROLE.match(line.strip())
                    if not line_match:
                        continue
                    role = line_match.group("role").strip()
                    if any(word in role.lower() for word in _ROLE_WORDS):
                        value, quote = role, line.strip()
                        break
            if not value:
                sentence = _first_sentence(text, _ROLE_SENTENCE)
                if sentence:
                    match = _ROLE_SENTENCE.search(sentence)
                    if match and any(word in match.group(1).lower() for word in _ROLE_WORDS):
                        value, quote = match.group(1).strip(" .,-"), sentence
            if value:
                return [
                    DocumentCandidate(
                        key=gap_key,
                        value=value[:600],
                        label="role",
                        quote=quote or value,
                        chunk_id=item.chunk.id,
                        document_id=item.document.id,
                        filename=item.document.filename,
                        page=item.chunk.page,
                    )
                ]
        elif gap_key == "identity.location":
            match = _BASED.search(text)
            if match:
                return [
                    DocumentCandidate(
                        key=gap_key,
                        value=match.group(1).strip(" .,-")[:600],
                        label="location",
                        quote=match.group(0).strip(),
                        chunk_id=item.chunk.id,
                        document_id=item.document.id,
                        filename=item.document.filename,
                        page=item.chunk.page,
                    )
                ]
    return []


def _contact(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        text = item.chunk.text
        if gap_key == "contact.email":
            match = _EMAIL.search(text)
            if match:
                line = text[: match.end()].rsplit("\n", 1)[-1]
                return [
                    DocumentCandidate(
                        key=gap_key,
                        value=match.group(0),
                        label="email",
                        quote=line.strip(),
                        chunk_id=item.chunk.id,
                        document_id=item.document.id,
                        filename=item.document.filename,
                        page=item.chunk.page,
                    )
                ]
        else:
            pattern = _IMAGE_URL if gap_key in _IMAGE_KEYS else _URL
            match = pattern.search(text)
            if match:
                url = _clean_url(match.group(0))
                return [
                    DocumentCandidate(
                        key=gap_key,
                        value=url,
                        label=gap_key.split(".")[-1].replace("_", " "),
                        quote=match.group(0),
                        chunk_id=item.chunk.id,
                        document_id=item.document.id,
                        filename=item.document.filename,
                        page=item.chunk.page,
                    )
                ]
    return []


def _offer(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        sentence = _first_sentence(item.chunk.text, _OFFER)
        if not sentence:
            continue
        match = _OFFER.search(sentence)
        if not match:
            continue
        value = match.group(0).strip(" .,-")
        if len(value) < 8:
            continue
        return [
            DocumentCandidate(
                key=gap_key,
                value=value[:600],
                label="offering",
                quote=sentence,
                chunk_id=item.chunk.id,
                document_id=item.document.id,
                filename=item.document.filename,
                page=item.chunk.page,
            )
        ]
    return []


def _price(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        match = _PRICE.search(item.chunk.text)
        if not match:
            continue
        sentence = _first_sentence(item.chunk.text, _PRICE) or match.group(0)
        return [
            DocumentCandidate(
                key=gap_key,
                value=match.group(1).replace(",", ""),
                unit="$",
                label="entry price",
                quote=sentence,
                chunk_id=item.chunk.id,
                document_id=item.document.id,
                filename=item.document.filename,
                page=item.chunk.page,
            )
        ]
    return []


def _recency(gap_key: str, retrieved: list[RetrievedChunk]) -> list[DocumentCandidate]:
    for item in retrieved:
        match = _MONTH.search(item.chunk.text)
        if not match:
            continue
        as_of = f"{match.group(2)}-{_MONTHS[match.group(1).lower()]:02d}"
        return [
            DocumentCandidate(
                key=gap_key,
                value=match.group(0)[:600],
                label="measured",
                as_of=as_of,
                quote=match.group(0),
                chunk_id=item.chunk.id,
                document_id=item.document.id,
                filename=item.document.filename,
                page=item.chunk.page,
            )
        ]
    return []


def heuristic_candidates(
    gap_key: str, retrieved: list[RetrievedChunk]
) -> list[DocumentCandidate]:
    if gap_key == "proof.metrics":
        return _metric(gap_key, retrieved)
    if gap_key == "commerce.price":
        return _price(gap_key, retrieved)
    if gap_key == "proof.quote":
        return _quote(gap_key, retrieved)
    if gap_key == "recency.metrics":
        return _recency(gap_key, retrieved)
    if gap_key.startswith("identity."):
        return _identity(gap_key, retrieved)
    if gap_key.startswith("contact.") or gap_key in _IMAGE_KEYS:
        return _contact(gap_key, retrieved)
    if gap_key == "offer.core":
        return _offer(gap_key, retrieved)
    return []


def _llm_candidate(
    gap_key: str,
    retrieved: list[RetrievedChunk],
    *,
    gap_class: str,
) -> DocumentCandidate | None:
    from app.pipeline.understand.llm import LLMClient, LLMError

    client = LLMClient()
    if not client.available:
        return None
    slot = slot_for(gap_key)
    payload = {
        "gap": {
            "key": gap_key,
            "class": gap_class,
            "question": slot.prompt if slot else gap_key,
        },
        "chunks": [
            {
                "chunk_id": item.chunk.id,
                "filename": item.document.filename,
                "page": item.chunk.page,
                "text": item.chunk.text,
            }
            for item in retrieved
        ],
    }
    try:
        answer = client.complete_json(
            load_prompt(), json.dumps(payload, ensure_ascii=False), temperature=0.0
        )
    except (LLMError, ValueError) as exc:
        logger.warning("document extraction LLM failed for %s: %s", gap_key, exc)
        return None

    value = answer.get("value")
    quote = answer.get("source_quote")
    if not isinstance(value, str) or not value.strip():
        return None
    if not isinstance(quote, str) or not quote.strip():
        return None

    chunk_id = answer.get("chunk_id")
    chunk = next((item for item in retrieved if item.chunk.id == chunk_id), None)
    if chunk is None:
        try:
            page = int(answer.get("page"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            page = -1
        chunk = next((item for item in retrieved if item.chunk.page == page), None)
    if chunk is None:
        chunk = next(
            (item for item in retrieved if quote.strip() in item.chunk.text), None
        )
    if chunk is None:
        return None

    accepted, reason = ground_fact(value, quote, chunk.chunk.text)
    if not accepted:
        logger.info("document LLM answer rejected for %s: %s", gap_key, reason)
        return None

    unit = answer.get("unit") if isinstance(answer.get("unit"), str) else None
    label = answer.get("label") if isinstance(answer.get("label"), str) else ""
    as_of = answer.get("as_of") if isinstance(answer.get("as_of"), str) else None
    try:
        confidence = float(answer.get("confidence", 0.9))
    except (TypeError, ValueError):
        confidence = 0.9
    return DocumentCandidate(
        key=gap_key,
        value=value.strip()[:600],
        unit=unit[:40] if unit else None,
        label=(label or gap_key)[:160],
        as_of=as_of[:40] if as_of else None,
        quote=quote.strip()[:2000],
        chunk_id=chunk.chunk.id,
        document_id=chunk.document.id,
        filename=chunk.document.filename,
        page=chunk.chunk.page,
        permission="brand_document" if gap_key == "proof.quote" else None,
        confidence=max(0.0, min(confidence, 1.0)),
        method="llm",
    )


def _audit(
    db: Session,
    run: Run,
    actor_id: str,
    action: str,
    candidate: DocumentCandidate,
    meta: dict[str, object],
) -> None:
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action=action,
            target_type="document",
            target_id=candidate.document_id,
            meta=meta,
        )
    )


def _persist(
    db: Session, run: Run, actor_id: str, candidate: DocumentCandidate
) -> tuple[FactRecord, bool]:
    existing = db.scalar(
        select(FactRecord).where(
            FactRecord.run_id == run.id,
            FactRecord.key == candidate.key,
            FactRecord.status == "accepted",
        )
    )
    if (
        existing is not None
        and existing.source_id == candidate.chunk_id
        and existing.value == candidate.value
    ):
        return existing, False

    new_fact_id = f"d_{new_id()[:12]}"
    status = "accepted"
    if existing is not None:
        resolution = resolve_conflict(
            FactCandidate(
                fact_id=existing.id,
                key=existing.key,
                value=existing.value,
                source_type=existing.source_type,
                tier=existing.tier,
                attested=existing.attested_by is not None,
            ),
            FactCandidate(
                fact_id=new_fact_id,
                key=candidate.key,
                value=candidate.value,
                source_type="document",
                tier=assign_tier("document"),
            ),
        )
        if resolution.winner_id == existing.id:
            status = "quarantined"
        else:
            existing.status = "quarantined"
            db.flush()
            _audit(
                db,
                run,
                actor_id,
                "fact.quarantined",
                candidate,
                {
                    "key": existing.key,
                    "reason": resolution.reason,
                    "replaced_by": new_fact_id,
                },
            )

    record = FactRecord(
        run_id=run.id,
        id=new_fact_id,
        tenant_id=run.tenant_id,
        key=candidate.key,
        value=candidate.value[:600],
        unit=candidate.unit,
        label=candidate.label[:160],
        as_of=candidate.as_of,
        source_type="document",
        source=candidate.filename[:2048],
        source_id=candidate.chunk_id,
        source_page=candidate.page,
        source_quote=candidate.quote[:2000],
        confidence=candidate.confidence,
        tier=assign_tier("document"),
        retrieved_at=utcnow().date(),
        published_at=None,
        permission=candidate.permission,
        status=status,
        attested_by=None,
    )
    db.add(record)
    db.flush()
    _audit(
        db,
        run,
        actor_id,
        "document.fact_extracted",
        candidate,
        {
            "key": candidate.key,
            "value": candidate.value,
            "page": candidate.page,
            "filename": candidate.filename,
            "chunk_id": candidate.chunk_id,
            "method": candidate.method,
            "status": status,
        },
    )
    return record, status == "accepted"


def extract_document_facts(
    db: Session,
    run: Run,
    actor_id: str,
    *,
    target_keys: list[str] | None = None,
    document_ids: list[str] | None = None,
) -> ExtractionReport:
    """Answer open gaps from uploaded documents, top three chunks per gap."""
    settings = get_settings()
    if not run.profile_json:
        raise DocumentError("run has no site profile; analyze the site first")
    profile = SiteProfile.model_validate(run.profile_json)
    gaps = {gap.key: gap for gap in profile.gaps}
    open_keys = [key for key, gap in gaps.items() if gap.status == "open"]
    if target_keys:
        unknown = [key for key in target_keys if key not in gaps]
        if unknown:
            raise DocumentError(f"unknown gap key {unknown[0]!r}")
        targets = [key for key in target_keys if key in open_keys]
    else:
        targets = open_keys[:8]

    report = ExtractionReport()
    created_any = False
    for key in targets:
        retrieved = search_for_gap(
            db,
            run,
            key,
            top_k=settings.retrieval_top_k,
            document_ids=document_ids,
        )[: settings.retrieval_top_chunks]
        if not retrieved:
            continue
        candidates = heuristic_candidates(key, retrieved)
        if not candidates:
            candidate = _llm_candidate(key, retrieved, gap_class=gaps[key].gap_class)
            candidates = [candidate] if candidate else []
        if not candidates:
            continue

        resolved = False
        for candidate in candidates:
            record, accepted = _persist(db, run, actor_id, candidate)
            report.facts_extracted += 1
            report.per_document[candidate.document_id] = (
                report.per_document.get(candidate.document_id, 0) + 1
            )
            if candidate.key == key and accepted:
                resolved = True
                report.resolved_gaps.append(key)
            document = db.get(Document, candidate.document_id)
            if document is not None:
                document.fact_count += 1
        created_any = created_any or resolved

    if created_any:
        rebuild(db, run)
    return report
