"""Turn a crawled profile into a grounded ContentModel and a gap list."""

import json
import logging
from dataclasses import dataclass
from datetime import date

from pydantic import ValidationError

from app.config import get_settings
from app.models.base import utcnow
from app.pipeline.extract.candidates import CandidateSet
from app.pipeline.extract.deterministic import deterministic_candidates
from app.pipeline.extract.llm import PROMPT_VERSION, load_prompt, parse_draft
from app.pipeline.extract.merge import merge_candidates
from app.pipeline.extract.model import build_content_model
from app.pipeline.extract.requirements import evaluate_gaps
from app.pipeline.understand.llm import LLMClient, LLMError, compressed_site
from app.schemas.content import ContentModel, RejectedFact
from app.schemas.profile import SiteProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionResult:
    content_model: ContentModel
    rejected: list[RejectedFact]
    conflicts: list[str]
    signals: dict[str, list[str]]
    model_versions: dict[str, str]
    llm_used: bool


def extract_content(
    profile: SiteProfile,
    client: LLMClient | None = None,
    retrieved_at: date | None = None,
) -> ExtractionResult:
    """Run the deterministic pass, optionally merge an LLM draft, then ground.

    The LLM is an optional contributor, never the source of truth: a draft fact
    is accepted only when its quote exists in a cited block and every number is
    present in that quote.
    """
    settings = get_settings()
    retrieved = retrieved_at or utcnow().date()
    prompt, digest = load_prompt()

    deterministic = deterministic_candidates(profile, retrieved)

    active = client
    if active is None and settings.llm_api_key:
        active = LLMClient()

    draft: CandidateSet | None = None
    llm_used = False
    if active is not None and active.available:
        try:
            payload = active.complete_json(
                prompt,
                json.dumps(compressed_site(profile), ensure_ascii=False, indent=1),
            )
            draft = parse_draft(payload, profile, retrieved)
            llm_used = True
        except (LLMError, ValidationError, ValueError, TypeError) as exc:
            logger.warning("LLM extraction failed; using deterministic pass: %s", exc)

    merged = merge_candidates(deterministic, draft)
    content_model = build_content_model(profile, merged)
    profile.gaps = evaluate_gaps(
        profile,
        content_model,
        conflicts=merged.conflicts,
        today=retrieved,
    )

    versions = {
        "extract_prompt": PROMPT_VERSION,
        "prompt_sha256": digest,
        "extractor": "v1",
        "llm": settings.llm_model if llm_used else "heuristic",
    }
    logger.info(
        "Extracted %d facts, %d rejected, %d gaps, llm=%s",
        len(content_model.facts),
        len(merged.rejected),
        len(profile.gaps),
        llm_used,
    )
    return ExtractionResult(
        content_model=content_model,
        rejected=merged.rejected,
        conflicts=merged.conflicts,
        signals=merged.signals,
        model_versions=versions,
        llm_used=llm_used,
    )
