# SnapToSpot — Progress

The build follows `../docs/steps.md`. Each step ends with a working app, a test run,
and a commit.

**Current step:** 0 — Foundations
**Last updated:** 2026-11-14

---

## Done

### Step 0 — Foundations

- FastAPI app factory with a request-id middleware and structured logging.
- `/`, `/healthz`, `/readyz` endpoints.
- Settings via `pydantic-settings` (`SNAP_` prefix, `.env` support). SQLite is the
  default so the app runs with no external services; Postgres is one env var away.
- `pyproject.toml` with runtime and dev extras, ruff and mypy config, pytest config.
- `docker-compose.yml` with Postgres 16 + pgvector and Redis 7.
- Smoke tests for health, root, readiness and request-id echoing.
- README with setup and run instructions.

**Commit:** `chore(snaptospot): scaffold FastAPI service`

---

## Next step

### Step 1 — Data layer and auth

1. SQLAlchemy engine, session factory and declarative base (SQLite for dev, Postgres
   for production).
2. Models: tenant, user, refresh token, site, audit log.
3. Alembic setup and the first migration.
4. OAuth2 password grant: sign-up, `POST /v1/token`, refresh rotation, logout.
5. Tenant-scoped `POST /v1/sites`, `GET /v1/sites`, `GET /v1/sites/{id}`.
6. Tests: auth round-trip, expired token, refresh rotation, cross-tenant isolation.

---

## How to run

From `snaptospot/` with the virtual environment active:

```powershell
uvicorn app.main:app --reload
```

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/healthz>
- Tests: `pytest`

No database or Docker is required yet.
