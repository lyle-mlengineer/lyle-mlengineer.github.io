from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (register mappers before create_all)
from app.db import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


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


def auth_headers(pair: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {pair['access_token']}"}
