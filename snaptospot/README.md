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
- Tesseract (optional; only for OCR of image uploads)

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

### Resolve gaps

After `analyze`, ask the run what is still missing and what to ask the user:

```powershell
$gaps = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/gaps" -Headers $headers
$gaps.coverage
$gaps.questions | Format-Table key, prompt, default, unlocks
```

`questions` is capped at five, ordered by card impact and never asks for a fact
that is already accepted. Every question has `default = "skip"`, which omits the
card honestly. Send answers back — `skip = true` accepts the default:

```powershell
$body = @{
  answers = @(
    @{ key = "offer.core"; value = "Brand strategy for small teams"; attest = $true }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/answers" `
  -Headers $headers -ContentType 'application/json' -Body $body
```

Facts can be reviewed and changed one at a time:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/facts" -Headers $headers

$override = @{ action = "override"; value = "10.1"; attest = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/facts/f_03" `
  -Headers $headers -ContentType 'application/json' -Body $override
```

`POST /v1/runs/{id}/render` returns 409 with the open blocking gaps and 202
`ready` once they are answered or skipped. An override requires `attest: true`;
the previous fact is kept as `quarantined`, and the audit log records the change.
The request schema rejects any client-supplied `tier`.

### Answer a gap from a document

Upload a deck, CV, case study or brand guide. Retrieval runs over the uploaded
files and the extractor reads only the top three chunks for one gap at a time.

```powershell
curl.exe -X POST "http://127.0.0.1:8000/v1/runs/$($run.id)/documents" `
  -H "Authorization: Bearer $($pair.access_token)" `
  -F "files=@growth-deck.pptx" `
  -F "gap_key=proof.metrics"

$facts = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/facts?status=accepted" -Headers $headers
$facts | Where-Object source_type -eq "document" | Format-Table key, value, source, source_page, tier, source_quote

$documents = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/documents" -Headers $headers
$documents | Format-Table filename, pages, chunk_count, fact_count, status, pinned_to_brand
```

Every document fact carries `source_type = "document"`, the filename, the
page/slide number, the chunk id and a verbatim quote. The upload response reports
pages, chunks, extracted facts and failures per file.

Limits: 10 MB, 40 pages/slides and five files per run. PDF, DOCX, PPTX, Markdown,
TXT and CSV are parsed directly; images need OCR (`SNAP_OCR_ENABLED=true` with
Tesseract installed). MIME type is sniffed from the bytes, archives are checked
for decompression bombs, and executables, macros and active content are rejected.

```powershell
# Keep a brand deck past the 30-day retention window.
$docId = $documents[0].id
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/documents/$docId/pin" `
  -Headers $headers -ContentType 'application/json' -Body '{"pinned":true}'

# Expire unpinned documents (run daily in production).
python -m app.cli expire-documents
python -m app.cli expire-documents --days 30
```

On Postgres, retrieval uses `tsvector` BM25 plus pgvector cosine behind HNSW and
GIN indexes. SQLite computes both legs in Python, so the local app needs no
vector extension. Embeddings use the configured OpenAI-compatible endpoint; with
no `SNAP_LLM_API_KEY` they fall back to deterministic local hashing.

### Search the web for a public gap

Search is a rung, not a dependency. Configure one provider; leaving the provider
or key blank keeps the endpoint working and labels the run as disabled.

```dotenv
SNAP_SEARCH_PROVIDER=brave        # brave | tavily | serp
SNAP_SEARCH_API_KEY=...
# SNAP_SEARCH_ENDPOINT=...        # optional override, e.g. a proxy
```

```powershell
$search = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/search" -Headers $headers

$search.status                    # searched | disabled | degraded | exhausted
$search.label
$search.queries | Format-Table gap_key, query, engine, score, status, cache_hit
$search.facts | Format-Table key, value, unit, tier, published_at, source, source_quote
$search.gaps.web_search
```

The resolver issues at most six queries per run, one per public gap class
(identity, offer, proof, commerce, recency). It fetches the top three results,
strips navigation, and keeps only sources scoring at least `0.65` on
`0.35 domain_quality + 0.25 first_party + 0.20 recency + 0.20 corroboration`.
Extraction must return a verbatim quote; web facts cap at tier B and become tier
C without a publication date, so an undated metric resolves the gap but never
renders a number. Every query is logged in `web_queries`, and a repeat within
seven days reuses the cached result list. A page that tries to instruct the
model is skipped with a warning and no fact.

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

# Documents and retrieval
SNAP_EMBEDDING_MODEL=text-embedding-3-small
SNAP_EMBEDDING_DIMENSIONS=1536
SNAP_MAX_UPLOAD_FILES=5
SNAP_MAX_DOCUMENT_BYTES=10485760
SNAP_MAX_DOCUMENT_PAGES=40
SNAP_DOCUMENT_RETENTION_DAYS=30
SNAP_RETRIEVAL_TOP_K=8
SNAP_RETRIEVAL_TOP_CHUNKS=3
SNAP_OCR_ENABLED=false   # true with Tesseract + pytesseract installed

# Web search; blank provider or key disables the rung
SNAP_SEARCH_PROVIDER=
SNAP_SEARCH_API_KEY=
SNAP_SEARCH_TIMEOUT_SECONDS=20
SNAP_WEB_SEARCH_MAX_QUERIES=6
SNAP_WEB_SEARCH_RESULTS=3
SNAP_WEB_SEARCH_CACHE_DAYS=7
SNAP_WEB_SEARCH_MIN_SCORE=0.65
```

LLM output is checked against the crawled block tree; unsupported claims are
dropped and the deterministic reading is used instead. Extraction uses the
versioned prompt in `prompts/extract_v1.md`; a draft fact is accepted only when
its quote appears in the cited block and every number in its value appears in
that quote. Without an API key the deterministic regex pass alone produces the
content model.

## Status

See `progress.md`. The API is built in phases; each phase ends with a working app.
