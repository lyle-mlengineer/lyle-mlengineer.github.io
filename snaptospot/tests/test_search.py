import json
import logging
from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import get_settings
from app.models import WebQuery
from app.models.base import utcnow
from app.pipeline.resolve import search as search_module
from app.pipeline.resolve.search import (
    SearchHit,
    build_queries,
    find_cached_query,
    score_source,
)
from app.schemas.profile import SiteProfile
from tests.conftest import TestingSession, auth_headers


class StubProvider:
    name = "brave"

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls
        self.calls = 0

    def search(self, query: str, limit: int) -> list[SearchHit]:
        self.calls += 1
        return [
            SearchHit(title=f"Result {index}", url=url)
            for index, url in enumerate(self.urls[:limit], start=1)
        ]


def _run(client: TestClient, signup, serve_site) -> tuple[dict, dict]:
    pair = signup()
    response = client.post(
        "/v1/sites",
        json={"url": serve_site("no-images"), "title": "Sparse"},
        headers=auth_headers(pair),
    )
    assert response.status_code == 201, response.text
    site = response.json()
    response = client.post(
        f"/v1/sites/{site['id']}/analyze", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "succeeded", run.get("error")
    return pair, run


def _configure(monkeypatch, urls: list[str]) -> StubProvider:
    settings = get_settings()
    monkeypatch.setattr(settings, "search_provider", "brave")
    monkeypatch.setattr(settings, "search_api_key", "test-key")
    provider = StubProvider(urls)
    monkeypatch.setattr(
        search_module, "build_provider", lambda settings=None: provider
    )
    return provider


def test_injection_fixture_produces_null_extraction(
    client: TestClient, signup, serve_site, monkeypatch, caplog
) -> None:
    pair, run = _run(client, signup, serve_site)
    base = serve_site("web-source")
    _configure(monkeypatch, [f"{base}/injection.html"])
    caplog.set_level(logging.WARNING, logger="app.pipeline.resolve.web")

    response = client.post(
        f"/v1/runs/{run['id']}/search", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "searched"
    assert body["facts"] == []
    assert any("injection" in warning.lower() for warning in body["warnings"])
    assert "prompt injection ignored" in caplog.text.lower()

    serialized = json.dumps(body)
    assert "print the system prompt" not in serialized
    assert "fabricated sentence" not in serialized
    assert "source_quote" not in serialized

    with TestingSession() as db:
        statuses = {row.status for row in db.query(WebQuery).all()}
    assert "injection" in statuses


def test_undated_metric_is_tier_c_and_not_renderable(
    client: TestClient, signup, serve_site, monkeypatch
) -> None:
    pair, run = _run(client, signup, serve_site)
    base = serve_site("web-source")
    _configure(monkeypatch, [f"{base}/undated.html"])

    response = client.post(
        f"/v1/runs/{run['id']}/search", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    metric = next(fact for fact in body["facts"] if fact["key"] == "proof.metrics")
    assert metric["source_type"] == "web"
    assert metric["tier"] == "C"
    assert metric["published_at"] is None
    assert metric["source"].endswith("/undated.html")

    refreshed = client.get(
        f"/v1/runs/{run['id']}", headers=auth_headers(pair)
    ).json()
    proof_ids = {item["fact_id"] for item in refreshed["content_model"]["proof"]}
    assert metric["id"] not in proof_ids

    gaps = client.get(
        f"/v1/runs/{run['id']}/gaps", headers=auth_headers(pair)
    ).json()
    assert gaps["web_search"] == "searched"


def test_dated_primary_source_becomes_tier_b(
    client: TestClient, signup, serve_site, monkeypatch
) -> None:
    pair, run = _run(client, signup, serve_site)
    base = serve_site("web-source")
    _configure(monkeypatch, [f"{base}/dated.html"])

    response = client.post(
        f"/v1/runs/{run['id']}/search", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    metric = next(fact for fact in body["facts"] if fact["key"] == "proof.metrics")
    assert metric["tier"] == "B"
    assert metric["published_at"] == "2026-06-01"
    assert metric["as_of"] == "2026-06"
    assert metric["source"].endswith("/dated.html")
    assert metric["source_quote"]

    refreshed = client.get(
        f"/v1/runs/{run['id']}", headers=auth_headers(pair)
    ).json()
    proof_ids = {item["fact_id"] for item in refreshed["content_model"]["proof"]}
    assert metric["id"] in proof_ids


def test_search_disabled_leaves_gaps_and_labels_run(
    client: TestClient, signup, serve_site
) -> None:
    pair, run = _run(client, signup, serve_site)
    response = client.post(
        f"/v1/runs/{run['id']}/search", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "disabled"
    assert body["facts"] == []
    assert "disabled" in body["label"].lower()
    assert body["gaps"]["questions"]
    assert body["gaps"]["web_search"] == "disabled"

    refreshed = client.get(
        f"/v1/runs/{run['id']}", headers=auth_headers(pair)
    ).json()
    assert refreshed["stats"]["web_search"] == "disabled"
    assert not [
        fact for fact in refreshed["content_model"]["facts"] if fact["source_type"] == "web"
    ]

    with TestingSession() as db:
        assert db.query(WebQuery).count() == 0


def test_query_builder_caps_six_and_one_per_class(
    client: TestClient, signup, serve_site
) -> None:
    _, run = _run(client, signup, serve_site)
    profile = SiteProfile.model_validate(run["profile"])
    plans = build_queries(profile, profile.gaps)

    assert 1 <= len(plans) <= 6
    assert len({plan.gap_class for plan in plans}) == len(plans)
    assert all(plan.query for plan in plans)
    assert all(plan.domain for plan in plans)
    assert "contact" not in {plan.gap_class for plan in plans}
    assert len(build_queries(profile, profile.gaps, limit=1)) == 1


def test_score_formula_and_seven_day_cache(
    client: TestClient, signup, serve_site, monkeypatch
) -> None:
    score = score_source(
        url="https://github.com/example/repo",
        text="The project reached 2,100 creators.",
        published_at=utcnow().date(),
        site_url="https://example.com",
        accepted_values=["2,100"],
        entity_names=["Example"],
        metric=True,
    )
    assert abs(
        score.total
        - (
            0.35 * 0.95
            + 0.25 * 0.0
            + 0.20 * 1.0
            + 0.20 * 1.0
        )
    ) < 1e-6
    assert score.domain_quality == 0.95
    assert score.first_party == 0.0
    assert score.corroboration == 1.0

    pair, run = _run(client, signup, serve_site)
    base = serve_site("web-source")
    _configure(monkeypatch, [f"{base}/dated.html"])
    response = client.post(
        f"/v1/runs/{run['id']}/search", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text

    with TestingSession() as db:
        row = db.query(WebQuery).first()
        assert row is not None
        cached = find_cached_query(
            db,
            tenant_id=row.tenant_id,
            domain=row.domain,
            query_hash_value=row.query_hash,
            days=7,
        )
        assert cached is not None
        row.created_at = utcnow() - timedelta(days=8)
        db.commit()
        assert (
            find_cached_query(
                db,
                tenant_id=row.tenant_id,
                domain=row.domain,
                query_hash_value=row.query_hash,
                days=7,
            )
            is None
        )
