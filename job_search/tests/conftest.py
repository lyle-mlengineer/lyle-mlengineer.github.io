from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.db import dispose_engines  # noqa: E402


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SKIPPER_ENV", "dev")
    monkeypatch.setenv("SKIPPER_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SKIPPER_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("SKIPPER_PORTFOLIO_DIR", str(ROOT / "data" / "portfolio"))
    monkeypatch.setenv("SKIPPER_ADMIN_USER", "lyle")
    monkeypatch.setenv("SKIPPER_ADMIN_PASSWORD", "test-password-123")
    monkeypatch.setenv("SKIPPER_LLM_PROVIDER", "fake")
    # The test suite must never dial a hosted provider, even when a developer's
    # .env has real keys and auto fallbacks enabled.
    monkeypatch.setenv("SKIPPER_LLM_FALLBACKS", "none")
    monkeypatch.setenv("SKIPPER_SEARCH_PROVIDER", "duckduckgo")
    # The audio tab must never reach a hosted speech API during tests.
    monkeypatch.setenv("SKIPPER_TTS_PROVIDER", "fake")
    monkeypatch.setenv("SKIPPER_SOFFICE_PATH", "skipper-no-libreoffice-installed")
    monkeypatch.setenv("SKIPPER_SECRET_KEY", "test-secret-key-not-for-production")

    get_settings.cache_clear()
    dispose_engines()

    from app.main import create_app

    application = create_app()

    class NoopSearch:
        name = "noop"

        def search(self, query, *, limit=5, recency_days=None):
            return []

        def health(self):
            return True

    with TestClient(application, raise_server_exceptions=True) as client:
        application.state.search = NoopSearch()
        yield client

    dispose_engines()
    get_settings.cache_clear()


@pytest.fixture()
def settings(app_env):
    return get_settings()


@pytest.fixture()
def client(app_env):
    return app_env


def login(client: TestClient, username: str = "lyle", password: str = "test-password-123"):
    return client.post(
        "/login",
        data={"username": username, "password": password, "next": "/dashboard"},
        follow_redirects=False,
    )
