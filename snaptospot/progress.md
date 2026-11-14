# SnapToSpot — Progress

The build follows `../docs/steps.md`. Each step ends with a working app, a test run,
and a commit.

**Current step:** 1 complete — data model, auth and tenant-scoped sites
**Next step:** 2 — ingestion (crawl, blocks, assets, `SiteProfile`)
**Last updated:** 2026-11-14

---

## Done

### Step 0 — Foundations

- FastAPI app factory with request-id middleware and structured logging.
- `/`, `/healthz`, `/readyz` endpoints.
- Settings via `pydantic-settings` (`SNAP_` prefix, `.env` support). SQLite is the
  default so the app runs with no external services; Postgres is one env var away.
- `pyproject.toml` with runtime and dev extras, ruff and pytest config.
- `docker-compose.yml` with Postgres 16 + pgvector and Redis 7.
- Smoke tests for health, root, readiness and request-id echoing.
- README with setup and run instructions.

**Commit:** `chore(snaptospot): scaffold FastAPI service`

### Step 1 — Data layer and auth

- SQLAlchemy 2 models: `tenants`, `users`, `refresh_tokens`, `sites`, `audit_log`.
- Alembic initial migration (`migrations/versions/46b315912487_initial_schema.py`);
  SQLite gets tables on startup for convenience, Postgres uses `alembic upgrade head`.
- OAuth2 password grant:
  - `POST /v1/auth/signup` creates a tenant + user and returns a token pair;
  - `POST /v1/token` is the password grant (email + password);
  - `POST /v1/token/refresh` rotates the refresh token and revokes the old one;
  - `POST /v1/logout` revokes a refresh token;
  - `GET /v1/me` returns the user and tenant.
- Argon2id password hashing, 15-minute JWT access tokens, opaque hashed refresh
  tokens with 30-day expiry.
- Tenant-scoped sites: `POST /v1/sites`, `GET /v1/sites`, `GET /v1/sites/{id}`.
  Cross-tenant reads return 404, covered by a dedicated isolation test.
- Audit log entries for signup and site creation.
- 16 tests passing; ruff clean.

**Commit:** `feat(snaptospot): add data model, auth and tenant-scoped sites`

---

## Next step

### Step 2 — Ingestion

1. `app/pipeline/ingest/robots.py`: fetch and parse `robots.txt`, per-host delay,
   SSRF guard (block private IPs, link-local and non-http schemes).
2. `crawl.py`: Playwright Chromium, deterministic viewport and flags, discover up
   to 12 pages by intent, wait for fonts/images, 20 s hard cap.
3. `blocks.py`: heading tree, paragraphs, list items and table cells with stable
   `source_id`s and bounding boxes.
4. `assets.py`: images from `srcset`/`og:image`/JSON-LD, fonts, palette in OKLab,
   logo candidates.
5. `screenshots.py`: full-page 2× capture and per-section project captures.
6. `profile.py`: assemble a schema-valid `SiteProfile` with `observed` and `gaps[]`.
7. `POST /v1/sites/{id}/analyze` creating a run record, plus `GET /v1/runs/{id}`.
8. Tests against local fixture pages: static site, JS-rendered SPA, robots-blocked,
   no-image site.

---

## How to run

From `snaptospot/`, with the virtual environment active:

```powershell
# one-time
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head

# every time
uvicorn app.main:app --reload
```

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/healthz>
- Tests: `pytest`

### Try the API

Sign up and create a site (PowerShell):

```powershell
$pair = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/auth/signup `
  -ContentType 'application/json' `
  -Body '{"email":"you@example.com","password":"supersecret","tenant_name":"My Studio"}'

$headers = @{ Authorization = "Bearer $($pair.access_token)" }

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/sites `
  -Headers $headers -ContentType 'application/json' `
  -Body '{"url":"https://lyle-mlengineer.github.io","title":"Portfolio"}'

Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/sites -Headers $headers
```

Or use the **Authorize** button in `/docs` with the access token (flow: password,
username = email, password = your password).

No Docker is required for these steps. Postgres is optional:

```powershell
docker compose up -d postgres redis
# set SNAP_DATABASE_URL=postgresql+psycopg://snaptospot:snaptospot@localhost:5432/snaptospot
```
