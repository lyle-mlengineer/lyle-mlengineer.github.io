from __future__ import annotations

from app.db import dispose_engines


def test_healthz_does_not_need_the_database(client, settings):
    dispose_engines()
    settings.db_path.unlink(missing_ok=True)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_each_component(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    components = body["components"]
    assert components["database"] is True
    assert components["account"] is True
    assert components["llm"] is True
    assert components["pdf_engine"] in {"libreoffice", "reportlab"}
    assert set(components) >= {"database", "account", "llm", "portfolio_chunks", "pdf_engine"}


def test_request_id_is_echoed(client):
    response = client.get("/healthz", headers={"X-Request-Id": "abc123"})
    assert response.headers["X-Request-Id"] == "abc123"
    generated = client.get("/healthz").headers["X-Request-Id"]
    assert generated and generated != "abc123"
