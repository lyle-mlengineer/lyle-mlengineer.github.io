from app.pipeline.ingest.crawl import crawl_site
from app.pipeline.ingest.profile import build_profile
from app.pipeline.understand import enrich_understanding
from app.pipeline.understand.heuristics import heuristic_understanding
from app.pipeline.understand.llm import parse_understanding


def _profile(serve_site):
    return build_profile(crawl_site(serve_site("portfolio")))


def test_heuristics_understand_the_site(serve_site) -> None:
    profile = _profile(serve_site)
    reading = heuristic_understanding(profile)
    assert reading.value_proposition is not None
    assert "speech ai" in reading.value_proposition.text.lower()
    assert reading.value_proposition.source_id
    assert {"home", "about", "work", "contact"} <= {role.role for role in reading.page_roles}
    assert any("technical" == tone for tone in reading.tone)
    assert any(offering.title == "What I do" for offering in reading.offerings)
    assert reading.ai_generated is False


def test_heuristics_are_deterministic(serve_site) -> None:
    profile = _profile(serve_site)
    assert heuristic_understanding(profile) == heuristic_understanding(profile)


def test_llm_output_with_unsupported_numbers_is_rejected(serve_site) -> None:
    profile = _profile(serve_site)
    home = next(page for page in profile.pages if page.id == "home")
    heading_id = home.headings[0].block_id

    payload = {
        "value_proposition": {"text": "Speech models shipped in 3 days", "source_id": heading_id},
        "audience": "hiring managers",
        "tone": ["technical", "confident"],
        "page_roles": [{"url": "https://not-crawled.example/", "role": "pricing"}],
        "offerings": [
            {"title": "Ghost offering", "summary": "Not on the site", "source_ids": ["b999999"]},
            {
                "title": "Speech AI",
                "summary": "Transcription and synthesis for African languages.",
                "source_ids": [home.headings[0].block_id],
            },
        ],
    }
    reading = parse_understanding(payload, profile)
    assert reading is not None
    assert reading.value_proposition is None
    assert reading.page_roles == []
    assert [offering.title for offering in reading.offerings] == ["Speech AI"]
    assert reading.ai_generated is True


def test_unsupported_llm_payload_falls_back(serve_site) -> None:
    profile = _profile(serve_site)

    class FakeClient:
        available = True

        def complete_json(self, system: str, user: str) -> dict:
            return {"value_proposition": None, "offerings": [], "page_roles": []}

    reading = enrich_understanding(profile, client=FakeClient())
    assert reading.ai_generated is False
    assert reading.value_proposition is not None


def test_valid_llm_payload_is_used(serve_site) -> None:
    profile = _profile(serve_site)
    home = next(page for page in profile.pages if page.id == "home")
    paragraph = next(block for block in home.blocks if block.kind == "p")

    class FakeClient:
        available = True

        def complete_json(self, system: str, user: str) -> dict:
            return {
                "value_proposition": {
                    "text": "Speech AI that ships for African languages.",
                    "source_id": paragraph.id,
                },
                "audience": "voice AI teams",
                "tone": ["technical", "direct"],
                "page_roles": [{"url": home.url, "role": "home"}],
                "offerings": [
                    {
                        "title": "Speech AI",
                        "summary": "Transcription and synthesis for African languages.",
                        "source_ids": [paragraph.id],
                    }
                ],
            }

    reading = enrich_understanding(profile, client=FakeClient())
    assert reading.ai_generated is True
    assert reading.value_proposition is not None
    assert reading.value_proposition.source_id == paragraph.id
    assert [offering.title for offering in reading.offerings] == ["Speech AI"]
