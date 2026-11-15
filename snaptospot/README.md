# SnapToSpot

Turn a website into a native campaign kit for every social platform — stills, video,
captions and posts built from the site's real content, screenshots and numbers.

This folder is the implementation. The design lives in `../docs/`:

- `../docs/snaptospot-design.md` — product and technical design
- `../docs/snaptospot-prd.md` — requirements
- `../docs/steps.md` — the build order
- `progress.md` — what is built so far and what is next

## Requirements

- Python 3.12 (3.15 works for the app but some dependencies ship no wheels yet)
- Docker (optional, for Postgres + Redis)
- ffmpeg (needed from the rendering step onward)
- Chromium via Playwright, or an installed Chrome/Edge (optional; without a browser
  the crawler uses static HTML)

## Setup (Windows PowerShell)

```powershell
cd snaptospot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head

# optional, for JS-rendered sites and screenshots
playwright install chromium
```

## Run

```powershell
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs> for the interactive API, or
<http://127.0.0.1:8000/healthz> for a quick check.

### Analyse a website

Sign up, create a site, then call `analyze`:

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
$run.profile.understanding
$run.content_model.facts
$run.stats.gaps

# the same document has its own endpoint
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/sites/$($site.id)/content-model" `
  -Headers $headers
```

The run is synchronous in this phase, so the response contains the finished
profile and content model. `GET /v1/runs/{id}`,
`GET /v1/sites/{id}/profile` and `GET /v1/sites/{id}/content-model` return the
same data later.

Metrics, badges and quotes in `content_model` are pointers into `facts[]`. Every
fact carries a tier (`A`–`D`), a source quote and a reject-free grounding record;
`stats.rejected_facts` lists anything the extractor refused.

The same pipeline works without the API:

```powershell
python -m app.cli ingest https://lyle-mlengineer.github.io --out var\profile.json
python -m app.cli extract https://lyle-mlengineer.github.io --out var\content.json
```

## Test

```powershell
pytest
ruff check .
```

The suite uses local fixture websites. The Playwright test uses bundled Chromium
when installed, otherwise it falls back to a system Chrome or Edge.

## Configuration

Everything is read from environment variables prefixed `SNAP_`, or from `.env`.
The default database is SQLite so the app runs with no services. To use Postgres:

```powershell
docker compose up -d postgres redis
# then set in .env:
# SNAP_DATABASE_URL=postgresql+psycopg://snaptospot:snaptospot@localhost:5432/snaptospot
```

Crawling and understanding are configured in `.env`:

```dotenv
SNAP_MAX_PAGES=12
SNAP_USE_PLAYWRIGHT=true
SNAP_CAPTURE_SCREENSHOTS=true
SNAP_FETCH_TIMEOUT_SECONDS=20
SNAP_SSRF_ALLOW_PRIVATE=false
SNAP_MEDIA_ROOT=var/media

# Optional OpenAI-compatible endpoint. Blank = deterministic heuristics.
SNAP_LLM_API_KEY=
SNAP_LLM_BASE_URL=https://api.openai.com/v1
SNAP_LLM_MODEL=gpt-4o-mini
```

LLM output is checked against the crawled block tree; unsupported claims are
dropped and the deterministic reading is used instead. Extraction uses the
versioned prompt in `prompts/extract_v1.md`; a draft fact is accepted only when
its quote appears in the cited block and every number in its value appears in
that quote. Without an API key the deterministic regex pass alone produces the
content model.

## Status

See `progress.md`. The API is built in phases; each phase ends with a working app.
