"""Merge deterministic candidates with an LLM draft.

Deterministic candidates win every tie: they already cite a crawled block. The
LLM may add a fact only when it supplies a verbatim quote for a source the
crawler saw, and a second value for an occupied key is quarantined.
"""

from app.pipeline.extract.candidates import CandidateSet


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _remap_refs(candidates: CandidateSet, id_map: dict[str, str]) -> None:
    available = {fact.id for fact in candidates.facts}
    for offering in candidates.offerings:
        if offering.metric_fact_id:
            offering.metric_fact_id = id_map.get(
                offering.metric_fact_id, offering.metric_fact_id
            )
            if offering.metric_fact_id not in available:
                offering.metric_fact_id = None
    for project in candidates.projects:
        if project.badge_fact_id:
            project.badge_fact_id = id_map.get(
                project.badge_fact_id, project.badge_fact_id
            )
            if project.badge_fact_id not in available:
                project.badge_fact_id = None


def merge_candidates(
    deterministic: CandidateSet,
    draft: CandidateSet | None,
) -> CandidateSet:
    merged = CandidateSet(
        facts=list(deterministic.facts),
        offerings=list(deterministic.offerings),
        projects=list(deterministic.projects),
        quote=deterministic.quote,
        rejected=list(deterministic.rejected),
        conflicts=list(deterministic.conflicts),
        signals={key: list(values) for key, values in deterministic.signals.items()},
    )
    if draft is None:
        _remap_refs(merged, {})
        return merged

    by_key = {fact.key: fact for fact in merged.facts}
    id_map: dict[str, str] = {}

    for fact in draft.facts:
        existing = by_key.get(fact.key)
        if existing is not None:
            if existing.value == fact.value:
                id_map[fact.id] = existing.id
                continue
            merged.conflicts.append(fact.key)
            merged.reject(
                key=fact.key,
                value=fact.value,
                unit=fact.unit,
                source_id=fact.source_id,
                source_quote=fact.source_quote,
                reason="conflict",
            )
            continue
        merged.facts.append(fact)
        by_key[fact.key] = fact
        id_map[fact.id] = fact.id

    seen_offerings = {offering.title.lower() for offering in merged.offerings}
    for offering in draft.offerings:
        if len(merged.offerings) >= 4:
            break
        if offering.title.lower() in seen_offerings:
            continue
        seen_offerings.add(offering.title.lower())
        merged.offerings.append(offering)

    seen_projects = {project.name.lower() for project in merged.projects}
    for project in draft.projects:
        if len(merged.projects) >= 8:
            break
        if project.name.lower() in seen_projects:
            continue
        seen_projects.add(project.name.lower())
        merged.projects.append(project)

    if merged.quote is None and draft.quote is not None:
        merged.quote = draft.quote
    elif merged.quote is not None and draft.quote is not None:
        merged.reject(
            key="proof.quote",
            value=draft.quote.fact.value,
            source_id=draft.quote.fact.source_id,
            source_quote=draft.quote.fact.source_quote,
            reason="conflict",
        )

    merged.rejected.extend(draft.rejected)
    merged.conflicts = _unique(merged.conflicts)
    _remap_refs(merged, id_map)
    return merged
