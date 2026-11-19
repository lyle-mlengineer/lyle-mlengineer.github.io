# Skipper

Skipper is a private job-search agent. Give it one input — a link to a company careers page, a link to a job board, or the job description pasted as text — and it produces the complete application pack for that role:

- a summary of the job and a fit/gap read
- company research with cited sources
- a tailored CV as **PDF and DOCX**
- a cover letter, as PDF, DOCX and Markdown
- the application email
- prepared answers for *tell me about yourself*, *work history* and *projects you are proud of*
- a likely technical interview with written answers
- a likely behavioural interview with STAR answers

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
- **LLM:** provider interface with Groq (`openai/gpt-oss-120b` large, `openai/gpt-oss-20b` small), NVIDIA NIM for the hosted DeepSeek V4 models (`deepseek-ai/deepseek-v4-pro` / `-flash`), and a fake provider for tests. A call ledger records every model call and web search with its tokens and cost.
- **Search:** provider interface with Serper (primary) and DuckDuckGo (no-key fallback)
- **Documents:** `python-docx` for DOCX, LibreOffice headless for PDF with a `reportlab` fallback

---

## Requirements

- Python **3.11+** (developed on 3.15)
- Optional: **LibreOffice** (`soffice`) for DOCX → PDF. Without it, the reportlab renderer is used.
- Optional: a **Groq** API key and a **Serper** key for real generation and research.

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
| `SKIPPER_LLM_PROVIDER` | `fake` | `fake`, `groq` or `nvidia` |
| `SKIPPER_GROQ_API_KEY` | — | Required for `groq` |
| `SKIPPER_GROQ_BASE_URL` | Groq API | `https://api.groq.com/openai/v1` |
| `SKIPPER_GROQ_TPM` | `30000` | Groq rate-limit bucket (tokens/min) |
| `SKIPPER_NVIDIA_API_KEY` | — | Required for `nvidia` (build.nvidia.com) |
| `SKIPPER_NVIDIA_BASE_URL` | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` |
| `SKIPPER_NVIDIA_TPM` | `40000` | NVIDIA rate-limit bucket |
| `SKIPPER_NVIDIA_REASONING_EFFORT` | `none` | `none`\|`high`\|`max` — DeepSeek thinking mode |
| `SKIPPER_LLM_MODEL_LARGE` | provider default | Override the "large" tier model (e.g. `deepseek-ai/deepseek-v4-pro`) |
| `SKIPPER_LLM_MODEL_SMALL` | provider default | Override the "small" tier model |
| `SKIPPER_SEARCH_PROVIDER` | `auto` | `serper`, `duckduckgo` or `auto` |
| `SKIPPER_SERPER_API_KEY` | — | Enables Serper; DDG works without a key |
| `SKIPPER_SOFFICE_PATH` | `soffice` | LibreOffice binary for PDF |

Each provider ships its own default model pair, so `SKIPPER_LLM_MODEL_LARGE`/`SMALL` are only needed to override them (empty means "the selected provider's default"). If you switch providers, clear those two variables.

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
