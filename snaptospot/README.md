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
- Chromium via Playwright, or an installed Chrome/Edge. Without a browser the
  crawler uses static HTML and composition falls back to an estimator instead of
  measuring real line boxes.
- Tesseract (optional; only for OCR of image uploads)

## Setup (Windows PowerShell)

```powershell
cd snaptospot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head

# browser for JS-rendered sites, screenshots and measured cards
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

### Compose measured cards

Composition turns the accepted content model into measured `LayoutAST` cards.
The site's palette seeds one of three directions, and that design system is
pinned on the site so later runs look consistent.

```powershell
$body = @{
  direction = "auto"       # auto | editorial_dark | swiss_paper | signal_grid
  platforms = @("linkedin")
  cards = @("hero", "capabilities", "projects", "proof")
} | ConvertTo-Json -Depth 4

$composed = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/compose" `
  -Headers $headers -ContentType 'application/json' -Body $body

$composed.design_system.direction
$composed.design_system_hash
$composed.measured_in_browser
$composed.layouts | Format-Table asset, ratio, measured.fit, measured.headline_pt, measured.overflow
$composed.layouts[3].slots.stats | Format-Table value, unit, label, fact_id, tier
```

- Supported stills: LinkedIn `1200x1200`, X `1600x900`, Instagram `1080x1350`,
  TikTok `1080x1920`, and WhatsApp status/share.
- `fit` reports `ok`, `reduced` (type shrank, never below 60% of nominal),
  `density_reduced` (a lower-density variant was chosen), or `overflow` with a
  warning telling you to shorten the copy.
- Every rendered number, badge and quote carries a `fact_id`. Tier C/D facts
  and stale undated metrics are filtered before composition.
- Chromium measures the real line boxes. Install it with
  `playwright install chromium`; without a browser the response is labelled
  `measured_in_browser=false`.

The same pipeline works without the API:

```powershell
python -m app.cli ingest https://lyle-mlengineer.github.io --out var\profile.json
python -m app.cli extract https://lyle-mlengineer.github.io --out var\content.json
```

## Step 8 — still rendering

Composition produces measured `LayoutAST`s; rendering turns each one into a PNG
without re-fitting anything. Chromium runs headless with a persistent worker,
captures at 2x and downsamples once with Lanczos to the platform size. The page
is self-contained: images are inlined as data URIs, network requests are
aborted, and a strict CSP is injected before capture.

```powershell
$stills = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/stills" `
  -Headers $headers -ContentType 'application/json' `
  -Body (@{ platforms = @("linkedin") } | ConvertTo-Json)

$stills.renderer_version
$stills.assets | Format-Table filename, width, height, bytes, cached, sha256
```

Files land under the tenant-scoped media root using the design contract names:

```text
var/media/<tenant>/<site>/<run>/stills/linkedin/
  01-announcement.png
  02-what-i-build.png
  03-selected-work.png
  04-proof.png
```

- Rendering uses the composed ASTs persisted in `runs.stats_json`; compose a run
  first. `POST /v1/runs/{id}/stills` returns `409` until then.
- The content-hash cache is keyed by
  `(content_model_hash, design_system_hash, platform, template_version)`. A
  repeat request is a disk read and reports `cached=true`; send
  `"reuse_cache": false` to recapture.
- PNGs carry no timestamp, EXIF or software metadata. Rendering the same AST
  twice yields the same SHA-256.
- Remote layout images are fetched once and cached as data URIs. Set
  `SNAP_RENDER_FETCH_REMOTE=false` for a render that never touches the network;
  unloadable images are omitted rather than drawn as broken placeholders.
- The CLI works without the API:

```powershell
python -m app.cli render --run $run.id --platform linkedin
python -m app.cli render --run $run.id --platform linkedin --force
```

The golden SSIM gate renders the hand-built `media/linkedin/assets/cards.html`
through the same capture pipeline and requires SSIM >= 0.98 against
`media/linkedin/0*.png` for all four cards.

## Step 9 — video

Video is a pure timeline rather than a screen recording. `app/render/frames.py`
ships one `renderAt(t)` function to a self-contained page; frame `n` is always
`n / fps`, so scenes, entrances, the progress bar and burned-in captions are a
function of time and nothing else. Frames are captured as 1× JPEG at quality 95
through CDP, split across workers by frame index and reassembled in order, then
encoded with ffmpeg.

```powershell
$videos = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/videos" `
  -Headers $headers -ContentType 'application/json' `
  -Body (@{ platforms = @("linkedin", "whatsapp"); workers = 2 } | ConvertTo-Json)

$videos.renderer_version
$videos.videos | Format-Table platform, filename, width, height, duration, bytes, cached, within_ceiling
$videos.videos[0].poster_path, $videos.videos[0].poster_timestamp
$videos.videos[0].probe | Format-List codec_name, pix_fmt, color_range, color_space, fps, duration
```

Files land under the tenant-scoped media root:

```text
var/media/<tenant>/<site>/<run>/videos/<platform>/
  launch-video.mp4      # linkedin, x, tiktok
  reel.mp4              # instagram
  status-video.mp4      # whatsapp
  video-poster.png      # reel-poster.png on instagram
```

- Specs: LinkedIn 1080×1080/15 s, X 1920×1080/15 s, Instagram 1080×1920/18 s,
  TikTok 1080×1920/21 s, WhatsApp 1080×1920/18 s, all at 30 fps.
- ffmpeg is required on `PATH`. Encoding is BT.709 limited range, H.264,
  `-crf 19`, `-preset slow`, `yuv420p`, `+faststart`, with bitexact flags so the
  same frames produce the same MP4 hash. ffprobe fields are returned with each
  video.
- `workers` (1–8, default 2) splits the timeline by index. Each worker replays a
  2.5 s warm-up window before its range so Chromium's text raster cache matches
  a single-worker run; 1, 2 and 4 workers produce identical frames and MP4s.
- The poster is captured at `duration − 0.8 s` and retried at 72% and 55% of the
  duration if the frame is flat.
- The cache is keyed by
  `(content_model_hash, design_system_hash, platform, template_version)` under
  `var/media/video-cache`. A repeat request reports `cached=true`; pass
  `"reuse_cache": false` or `--force` to re-encode.
- `within_ceiling` checks the platform limit (LinkedIn 5 GB, X 512 MB,
  Instagram/TikTok 4 GB, WhatsApp 16 MB) and adds a warning when exceeded.
- The CLI works without the API:

```powershell
python -m app.cli video --run $run.id --platform linkedin --platform whatsapp
python -m app.cli video --run $run.id --platform linkedin --workers 4 --force
```

The LinkedIn and X last line is the URL; Instagram points at the bio, TikTok
asks for a follow, and WhatsApp asks for a reply. Composing a run is a
prerequisite; the endpoint returns 409 until it exists.

## Step 10 — copy and alt text

Copy is generated from the content model, not from screenshots. Each platform
has a `PostSpec` with its own hard limit, hashtag range and link policy. X
counts every URL as 23 characters and wide emoji as 2; the other platforms count
grapheme clusters, so a combining accent or a ZWJ emoji stays one character.

```powershell
$copy = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/copy" `
  -Headers $headers -ContentType 'application/json' `
  -Body (@{ platforms = @("linkedin", "x", "instagram", "whatsapp"); use_llm = $true } | ConvertTo-Json)

$copy.voice | Format-List person, tense, formality, sentence_length
$copy.files | Format-Table platform, primary_chars, short_chars, source, validated
$copy.decks | ForEach-Object { $_.primary; "" }
```

The CLI works offline:

```powershell
python -m app.cli copy --run $run.id --platform linkedin --platform x --no-llm
```

```text
var/media/<tenant>/<site>/<run>/posts/<platform>/post.md
```

- Each `post.md` has the nine §11 sections: header, recommended copy with
  counts, thread/carousel/short variant (or the four WhatsApp shapes), video
  caption, alt text, checklist, files, re-render commands, and sources plus
  omissions.
- The deck is always eight fields: `primary`, exactly three `alternatives`, a
  `thread` for X, `short_variant`, `hashtags`, `alt_text` and WhatsApp
  `messages`.
- Every number must appear in a tier A/B fact. URLs and `N/` thread numbers are
  stripped before the digit check. Banned phrases live in
  `SNAP_COPY_BANNED_PHRASES`, so changing them does not change the prompt.
- A model draft gets one correction attempt. If it still fails the hard rules,
  the deterministic deck is written and the reasons are returned in `warnings`.
- Alt text walks the `LayoutAST` and mentions every visible string. Spatial
  hints ("portrait on the right") are used only when the measured box agrees.
- WhatsApp status has no hashtags and no link; the individual, group and
  broadcast messages carry the URL where a message can.

## Test

```powershell
pytest
ruff check .
```

The suite uses local fixture websites. The composition tests use bundled
Chromium when installed, otherwise a system Chrome or Edge; if neither exists
the browser exit-criterion test skips and the unit tests use the estimator.
Template snapshots live in `tests/fixtures/snapshots/` (34 ratio/density cases).
Refresh them after an intentional template change:

```powershell
$env:SNAP_UPDATE_SNAPSHOTS="1"
pytest -k snapshot
Remove-Item Env:SNAP_UPDATE_SNAPSHOTS
```

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
SNAP_RENDER_FETCH_REMOTE=true

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
