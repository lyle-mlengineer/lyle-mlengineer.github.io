# Skipper

Skipper is a private job-search agent. Give it one input — a link to a company careers page, a link to a job board, or the job description pasted as text — and it produces the complete application pack for that role:

- a summary of the job and a fit/gap read
- company research with cited sources
- a tailored CV as **PDF and DOCX**
- a cover letter, as PDF, DOCX and Markdown
- the application email
- prepared answers for *tell me about yourself*, *work history* and *projects you are proud of*
- a likely technical interview with written answers
- a likely system-design and **low-level design** brief with components, data structures and trade-offs
- a likely behavioural interview with STAR answers
- an **interview study workspace** at `/study`, independent of any job: upload PDFs, DOCX files, articles or pasted text, choose a job category and level, generate practice questions with answers and play them as audio
- an **audio tab** that reads the pack out loud: an interviewer voice asks each question, an interviewee voice answers, delivery follows the notes the LLM wrote, and your own reference recording can voice the answers

Jobs, companies and application status live on a password-gated dashboard. The public landing page is a rebuilt version of the existing portfolio, in the same visual language, with the dashboard entry point.

The full brief is in [`../job_search.md`](../job_search.md), the technical design in [`docs/design.md`](docs/design.md), requirements in [`docs/prd.md`](docs/prd.md), and the build order in [`docs/steps.md`](docs/steps.md). Live progress for whoever picks this up next is in [`progress.md`](progress.md).

---

## Status

| Area | State |
| --- | --- |
| Landing page (portfolio styling, responsive, dark mode) | **Built** |
| Session auth (argon2id, CSRF, throttling) | **Built** |
| App shell, dashboard, jobs/companies/settings pages | **Built** (empty states) |
| SQLAlchemy 2.0 data model + SQLite schema | **Built** |
| LLM / search / fetch provider seams | **Built** (Phase 2) |
| Portfolio RAG (FTS5) | **Built** (Phase 3) |
| Job intake + extraction + polling job page | **Built** (Phase 4) |
| Tailored CV as DOCX + PDF, versioned download and preview | **Built** (Phase 5) |
| Remaining skills and the full application pack | Planned — Phase 6 |
| Tracking, artifact editing, hardening | Planned — Phases 7–9 |

The dashboard is deliberately honest about this: it shows what exists and names what is not wired yet.

---

## Stack

- **Web:** FastAPI, Jinja2 templates, vanilla CSS/JS (no build step)
- **Data:** SQLAlchemy 2.0 ORM over SQLite in WAL mode, FTS5 for retrieval
- **Jobs:** FastAPI `BackgroundTasks` writing a run ledger to the database; the UI polls. A stopped run (failed, cancelled or interrupted) resumes from its first unfinished step and reuses every output that already succeeded.
- **LLM:** provider interface with Groq (`openai/gpt-oss-120b` large, `openai/gpt-oss-20b` small), NVIDIA NIM for the current free endpoints (`moonshotai/kimi-k3.1-pro` large, `nvidia/nemotron-3.5-lightning-30b-a3b` small), OpenRouter (`openrouter/free`, a zero-cost router across its free models), and a fake provider for tests. When the active provider returns 429/5xx the chain switches to another keyed provider for the rest of the run; when NVIDIA retires a model with 404/410 the provider swaps that tier onto the next free endpoint in `SKIPPER_NVIDIA_MODEL_FALLBACKS`. A call ledger records every model call and web search with its tokens and cost.
- **Search:** provider interface with Serper (Google), Exa (semantic) and DuckDuckGo (no-key fallback)
- **Speech:** provider interface with ElevenLabs (catalogue + cloning), Breeze Blue (catalogue + tags + cloning), Orpheus on Groq (tags, no cloning) and an offline fake provider. The audio tab plans interviewer/interviewee turns, can scope a take to one pack section, and joins each provider's WAV output without a transcode.
- **Documents:** `python-docx` for DOCX, LibreOffice headless for PDF with a `reportlab` fallback

---

## Requirements

- Python **3.11+** (developed on 3.15)
- Optional: **LibreOffice** (`soffice`) for DOCX → PDF. Without it, the reportlab renderer is used.
- Optional: a **Groq**, **NVIDIA NIM** or **OpenRouter** API key for real generation, and a **Serper** or **Exa** key for research.

---

## Run it

```bash
cd job_search

python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[dev]"

cp .env.example .env
# edit .env: set SKIPPER_ADMIN_PASSWORD, then optionally
# SKIPPER_LLM_PROVIDER=groq and SKIPPER_GROQ_API_KEY=...
# or SKIPPER_LLM_PROVIDER=openrouter and SKIPPER_OPENROUTER_API_KEY=...
```

Start the server:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000/>:

- `/` — the landing page (public)
- `/login` — dashboard sign-in
- `/dashboard` — the app (session required)
- `/jobs` — tracked jobs
- `/resources` — LLM calls, tokens, and spend per job, with charts and filters
- `/companies` — companies and their research
- `/readyz` — component readiness as JSON

### First sign-in

In development, if `SKIPPER_ADMIN_PASSWORD` is unset, the account is seeded as:

```
username: lyle        (SKIPPER_ADMIN_USER)
password: skipper-dev
```

The password is printed as a warning at first boot. Set `SKIPPER_ADMIN_PASSWORD` **before the first run** in any environment you care about — it is only read when the users table is empty, and it is stored as an argon2id hash. In production (`SKIPPER_ENV=prod`) the app refuses to seed without it, and `/readyz` reports `account: false`.

Passwords must be at least 8 characters. Change one with:

```bash
python -c "from app.security import hash_password; print(hash_password('new-password'))"
# then: UPDATE users SET password_hash='...' WHERE username='lyle';
```

---

## Configuration

Every setting is read from the environment with the `SKIPPER_` prefix; `.env` is loaded in development. See [`.env.example`](.env.example) for the full list. The ones that matter first:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SKIPPER_ENV` | `dev` | `prod` enforces secure cookies and disables API docs |
| `SKIPPER_ADMIN_USER` | `lyle` | The single account |
| `SKIPPER_ADMIN_PASSWORD` | — | Read once, at first boot |
| `SKIPPER_DB_PATH` | `var/skipper.db` | SQLite file |
| `SKIPPER_ARTIFACTS_DIR` | `var/artifacts` | Generated CVs, letters and briefs |
| `SKIPPER_PORTFOLIO_DIR` | `data/portfolio` | RAG corpus (source of truth) |
| `SKIPPER_LLM_PROVIDER` | `fake` | `fake`, `groq`, `nvidia` or `openrouter` |
| `SKIPPER_GROQ_API_KEY` | — | Required for `groq` |
| `SKIPPER_GROQ_BASE_URL` | Groq API | `https://api.groq.com/openai/v1` |
| `SKIPPER_GROQ_TPM` | `30000` | Groq rate-limit bucket (tokens/min) |
| `SKIPPER_NVIDIA_API_KEY` | — | Required for `nvidia` (build.nvidia.com) |
| `SKIPPER_NVIDIA_BASE_URL` | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` |
| `SKIPPER_NVIDIA_TPM` | `40000` | NVIDIA rate-limit bucket |
| `SKIPPER_NVIDIA_REASONING_EFFORT` | `none` | `none`\|`high`\|`max` — DeepSeek thinking mode |
| `SKIPPER_NVIDIA_MODEL_LARGE` | `moonshotai/kimi-k3.1-pro` | NVIDIA large-tier model (a current free endpoint) |
| `SKIPPER_NVIDIA_MODEL_SMALL` | `nvidia/nemotron-3.5-lightning-30b-a3b` | NVIDIA small-tier model |
| `SKIPPER_NVIDIA_MODEL_FALLBACKS` | built-in chain | Model ids tried in order when a pinned id answers 404/410 |
| `SKIPPER_OPENROUTER_API_KEY` | — | Required for `openrouter` (free key at openrouter.ai/keys) |
| `SKIPPER_OPENROUTER_BASE_URL` | OpenRouter API | `https://openrouter.ai/api/v1` |
| `SKIPPER_OPENROUTER_TPM` | `20000` | Local request-spacing bucket |
| `SKIPPER_OPENROUTER_MODEL_LARGE` | `openrouter/free` | Free large-tier model or router |
| `SKIPPER_OPENROUTER_MODEL_SMALL` | `openrouter/free` | Free small-tier model or router |
| `SKIPPER_OPENROUTER_REFERER` | — | Optional `HTTP-Referer` attribution header |
| `SKIPPER_OPENROUTER_TITLE` | `Skipper` | Optional `X-Title` attribution header |
| `SKIPPER_LLM_MODEL_LARGE` | provider default | Override the "large" tier model (e.g. `moonshotai/kimi-k3.1-pro`) |
| `SKIPPER_LLM_MODEL_SMALL` | provider default | Override the "small" tier model |
| `SKIPPER_LLM_FALLBACKS` | `auto` | Providers tried after a 429/5xx: `auto` (every other keyed provider), a comma list, or `none` |
| `SKIPPER_SEARCH_PROVIDER` | `auto` | `serper`, `exa`, `duckduckgo` or `auto` |
| `SKIPPER_SERPER_API_KEY` | — | Enables Serper; DDG works without a key |
| `SKIPPER_EXA_API_KEY` | — | Enables Exa semantic search; used by `auto` when keyed |
| `SKIPPER_RESEARCH_TTL_DAYS` | `30` | Reuse a company brief across jobs while it is this fresh; `0` always researches |
| `SKIPPER_TTS_PROVIDER` | `auto` | `auto`, `fake`, `orpheus`, `elevenlabs` or `breeze` |
| `SKIPPER_ELEVENLABS_API_KEY` | — | Enables ElevenLabs voices and cloning |
| `SKIPPER_BREEZE_API_KEY` | — | Enables Breeze Blue voices and cloning |
| `SKIPPER_TTS_MAX_TURNS` | `30` | Cap on spoken turns in one take |
| `SKIPPER_INTERVIEW_MAX_UPLOAD_BYTES` | `8000000` | Largest interview source upload |
| `SKIPPER_INTERVIEW_MAX_SOURCE_CHARS` | `400000` | Text kept per uploaded source |
| `SKIPPER_INTERVIEW_PRACTICE_QUESTIONS` | `8` | Default practice-set size |
| `SKIPPER_SOFFICE_PATH` | `soffice` | LibreOffice binary for PDF |

Each provider ships its own default model pair, so `SKIPPER_LLM_MODEL_LARGE`/`SMALL` are only needed to override them (empty means "the selected provider's default"). If you switch providers, clear those two variables.

NVIDIA retires free endpoints with a `410 Gone` body (the DeepSeek V4 pair went on 2026-08-07, and `-flash-0731` followed in September). The provider treats 404/410 as "this model is gone", swaps the tier onto the next id in `SKIPPER_NVIDIA_MODEL_FALLBACKS` and remembers the swap for the rest of the process. The built-in chain is Kimi K3.1 Pro, Nemotron 3.5 Lightning, MiniMax M3.1 Flash, DeepSeek V4.1 Flash, GLM-5.3 Flash and Mistral Large 4. Copy live ids from <https://build.nvidia.com/models>.

OpenRouter also rotates its free catalogue. Both tiers default to `openrouter/free`, which selects a zero-priced model that supports the request (including JSON output), so a retired free id does not break the app. To pin one, set `SKIPPER_OPENROUTER_MODEL_LARGE`/`SMALL` to an id ending in `:free` — the current useful ones include `nvidia/nemotron-3-ultra-550b-a55b:free`, `nvidia/nemotron-3.5-lightning:free`, `minimax/minimax-m3.1-flash:free`, `google/gemma-4-31b-it:free` and `thinkingmachines/inkling-small:free`. OpenRouter's free tier is capped per day (50 requests, or 1000 after a one-off credit purchase), so `auto` fallbacks to Groq/NVIDIA matter here more than elsewhere. The provider retries once without JSON mode when an individual free model rejects `response_format`.

---

## Tests

```bash
python -m pytest            # offline: fake providers, temp database
python -m pytest -q         # quiet
ruff check app tests        # lint
```

The suite currently covers the landing page, auth (session, CSRF, throttling, expiry, open-redirect), the ORM contract, startup sweeps, readiness and request headers. It never calls the network.

---

## Project layout

```text
job_search/
  app/
    main.py            # app factory, middleware, lifespan
    config.py          # settings (SKIPPER_ prefix)
    db.py              # engine, sessions, schema bootstrap, sweeps
    models.py          # SQLAlchemy 2.0 models (single source of truth)
    domain.py          # statuses, transitions, skills manifest, labels
    security.py        # argon2id, sessions, CSRF, login throttle
    deps.py            # request dependencies
    routes/            # pages + JSON API
    interview/         # uploaded sources, FTS search, practice generation
    templates/         # Jinja2: landing, login, app shell, dashboard, ...
    static/            # css/js/img — portfolio tokens reused
  data/portfolio/      # Markdown corpus: profile, experience, projects, skills, voice
  docs/                # design.md, prd.md, steps.md
  tests/               # pytest suite
  var/                 # runtime: DB, artifacts, logs (gitignored)
  progress.md          # build log and hand-off notes
```

Design rules worth knowing before editing:

1. The static portfolio at the repository root is **read-only**. The landing page in `app/templates/landing.html` is its rebuild.
2. Timestamps are UTC ISO-8601 strings ending in `Z` (SQLite-friendly, sortable, no timezone bugs).
3. Status vocabularies live in `app/domain.py`; the database stores strings, services enforce legality.
4. `Base.metadata.create_all` is the pre-release schema mechanism. Before the first deployed schema change, add Alembic and ship forward-only revisions.
5. Untrusted content (job pages, search snippets) is data, never instructions, and is never rendered as raw HTML.

---

## Data and backup

Everything the app owns lives in `var/`:

```bash
sqlite3 var/skipper.db ".backup var/backups/skipper-$(date +%F).db"
tar -czf var/backups/artifacts-$(date +%F).tar.gz var/artifacts
```

Restore by putting both back and restarting. Sessions survive a database restore; runs do not — any run that was active becomes `interrupted`. Open the job and press **Resume run**: it continues from the first unfinished step and reuses every output that already succeeded, so nothing is paid for twice.

---

## Deployment notes

One process, one SQLite file:

```bash
SKIPPER_ENV=prod uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

- **Do not run multiple workers** until the job runner moves to a real queue: `BackgroundTasks` is in-process.
- Put TLS in front (Caddy/Nginx/Render/Fly) so the session cookie is sent `Secure`.
- Mount a persistent disk at `var/`.
- Install LibreOffice in the image if you want LibreOffice-quality PDFs.

---

## Licence

MIT. The portfolio content, CVs and personal data are Lyle Okoth's and are not part of the reusable code.
