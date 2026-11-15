"""LLM extraction pass: validate a drafted content model against the crawl."""

import hashlib
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.pipeline.extract.candidates import CandidateSet, QuoteCandidate, slug
from app.pipeline.extract.ground import ground_fact, ground_quote, numbers
from app.schemas.content import Fact, Offering, Project
from app.schemas.profile import SiteProfile

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "extract_v1.md"
PROMPT_VERSION = "extract_v1"
_ALLOWED_STATUS = {"shipped", "active", "wip", "archived"}


@lru_cache(maxsize=1)
def load_prompt() -> tuple[str, str]:
    """Return the versioned prompt and its SHA-256 digest."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_hash() -> str:
    return load_prompt()[1]


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:limit] if cleaned else None


def _block_index(profile: SiteProfile) -> dict[str, tuple[str, str]]:
    return {
        block.id: (page.url, block.text)
        for page in profile.pages
        for block in page.blocks
    }


def _valid_key(value: str | None, fallback: str) -> str:
    candidate = (value or "").strip().lower()
    candidate = re.sub(r"[^a-z0-9_.-]+", ".", candidate).strip(".")
    return candidate[:100] or fallback


def _cited_corpus(raw_ids: Any, blocks: dict[str, tuple[str, str]]) -> tuple[list[str], str]:
    if not isinstance(raw_ids, list):
        return [], ""
    ids = [item for item in raw_ids if isinstance(item, str) and item in blocks][:6]
    corpus = " ".join(blocks[item][1] for item in ids)
    return ids, corpus


def _metric_facts(
    candidates: CandidateSet,
    payload: dict[str, Any],
    blocks: dict[str, tuple[str, str]],
    retrieved_at: date,
) -> None:
    metrics = payload.get("metrics")
    if not isinstance(metrics, list):
        return

    for entry in metrics[:12]:
        if not isinstance(entry, dict):
            continue
        value = _text(entry.get("value"), 120)
        if value is None:
            continue
        unit = _text(entry.get("unit"), 40)
        label = _text(entry.get("label"), 160) or unit or "metric"
        source_id = entry.get("source_id")
        source_quote = _text(entry.get("source_quote"), 2000) or ""
        key = _valid_key(_text(entry.get("key"), 120), f"metric.{slug(label)}")

        if not isinstance(source_id, str) or source_id not in blocks:
            candidates.reject(
                key=key,
                value=value,
                unit=unit,
                source_id=source_id if isinstance(source_id, str) else None,
                source_quote=source_quote,
                reason="no_source",
            )
            continue
        source, source_text = blocks[source_id]
        accepted, reason = ground_fact(value, source_quote, source_text)
        if not accepted:
            candidates.reject(
                key=key,
                value=value,
                unit=unit,
                source_id=source_id,
                source_quote=source_quote,
                reason=reason or "invalid",
            )
            continue

        existing = next((fact for fact in candidates.facts if fact.key == key), None)
        if existing is not None:
            if existing.value == value:
                continue
            candidates.conflicts.append(key)
            candidates.reject(
                key=key,
                value=value,
                unit=unit,
                source_id=source_id,
                source_quote=source_quote,
                reason="conflict",
            )
            continue

        candidates.facts.append(
            Fact(
                id=f"d_{len(candidates.facts) + 1:02d}",
                key=key,
                value=value,
                unit=unit,
                label=label,
                source_type="site",
                source=source,
                source_id=source_id,
                source_quote=source_quote,
                confidence=0.95,
                tier="A",
                retrieved_at=retrieved_at,
            )
        )


def _offering_candidates(
    candidates: CandidateSet,
    payload: dict[str, Any],
    blocks: dict[str, tuple[str, str]],
    metric_ids: dict[str, str],
) -> None:
    offerings = payload.get("offerings")
    if not isinstance(offerings, list):
        return

    for entry in offerings[:4]:
        if not isinstance(entry, dict):
            continue
        title = _text(entry.get("title"), 120)
        if title is None:
            continue
        source_ids, corpus = _cited_corpus(entry.get("source_ids"), blocks)
        if not source_ids:
            continue
        one_liner = _text(entry.get("one_liner"), 320) or title
        if not numbers(one_liner) <= numbers(corpus):
            one_liner = title
        if not numbers(title) <= numbers(corpus):
            continue

        tools: list[str] = []
        raw_tools = entry.get("tools")
        if isinstance(raw_tools, list):
            tools = [
                item for item in (_text(tool, 40) for tool in raw_tools) if item
            ][:12]
        metric_key = _text(entry.get("metric_fact_key"), 120)
        candidates.offerings.append(
            Offering(
                key=f"offer.{slug(title)}",
                title=title,
                one_liner=one_liner,
                metric_fact_id=metric_ids.get(metric_key) if metric_key else None,
                tools=tools,
            )
        )


def _project_candidates(
    candidates: CandidateSet,
    payload: dict[str, Any],
    blocks: dict[str, tuple[str, str]],
    metric_ids: dict[str, str],
) -> None:
    projects = payload.get("projects")
    if not isinstance(projects, list):
        return

    for entry in projects[:8]:
        if not isinstance(entry, dict):
            continue
        name = _text(entry.get("name"), 100)
        if name is None:
            continue
        source_ids, corpus = _cited_corpus(entry.get("source_ids"), blocks)
        if not source_ids:
            continue
        if not numbers(name) <= numbers(corpus):
            continue
        blurb = _text(entry.get("blurb"), 240) or ""
        if not numbers(blurb) <= numbers(corpus):
            blurb = ""
        status = _text(entry.get("status"), 20)
        badge = _text(entry.get("badge_fact_key"), 120)
        candidates.projects.append(
            Project(
                name=name,
                blurb=blurb,
                badge_fact_id=metric_ids.get(badge) if badge else None,
                status=status if status in _ALLOWED_STATUS else "shipped",
            )
        )


def _quote_candidate(
    candidates: CandidateSet,
    payload: dict[str, Any],
    blocks: dict[str, tuple[str, str]],
    retrieved_at: date,
) -> None:
    entry = payload.get("quote")
    if not isinstance(entry, dict):
        return
    text = _text(entry.get("text"), 600)
    source_id = entry.get("source_id")
    permission = _text(entry.get("permission"), 40)
    if text is None or permission != "published_on_site":
        return
    if not isinstance(source_id, str) or source_id not in blocks:
        candidates.reject(
            key="proof.quote",
            value=text,
            source_id=source_id if isinstance(source_id, str) else None,
            source_quote=text,
            reason="no_source",
        )
        return
    source, source_text = blocks[source_id]
    accepted, reason = ground_quote(text, source_text)
    if not accepted:
        candidates.reject(
            key="proof.quote",
            value=text,
            source_id=source_id,
            source_quote=text,
            reason=reason or "no_source",
        )
        return
    fact = Fact(
        id=f"d_{len(candidates.facts) + 1:02d}",
        key="proof.quote",
        value=text,
        label="client quote",
        source_type="site",
        source=source,
        source_id=source_id,
        source_quote=text,
        confidence=0.95,
        tier="A",
        retrieved_at=retrieved_at,
        permission="published_on_site",
    )
    candidates.facts.append(fact)
    candidates.quote = QuoteCandidate(
        fact=fact,
        attribution=_text(entry.get("attribution"), 120),
        role=_text(entry.get("role"), 160),
    )


def parse_draft(
    payload: dict[str, Any],
    profile: SiteProfile,
    retrieved_at: date,
) -> CandidateSet:
    """Validate an LLM draft. Every returned candidate cites a crawled block."""
    candidates = CandidateSet()
    blocks = _block_index(profile)
    _metric_facts(candidates, payload, blocks, retrieved_at)
    metric_ids = {fact.key: fact.id for fact in candidates.facts}
    _offering_candidates(candidates, payload, blocks, metric_ids)
    _project_candidates(candidates, payload, blocks, metric_ids)
    _quote_candidate(candidates, payload, blocks, retrieved_at)
    return candidates
