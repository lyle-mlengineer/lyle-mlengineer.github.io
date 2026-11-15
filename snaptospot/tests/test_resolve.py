from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.models import AuditLog, FactRecord
from app.pipeline.extract import extract_content
from app.pipeline.ingest.crawl import crawl_site
from app.pipeline.ingest.profile import build_profile
from app.pipeline.resolve.conflicts import FactCandidate, resolve_conflict
from app.pipeline.resolve.questions import generate_questions
from app.pipeline.resolve.tiers import assign_tier
from app.pipeline.understand import enrich_understanding
from tests.conftest import TestingSession, auth_headers


def _site(client: TestClient, pair: dict, url: str) -> dict:
    response = client.post(
        "/v1/sites",
        json={"url": url, "title": "Fixture"},
        headers=auth_headers(pair),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _analyze(
    client: TestClient,
    signup,
    serve_site,
    fixture: str = "no-images",
) -> tuple[dict, dict, dict]:
    pair = signup()
    site = _site(client, pair, serve_site(fixture))
    response = client.post(
        f"/v1/sites/{site['id']}/analyze", headers=auth_headers(pair)
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "succeeded", run.get("error")
    return pair, site, run


def _profile(serve_site, name: str):
    profile = build_profile(crawl_site(serve_site(name)))
    profile.understanding = enrich_understanding(profile)
    return profile


def _fact(
    *,
    run_id: str,
    tenant_id: str,
    fact_id: str,
    key: str,
    value: str,
    status: str = "accepted",
) -> FactRecord:
    return FactRecord(
        run_id=run_id,
        id=fact_id,
        tenant_id=tenant_id,
        key=key,
        value=value,
        label=key,
        source_type="site",
        source="https://example.test",
        source_quote="a verbatim sentence with the value",
        tier="A",
        retrieved_at=date.today(),
        status=status,
    )


def test_sparse_fixture_has_gaps_and_four_to_five_questions(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site)
    response = client.get(f"/v1/runs/{run['id']}/gaps", headers=auth_headers(pair))
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["coverage"] == 0.0
    assert report["ready"] is False
    assert report["blocking_open"]
    assert len(report["questions"]) == 5
    assert all(question["default"] == "skip" for question in report["questions"])
    assert all(question["unlocks"] for question in report["questions"])
    assert "offer.core" in {question["key"] for question in report["questions"]}
    assert "class" in report["questions"][0]
    assert "gap_class" not in report["questions"][0]


def test_answering_and_skipping_unblocks_render(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site)
    headers = auth_headers(pair)

    blocked = client.post(f"/v1/runs/{run['id']}/render", headers=headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["blocking_gaps"]
    assert blocked.json()["ready"] is False

    report = client.get(f"/v1/runs/{run['id']}/gaps", headers=headers).json()
    answers = []
    for question in report["questions"]:
        if question["key"] == "offer.core":
            answers.append(
                {
                    "key": "offer.core",
                    "value": "Brand strategy for small teams",
                    "attest": True,
                }
            )
        elif question["key"] == "identity.name":
            answers.append({"key": "identity.name", "value": "Quiet Studio", "attest": True})
        else:
            answers.append({"key": question["key"], "skip": True})

    response = client.post(
        f"/v1/runs/{run['id']}/answers", json={"answers": answers}, headers=headers
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["coverage"] > report["coverage"]
    assert updated["ready"] is True
    assert updated["blocking_open"] == []

    assert not [
        question
        for question in updated["questions"]
        if question["key"] in {"offer.core", "identity.name"}
    ]

    ready = client.post(f"/v1/runs/{run['id']}/render", headers=headers)
    assert ready.status_code == 202, ready.text
    assert ready.json()["status"] == "ready"
    assert ready.json()["ready"] is True

    with TestingSession() as db:
        actions = {
            row.action
            for row in db.query(AuditLog)
            .filter(AuditLog.target_type.in_(["run", "fact"]))
            .all()
        }
    assert "gap.answered" in actions
    assert "gap.skipped" in actions


def test_skipping_blocking_gaps_unblocks_render(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site)
    headers = auth_headers(pair)
    report = client.get(f"/v1/runs/{run['id']}/gaps", headers=headers).json()
    answers = [{"key": key, "skip": True} for key in report["blocking_open"]]
    assert answers

    response = client.post(
        f"/v1/runs/{run['id']}/answers", json={"answers": answers}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["ready"] is True
    assert client.post(f"/v1/runs/{run['id']}/render", headers=headers).status_code == 202


def test_override_requires_attest_and_stores_one_accepted_fact(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site, "portfolio")
    headers = auth_headers(pair)
    facts = client.get(f"/v1/runs/{run['id']}/facts", headers=headers).json()
    target = next(fact for fact in facts if fact["key"] == "asr.wer")

    no_attest = client.post(
        f"/v1/runs/{run['id']}/facts/{target['id']}",
        json={"action": "override", "value": "10.1"},
        headers=headers,
    )
    assert no_attest.status_code == 422, no_attest.text

    with_tier = client.post(
        f"/v1/runs/{run['id']}/facts/{target['id']}",
        json={"action": "override", "value": "10.1", "attest": True, "tier": "A"},
        headers=headers,
    )
    assert with_tier.status_code == 422, with_tier.text

    override = client.post(
        f"/v1/runs/{run['id']}/facts/{target['id']}",
        json={"action": "override", "value": "10.1", "attest": True},
        headers=headers,
    )
    assert override.status_code == 200, override.text
    replacement = override.json()
    assert replacement["id"] != target["id"]
    assert replacement["status"] == "accepted"
    assert replacement["tier"] == "A"
    assert replacement["source_type"] == "user_answer"
    assert replacement["attested_by"]

    after = client.get(f"/v1/runs/{run['id']}/facts", headers=headers).json()
    accepted = [
        fact
        for fact in after
        if fact["key"] == "asr.wer" and fact["status"] == "accepted"
    ]
    quarantined = [
        fact
        for fact in after
        if fact["key"] == "asr.wer" and fact["status"] == "quarantined"
    ]
    assert len(accepted) == 1
    assert accepted[0]["id"] == replacement["id"]
    assert [fact["id"] for fact in quarantined] == [target["id"]]

    with TestingSession() as db:
        actions = {row.action for row in db.query(AuditLog).all()}
    assert "fact.overridden" in actions
    assert "fact.quarantined" in actions


def test_one_accepted_fact_per_key_is_enforced_by_the_index(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site, "portfolio")
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]

    with TestingSession() as db:
        db.add(
            _fact(
                run_id=run["id"],
                tenant_id=tenant_id,
                fact_id="t_01",
                key="custom.metric",
                value="1",
            )
        )
        db.commit()

        db.add(
            _fact(
                run_id=run["id"],
                tenant_id=tenant_id,
                fact_id="t_02",
                key="custom.metric",
                value="2",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_quarantined_fact_does_not_block_a_new_accepted_fact(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site, "portfolio")
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]

    with TestingSession() as db:
        db.add(
            _fact(
                run_id=run["id"],
                tenant_id=tenant_id,
                fact_id="t_03",
                key="custom.metric",
                value="1",
                status="quarantined",
            )
        )
        db.add(
            _fact(
                run_id=run["id"],
                tenant_id=tenant_id,
                fact_id="t_04",
                key="custom.metric",
                value="2",
                status="accepted",
            )
        )
        db.commit()


def test_lazy_backfill_does_not_ask_present_facts(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site, "portfolio")
    headers = auth_headers(pair)
    with TestingSession() as db:
        db.query(FactRecord).filter(FactRecord.run_id == run["id"]).delete()
        db.commit()

    report = client.get(f"/v1/runs/{run['id']}/gaps", headers=headers).json()
    present = {fact["key"] for fact in run["content_model"]["facts"]}
    assert not ({question["key"] for question in report["questions"]} & present)

    facts = client.get(f"/v1/runs/{run['id']}/facts", headers=headers).json()
    accepted = [fact for fact in facts if fact["status"] == "accepted"]
    assert len(accepted) == len(run["content_model"]["facts"])


def test_answer_validation(client: TestClient, signup, serve_site) -> None:
    pair, _, run = _analyze(client, signup, serve_site)
    headers = auth_headers(pair)

    unknown = client.post(
        f"/v1/runs/{run['id']}/answers",
        json={"answers": [{"key": "not.a.slot", "value": "x"}]},
        headers=headers,
    )
    assert unknown.status_code == 422

    quote_without_attest = client.post(
        f"/v1/runs/{run['id']}/answers",
        json={"answers": [{"key": "proof.quote", "value": "A real quote."}]},
        headers=headers,
    )
    assert quote_without_attest.status_code == 422

    bad_metric = client.post(
        f"/v1/runs/{run['id']}/answers",
        json={"answers": [{"key": "proof.metrics", "value": "very fast", "attest": True}]},
        headers=headers,
    )
    assert bad_metric.status_code == 422

    client_tier = client.post(
        f"/v1/runs/{run['id']}/answers",
        json={
            "answers": [
                {"key": "identity.name", "value": "Quiet Studio", "tier": "A"}
            ]
        },
        headers=headers,
    )
    assert client_tier.status_code == 422


def test_fact_reject_updates_the_model(
    client: TestClient, signup, serve_site
) -> None:
    pair, _, run = _analyze(client, signup, serve_site, "portfolio")
    headers = auth_headers(pair)
    facts = client.get(f"/v1/runs/{run['id']}/facts", headers=headers).json()
    target = next(fact for fact in facts if fact["key"] == "asr.wer")

    response = client.post(
        f"/v1/runs/{run['id']}/facts/{target['id']}",
        json={"action": "reject", "reason": "stale"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"

    after = client.get(f"/v1/runs/{run['id']}/facts", headers=headers).json()
    rejected = next(fact for fact in after if fact["id"] == target["id"])
    assert rejected["status"] == "rejected"
    model = client.get(f"/v1/runs/{run['id']}", headers=headers).json()["content_model"]
    assert target["key"] not in {fact["key"] for fact in model["facts"]}


def test_resolve_endpoints_are_tenant_scoped(
    client: TestClient, signup, serve_site
) -> None:
    ada, _, run = _analyze(client, signup, serve_site, "portfolio")
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")
    headers = auth_headers(marcus)
    facts = client.get(f"/v1/runs/{run['id']}/facts", headers=auth_headers(ada)).json()

    assert client.get(f"/v1/runs/{run['id']}/gaps", headers=headers).status_code == 404
    assert client.get(f"/v1/runs/{run['id']}/facts", headers=headers).status_code == 404
    assert (
        client.post(
            f"/v1/runs/{run['id']}/answers",
            json={"answers": [{"key": "identity.name", "value": "Marcus"}]},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v1/runs/{run['id']}/facts/{facts[0]['id']}",
            json={"action": "reject"},
            headers=headers,
        ).status_code
        == 404
    )
    assert client.post(f"/v1/runs/{run['id']}/render", headers=headers).status_code == 404


@pytest.mark.parametrize("fixture", ["portfolio", "adversarial", "no-images", "spa"])
def test_question_generator_never_asks_for_a_present_fact(serve_site, fixture: str) -> None:
    profile = _profile(serve_site, fixture)
    result = extract_content(profile)
    questions = generate_questions(profile.gaps, result.content_model.facts)

    present = {fact.key for fact in result.content_model.facts}
    assert len(questions) <= 5
    assert not ({question.key for question in questions} & present)


def test_tier_assignment_is_mechanical() -> None:
    assert assign_tier("site") == "A"
    assert assign_tier("user_answer") == "A"
    assert assign_tier("document") == "A"
    assert assign_tier("web", score=0.95, corroborated=True) == "B"
    assert assign_tier("web", score=0.5) == "C"
    assert assign_tier("inference") == "D"
    with pytest.raises(ValueError):
        assign_tier("rumour")


def test_conflict_precedence() -> None:
    site = FactCandidate("f_site", "asr.wer", "11.8", "site", "A")
    attested_user = FactCandidate("f_user", "asr.wer", "10.1", "user_answer", "A", True)
    unattested_user = FactCandidate("f_user", "asr.wer", "10.1", "user_answer", "A", False)
    web = FactCandidate("f_web", "asr.wer", "9.0", "web", "C")
    document = FactCandidate("f_doc", "asr.wer", "11.0", "document", "A")
    other_web = FactCandidate("f_web2", "asr.wer", "12.0", "web", "C")

    winner = resolve_conflict(site, attested_user)
    assert winner.winner_id == "f_user"
    assert winner.quarantined_ids == ("f_site",)
    assert winner.overrides == "site"

    assert resolve_conflict(site, unattested_user).winner_id == "f_site"
    assert resolve_conflict(web, site).winner_id == "f_site"
    assert resolve_conflict(web, document).winner_id == "f_doc"

    no_winner = resolve_conflict(web, other_web)
    assert no_winner.winner_id is None
    assert set(no_winner.quarantined_ids) == {"f_web", "f_web2"}
