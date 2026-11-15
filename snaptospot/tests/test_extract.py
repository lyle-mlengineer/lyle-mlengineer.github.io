import hashlib

from app.pipeline.extract import extract_content
from app.pipeline.extract.ground import ground_fact
from app.pipeline.extract.llm import PROMPT_VERSION, load_prompt
from app.pipeline.ingest.crawl import crawl_site
from app.pipeline.ingest.profile import build_profile
from app.pipeline.understand import enrich_understanding

METRIC_KEYS = {
    "work.projects",
    "media.render_seconds",
    "asr.wer",
    "system.latency",
    "asr.voices",
    "product.creators",
    "product.retention",
}


def _profile(serve_site, name: str = "portfolio"):
    profile = build_profile(crawl_site(serve_site(name)))
    profile.understanding = enrich_understanding(profile)
    return profile


def _run(serve_site, name: str = "portfolio", client=None):
    profile = _profile(serve_site, name)
    return profile, extract_content(profile, client=client)


class FakeClient:
    available = True

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def complete_json(self, system: str, user: str) -> dict:
        self.calls += 1
        return self.payload


def test_portfolio_has_seven_grounded_metrics(serve_site) -> None:
    profile, result = _run(serve_site)
    model = result.content_model
    metrics = {fact.key: fact for fact in model.facts if fact.key != "proof.quote"}

    assert set(metrics) == METRIC_KEYS
    assert result.rejected == []
    assert result.conflicts == []
    assert result.llm_used is False

    expected = {
        "work.projects": "7",
        "media.render_seconds": "22",
        "asr.wer": "11.8",
        "system.latency": "310",
        "asr.voices": "42",
        "product.creators": "2,100",
        "product.retention": "61",
    }
    blocks = {
        block.id: block.text for page in profile.pages for block in page.blocks
    }
    for key, value in expected.items():
        fact = metrics[key]
        assert fact.value == value
        assert fact.tier == "A"
        assert fact.source_type == "site"
        assert fact.source_quote
        accepted, reason = ground_fact(
            fact.value, fact.source_quote, blocks[fact.source_id]
        )
        assert accepted, reason
    assert metrics["asr.wer"].source_quote.endswith("down from 23.4%.")
    assert metrics["product.creators"].as_of == "2026-10"


def test_deterministic_pass_collects_contact_and_client_signals(serve_site) -> None:
    _, result = _run(serve_site)
    assert "lyleokoth.mlengineer@gmail.com" in result.signals["emails"]
    assert any("797" in phone for phone in result.signals["phones"])
    assert "2026-10" in result.signals["dates"]
    assert any("Kite Learning" in client for client in result.signals["clients"])


def test_portfolio_quote_and_proof_are_grounded(serve_site) -> None:
    profile, result = _run(serve_site)
    model = result.content_model

    assert model.quote is not None
    quote_fact = next(fact for fact in model.facts if fact.id == model.quote.fact_id)
    assert quote_fact.permission == "published_on_site"
    assert "narration pipeline" in quote_fact.value
    assert model.quote.attribution == "Daniel Reyes"
    assert "Kite Learning" in (model.quote.role or "")

    assert len(model.proof) == 4
    assert model.proof[0].emphasis == "lead"
    lead = next(fact for fact in model.facts if fact.id == model.proof[0].fact_id)
    assert lead.key == "work.projects"

    assert len(model.offerings) <= 4
    assert len(model.projects) <= 8
    project_names = {project.name for project in model.projects}
    assert "SautiFlow" in project_names
    assert "Swahili ASR" in project_names


def test_extraction_is_deterministic(serve_site) -> None:
    profile = _profile(serve_site)
    first = extract_content(profile)
    second = extract_content(profile)
    assert first.content_model.model_dump() == second.content_model.model_dump()
    assert first.rejected == second.rejected


def test_prompt_is_versioned_and_hashed() -> None:
    text, digest = load_prompt()
    assert PROMPT_VERSION == "extract_v1"
    assert "source_quote" in text
    assert digest == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert len(digest) == 64


def test_llm_rounding_is_rejected(serve_site) -> None:
    profile = _profile(serve_site, "adversarial")
    block = next(
        block for block in profile.pages[0].blocks if "60% faster" in block.text
    )
    payload = {
        "metrics": [
            {
                "key": "performance.speed",
                "value": "2",
                "unit": "x faster",
                "label": "speedup",
                "source_id": block.id,
                "source_quote": block.text,
            }
        ]
    }
    result = extract_content(profile, client=FakeClient(payload))

    assert result.llm_used is True
    assert [fact.value for fact in result.content_model.facts] == ["60"]
    assert any(
        rejected.reason == "number_mismatch" and rejected.value == "2"
        for rejected in result.rejected
    )
    assert all(fact.value != "2" for fact in result.content_model.facts)


def test_llm_offering_with_unsupported_number_is_neutralised(serve_site) -> None:
    profile = _profile(serve_site, "adversarial")
    block = next(
        block for block in profile.pages[0].blocks if "60% faster" in block.text
    )
    payload = {
        "offerings": [
            {
                "title": "Compiler speed",
                "one_liner": "Ships 2x faster than the previous release.",
                "source_ids": [block.id],
            }
        ]
    }
    result = extract_content(profile, client=FakeClient(payload))
    offering = next(
        item for item in result.content_model.offerings if item.title == "Compiler speed"
    )
    assert offering.one_liner == "Compiler speed"


def test_llm_quote_must_be_verbatim(serve_site) -> None:
    profile = _profile(serve_site, "adversarial")
    block = profile.pages[0].blocks[-1]
    payload = {
        "quote": {
            "text": "This praise was never on the page.",
            "source_id": block.id,
            "attribution": "A Person",
            "role": "Founder",
            "permission": "published_on_site",
        }
    }
    result = extract_content(profile, client=FakeClient(payload))
    assert result.content_model.quote is None
    assert any(rejected.reason == "no_source" for rejected in result.rejected)


def test_sparse_site_declares_expected_gap_classes(serve_site) -> None:
    profile, result = _run(serve_site, "no-images")
    assert result.content_model.facts == []
    classes = {gap.gap_class for gap in profile.gaps}
    assert {"identity", "offer", "proof", "visual"} <= classes
    keys = {gap.key for gap in profile.gaps}
    assert {"identity.portrait", "proof.metrics", "proof.quote", "visual.project_shot"} <= keys

    serialized = profile.gaps[0].model_dump(by_alias=True)
    assert "class" in serialized
    assert "gap_class" not in serialized
