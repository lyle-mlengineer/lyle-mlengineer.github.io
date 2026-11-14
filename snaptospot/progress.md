# SnapToSpot — Progress

The build follows `../docs/steps.md`. Each step ends with a working app, a test run,
and a commit.

**Current step:** 2 complete — ingestion, `SiteProfile` and LLM-assisted site understanding
**Next step:** 3 — extraction and content model
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

### Step 2 — Ingestion

- **Safety first.** `ingest/security.py` rejects non-HTTP schemes and hosts that
  resolve to private, loopback, link-local, multicast or reserved addresses.
  `ingest/robots.py` fetches and enforces `robots.txt`, honours `Crawl-delay`
  (capped at 2 s) and records sitemaps. A missing or broken robots file fails open,
  a disallow fails closed.
- **Crawl.** `ingest/crawl.py` normalises the URL, strips tracking parameters,
  fetches the home page, discovers internal links and ranks them by intent
  (`about`, `work`, `services`, `pricing`, `contact`, `blog`), with a 12-page cap.
  It skips assets, login/admin paths, cross-host links and already-visited URLs.
  Every page records one failure without killing the run.
- **Rendering.** `ingest/fetch.py` has a Playwright Chromium fetcher (1440×900,
  2× screenshots, `document.fonts.ready`, bounded network-idle wait, 20 s timeout,
  full-page capture) and a static httpx fallback. If Chromium is missing the app
  logs a warning and keeps working with the fallback. Playwright also tags block
  nodes with a DOM index so the parser can attach bounding boxes.
- **Blocks.** `ingest/blocks.py` produces heading nodes, paragraphs, list items,
  quotes, captions and table cells. IDs are content-addressed
  (`sha1(kind + text)[:7]`), so two runs over the same page produce identical
  `source_id`s. Nested block text is de-duplicated, hidden nodes are ignored and
  pages are capped at 400 blocks.
- **Assets.** `ingest/assets.py` harvests `<img>` (`srcset` included), `og:image`,
  `twitter:image`, JSON-LD images and icons; classifies roles (`logo`, `portrait`,
  `product_shot`, `stock`, `icon`); extracts Google Fonts and CSS families; and
  clusters screenshot pixels in OKLab into brand colours with roles and area
  fractions. CSS hex colours are the fallback when screenshots are off.
- **Entities.** `ingest/entities.py` reads JSON-LD (`Person`, `Organization`),
  title/heading structure, mailto/tel links and visible text to recover name,
  role, location, organisation, email, phone and contact URL. Unknown values stay
  `None`; nothing is guessed.
- **Profile.** `ingest/profile.py` assembles a schema-valid `SiteProfile` with
  pages, block trees, brand, entities, images and `observed` (page count, asset
  count, crawl time, SHA-256 site hash). `gaps[]` starts empty; the resolver in
  step 3 fills it.
- **Understanding.** `pipeline/understand/` adds an optional OpenAI-compatible
  LLM pass over a compressed site representation (headings, blocks with IDs,
  meta). The model returns value proposition, audience, tone, page roles and
  offerings. Every value is validated before use: source IDs must exist, URLs
  must have been crawled, and any number not present in the site text rejects the
  claim. Without an API key, or when the model output fails validation, the
  deterministic heuristics produce the same shape. `ai_generated` records which
  path ran. The LLM never sees raw HTML and is never a source of rendered facts.
- **Runs.** `Run` model + Alembic migration `4360c82be28d`, plus:
  - `POST /v1/sites/{id}/analyze` — creates a run, crawls, profiles, understands,
    updates the site status and returns the finished run with its profile;
  - `GET /v1/runs/{id}` and `GET /v1/runs?site_id=...` — tenant-scoped run
    history;
  - `GET /v1/sites/{id}/profile` — latest successful profile.
- **CLI.** `python -m app.cli ingest URL --out profile.json` runs the same
  pipeline without a database.
- **Fixtures and tests.** Local HTTP fixtures for a static portfolio, a
  JS-rendered SPA, a robots-blocked site and a no-image site. Coverage includes
  SSRF rejection, robots enforcement, stable block IDs, asset/colour/entity
  extraction, LLM claim rejection, deterministic fallback, tenant-scoped runs and
  the end-to-end analyze endpoint. 33 tests pass; the Playwright SPA test skips
  when Chromium is not installed. ruff is clean.
- **Live smoke test.** Started the API and a local fixture server, signed up,
  created a site, analysed it, then read the run and profile back:
  `status=succeeded pages=4 assets=4 ai=False`, name `Lyle Okoth`, role
  `Machine Learning Engineer`, accent `#f04080`, value proposition from the home
  page.

**Commit:** `feat(snaptospot): ingest sites and build the first SiteProfile`

---

## Next step

### Step 3 — Extraction and content model

1. Versioned extraction prompts in `prompts/extract_v1.md` with JSON-schema output.
2. `pipeline/extract/`: regex pre-pass for numbers, dates, emails, phones and
   client names, then one LLM call per site for offerings, projects and proof.
3. Grounding: quote normalisation, fuzzy containment, number-in-quote checks and
   banned roundings.
4. `ContentModel` facts with trust tiers A–D, source quotes and reject reasons.
5. Populate `SiteProfile.gaps[]` for every empty requirement slot and add the
   resolver ladder (site → user question → RAG → web → infer → omit).
6. Contract tests with the portfolio's seven facts plus adversarial fixtures.

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

# browser rendering (optional; the app falls back to static HTML)
playwright install chromium

# every time
uvicorn app.main:app --reload
```

- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/healthz>
- Tests: `pytest`
- Lint: `ruff check .`

### Analyse a site

```powershell
$pair = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/auth/signup `
  -ContentType 'application/json' `
  -Body '{"email":"you@example.com","password":"supersecret","tenant_name":"My Studio"}'

$headers = @{ Authorization = "Bearer $($pair.access_token)" }

$site = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/sites `
  -Headers $headers -ContentType 'application/json' `
  -Body '{"url":"https://lyle-mlengineer.github.io","title":"Portfolio"}'

$run = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/sites/$($site.id)/analyze" `
  -Headers $headers

$run.status
$run.profile.observed
$run.profile.entities
$run.profile.brand
$run.profile.understanding

Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/sites/$($site.id)/profile" -Headers $headers
```

Or use the **Authorize** button in `/docs` (flow: password, username = email).
`analyse` is synchronous in this step, so the response already contains the
profile; later it moves behind a worker and the run endpoint is what the UI polls.

### Optional LLM understanding

Any OpenAI-compatible endpoint works:

```dotenv
SNAP_LLM_API_KEY=sk-...
SNAP_LLM_BASE_URL=https://api.openai.com/v1
SNAP_LLM_MODEL=gpt-4o-mini
```

Leave `SNAP_LLM_API_KEY` blank to use the deterministic heuristics. LLM output is
validated against the block tree and falls back automatically.

### CLI

```powershell
python -m app.cli ingest https://lyle-mlengineer.github.io --out var\profile.json
```

### Useful settings

```dotenv
SNAP_MAX_PAGES=12
SNAP_USE_PLAYWRIGHT=true
SNAP_CAPTURE_SCREENSHOTS=true
SNAP_FETCH_TIMEOUT_SECONDS=20
SNAP_SSRF_ALLOW_PRIVATE=false   # true only for local fixture servers
SNAP_MEDIA_ROOT=var/media
```

No Docker is required for these steps. Postgres is optional:

```powershell
docker compose up -d postgres redis
# set SNAP_DATABASE_URL=postgresql+psycopg://snaptospot:snaptospot@localhost:5432/snaptospot
```
