import functools
import threading
from collections.abc import Generator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (register mappers before create_all)
from app.config import get_settings
from app.db import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

FIXTURE_SITES = Path(__file__).parent / "fixtures" / "sites"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture(autouse=True)
def offline_settings(tmp_path) -> Generator[None, None, None]:
    """Keep tests offline and deterministic.

    Private-address crawling is allowed so tests can use a local HTTP server;
    the SSRF test flips it back off explicitly.
    """
    settings = get_settings()
    previous = {
        "ssrf_allow_private": settings.ssrf_allow_private,
        "use_playwright": settings.use_playwright,
        "capture_screenshots": settings.capture_screenshots,
        "llm_api_key": settings.llm_api_key,
        "max_pages": settings.max_pages,
        "media_root": settings.media_root,
        "max_document_bytes": settings.max_document_bytes,
        "max_document_pages": settings.max_document_pages,
        "max_upload_files": settings.max_upload_files,
        "ocr_enabled": settings.ocr_enabled,
    }
    settings.ssrf_allow_private = True
    settings.use_playwright = False
    settings.capture_screenshots = False
    settings.llm_api_key = None
    settings.max_pages = 12
    settings.media_root = str(tmp_path / "media")
    settings.max_document_bytes = 10 * 1024 * 1024
    settings.max_document_pages = 40
    settings.max_upload_files = 5
    settings.ocr_enabled = False
    yield
    for key, value in previous.items():
        setattr(settings, key, value)


@pytest.fixture(autouse=True)
def fresh_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def signup(client: TestClient):
    def _signup(
        email: str = "ada@example.com",
        password: str = "supersecret",
        tenant_name: str = "Ada Labs",
    ) -> dict:
        response = client.post(
            "/v1/auth/signup",
            json={"email": email, "password": password, "tenant_name": tenant_name},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _signup


@pytest.fixture
def serve_site() -> Generator[object, None, None]:
    """Serve a fixture directory from a random localhost port."""
    servers: list[ThreadingHTTPServer] = []

    def _serve(name: str) -> str:
        handler = functools.partial(QuietHandler, directory=str(FIXTURE_SITES / name))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield _serve
    for server in servers:
        server.shutdown()
        server.server_close()


def auth_headers(pair: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {pair['access_token']}"}
