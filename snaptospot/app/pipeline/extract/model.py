"""Assemble a renderable ContentModel from grounded candidates."""

from urllib.parse import urlparse

from app.pipeline.extract.candidates import CandidateSet, supported_numbers
from app.pipeline.extract.deterministic import ensure_understanding
from app.schemas.content import CTA, ContentModel, Fact, Offering, Project, Proof, QuoteRef
from app.schemas.profile import SiteProfile

_PROOF_ORDER = (
    "work.projects",
    "asr.wer",
    "product.creators",
    "product.retention",
    "system.latency",
    "asr.voices",
    "media.render_seconds",
)


def _clean(text: str, facts: list[Fact], limit: int, fallback: str = "") -> str:
    if not text or not supported_numbers(text, facts):
        return fallback
    return text[:limit]


def _proof_facts(facts: list[Fact]) -> list[Fact]:
    candidates = [fact for fact in facts if fact.key != "proof.quote" and fact.tier in {"A", "B"}]
    ranked = sorted(
        candidates,
        key=lambda fact: (
            _PROOF_ORDER.index(fact.key) if fact.key in _PROOF_ORDER else len(_PROOF_ORDER),
            fact.id,
        ),
    )
    return ranked[:4]


def _cta_label(profile: SiteProfile) -> str:
    host = urlparse(profile.url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    label = host or profile.title or profile.url
    return label[:120]


def build_content_model(profile: SiteProfile, candidates: CandidateSet) -> ContentModel:
    reading = ensure_understanding(profile)
    facts = [fact for fact in candidates.facts if fact.tier in {"A", "B"}]
    fact_ids = {fact.id for fact in facts}

    thesis_source = (
        reading.value_proposition.text if reading.value_proposition else profile.title
    )
    thesis = _clean(
        thesis_source,
        facts,
        320,
        fallback="Selected work and capabilities",
    )
    audience = _clean(reading.audience or "", facts, 200)

    offerings: list[Offering] = []
    for offering in candidates.offerings:
        if len(offerings) >= 4:
            break
        title = _clean(offering.title, facts, 120)
        if not title:
            continue
        one_liner = _clean(offering.one_liner, facts, 320, fallback=title)
        metric_id = offering.metric_fact_id
        if metric_id not in fact_ids:
            metric_id = None
        offerings.append(
            Offering(
                key=offering.key,
                title=title,
                one_liner=one_liner,
                metric_fact_id=metric_id,
                tools=offering.tools[:12],
            )
        )

    projects: list[Project] = []
    for project in candidates.projects:
        if len(projects) >= 8:
            break
        name = _clean(project.name, facts, 100)
        if not name:
            continue
        blurb = _clean(project.blurb, facts, 240)
        badge_id = project.badge_fact_id
        if badge_id not in fact_ids:
            badge_id = None
        projects.append(
            Project(
                name=name,
                blurb=blurb,
                badge_fact_id=badge_id,
                image=project.image,
                status=project.status,
            )
        )

    proof = [
        Proof(fact_id=fact.id, emphasis="lead" if index == 0 else "normal")
        for index, fact in enumerate(_proof_facts(facts))
    ]

    quote: QuoteRef | None = None
    if candidates.quote is not None and candidates.quote.fact.id in fact_ids:
        quote = QuoteRef(
            fact_id=candidates.quote.fact.id,
            attribution=candidates.quote.attribution,
            role=candidates.quote.role,
        )

    arc = ["hook", "capability", "evidence", "proof"] if proof else ["hook", "capability"]
    if quote is not None and "proof" not in arc:
        arc.append("proof")

    return ContentModel(
        thesis=thesis,
        audience=audience,
        arc=arc,
        facts=facts,
        offerings=offerings,
        projects=projects,
        proof=proof,
        quote=quote,
        cta=CTA(url=profile.url, label=_cta_label(profile)),
        disclaimers=[],
    )
