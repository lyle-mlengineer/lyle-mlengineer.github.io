"""Assign trust tiers mechanically.

The extraction model never supplies a tier. It supplies a source type and,
optionally, a source score; this module turns that into the tier the renderer
reads. Client-supplied tiers are rejected by the request schema and by
``reject_client_tier`` for callers that pass raw mappings.
"""

from collections.abc import Mapping

from app.schemas.content import Tier


def assign_tier(
    source_type: str,
    *,
    score: float | None = None,
    corroborated: bool = False,
) -> Tier:
    """Return the trust tier for a fact source.

    ``site``, ``user_answer`` and ``document`` are first-party and become tier
    A. A public web source becomes B only when it is strong enough to support a
    card; everything else from the web is C (copy-only). Inference is D.
    """
    if source_type in {"site", "user_answer", "document"}:
        return "A"
    if source_type == "web":
        effective = score if score is not None else 0.0
        if effective >= 0.85 and corroborated:
            return "B"
        if effective >= 0.9:
            return "B"
        return "C"
    if source_type == "inference":
        return "D"
    raise ValueError(f"unknown source_type {source_type!r}")


def reject_client_tier(payload: Mapping[str, object]) -> None:
    """Guard raw mappings that bypass the Pydantic schema."""
    if "tier" in payload or "trust_tier" in payload:
        raise ValueError("tier is assigned by the resolver, not by the client")
