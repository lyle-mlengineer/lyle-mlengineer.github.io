# Skipper — Implementation Steps

**Version:** 1.0
**Date:** November 2026
**Target:** v1 (landing page, auth, job ingestion, 11 skills, artifacts, dashboard)
**Companion documents:** `design.md`, `prd.md`, `../progress.md`

---

## How to use this document

This is the build order, not a wish list. Each phase has a **goal**, **deliverables**, **tasks**, **tests** and **exit criteria**. Do not start a phase until the previous phase's exit criteria pass, unless the phase is explicitly marked as parallel.

Estimates assume one engineer who knows Python and FastAPI. A task is done when it has: code, a test where a test is meaningful, and a line in the README (or the OpenAPI/route description). Checkboxes here are the plan; live status lives in `../progress.md`.

---

## Ground rules

1. **The static portfolio at the repo root is read-only.** Copy assets out of it; never edit `index.html`, `css/style.css`, `js/main.js` in place.
2. **No fabricated facts.** Skills receive a portfolio context block; outputs are validated; numeric claims are checked against the corpus.
3. **Every phase leaves the app runnable.** No long-lived broken `main`.
4. **Provider seams before providers.** Write the ABC, the fake, the tests, then the real HTTP client.
5. **No hidden background state.** If a run is `running`, a row says so; if the server dies, it becomes `interrupted`.
6. **Models are the schema.** Declare tables in `app/models.py`. `create_all` is pre-release only; once v1 is deployed, every change ships as a forward-only Alembic revision guarded by `schema_version`.
7. **Secrets from env only.** Never in templates, fixtures, logs or commits.
8. **Tests never hit the network.** `FakeLLMProvider`, `FakeSearchProvider` and saved HTML fixtures only.

---

## Phase 0 — Foundations (0.5 day)

**Goal:** a repository that boots, migrates, health-checks and tests itself.

**Deliverables**

- `job_search/pyproject.toml` — deps, `ruff`, `pytest`, `pyproject` metadata.
- `job_search/.env.example` — every variable from design §9, no real secrets.
- `job_search/README.md` — setup, run, test, deploy.
- `app/config.py` — `pydantic-settings`, `SKIPPER_` prefix, validation.
- `app/models.py` — SQLAlchemy 2.0 declarative models for every entity in design §10.2 (Base, typed `Mapped[...]` columns, relationships, indexes, unique constraints).
- `app/db.py` — engine per database path (WAL, `foreign_keys=ON`, `busy_timeout`), `sessionmaker`, `session_scope`, `create_all` bootstrap, `schema_version`, startup sweeps.
- `app/domain.py` — status vocabularies, transition table, skill manifest and labels.
- `app/main.py` — app factory, lifespan (migrate → sweeps → reindex), request-id + security-headers middleware, routers.
- `app/routes/health.py` — `/healthz`, `/readyz`.
- `tests/conftest.py` — temp DB, `TestClient`/ASGI client, provider fakes.

**Tasks**

1. Create the package layout from design §7 (empty modules with docstrings are fine).
2. Write the ORM models and the bootstrap; assert idempotence by running startup twice in a test. Verify the FTS5 virtual table is created by raw DDL after `create_all`.
3. Implement request-id middleware (`X-Request-Id`, generated if absent) and structured logging.
4. Implement security headers middleware (CSP, nosniff, referrer policy, frame denial).
5. Add `ar`-free `Makefile`-ish commands to README: `python -m uvicorn app.main:app --reload`.

**Tests**

- Startup creates all tables and the FTS5 index; second startup is a no-op and inserts no duplicate `schema_version`.
- `/healthz` 200 without DB; `/readyz` reports component statuses.
- Request id is echoed; a missing one is generated.
- `get_settings()` fails loudly when `SKIPPER_LLM_PROVIDER=groq` and no key (validation message names the variable).

**Exit criteria:** `pytest` green on a fresh clone with no `.env` (fake provider default in tests), app boots in < 2 s, `README` runs the app.

**Commit:** `chore(skipper): scaffold FastAPI app, schema and config`

---

## Phase 1 — Landing page, auth and app shell

**Goal:** the public face and the front door. Someone can land on `/`, read the portfolio, click Dashboard, log in and reach an (empty) dashboard.

**Deliverables**

- `app/templates/landing.html` — rebuilt portfolio: header/nav, hero with portrait and two CTAs, **Skipper** section (what it does, skill chips, paste → run → apply strip, CSS-built product panel), selected work grid, condensed about, contact, footer, theme toggle.
- `app/static/css/style.css` — portfolio token sheet copied from `../../css/style.css` and trimmed (no Swiper, no unused blog/testimonial rules).
- `app/static/css/landing.css` — new section styling that only uses brand tokens.
- `app/static/js/main.js` + `theme.js` — nav toggle, scroll header, active link, theme persistence, scroll-to-top. No dependencies.
- `app/templates/login.html` + `app/routes/auth.py` + `app/security.py` — argon2id, sessions, CSRF, throttle, redirect with `next`.
- `app/templates/base.html` + `dashboard.html` + rail/top-bar app shell, empty state ("No jobs yet — add your first one").
- `app/routes/pages.py` — `/`, `/login`, `/dashboard`.
- `data/portfolio/*.md` — initial corpus files (profile, experience, projects, skills, writing), written by hand from the CVs.

**Tasks**

1. Copy only the assets the page uses into `app/static/img/` (portraits, project screenshots, favicons); keep filenames.
2. Rebuild the landing page by hand — same classes, same tokens; no Swiper; static project grid.
3. Add the Skipper sections with a "Dashboard" CTA (`/login?next=/dashboard`) and a secondary "Add a job" mention for signed-in users.
4. Implement `security.py`: `hash_password`, `verify_password`, `create_session`, `get_session`, `require_user`, `csrf_for`, `verify_csrf`, `LoginThrottle`.
5. Seed the single user at first boot from env; log a warning if `SKIPPER_ADMIN_PASSWORD` is set after the user exists.
6. Build the app shell: left rail (desktop), bottom tabs (mobile), top bar with **Add job** (disabled until Phase 4), account menu with sign out.
7. Verify landing/auth at 320, 768 and 1440 px, light and dark.

**Tests**

- `/` 200 with no DB rows and no provider keys; contains hero, Skipper section, Dashboard link.
- `/dashboard` redirects to `/login?next=/dashboard` when anonymous.
- Correct credentials set a session cookie (`HttpOnly`, `SameSite=Lax`) and redirect to `next` only when it is a local path.
- Wrong password: generic 401/redirect, no user enumeration; 6th attempt within 15 min is throttled.
- Mutation without `X-CSRF-Token` → 403.
- Logout deletes the session row; the cookie no longer authenticates.
- Landing page HTML < 120 KB and contains no `mailto:` other than contact.

**Exit criteria:** browser check at three widths in both themes; auth tests green; landing screenshots committed to `docs/` or recorded in `progress.md`.

**Commit:** `feat(skipper): landing page shell, session auth and app chrome`

---

## Phase 2 — Provider seams

**Goal:** every external call goes through an interface that tests can replace.

**Deliverables**

- `providers/llm/base.py` — `ChatMessage`, `LLMResponse`, `LLMProvider` ABC, `complete_json` (parse → repair → validate), `SkillValidationError`.
- `providers/llm/groq.py` — Groq over `httpx` with tier→model map, token bucket, retries, `retry-after`, JSON mode, latency/token capture.
- `providers/llm/fake.py` — deterministic provider: maps prompt hash/skill name → fixture payloads; records calls.
- `providers/llm/pricing.py` + `registry.py` — model routing and cost table.
- `providers/search/base.py`, `serper.py`, `duckduckgo.py`, `registry.py` — plus 24 h cache and query budget.
- `providers/fetch/http.py` + `extract.py` — SSRF guard, robots, size/time caps, article extraction.
- Fixtures: saved careers-page HTML, Groq/Serper/DDG response JSON.

**Tasks**

1. Define the ABCs exactly as design §12/§13; no provider-specific types leak upward.
2. Implement the token bucket and retry policy; unit-test 429/500/timeout paths with a mocked transport.
3. Implement `complete_json` with fence stripping, one repair turn, schema validation.
4. Implement Serper and DDG parsers against fixtures; unwrap DDG redirects; dedupe results by URL.
5. Implement article extraction scoring (`main`/`article`/class hints) with a text-density heuristic; test on a real saved careers page and a JS-only page.
6. Add `FakeSearchProvider` returning fixture results and `FakeFetcher` serving fixture HTML by URL.
7. Wire `registry.build_providers(settings)` and expose health for `/readyz`.

**Tests**

- `complete_json` repairs a fenced/truncated JSON reply; fails after two attempts with a typed error.
- Retry: two 429s then success; 401 not retried; budget exhaustion raises `BudgetExceeded`.
- Serper and DDG maps produce identical `SearchResult` shape; cache hit does not call transport.
- Extractor returns > 400 chars from the careers-page fixture and < 400 from the JS-only fixture.
- SSRF guard rejects `http://127.0.0.1`, `http://10.0.0.5`, `file://`, and a redirect into a private range.

**Exit criteria:** the app runs the whole test suite with zero outbound sockets; a manual smoke call to Groq and Serper succeeds when keys are present.

**Commit:** `feat(skipper): LLM, search and fetch provider seams with fakes`

---

## Phase 3 — Portfolio corpus and RAG

**Goal:** a maintained source of truth about Lyle that every skill cites.

**Deliverables**

- `data/portfolio/profile.md`, `experience.md`, `projects.md`, `skills.md`, `writing.md` — human-editable, factual, with metrics in their canonical form.
- `app/rag/ingest.py` — hash-based incremental ingest through the ORM, heading-aware chunking (~700–900 chars, 120 overlap), FTS5 population via raw SQL (the index is not a mapped entity).
- `app/rag/retrieve.py` — query builder from a job (title, must-haves, keywords), `bm25` field boosts, top-k, dedupe, context packing to a token budget.
- `POST /api/portfolio/reindex` + settings page toggle.
- `tests/fixtures/portfolio/` for deterministic tests.

**Tasks**

1. Write the corpus from `cv/_generate_cvs.py` content: canonical numbers (`23.4% → 11.8% WER`, `1,240 hours`, `310 ms`), real employers, real dates. No aspirational claims.
2. Chunk with heading context so a bullet never loses its section.
3. Query builder strips stop-words, weights title tokens, OR-joins terms; add exact-match boost for skill names.
4. Add a `/settings` panel showing document count, chunk count, last index time and a "test retrieval" box.
5. Add a grounding helper `rag/grounding.py::check_numbers(text, corpus)` returning unmatched numeric tokens for postprocessing.

**Tests**

- Ingest twice → no duplicates, no re-chunking of unchanged files.
- Editing one file reindexes only that file.
- A query for "speech recognition WER Swahili" returns the chunk containing `23.4% → 11.8%`.
- Context packing respects the token budget and keeps headings.
- `check_numbers` flags `35%` but accepts `11.8%`, `1,240` and `310 ms`.

**Exit criteria:** reindex on startup < 500 ms for the corpus; retrieval quality eyeballed on five real postings and recorded in `progress.md`.

**Commit:** `feat(skipper): portfolio corpus with FTS5 retrieval and grounding checks`

---

## Phase 4 — Ingestion, job extraction and the job page

**Goal:** the vertical slice: add a job, watch it being read, land on a job page with a stored brief and summary.

**Deliverables**

- `POST /api/jobs` (link or text), fingerprint dedupe, company resolution, `job_events` row.
- `app/jobs/pipeline.py` + `worker.py` — run + step rows, sequential executor, progress, cancel checks, startup sweep.
- Skills 1–2: `job_extraction`, `job_summary`.
- `app/repositories/*` for jobs, companies, runs, artifacts, events.
- Pages: `/jobs`, `/jobs/{id}`, `partials/run_progress.html`, `partials/status_pill.html`, `empty_state.html`.
- JS: `poll.js`, `jobs.js`, `job_detail.js`, add-job modal (link/paste tabs).

**Tasks**

1. Implement the run state machine exactly as design §15.4, including atomic claim and interrupted sweep.
2. Weighted progress; `current_step`; per-step duration/tokens.
3. Job page layout: header (company, title, status, salary chips), brief (responsibilities/must-haves), summary, run panel, artifact tabs placeholder.
4. Add-job modal: validate URL/text client-side and server-side; show parse errors inline; allow "attach to existing job" on duplicate.
5. Jobs table: filters (status, company, query), sort by last update, pagination, row → detail.
6. Polling with backoff, visibility pause, terminal-state reload and failure panel with Retry.

**Tests**

- URL ingestion with a fixture page creates company + job + run and reaches `reviewing`.
- Paste ingestion with 199 chars → 422 with a helpful message; 60k+ truncated with an event.
- Duplicate fingerprint → 409 with existing job id; `?attach=1` starts a run instead of a duplicate.
- Extraction schema failure → step failed, run failed, job page shows failure and Retry works with the fake provider.
- `GET /api/runs/{id}` shows monotonic progress and terminal status.
- Cancel between steps → `cancelled`, artifacts kept.
- Restart simulation: `running` run becomes `interrupted` on next startup.

**Exit criteria:** a real posting (one company site, one board, one paste) each produce a job page with a brief and summary, end to end, in under 60 s with real providers.

**Commit:** `feat(skipper): job ingestion, extraction, summary and polling job page`

---

## Phase 5 — CV pipeline (DOCX + PDF)

**Goal:** the artifact that decides whether the rest is useful.

**Deliverables**

- Skill 4 `cv_writing` with the resume content model.
- `documents/cv_docx.py` — layout mirrored from `cv/_generate_cvs.py`.
- `documents/cv_pdf.py` — LibreOffice conversion with reportlab fallback.
- `documents/storage.py` — versioned paths, hashes, current flag, download names.
- `GET /api/artifacts/{id}/download`; artifact viewer for CV in the job page.

**Tasks**

1. Write the resume JSON schema and postprocessor (dates normalised, bullets ≤ 2 lines, 3–5 bullets per role, ATS-safe section order).
2. Port the DOCX builders (header, section heading, job header, bullets) and unit-test the document text.
3. Implement PDF: `soffice` detection at startup (`SKIPPER_SOFFICE_PATH`), 60 s timeout, temp dir cleanup; fallback reportlab renderer with the same content model.
4. Filename convention `LYLE-OKOTH-<COMPANY>-<ROLE>-CV-v<n>.<ext>`; sanitise; persist bytes and sha256.
5. Render the CV in an `<iframe>`/object preview in the artifact tab, with Download PDF/DOCX and Regenerate.
6. Assert page count ≤ 2 via PDF page count (reportlab) or LibreOffice output size heuristic; log a warning when exceeded.

**Tests**

- DOCX opens with `python-docx`; contains name, headline, each employer and every bullet.
- PDF starts with `%PDF-`, > 20 KB, and page count ≤ 2 for the fixture job.
- Regenerate creates `v2`, flips `is_current`, leaves `v1` downloadable.
- No number appears in the CV that is absent from the portfolio fixture (`check_numbers`).
- Missing LibreOffice → reportlab path used and `/readyz` reports `pdf_engine=reportlab`.

**Exit criteria:** a downloadable, ATS-clean, two-page-max CV for a real ML job, visually checked against the existing `cv/LYLE-OKOTH-*.pdf` set.

**Commit:** `feat(skipper): tailored CV generation as DOCX and PDF`

---

## Phase 6 — The full pack

**Goal:** all eleven skills, one run, twelve artifacts, human-readable output.

**Deliverables**

- Skills 3, 5–11 with schemas, prompts and renderers.
- `jobs/prompts.py` — shared system preamble, untrusted-content wrapper, grounding rules.
- Company research with search + fetch + citations stored on `companies`/`sources`.
- Artifact viewer tabs: Summary, Research, CV, Cover letter, Email, Interview prep (technical/behavioural), Spoken answers (TMAB/work history/project).
- `run_steps.output_json` persisted so regeneration is possible.

**Tasks**

1. Write each prompt against its schema; keep prompts in code with an explicit `version`, snapshot their hashes in tests.
2. Company research: build ≤ 5 queries, fetch top 3 pages, summarise with citations, store `sources`, degrade gracefully when search fails.
3. Cover letter, email: enforce word limits in postprocessing; strip clichés with a lint list; email handled as artifact with Copy + `mailto:`.
4. Spoken answers: 150–220 words, first person, anchored to portfolio projects; delivery notes separate.
5. Interviews: question count ranges, topic tags from the job's must-haves, answers ≤ 250 words, STAR structure for behavioural, follow-ups for technical.
6. Markdown renderer with escaping + allowlist; artifact tabs deep-linkable (`?tab=technical`).
7. Pipeline failure policy: required (extraction, CV, cover) vs optional (research, email, spoken, interviews); progress weights from design §15.3.

**Tests**

- Fixture full run with `FakeLLM`: exactly 12 current artifacts, run `succeeded`, job `ready`.
- Every rendered artifact contains the company name and role title; none contains `[` placeholder brackets.
- Word/character limits enforced for cover letter, email, spoken answers and interview answers.
- Research output cites ≥ 3 URLs when the fake search returns results; degrades to 0 citations with a labelled warning when it returns none.
- Numeric grounding: a fake payload with `35%` is rejected/rewritten and logged.
- Optional-skill failure leaves CV + cover current and run `succeeded`; required failure → `failed`.

**Exit criteria:** one real job produces a pack Lyle would send with ≤ 1 edit, timed and recorded in `progress.md`.

**Commit:** `feat(skipper): full application pack across all eleven skills`

---

## Phase 7 — Companies and application tracking

**Goal:** the dashboard becomes the place applications are run from.

**Deliverables**

- `/companies`, `/companies/{id}`: research, jobs, notes, reuse of stored research.
- `PATCH /api/jobs/{id}` status machine with transition validation, `job_events` timeline.
- Next action + date; dashboard "needs action" list (due today/overdue, applied > 7 days, ready but not sent).
- Dashboard counters and recent activity.
- `/api/dashboard/stats`, `/api/companies*`, `/api/jobs` filters.

**Tasks**

1. Implement the transition table; reject invalid jumps (e.g. `discovered → offer`) with 422 and the allowed set.
2. Build the status control (segmented buttons/menu) with optimistic UI and rollback on error.
3. Timeline component reading `job_events`, newest first, with actor ("you" vs "run").
4. Company page: research sections with source links, job list, notes editor (debounced autosave), "Add job here" prefilled.
5. Dashboard cards: counts by status, needs-action list, recent activity, provider health banner.
6. Jobs list: keyboard-navigable rows, sticky filters, empty filter state with "clear".

**Tests**

- Every valid transition is accepted and recorded; every invalid one is rejected with the allowed set.
- Notice event on status change; timeline ordering.
- Dashboard stats match seeded rows; needs-action excludes archived and completed.
- Company notes persist and are escaped on render.
- Company research reuse: second job at same domain does not call search again.

**Exit criteria:** a week of real applications can be tracked without a spreadsheet; dashboard answers "what needs me today" in one screen.

**Commit:** `feat(skipper): company pages, status machine and dashboard tracking`

---

## Phase 8 — Regeneration, editing and recovery

**Goal:** the pack is correctable without re-paying for everything.

**Deliverables**

- `POST /api/jobs/{id}/regenerate` with dependency check and `409` explanations.
- `PATCH /api/artifacts/{id}` with markdown edit → new version.
- Resume after interrupt; retry single step; cancel; single-flight guard.
- Version switcher in the artifact viewer ("v2 current · view v1").

**Tasks**

1. Load dependency outputs from `run_steps.output_json`/`artifacts.meta_json` into `SkillContext.prior`.
2. Implement edit → re-render (markdown and documents) → new version; never mutate old files.
3. Resume: new run seeded with prior outputs, steps marked succeeded are skipped, progress starts non-zero.
4. Retry: re-run from a chosen skill through its dependants only.
5. Concurrency: guard duplicate runs; cancel checks between retries; ensure no orphan files after cancel.

**Tests**

- Regenerate cover letter bumps only that artifact; tokens spent < full run.
- Edit markdown creates a version, download reflects the edit, old version still available.
- Regenerate with missing dependency → 409 listing required skills.
- Resume skips completed skills (assert LLM call count).
- Double `POST /runs` → 409.
- Cancel leaves no partial artifact rows marked current.

**Exit criteria:** Lyle can fix any single document in under a minute without regenerating the pack.

**Commit:** `feat(skipper): artifact regeneration, editing and run recovery`

---

## Phase 9 — Hardening and hand-off

**Goal:** safe to expose on the internet and easy for the next agent.

**Deliverables**

- Security pass: CSP without inline-script needs, CSRF everywhere, SSRF tests, rate limits, headers, cookie flags in prod.
- Responsive/accessibility pass at 320/768/1024/1440 in both themes, keyboard-only run-through.
- Operations: Dockerfile with LibreOffice, render/fly notes, backup + restore commands, `/readyz` semantics.
- README complete: setup, env table, run, test, deploy, back up, troubleshoot.
- `progress.md` final state: what works, what does not, next three tasks.

**Tasks**

1. Run a security checklist (`freepi-security-audit` skill) over auth, fetch, rendering and file download.
2. Fix all high/medium findings; record accepted risks.
3. Add accessibility tests (axe via browser check or manual list) and fix contrast/focus/labels.
4. Load-test polling endpoint; confirm p95 < 15 ms with 500 runs and 20k steps seeded.
5. Verify backup/restore on a copy: restore DB + artifacts, boot, see jobs.
6. Write the hand-off section with exact commands and known limitations.

**Tests**

- Full suite green offline; e2e script from fixture posting to downloaded CV passes in CI.
- 401/403 matrix for every route (anonymous, no CSRF, expired session).
- Restore drill produces an identical dashboard count.
- No secret value appears in `var/logs` or HTML output (grep test over captured logs).

**Exit criteria:** deployed behind TLS with a real password, a successful backup/restore drill, and a fresh clone following the README reaching the dashboard in under 10 minutes.

**Commit:** `chore(skipper): hardening, ops docs and hand-off notes`

---

## Test matrix summary

| Layer | Tooling | What must be covered |
| --- | --- | --- |
| Unit | pytest | schemas, postprocessors, markdown escaping, slugs, fingerprints, status table, RAG chunking/ranking, extractors, provider parsers |
| API | pytest + `httpx.ASGITransport` | auth/CSRF/throttle, job create/dedupe, run transitions, cancel/resume, regenerate, downloads, health |
| Documents | pytest + python-docx/reportlab | DOCX content, PDF magic bytes, page count, filename sanitisation |
| E2E | pytest with fakes | paste → 12 artifacts → `ready` → download → status `applied` |
| Visual/manual | browser at 4 widths, 2 themes | landing, login, dashboard, jobs, job detail, companies, company detail |

## Definition of done (every task)

1. Code follows the layout in design §7; no dead modules.
2. A test exercises the happy path and at least one failure path.
3. Errors are typed and human-readable; no bare `except`.
4. Logs carry `request_id`/`run_id` where relevant.
5. `progress.md` updated with what changed and what is next.
