# Skipper — Progress

The build follows [`docs/steps.md`](docs/steps.md). Each phase ends with a working app, a passing test run and (when the repo is committed) a commit.

**Current phase:** 1 complete — landing page, auth and app shell
**Next phase:** 2 — provider seams (LLM, search, fetch)
**Last updated:** 2026-11-19
**Suite:** 30 tests passing offline (`python -m pytest -q`)

---

## What Skipper is

A single-user, self-hosted job-search agent. One input (a job URL or pasted posting) produces a complete application pack: job summary, company research, CV (PDF + DOCX), cover letter, email, three spoken answers, and technical + behavioural interview briefs. A password-gated dashboard tracks every job and its application status. The public `/` is a rebuild of the portfolio in the same visual language, with the dashboard entry point.

Docs:

- `docs/design.md` — architecture, data model, providers, skills, security, UX
- `docs/prd.md` — problem, personas, requirements, release plan
- `docs/steps.md` — the nine build phases and their exit criteria
- `README.md` — setup, run, test, deploy

---

## Done

### Step 0 — Foundations

- `pyproject.toml` with runtime/dev dependencies (`fastapi`, `uvicorn`, `jinja2`, `sqlalchemy>=2.0`, `httpx`, `beautifulsoup4`, `python-docx`, `reportlab`, `argon2-cffi`, `pydantic-settings`, `python-multipart`), ruff and pytest config.
- `.env.example` with every `SKIPPER_*` setting and no secrets.
- `app/config.py` — pydantic-settings, `SKIPPER_` prefix, env validation, runtime-directory creation, persisted `var/secret.key` when no key is supplied.
- `app/models.py` — SQLAlchemy 2.0 declarative models for all 16 entities (users, sessions, login attempts, companies, jobs, job events, runs, run steps, artifacts, sources, caches, portfolio docs/chunks, settings, schema version).
- `app/db.py` — engine per database path with SQLite pragmas (WAL, foreign keys, busy timeout, synchronous normal), `sessionmaker(autoflush=False, expire_on_commit=False)`, `session_scope`, `create_all` bootstrap, FTS5 virtual table via raw DDL, `schema_version`, expired-session and interrupted-run sweeps, `dispose_engines()` for tests.
- `app/domain.py` — job statuses and labels, forward-only transition table, run/step statuses, artifact kinds and labels, the 11-skill manifest with weights/requirements, status tone map.
- `app/main.py` — app factory, lifespan (settings → dirs → schema → admin seed → sweeps), request-id and security-header middleware (CSP, nosniff, frame denial, referrer policy), 404 handling for pages and API.
- `app/routes/health.py` — `/healthz` (no DB), `/readyz` (database, account, LLM key, search, portfolio chunk count, PDF engine).
- `tests/` — 30 tests: landing, auth, CSRF, throttling, session expiry, open-redirect rejection, ORM round-trip, startup sweeps, settings table, status transitions, skill manifest, readiness, request ids.

### Step 1 — Landing page, auth and app shell

- `app/templates/landing.html` — rebuilt portfolio: fixed header with a **Dashboard** button, hero (blob portrait, status pill, two CTAs, privacy note), **Skipper** section (three feature cards, 11-skill chip list, paste → run → send steps, gated-dashboard CTA), about with stats and CV download (links to the static portfolio), skills accordion (both cards open on load), six-card selected-work grid, contact panel, footer. No Swiper, no build step.
- `app/static/css/style.css` — the portfolio token sheet copied verbatim (Poppins, hue 340, radii, dark theme, breakpoints).
- `app/static/css/landing.css` — new sections built only from those tokens; fixes for footer wrapping and hero spacing found in visual review.
- `app/static/css/app.css` — app shell (desktop rail, mobile bottom tabs), stat cards, panels, notices, empty states, status pills, auth card, error page, settings key/value grid, skip link.
- `app/static/js/main.js` — theme toggle (persisted), mobile nav, header shadow, active section link, skills accordion, copy buttons. `theme-init.js` applies the stored theme before paint. No dependencies.
- `app/security.py` — argon2id hashing, opaque sessions stored as SHA-256, CSRF tokens, 12-hour expiry with rolling `last_seen_at`, login throttling (5 failures / 15 min per IP+username), first-boot admin seeding.
- `app/routes/pages.py` — `/`, `/login` (GET + form POST), `/logout`, `/dashboard`, `/jobs`, `/companies`, `/settings`; local-only `next` redirects; eager-loaded relationships so templates never lazy-load after the session closes.
- `app/routes/auth.py` — `/api/auth/login` (same-origin check), `/api/auth/logout` (CSRF), `/api/auth/me`.
- `app/templates/` — `base.html`, `app_shell.html`, `landing.html`, `login.html`, `dashboard.html`, `jobs.html`, `companies.html`, `settings.html`, `error.html`.
- `data/portfolio/` — the factual RAG corpus: `profile.md`, `experience.md`, `projects.md`, `skills.md`, `writing.md`, including canonical metrics (23.4% → 11.8% WER, 1,240 hours, 310 ms, 42 voices/GPU) and the voice rules.
- `README.md` — what the app is, stack, setup, run, first login, config table, tests, layout, backup and deployment notes.

### Verification performed

- `python -m pytest -q` → **30 passed**, no network access.
- Server booted on `127.0.0.1:8123`: `/` 200, `/healthz` `{"status":"ok"}`, startup log clean.
- Playwright (Chromium) checks at 1440 and 375 px:
  - horizontal overflow `0` on landing and dashboard;
  - no console errors;
  - `#nav-toggle` opens the mobile menu (`#nav-menu` bottom = 0);
  - dashboard bottom tab bar visible on mobile;
  - form login with the dev account reaches `/dashboard`.
- Screenshots: `var/logs/landing-full-1440.png`, `landing-full-375.png`, `landing-nav-open-375.png`, `landing-dark-1440.png`, `login-1440.png`, `dashboard-1440.png`, `dashboard-375.png`. Visual review found and fixed: a collapsed skills card that looked empty, footer link wrapping and crowded socials, and excess hero top spacing.

---

## Deliberately not built yet

| Thing | Why it is absent | Where it lands |
| --- | --- | --- |
| Add-job flow | Requires the ingestion + extraction phase | Phase 4 |
| LLM/search/fetch providers | Seam-first order: ABC + fakes + tests before HTTP | Phase 2 |
| RAG ingest/retrieval | Corpus exists; index is created by the RAG module | Phase 3 |
| Skills, artifacts, document renderers | Depend on providers and RAG | Phases 5–6 |
| Tracking/status API, company pages | Depend on jobs existing | Phase 7 |
| Regeneration, resume, cancel | Depend on runs existing | Phase 8 |
| Alembic | `create_all` is acceptable pre-release; no deployed schema yet | Before first deploy |

The UI does not pretend: the dashboard, jobs and companies pages show honest empty states, the "Add job" control is visibly disabled with a title explaining why, and `/settings` lists what is pending.

---

## Decisions taken during the build

1. **SQLAlchemy 2.0 ORM instead of raw `sqlite3`** (owner request mid-build). Consequences: models are the single schema definition, typed `Mapped[...]` columns, relationship loading with `joinedload`/`selectinload` because Jinja renders after the request session commits. FTS5 stays raw DDL — it is an index, not an entity. Docs updated in design §7/§8/§10/§24/§25, PRD NFR-4 and steps Phase 0.
2. **Timestamps as UTC ISO-8601 strings** (`YYYY-MM-DDTHH:MM:SSZ`): portable, sortable, no SQLite timezone loss, trivial JSON export. Documented as invariant 6 in design §10.3.
3. **Eager loading, not `expire_on_commit=True`**: avoids `DetachedInstanceError` in templates and N+1 on dashboard/jobs pages.
4. **Single worker.** `BackgroundTasks` is in-process; the README and design §24 forbid `--workers > 1` until a real queue exists.
5. **Landing page lives in `app/templates/`, not in the static portfolio.** The root `index.html`, CSS and JS were copied from, never edited.
6. **Portfolio corpus written early.** RAG is Phase 3, but the factual source of truth is prerequisite for every prompt; writing it now keeps later prompts honest and gives the corpus a review pass.
7. **Dev default password is explicit.** `skipper-dev` is logged loudly at first boot; production refuses to seed without `SKIPPER_ADMIN_PASSWORD`.
8. **Course-corrected after visual review**: both skills cards open on the landing page, footer links `white-space: nowrap`, footer grid aligned to start, hero top padding reduced, social rail pulled closer.

---

## Next three tasks (pick up here)

### 1. Provider seams (Phase 2)

Files: `app/providers/llm/base.py`, `groq.py`, `fake.py`, `registry.py`, `pricing.py`; `app/providers/search/base.py`, `serper.py`, `duckduckgo.py`, `registry.py`; `app/providers/fetch/http.py`, `extract.py`; fixtures under `tests/fixtures/`.

Acceptance:

- `LLMProvider.complete()` and `complete_json()` implemented with fence stripping, one repair turn, schema validation, typed `SkillValidationError`.
- Groq provider honours `retry-after`, retries 429/5xx/timeout with exponential backoff, captures tokens and latency.
- Serper and DDG return the same `SearchResult` shape; 24 h cache; query budget.
- Fetcher enforces schemes, rejects private/loopback ranges (SSRF), caps size/redirects, respects robots for non-user-supplied URLs.
- Extractor returns > 400 chars from a real careers-page fixture and reports failure on a JS-only fixture.
- Tests use `httpx.MockTransport`; the suite still makes no outbound calls.

### 2. Portfolio RAG (Phase 3)

Files: `app/rag/ingest.py`, `app/rag/retrieve.py`, `app/rag/grounding.py`, `app/routes/pages.py` (reindex endpoint), settings panel.

Acceptance:

- Incremental ingest keyed by file hash; heading-aware chunks (700–900 chars, 120 overlap); FTS5 rebuilt correctly; re-running changes nothing.
- Query builder from a job; BM25 with heading boost; top-k packed to a token budget.
- `check_numbers()` flags `35%` but accepts `11.8%`, `1,240`, `310 ms`.
- Retrieval test for "speech recognition WER Swahili" returns the chunk containing `23.4% → 11.8%`.

### 3. Ingestion + extraction + job page (Phase 4)

Files: `app/routes/jobs.py`, `app/repositories/*`, `app/skills/job_extraction.py`, `job_summary.py`, `app/jobs/pipeline.py`, `worker.py`, `app/templates/job_detail.html`, `partials/run_progress.html`, `app/static/js/poll.js`, `job_detail.js`.

Acceptance:

- `POST /api/jobs` with a URL or text creates company + job + run, returns 202 with `poll_url`.
- Fingerprint dedupe returns 409 with the existing job; `?attach=1` starts a run instead.
- Run state machine matches design §15.4, including atomic claim, cancel between steps, and interrupted sweep on restart.
- Job page polls every 1.5 s, backs off, pauses when hidden, and reloads on success.
- Extraction failure shows which skill failed and offers Retry.

---

## How to resume

```bash
cd job_search
python -m pytest -q                       # 30 passing now
python -m uvicorn app.main:app --reload --port 8000
```

Dev login: `lyle` / `skipper-dev` (seeded only when the users table is empty and `SKIPPER_ADMIN_PASSWORD` is unset). Set `SKIPPER_ADMIN_PASSWORD` before the first boot to avoid it.

Environment: copy `.env.example` to `.env`. `SKIPPER_LLM_PROVIDER=fake` keeps everything offline; switch to `groq` with `SKIPPER_GROQ_API_KEY` for real generation. `SKIPPER_SEARCH_PROVIDER=duckduckgo` needs no key.

Useful checks:

```bash
curl -s localhost:8000/healthz
curl -s localhost:8000/readyz
sqlite3 var/skipper.db ".tables"
```

Database file: `var/skipper.db` (gitignored). Deleting it recreates everything and reseeds the account.

### Files a new agent should read first

1. `docs/design.md` §6 (runtime), §10 (data model), §15 (skills/pipeline), §19 (frontend).
2. `docs/steps.md` Phase 2 onward.
3. `app/domain.py` (statuses, transitions, skill manifest) and `app/models.py` (schema).
4. This file, section "Next three tasks".

---

## Known issues / caveats

- `/jobs` and `/companies` render empty states only; `/companies/{id}` and `/jobs/{id}` routes do not exist yet (Phase 4/7). The dashboard links to `/jobs/{id}` only when rows exist, so nothing 404s today.
- `Add job` is a disabled-looking control on purpose; it becomes a modal in Phase 4.
- No Alembic yet: `create_all` will not alter existing tables. When the first post-v1 schema change is needed, add Alembic before touching models (design §24).
- `login_attempts` grows to one day of failures; cleaned on each failure write.
- LibreOffice is not required for tests; `/readyz` reports `pdf_engine: reportlab` when `soffice` is absent.
- No CSRF token on the HTML login form: it is protected by same-site cookies and an origin check on the JSON endpoint. Revisit if the form ever accepts cross-site posts (it does not by design).
- The repository is uncommitted at the time of writing (`job_search/` is untracked). Commit with the phase message from `docs/steps.md` when ready.

---

## Command log (latest first)

```text
2026-11-19  python -m pytest -q                                  → 30 passed
2026-11-19  uvicorn app.main:app --port 8123                     → landing 200, healthz ok
2026-11-19  playwright landing/dashboard at 1440 / 375           → 0 overflow, 0 console errors
2026-11-19  python -m compileall app                            → clean
```
