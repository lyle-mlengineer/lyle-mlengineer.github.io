import logging

from app.config import get_settings
from app.pipeline.understand.heuristics import heuristic_understanding
from app.pipeline.understand.llm import (
    LLMClient,
    LLMError,
    build_messages,
    parse_understanding,
)
from app.schemas.profile import SiteProfile, Understanding

logger = logging.getLogger(__name__)


def enrich_understanding(
    profile: SiteProfile,
    client: LLMClient | None = None,
) -> Understanding:
    """Read meaning out of the crawled site.

    An LLM is used when one is configured; otherwise deterministic heuristics
    produce the same shape. LLM output is validated against the block tree and
    silently discarded if it is unsupported, so the fallback is always safe.
    """
    settings = get_settings()
    active = client
    if active is None and settings.llm_api_key:
        active = LLMClient()

    if active is not None and active.available:
        try:
            system, user = build_messages(profile)
            payload = active.complete_json(system, user)
            understanding = parse_understanding(payload, profile)
            if understanding is not None:
                return understanding
            logger.info("LLM understanding had no supported claims; using heuristics")
        except (LLMError, ValueError, TypeError) as exc:
            logger.warning("LLM understanding failed; using heuristics: %s", exc)

    return heuristic_understanding(profile)
