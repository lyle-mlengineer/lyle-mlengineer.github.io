from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_signup_returns_tokens_and_me(client: TestClient, signup) -> None:
    pair = signup()
    assert pair["access_token"]
    assert pair["refresh_token"]
    assert pair["token_type"] == "bearer"

    response = client.get("/v1/me", headers=auth_headers(pair))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["tenant_name"] == "Ada Labs"


def test_password_grant(client: TestClient, signup) -> None:
    signup()
    response = client.post(
        "/v1/token",
        data={"username": "ada@example.com", "password": "supersecret"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_wrong_password_is_rejected(client: TestClient, signup) -> None:
    signup()
    response = client.post(
        "/v1/token",
        data={"username": "ada@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_duplicate_email_is_rejected(client: TestClient, signup) -> None:
    signup()
    response = client.post(
        "/v1/auth/signup",
        json={"email": "ada@example.com", "password": "anothersecret"},
    )
    assert response.status_code == 409


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/signup",
        json={"email": "ada@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_refresh_rotates_and_revokes_the_old_token(client: TestClient, signup) -> None:
    pair = signup()

    refreshed = client.post("/v1/token/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refreshed.status_code == 200
    new_pair = refreshed.json()
    assert new_pair["refresh_token"] != pair["refresh_token"]

    reused = client.post("/v1/token/refresh", json={"refresh_token": pair["refresh_token"]})
    assert reused.status_code == 401

    good = client.post("/v1/token/refresh", json={"refresh_token": new_pair["refresh_token"]})
    assert good.status_code == 200


def test_logout_revokes_refresh_token(client: TestClient, signup) -> None:
    pair = signup()
    logged_out = client.post("/v1/logout", json={"refresh_token": pair["refresh_token"]})
    assert logged_out.status_code == 204
    assert (
        client.post("/v1/token/refresh", json={"refresh_token": pair["refresh_token"]}).status_code
        == 401
    )


def test_expired_access_token_is_rejected(client: TestClient, signup) -> None:
    signup()
    import jwt

    from app.config import get_settings

    settings = get_settings()
    expired = jwt.encode(
        {"sub": "nobody", "tenant_id": "none", "type": "access", "exp": 1},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_sites_require_auth(client: TestClient) -> None:
    assert client.get("/v1/sites").status_code == 401
