from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_create_list_and_get_site(client: TestClient, signup) -> None:
    pair = signup()
    headers = auth_headers(pair)

    created = client.post(
        "/v1/sites",
        json={"url": "https://lyle-mlengineer.github.io", "title": "Portfolio"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    site = created.json()
    assert site["domain"] == "lyle-mlengineer.github.io"
    assert site["status"] == "new"

    listed = client.get("/v1/sites", headers=headers)
    assert listed.status_code == 200
    assert [s["id"] for s in listed.json()] == [site["id"]]

    fetched = client.get(f"/v1/sites/{site['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["url"].startswith("https://lyle-mlengineer.github.io")


def test_invalid_url_is_rejected(client: TestClient, signup) -> None:
    pair = signup()
    response = client.post("/v1/sites", json={"url": "not a url"}, headers=auth_headers(pair))
    assert response.status_code == 422


def test_sites_are_isolated_between_tenants(client: TestClient, signup) -> None:
    ada = signup(email="ada@example.com", tenant_name="Ada Labs")
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")

    created = client.post(
        "/v1/sites",
        json={"url": "https://ada.example.com"},
        headers=auth_headers(ada),
    )
    site_id = created.json()["id"]

    assert client.get("/v1/sites", headers=auth_headers(marcus)).json() == []
    assert client.get(f"/v1/sites/{site_id}", headers=auth_headers(marcus)).status_code == 404
    assert client.get(f"/v1/sites/{site_id}", headers=auth_headers(ada)).status_code == 200
