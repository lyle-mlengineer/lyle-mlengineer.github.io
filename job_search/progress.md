# Skipper — Progress

The build follows [`docs/steps.md`](docs/steps.md). Each phase ends with a working app, a passing test run and (when the repo is committed) a commit.

**Current phase:** 5 complete — tailored CV as DOCX and PDF
**Next phase:** 6 — the remaining eight skills and the full application pack
**Last updated:** 2026-11-19
**Suite:** 176 tests passing offline (`python -m pytest -q`)

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

- `app/templates/landing.html` — rebuilt portfolio: fixed header with a **Dashboard** button, hero (blob portrait, status pill, two CTAs, privacy note), **Skipper** section (three feature cards, 11-skill chip list, paste → run → send steps, gated-dashboard CTA), about with stats and a CV picker listing all six role variants (PDFs open in a new tab), all four portfolio skill groups with 16 bars and 49 toolchain chips, all ten projects in the selected-work grid, contact panel, footer. No Swiper, no build step.
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

### Step 2 — Provider seams

- `app/validation.py` — dependency-free JSON schema validation (`type`, `required`, `properties`, `items`, `enum`, `min_len`, `nullable`), with every failure path reported so repair prompts can name them.
- `app/providers/llm/base.py` — `ChatMessage`, `LLMResponse`, `LLMProvider` ABC, shared `complete_json()`: fence stripping, one repair turn carrying the exact errors, typed `SkillValidationError`.
- `app/providers/llm/groq.py` — Groq chat completions with JSON mode, `max_completion_tokens`, `reasoning_effort=low` for gpt-oss, per-process TPM token bucket, retry on 429/5xx/timeouts honouring `retry-after`, no retry on 4xx, token/latency capture.
- `app/providers/llm/fake.py` — deterministic provider keyed by conversation marker, so the whole app and every pipeline test runs without a key.
- `app/providers/llm/cache.py` — exact-match cache keyed on provider, model, temperature, response format and full messages; hits return `tokens_in=0`.
- `app/providers/llm/pricing.py` — approximate USD cost from token usage for the run summary.
- `app/providers/llm/registry.py` — settings → provider, with cache wrapping and an explicit error when `groq` is selected without a key.
- `app/providers/search/base.py` — `SearchResult`, `SearchProvider`, `SearchBudget`/`BudgetExceeded`, `BudgetedSearchProvider` (budget counts network calls, not cache hits).
- `app/providers/search/serper.py` — Serper organic results, recency windows (`qdr:d/w/m/y`), clear errors on 4xx.
- `app/providers/search/duckduckgo.py` — HTML endpoint plus lite fallback, `uddg=` unwrapping, no key required.
- `app/providers/search/registry.py` — `AutoSearchProvider` (Serper → DDG on error or empty), 24-hour `CachedSearchProvider`, and the builder used by the app.
- `app/providers/fetch/extract.py` — chrome stripping, container scoring by text-minus-links, Markdown-ish headings/bullets; pages under 400 characters are reported as JavaScript-only instead of silently empty.
- `app/providers/fetch/http.py` — SSRF guard (scheme/credential checks, DNS resolution, every redirect hop re-checked, non-public addresses refused), robots.txt for crawled links only, streaming 3 MB cap, HTML content-type requirement, redirect limit.
- Providers are constructed once in the app lifespan and exposed as `app.state.llm`, `app.state.search` and `app.state.session_factory`; `/readyz` already reports key configuration.
- Tests: `test_validation.py`, `test_llm.py`, `test_search.py`, `test_fetch.py` with `httpx.MockTransport`, real pages as fixtures, and no outbound traffic.

### Step 3 — Portfolio RAG

- `app/rag/ingest.py` — SHA-256 per file, so a second run writes nothing; heading-aware sections (`#` sets the title, `##`/`###` become chunk headings); paragraph blocks split at sentence and word boundaries; 700–900 character windows with a ~120 character overlap; FTS5 rows inserted with the chunk id as `rowid`.
- `app/rag/retrieve.py` — job → query builder (title, seniority, skills, first 600 characters of the description), stop-words and duplicate terms removed, OR-joined quoted terms; SQLite `bm25()` with a 2× heading boost; top-k results packed to a 3,500 character context budget with `doc_title › heading` citations.
- `app/rag/grounding.py` — `extract_numbers()` understands percentages, `ms`, `GB`, `MB`, `hours`, `voices`, `users`, `creators`, `x` and comma thousands; `check_numbers()` returns unsupported tokens (`35%`) while accepting corpus values (`11.8%`, `1,240`, `310 ms`); `grounding_report()` adds the full checked list.
- Startup indexing in `app/main.py` (changed documents only, failures logged without taking the app down), `POST /settings/reindex` for the settings page, and `POST /api/portfolio/reindex` returning `{docs_indexed, docs_skipped, docs_removed, chunks, changed}`.
- Settings page shows document/chunk counts and a reindex form with a post/redirect/get notice; `/readyz` already reports `portfolio_chunks`.
- Tests: `tests/test_rag.py` — chunk sizes and headings, idempotent re-ingest, doc/chunk counts, the WER query, budget packing, empty queries, number parsing, grounding, settings reindex, CSRF and the JSON API.
- Measured fresh ingest: **23 ms** for 5 documents / 35 chunks (budget in design §22 is 2 s for the whole cold start).

### Step 4 — Ingestion, extraction and the job page

- `app/jobs/ingest.py` — exactly one of a link or pasted text; links canonicalised (lowercased host, tracking parameters and fragments removed, 2,048-character cap), fetched through the SSRF-guarded fetcher, and rejected with "paste the text instead" when the page yields under 400 characters. Text is accepted at 200–60,000 characters and a longer paste is truncated with a job event.
- Stable duplicate key: `Job.fingerprint` is `sha1("url|" + canonical_url)` or `sha1("text|" + normalised_text)` and never changes when extraction renames the job. That is what makes the second paste return `409 duplicate_job` with the existing `job_id`, while `?attach=1` queues another run on the same job. (Design §11.2 originally proposed a post-extraction company/title/location key; a key that changes after creation cannot reliably dedupe. Recorded here and in design.)
- `app/skills/base.py` — `SkillContext`, `SkillResult`, grounding rules, prompt hashing, shared `execute()` around `llm.complete_json()`.
- `app/skills/job_extraction.py` — schema plus postprocessing: salary integers and currency shape, `remote/hybrid/onsite`, employment and seniority vocabularies, deadline normalisation, list clamping and keyword dedupe.
- `app/skills/job_summary.py` — second skill, small tier, renders the `job_summary` Markdown artifact with what-you-do / what-they-want / why-it-matters / fit / gaps.
- `app/jobs/pipeline.py` — atomic claim (`UPDATE … WHERE status='queued'`), deterministic step order, per-step timing/tokens/prompt hash, weighted progress, token and minute ceilings, cancel checks between steps, optional-step handling, `failed` with a human message, artifact versioning (`is_current` flip), company resolution, and resume from the latest succeeded run's outputs.
- `app/jobs/render.py` — escapes model Markdown before adding headings, lists and bold; no `|safe` on raw output.
- `app/routes/jobs.py` — `POST /api/jobs` (202 with `job_id`, `run_id`, `poll_url`; 409 duplicate; 422 unreadable/short), `GET /api/runs/{id}`, `POST /api/runs/{id}/cancel`, `POST /api/jobs/{id}/runs` for retry/resume (single-flight 409).
- `app/templates/jobs.html` + `app/static/js/add_job.js` — filterable list and an accessible native dialog with link/paste tabs, inline errors and redirect to the job page.
- `app/templates/job_detail.html` + `poll.js` + `job_detail.js` — progress bar, per-step states and timings, cancel/retry, safe summary, extracted chips, timeline and run cost. Polling is 1.5 s → 2 s after 30 s → 5 s after 3 min, pauses while hidden, gives up after five consecutive failures.
- Hero fix: the SVG `<image>` was sized in user units by `.home__blob-img { width: 26rem }`, rendering it 865 px wide inside a 416 px blob. It now fills the viewBox with `xMidYMin slice` and uses a pre-cropped 832×778 asset (`lyle-hero-2x.jpg`, 107 KB) so the browser is not downscaling a 1792×2400 JPEG through SVG.
- Tests: `tests/test_jobs.py` — text and URL ingestion, short/both-input rejection, auth/CSRF, duplicate + attach, source provenance, unreadable page, failed extraction and retry, cancel, single-flight, resume without new tokens, URL canonicalisation, fingerprinting and Markdown escaping.

### Step 5 — Tailored CV, DOCX and PDF

- `app/skills/cv_writing.py` — resume schema and prompt (headline, summary, four skill groups, five roles max, three projects), with dates normalised to `2024 – Present`, bullets clamped to five per role, duplicate bullets removed, and section order fixed for ATS readers. The prompt receives the job, its extraction and the portfolio corpus (profile, experience, skills, projects) wrapped as untrusted data.
- Numeric grounding runs in postprocessing, not just in the prompt: `check_numbers()` compares every claim with the corpus and unsupported tokens are replaced with "measurably" and logged. The fixture CV therefore keeps 23.4%, 11.8%, 1,240 hours, 310 ms and 42 voices, and cannot carry a dimension the portfolio does not state.
- `app/documents/resume.py` — canonical identity and ATS-safe names: `LYLE-OKOTH-ACME-SPEECH-SENIOR-MACHINE-LEARNING-ENGINEER-CV-v1.pdf`, company/role slugged, capped at 90 characters.
- `app/documents/cv_docx.py` — one-column Calibri A4, 0.45–0.5" margins, name 18 pt, ruled section headings, right-aligned dates, real hyperlinks, no tables or text boxes. Compact spacing keeps the fixture to two pages.
- `app/documents/cv_pdf.py` — LibreOffice `soffice` conversion with an isolated profile, 60 s timeout and temp-dir cleanup; isolating the profile stops a running desktop LibreOffice from deadlocking it. The reportlab fallback renders the same model with A4 margins, rules and bullets, and is the deterministic path used by the suite. `pdf_page_count()` reads page objects without an extra dependency.
- `app/documents/storage.py` — renders both formats at one shared version, writes bytes to `var/artifacts/job-<id>/`, stores sha256/bytes/download name plus the resume JSON and page count, flips `is_current` for the pair, and logs an event. Path resolution refuses anything outside `SKIPPER_ARTIFACTS_DIR`.
- `app/jobs/pipeline.py` — CV is step 3 of the full run (`job_extraction` → `job_summary` → `cv_writing`), required, weight 3.0. Failure marks the run failed; the completed brief stays current. Regeneration runs only the target skill but keeps its dependency outputs, so the extraction prompt is still available.
- `app/routes/jobs.py` — `POST /api/jobs/{id}/regenerate {skill}` (single skill, 409 when extraction is missing), session-gated `GET /api/artifacts/{id}/download` with a filename and attachment header, and `GET /api/artifacts/{id}/preview` for the embedded viewer.
- `app/templates/job_detail.html` + CSS — CV panel with PDF frame, PDF/DOCX downloads, Regenerate, version/page/engine metadata and an honest empty state. The CSP stays `frame-ancestors 'none'` everywhere except the preview response, which allows same-origin framing only.
- Tests: `tests/test_documents.py` — DOCX text contains the name, headline, employers, bullets and section order; fallback PDF is `%PDF-`, two pages; filenames are sanitised; unsupported numbers are scrubbed; pipeline CV is grounded, downloadable and framed; regeneration creates v2 while v1 stays downloadable; download is session-gated and regenerating needs CSRF.

### Step 5.1 — Regenerate fix, job-page polish and document parity

- **CV Regenerate was dead in the browser.** The button carried `id="cv-regenerate"` but not the `data-regenerate` attribute that `job_detail.js` delegates from, so clicking it did nothing. It now carries both; a regression test asserts the hook is in the rendered page, and a Playwright click took a live job from CV v1 to v2 with v1 still downloadable.
- `app/jobs/render.py` now understands `[label](url)` links, which company research emits for news and sources. Only `http`/`https` URLs become anchors (`target="_blank" rel="noopener noreferrer"`); anything else stays literal escaped text. Link text is escaped before markup, so a prompt-injected `<img onerror>` cannot survive. Two tests cover the allowlist and the escaping.
- Job page sections restyled on the existing tokens:
  - **Company brief** — `.panel--dossier` with an accent top border, a soft corner glow, uppercase section rules with a colour chip, a lead paragraph, pink bullet markers and linked citations.
  - **Brief** — `.panel--brief` with a tinted header wash; the posting's deck line becomes an accent heading, the one-liner sits on a left accent rule, and each section heading carries a gradient rule with arrow bullets.
  - **Timeline** — replaced the stacked list rows with `.timeline`: hairline rail, iconised dots per event type, status pills, note and tabular-figure timestamp.
- **CV and cover letter now share one letterhead.** `identity_header()` in `cv_docx.py` is public and used by `letters.py`: centred name 18 pt, uppercase role tagline 11.5 pt, contact 10 pt, real hyperlinks 9 pt, navy hairline. The cover letter gains a rule and a date line and stays one page; CV role headers moved to 11 pt / 10.5 pt dates to match `cv/_generate_cvs.py`. Rendered with LibreOffice: CV 2 pages, letter 1 page.
- `/readyz` now reports the PDF engine the renderer will actually use. It called `shutil.which()` only, so a Windows LibreOffice install (found by `find_soffice()` in the standard paths) was reported as `reportlab` while every CV rendered through LibreOffice. Both now share `find_soffice()`.
- Verified in a browser at 320, 375 and 1440 px: zero horizontal overflow, zero console errors, 8 timeline entries with rails and dots, `data-regenerate` present, and the Regenerate click produced CV v2 (`libreoffice`, 2 pages) with v1 kept in history. Screenshots: `var/logs/styled-job-1440.png`, `styled-job-375.png`, `styled-job-after-regen.png`, `section-research.png`, `section-brief.png`, `section-timeline.png`.

### Step 6 — Application pack, resources dashboard and resume/retry

- **Resume and retry.** `POST /api/jobs/{id}/resume` continues a stopped run (failed, cancelled or interrupted) from its first unfinished step. `run_remaining_skills()` derives the work left, `create_run(..., kind="resume")` queues only those steps, and `_prior_outputs()` now reads the succeeded steps of recent runs — including a failed or interrupted one — so a resume never re-pays for work already done. The job page shows **Resume run** plus **Start over**, a per-step **Retry** for failed optional steps, and the remaining step count in the run hint. Resuming needs login and CSRF, refuses a job with a run in flight, and refuses a run that already succeeded (regenerate an artifact instead).
- **Usage ledger.** Every model call lands in `llm_calls` and every search in `search_calls` (job, run, skill, provider, model, tokens, cost, latency, cache flag), attributed by `call_context()` in the pipeline and wrapped outside the cache so a hit is recorded as free rather than invisible. `app/usage.py` aggregates per job and per day, falls back to run totals for jobs older than the ledger, and feeds `/resources` — stat cards, CSS-only charts, filters (query, status, model, skill, window) and a per-job table.
- **Providers.** Groq and NVIDIA NIM share one OpenAI-compatible transport (`openai_compat.py`); Groq keeps its exact retry and rate-limit behaviour, NVIDIA adds DeepSeek V4 pro/flash with `max_tokens` and a `reasoning_effort` map that defaults to `none`. Each provider carries its own default model pair, so switching `SKIPPER_LLM_PROVIDER` is enough.
- **The rest of the pack.** Company research, cover letter, email, three spoken answers and two interview briefs, plus the company detail page (`/companies/{id}`) that previously 404'd. Spoken answers keep their paragraph breaks end to end (`prose_text()`, paragraph-preserving clichés/clipping) and render as scannable blocks with a `+`/`−` collapsible marker.
- **CSS token repair.** `--line`, `--text-muted` and `--radius-sm` were referenced but never defined, which silently voided every dashboard border and radius (including the collapsible marker). They are now aliases in `style.css`, and a test fails if `app.css` uses an undefined custom property.
- Tests: `tests/test_resume.py` (resume after a failure, prior outputs reused, 409 in flight, 409 already finished, auth/CSRF, 404), `tests/test_resources.py` (ledger writes, search pricing, cache hits, filters, empty states, company page) and `tests/test_llm.py` (NVIDIA payload, effort map, JSON-mode fallback, missing key, model resolution).

### Verification performed

- `python -m pytest -q` → **176 passed**, no network access.
- `ruff check app tests` → clean.
- Server booted on `127.0.0.1:8127` and `:8130`: `/readyz` reports `portfolio_chunks: 35`; a pasted posting ran end to end with the fake provider, reached `reviewing`, and produced the summary artifact.
- Playwright at 1440/768/375/320 px: add-job dialog centred at every width, zero horizontal overflow on `/jobs` and `/jobs/{id}`, zero console errors; filters return one row for `q=Acme` and the empty state for an unmatched query.
- Phase 5 browser check at 1440 and 375 px: CV panel shows PDF/DOCX/Regenerate, preview frame is 1082 px on desktop and 290 px on mobile, zero horizontal overflow, zero console errors. Headed Chromium renders the two-page PDF viewer inside the frame; headless Chromium leaves the PDF plugin area blank, so the visual check used a headed browser.
- Playwright (Chromium) checks at 1920/1440/768/375/320 px across `/dashboard`, `/jobs`, `/companies`, `/settings` and `/`: zero horizontal overflow, zero console errors. Settings reindex form and counts verified after login.
- Visual pass on the app shell and settings page: removed a duplicate dashboard render caused by a template block collision, centred a 1240 px content column, rebuilt stat cards and panels, fixed the old two-column `.kv` rule that fought the new row markup, and hid the landing page's scroll-up button inside the app (it overlapped the last card). Screenshots: `var/logs/final-dash-1440.png`, `final-settings2.png`, `settings-375.png`, `landing-1920.png`.
- Playwright (Chromium) checks at 1440 and 375 px:
  - horizontal overflow `0` on landing and dashboard;
  - no console errors;
  - `#nav-toggle` opens the mobile menu (`#nav-menu` bottom = 0);
  - dashboard bottom tab bar visible on mobile;
  - form login with the dev account reaches `/dashboard`.
- Screenshots: `var/logs/landing-full-1440.png`, `landing-full-375.png`, `landing-nav-open-375.png`, `landing-dark-1440.png`, `login-1440.png`, `dashboard-1440.png`, `dashboard-375.png`. Visual review found and fixed: a collapsed skills card that looked empty, footer link wrapping and crowded socials, and excess hero top spacing.
- Landing refresh verified with Playwright: all ten project images load after lazy-scroll (`naturalWidth > 0`), ten work cards, four skill groups with 16 bars and 49 chips, six CV entries, dropdown fits and stays inside the viewport at 320/375/414/480/768/1440 px, `Escape` closes it, and every CV link is `target="_blank"` pointing at a served PDF.
- Docs updated for the SQLAlchemy 2.0 switch and the completed provider seams; design §12/§13/§19 and the README status table match the code.

---

## Deliberately not built yet

| Thing | Why it is absent | Where it lands |
| --- | --- | --- |
| Cover letter, research, email, spoken and interview skills | Need their schemas and renderers | Phase 6 |
| Status controls and company detail pages | Depend on the remaining skills | Phase 7 |
| Artifact editing and version switching | Regeneration exists for CV; editing is Phase 8 | Phase 8 |
| Alembic | `create_all` is acceptable pre-release; no deployed schema yet | Before first deploy |

The UI does not pretend: empty states name the next real action, `/settings` lists what is still pending, and a failed run keeps its artifacts and offers a retry instead of showing a success.

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
9. **Source-stable fingerprints, not extracted-field fingerprints.** Extraction can rename `title` and fill `company`, so the duplicate key must be fixed at creation. See Step 4 above; design §11.2 carries the same note.
10. **The job page stops at `reviewing` after extraction + summary + CV.** `ready` is reserved for when the full application pack exists, so the status never overstates what the app has produced.
11. **Numeric grounding is enforced after generation.** `cv_writing` scrubs any number absent from the portfolio and logs it; a prompt instruction alone would not survive a creative model.
12. **CV artifacts share one version across PDF and DOCX.** Regenerating writes v2 for both and flips v1 to non-current, so the pair never disagrees.

---

## Next three tasks (pick up here)

### 1. Remaining skills and the application pack (Phase 6)

Files: `app/skills/company_research.py`, `cover_letter.py`, `email_writing.py`, the spoken and interview skills, `app/jobs/prompts.py`, `app/rag/grounding.py` wiring, `app/templates/partials/artifact_viewer.html`.

Acceptance:

- Every skill declares its schema, tier, weight and required/optional status from `app/domain.py`.
- Prompts wrap sources in `<untrusted>` and use `<portfolio>` as the only factual source; numeric claims pass `check_numbers()`.
- A fake-provider run produces all eleven artifacts; one invalid model response is repaired, not silently dropped.
- The pack only marks a job `ready` when its required artifacts exist.

### 2. Tracking, status controls and company pages (Phase 7)

Files: `app/routes/jobs.py` (PATCH/DELETE), `app/routes/companies.py`, company detail template, status control, `tests/test_tracking.py`.

Acceptance:

- `PATCH /api/jobs/{id}` enforces `STATUS_TRANSITIONS` and writes an event for every change.
- Applied/interviewing jobs get a next action and date; the dashboard follows up on them.
- Company cards show research, jobs and notes; archive is reversible and never deletes artifacts.
- Filtering, sorting and pagination stay responsive at 320 px with the mobile card layout.

### 3. Deployment and hand-off (Phase 9)

Files: `Dockerfile`, README deploy section, backup/restore drill. The portfolio's Skipper link currently points at the source folder; replace it with the hosted URL on the root `index.html` once deployed.

Acceptance:

- One command builds an image with LibreOffice and the app starts with `/readyz` green.
- A backup/restore drill reproduces the same job and artifact counts.
- Root portfolio link opens the hosted Skipper; HTTPS, real password, single worker documented.

---

## How to resume

```bash
cd job_search
python -m pytest -q                       # 134 passing now
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

- `/companies` is still a list/empty state; `/companies/{id}` lands in Phase 7.
- No Alembic yet: `create_all` will not alter existing tables. When the first post-v1 schema change is needed, add Alembic before touching models (design §24).
- `login_attempts` grows to one day of failures; cleaned on each failure write.
- LibreOffice is not required for tests; `/readyz` reports `pdf_engine: reportlab` when `soffice` is absent.
- No CSRF token on the HTML login form: it is protected by same-site cookies and an origin check on the JSON endpoint. Revisit if the form ever accepts cross-site posts (it does not by design).
- CV PDFs under `app/static/cv/` are copies of `../cv/*.pdf`. Re-copy them whenever the CV generator runs; the dashboard-generated CVs are separate artifacts.
- Three skills are wired (`job_extraction`, `job_summary`, `cv_writing`); the remaining eight are Phase 6. A fake run produces the brief and CV, not the full pack.
- CV PDFs under `app/static/cv/` are copies of `../cv/*.pdf`; generated CVs live under `var/artifacts/job-<id>/`.

---

## Command log (latest first)

```text
2026-11-19  python -m pytest                                       → 176 passed
2026-11-19  ruff check app tests                                   → clean
2026-11-19  python -m pytest                                       → 146 passed
2026-11-19  playwright CV regenerate click, 3 widths                → v1 → v2, 0 overflow, 0 console errors
2026-11-19  libreoffice CV / letter render                          → 2 pages / 1 page
2026-11-19  python -m pytest -q                                  → 134 passed
2026-11-19  playwright headed CV preview 1440 / 375              → PDF renders, 0 overflow, 0 console errors
2026-11-19  fallback CV benchmark                                 → 2 pages, 14.4 KB, reportlab
2026-11-19  playwright jobs/detail/modal at 1440–320             → 0 overflow, 0 console errors
2026-11-19  fake end-to-end paste                               → reviewing, summary + CV, 3/3 steps
2026-11-19  python -m pytest -q                                  → 109 passed
2026-11-19  ruff check app tests                                → clean
2026-11-19  playwright app pages at 1920–320                    → 0 overflow, 0 console errors
2026-11-19  fresh portfolio ingest benchmark                    → 23 ms (5 docs, 35 chunks)
2026-11-19  uvicorn app.main:app --port 8127                     → readyz chunks=35, startup index log
2026-11-19  python -m pytest -q                                  → 93 passed
2026-11-19  uvicorn app.main:app --port 8123                     → landing 200, healthz ok
2026-11-19  playwright landing/dashboard at 1440 / 375           → 0 overflow, 0 console errors
2026-11-19  python -m compileall app                            → clean
2026-11-19  ruff check app tests                                   → clean
2026-11-19  playwright landing, CV picker, skills, work at 320–1440 → 0 overflow, 10/10 images, 6 CV links
```
