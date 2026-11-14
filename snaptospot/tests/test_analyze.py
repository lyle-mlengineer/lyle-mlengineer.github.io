from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _site(client: TestClient, pair: dict, url: str) -> dict:
    response = client.post(
        "/v1/sites",
        json={"url": url, "title": "Fixture"},
        headers=auth_headers(pair),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_analyze_creates_profile_and_run(client: TestClient, signup, serve_site) -> None:
    pair = signup()
    site = _site(client, pair, serve_site("portfolio"))

    response = client.post(f"/v1/sites/{site['id']}/analyze", headers=auth_headers(pair))
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "succeeded", run.get("error")
    assert run["ai_generated"] is False
    assert run["profile"] is not None
    assert run["profile"]["observed"]["page_count"] >= 4
    assert run["profile"]["entities"]["contact"]["email"] == "lyleokoth.mlengineer@gmail.com"
    assert run["profile"]["understanding"]["value_proposition"] is not None
    assert run["stats"]["robots_status"] == "ok"

    stored = client.get(f"/v1/sites/{site['id']}/profile", headers=auth_headers(pair))
    assert stored.status_code == 200
    assert stored.json()["observed"]["page_count"] == run["profile"]["observed"]["page_count"]

    fetched_run = client.get(f"/v1/runs/{run['id']}", headers=auth_headers(pair))
    assert fetched_run.status_code == 200
    assert fetched_run.json()["profile"]["title"].startswith("Lyle Okoth")

    site_after = client.get(f"/v1/sites/{site['id']}", headers=auth_headers(pair)).json()
    assert site_after["status"] == "analyzed"


def test_runs_are_tenant_scoped(client: TestClient, signup, serve_site) -> None:
    ada = signup(email="ada@example.com", tenant_name="Ada Labs")
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")
    site = _site(client, ada, serve_site("portfolio"))
    run = client.post(
        f"/v1/sites/{site['id']}/analyze", headers=auth_headers(ada)
    ).json()

    assert (
        client.get(f"/v1/runs/{run['id']}", headers=auth_headers(marcus)).status_code == 404
    )
    assert client.get("/v1/runs", headers=auth_headers(marcus)).json() == []
    assert (
        client.get(f"/v1/sites/{site['id']}/profile", headers=auth_headers(marcus)).status_code
        == 404
    )


def test_analyze_unknown_site_is_404(client: TestClient, signup) -> None:
    pair = signup()
    assert (
        client.post("/v1/sites/does-not-exist/analyze", headers=auth_headers(pair)).status_code
        == 404
    )


def test_profile_before_analysis_is_404(client: TestClient, signup, serve_site) -> None:
    pair = signup()
    site = _site(client, pair, serve_site("portfolio"))
    response = client.get(f"/v1/sites/{site['id']}/profile", headers=auth_headers(pair))
    assert response.status_code == 404
