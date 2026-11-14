# SnapToSpot — Implementation Steps

**Version:** 1.0
**Date:** November 2026
**Target:** v1 (5 platforms, stills + video + copy, export)
**Companion documents:** `docs/snaptospot-prd.md`, `docs/snaptospot-design.md`

---

## How to use this document

This is the build order, not a wish list. Each phase has a **goal**, **deliverables**, **tasks**, **tests** and **exit criteria**. Do not start a phase until the previous phase's exit criteria pass. The order is chosen so that something renderable exists as early as possible — a vertical slice that produces one real LinkedIn card beats three weeks of perfect infrastructure.

Estimates assume one full-time engineer who knows Python and has used FastAPI before. Parallel tracks are marked **[parallel]**.

Check a box only when the task has: code, a test, and a line in the README or OpenAPI description. That is the definition of done for every task in this file.

---

## Ground rules

1. **The `media/` kits are the specification.** They are hand-built, correct, and must not be modified. They are the golden baseline for visual regression.
2. **Facts are pointers, never strings.** If a number appears in a payload without a `fact_id`, the payload is wrong.
3. **The renderer never decides truth.** It renders what it is given; validation happens before it runs.
4. **One vertical slice first.** Ingestion → extraction → one card → one PNG. Then widen.
5. **Every phase leaves the app runnable.** No long-lived broken `main`.
6. **Migrations are forward-only.** Never edit a shipped migration.
7. **Containers for services, not for the dev loop.** Postgres, Redis and B2 run in Docker; Python runs on the host for fast reloads.

---

## Repository layout (target)

```text
app/
  main.py                 # FastAPI app factory
  config.py               # pydantic-settings
  cli.py                  # typer/argparse commands
  db.py                   # engine, session, base
  models/                 # SQLAlchemy models
  schemas/                # pydantic: SiteProfile, ContentModel, LayoutAST, ...
  api/
    deps.py
    routes/
      auth.py  sites.py  runs.py  facts.py  gaps.py  documents.py
      kits.py  export.py  webhooks.py  health.py
  auth/
    security.py           # argon2, jwt, refresh rotation
  pipeline/
    ingest/   crawl.py  assets.py  screenshots.py  robots.py
    extract/  blocks.py  profile.py  images.py  brand.py
    resolve/  schema.py  questions.py  documents.py  search.py  tiers.py  conflicts.py
    content/  model.py  ground.py
    design/   directions.py  tokens.py
    compose/  layouts.py  fitting.py  ast.py
    render/   stills.py  frames.py  encode.py  poster.py  chrome.py
    copy/     deck.py  counts.py  alt.py
    qa/       ocr.py  overflow.py  contrast.py  safearea.py  provenance.py  report.py
    pack/     manifest.py  zip.py  contact_sheet.py  postmd.py
  workers/
    celery_app.py  tasks.py  routing.py
  templates/              # Jinja2 UI
    base.html  start.html  analysis.html  review.html  preview.html  export.html
  static/                 # vanilla JS + CSS
    app.js  styles.css
  asset_templates/        # Jinja2 for cards and video
    linkedin_square/  x_wide/  ig_portrait/  tiktok_vertical/  wa_status/
  prompts/                # versioned prompt files
migrations/               # alembic
tests/
  unit/  contract/  e2e/  golden/  fixtures/
docs/
  snaptospot-design.md  snaptospot-prd.md  steps.md
```

---

## Phase 0 — Foundations (2–3 days)

**Goal:** a repository that runs, tests and deploys a hello-world API.

### Tasks

- [ ] Create `pyproject.toml` with Python 3.12, `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `alembic`, `psycopg[binary]`, `pydantic-settings`, `celery[redis]`, `redis`, `httpx`, `jinja2`, `python-multipart`, `argon2-cffi`, `pyjwt`, `boto3`, `pillow`, `numpy`, `pgvector`, `tenacity`, `structlog`.
- [ ] Dev extras: `pytest`, `pytest-cov`, `respx`, `ruff`, `mypy`, `pre-commit`, `scikit-image` (SSIM).
- [ ] `docker-compose.yml`: Postgres 16 + pgvector image, Redis 7, MinIO as a local stand-in for B2.
- [ ] `.env.example` with every setting named in `app/config.py`.
- [ ] `app/main.py`: app factory, `/healthz`, `/readyz`, structured logging, request ID middleware.
- [ ] `ruff` + `mypy` config; pre-commit run.
- [ ] GitHub Actions: lint, type-check, unit tests, migration check.
- [ ] `Makefile` or `justfile`: `dev`, `test`, `lint`, `migrate`, `worker`, `render`.

### Tests

- [ ] `tests/unit/test_health.py` — app boots, health returns 200.
- [ ] CI fails on lint or type errors.

### Exit criteria

`docker compose up -d` + `uvicorn app.main:app` + `pytest` all succeed from a clean clone in under five minutes.

### Notes

- Local dev on Windows works; Playwright and ffmpeg run on the host. Render workers in production run in Linux containers with a pinned Chrome image.
- Pin `playwright` and install Chromium with `playwright install chromium`. Use the bundled browser, not the system Chrome, so the render is reproducible.

---

## Phase 1 — Data layer and auth (4–5 days)

**Goal:** every table in design §15 exists, and a user can sign up, sign in and be isolated by tenant.

### Tasks

- [ ] `app/db.py`: sync engine (`psycopg`), session factory, `Base`.
- [ ] Models in `app/models/`: `Tenant`, `User`, `Site`, `Run`, `RunEvent`, `Page`, `Block`, `Document`, `Chunk`, `Fact`, `GapAnswer`, `WebQuery`, `Kit`, `Asset`, `AssetAlt`, `Publication`, `AuditLog`.
- [ ] Alembic init; first migration creates the schema, the `facts_one_accepted` partial unique index, HNSW and GIN indexes, and the `claims` compatibility view.
- [ ] `app/auth/security.py`: Argon2id hashing, JWT encode/decode, refresh-token rotation, revocation table.
- [ ] `app/api/routes/auth.py`: `POST /v1/token`, `POST /v1/token/refresh`, `POST /v1/logout`, `POST /v1/password-reset`.
- [ ] `app/api/deps.py`: `get_current_user`, `get_tenant`, scope checks.
- [ ] Tenant filter enforced in a repository base class, not per query.
- [ ] Pydantic schemas mirroring design §7 (`SiteProfile`, `ContentModel`, `LayoutAST`, `Timeline`, `PlatformSpec`).

### Tests

- [ ] Auth round-trip; expired token rejected; refresh rotation invalidates the old token.
- [ ] `tests/e2e/test_isolation.py`: two tenants, every GET by id returns 404 across tenants. This suite is mandatory forever.
- [ ] Migration up/down on an empty database.

### Exit criteria

Sign-up → sign-in → create a site row → read it back, all through the API, with isolation tests green.

### Notes

- Use `tenant_id` on every table, including `assets`. A signed URL must be scoped to a kit the tenant owns.
- Store `facts.tier` as a `char(1)` with a check constraint, not an enum: tier assignment changes faster than migrations.

---

## Phase 2 — Ingestion (5–6 days)

**Goal:** given a URL, produce sanitised pages, a block tree and image assets.

### Tasks

- [ ] `robots.py`: fetch and parse `robots.txt`; per-host delay; block private IPs and non-http schemes (SSRF guard).
- [ ] `crawl.py`: Playwright Chromium, `--force-device-scale-factor=1`, `--hide-scrollbars`, viewport 1440 × 900; discover up to 12 pages by intent over anchor text and headings.
- [ ] Wait strategy: `document.readyState`, `document.fonts.ready`, settle images, 5 s network idle, 20 s hard cap.
- [ ] `blocks.py`: heading tree + paragraph list + list items + table cells, each with a stable `source_id` (`b12`), kind, and bbox.
- [ ] `assets.py`: harvest `<img>` (srcset, `og:image`, JSON-LD), fonts (computed families), palette (screenshot pixel clustering in OKLab), logo candidates.
- [ ] `screenshots.py`: full-page screenshot at 2×, plus per-section captures for project tiles.
- [ ] Store binaries in B2 under `tenant/site/run/...`; hashes in Postgres; 24 h lifecycle rule on the bucket prefix.
- [ ] `profile.py`: assemble `SiteProfile` including `observed` and an empty `gaps[]`.
- [ ] Crawl cache keyed by `(domain, page_url, html_hash)`.

### Tests

- [ ] Fixture sites served from a local static server: a JS-rendered SPA, a robots-blocked page, a site with no images, a site with a 10 MB page.
- [ ] No outbound request to `127.0.0.1`, `169.254.169.254`, `file://`.
- [ ] Block IDs stable across two runs of the same page.

### Exit criteria

`python -m app.cli ingest https://lyle-mlengineer.github.io` writes a schema-valid `SiteProfile` with 6–12 pages, a portrait with a face box, an accent colour and contact details.

### Notes

- The reference kits used `Bahnschrift` and `Segoe UI`; do not assume those exist in the container. Bundle the render fonts or fail loudly.
- Face detection can be a small ONNX model or OpenCV Haar as a fallback; it only needs a bounding box, not identity.

---

## Phase 3 — Extraction and content model (5–6 days)

**Goal:** turn blocks into offerings, projects, proof candidates and a narrative arc.

### Tasks

- [ ] Prompt files in `prompts/extract_v1.md`; JSON-schema output enforced by the provider or a validator.
- [ ] `extract/model.py`: one call per site, compressed input (heading tree, blocks with ids, meta, OG), max 4 offerings, 8 projects, 4 proof points.
- [ ] Deterministic pre-pass: regex for numbers + units, dates, emails, phone numbers, client names near "client"/"customer"/"testimonial".
- [ ] Merge pass: deterministic candidates first, LLM fills gaps; the LLM may not invent a candidate the regex pass did not see unless it supplies a verbatim quote.
- [ ] `ground.py`: quote normalisation, fuzzy containment ≥ 0.92, number-in-quote check, banned roundings.
- [ ] Reject reasons stored per fact (`no_source`, `number_mismatch`, `unsupported_rounding`).
- [ ] `SiteProfile.gaps[]` populated for every requirement slot that is still empty.

### Tests

- [ ] `tests/contract/test_content_model.py`: fixture JSON validates; a fact without `source_quote` fails; a tier-C fact referenced by `proof` fails.
- [ ] Golden text fixture: the portfolio's 7 facts, exact values and quotes.
- [ ] Adversarial fixture: a page that says "60% faster" and a model that writes "2× faster" is rejected.

### Exit criteria

The portfolio fixture produces a `ContentModel` with 0 fabricated facts, and a deliberately sparse fixture produces a `gaps[]` with the expected classes.

### Notes

- Keep the extraction prompt at temperature 0.2 and version it. Store the prompt hash in `runs.model_versions_json`.
- Do not let the copy prompt see the raw site. It sees `facts[]` only.

---

## Phase 4 — Gap questions and conflicts (3–4 days)

**Goal:** the app can ask a short, useful interview and reconcile disagreement.

### Tasks

- [ ] `resolve/schema.py`: requirement slots per campaign type (`identity`, `offer`, `proof`, `contact`, `visual`, `commerce`) with severity.
- [ ] `resolve/questions.py`: generate ≤ 5 questions with type, options, default, `unlocks`; dedupe against resolved facts; deterministic ordering by card impact.
- [ ] `resolve/conflicts.py`: group by `key`; apply precedence table (site vs user, site vs document, site vs web, two web sources); mark losers `quarantined`.
- [ ] `resolve/tiers.py`: assign tier from `source_type` and score; reject any client-supplied tier.
- [ ] API: `GET /v1/runs/:id/gaps`, `POST /v1/runs/:id/answers`, `POST /v1/runs/:id/facts/:id` (accept/override/reject).
- [ ] Audit log entries for answers, overrides and omissions.
- [ ] Blocking-gap guard: render returns 409 with the list of open gaps.

### Tests

- [ ] Question generator never asks for a fact already present (property test over fixtures).
- [ ] Exactly one accepted fact per key, enforced by the DB index.
- [ ] Override requires `attest: true`; without it, 422.

### Exit criteria

The sparse fixture produces 4–5 questions with sensible defaults; answering them updates coverage and unblocks render.

### Notes

- The default must always be safe to accept blindly. "Omit this card" is a legitimate default.
- Store the question text and the answer together: a fact that came from a question needs the question for context later.

---

## Phase 5 — Documents and retrieval (5–6 days)

**Goal:** an uploaded deck can answer a gap with a page-level citation.

### Tasks

- [ ] `POST /v1/runs/:id/documents` with MIME sniffing, 10 MB / 40 page / 5 file limits, malware hook, decompression-bomb guard.
- [ ] Parsers: `pypdf` for PDF, `python-docx` for DOCX, `python-pptx` for PPTX, plain read for MD/TXT/CSV, OCR for images.
- [ ] `documents.py`: structure-aware chunking (~700 tokens, 120 overlap), page/ordinal metadata.
- [ ] Embeddings via the provider; store in `chunks.embedding`; HNSW index.
- [ ] Retrieval: BM25 (`tsvector`) + vector, reciprocal rank fusion, cross-encoder rerank to top 8, extract from top 3 per gap.
- [ ] Tenant filter in the retrieval query (`site_id` + `tenant_id`), tested.
- [ ] 30-day expiry job; "pin to brand" flag.

### Tests

- [ ] A deck with the answer on slide 7 cites slide 7.
- [ ] Retrieval never returns another tenant's chunk (isolation fixture).
- [ ] A 41-page PDF is rejected with a clear error.
- [ ] Malformed PDF fails gracefully; the gap continues to the next rung.

### Exit criteria

Upload a 12-slide deck, ask for a metric that only appears on slide 7, and get a tier-A fact with `document`, filename, page 7 and a verbatim quote.

### Notes

- Never summarise the whole document. Extract from the top chunks, one gap at a time.
- Keep the original file until expiry so the citation can be re-checked.

---

## Phase 6 — Web search (3–4 days)

**Goal:** fill public, professional gaps with scored, dated, cited web facts.

### Tasks

- [ ] `resolve/search.py` behind a provider interface (`brave`, `tavily`, `serp`).
- [ ] Query builder: templates per gap class using extracted entities; hard cap 6 per run, 1 per class.
- [ ] Fetch top 3 results with a text extractor; strip nav/boilerplate.
- [ ] Score: `0.35 domain_quality + 0.25 first_party + 0.20 recency + 0.20 corroboration`; discard < 0.65.
- [ ] Extraction prompt returns `{value, unit, source_quote, published_at, confidence}` or null.
- [ ] Cap tier at B; downgrade to C when `published_at` is missing.
- [ ] `web_queries` log; 7-day cache keyed by `(domain, query_hash)`.
- [ ] Prompt-injection wrapper and a test fixture page containing instructions.

### Tests

- [ ] Injection fixture → null extraction, warning logged, no schema keys leaked.
- [ ] Outdated metric (no date) → tier C → not renderable.
- [ ] Search disabled → run completes with questions/documents only and is labelled.

### Exit criteria

A gap that the site cannot answer is filled from a primary source with a working URL and date, or honestly left open.

### Notes

- If the search provider is down, degrade; never block the whole run on it.
- Do not persist page bodies, only the quote and URL.

---

## Phase 7 — Design system and composition (6–7 days)

**Goal:** brand tokens in, measured `LayoutAST` out, for all five ratios.

### Tasks

- [ ] `design/directions.py`: Editorial Dark, Swiss Paper, Signal Grid as full token sets (design §6.5, §7.3).
- [ ] `tokens.py`: OKLab palette clustering, contrast check ≥ 4.5:1, accent fallback, font mapping with pinned families.
- [ ] `asset_templates/` Jinja macros per ratio; slot schema `eyebrow`, `headline[]`, `stat[]`, `media[]`, `quote`, `cta`, `qr`.
- [ ] `compose/layouts.py`: density variants (proof 4/3/2, projects 8/6/4/2), per-platform variant selection from `PlatformSpec`.
- [ ] `compose/fitting.py`: binary search on font size via Playwright measurement; min 60% of nominal; reduce density before further shrinking; no widows, no hyphenation in display type.
- [ ] `compose/ast.py`: emit `LayoutAST` with measured boxes and `fact_id` on every value.
- [ ] Portrait treatment: conic ring, face-aware `object-position`, grayscale-to-warm grade that never changes identity.

### Tests

- [ ] Snapshot tests for each template at each density.
- [ ] Fitting test: a 90-character headline at 1:1 shrinks once, then density drops, never below the floor.
- [ ] Token contrast test across all three directions.

### Exit criteria

Given the portfolio `ContentModel`, all four LinkedIn compositions produce a valid `LayoutAST` at 1200 × 1200 with zero overflow.

### Notes

- Measure in the browser, not in Python. Pillow text metrics do not match Chrome.
- Keep the QR generation deterministic and local; do not call an external QR service.

---

## Phase 8 — Still rendering (3–4 days)

**Goal:** `LayoutAST` → PNG, byte-identical on repeat.

### Tasks

- [ ] `render/chrome.py`: persistent Chromium per worker, one page per asset, CDP via Playwright.
- [ ] Device metrics override, `deviceScaleFactor=2`, `--force-color-profile=srgb`, `--disable-gpu`, deterministic flags.
- [ ] Local file URL or `page.set_content` with a strict CSP; no network fonts.
- [ ] `screenshots` at 2×, downsample to 1× with Lanczos; strip metadata.
- [ ] Output naming per design §11.
- [ ] Content-hash cache keyed by `(content_model_hash, design_system_hash, platform, template_version)`.

### Tests

- [ ] Render the same AST twice → identical SHA-256.
- [ ] Golden SSIM ≥ 0.98 vs `media/linkedin/0*.png` using the fixture `ContentModel`.
- [ ] 320 px downsample is legible (manual check + OCR gate in Phase 12).

### Exit criteria

Four LinkedIn PNGs from the app match the hand-built kit closely enough that a reviewer cannot tell which is which in a blind A/B.

### Notes

- The reference `media/*/assets/*.html` files are the visual source of truth; port their CSS, do not redesign.
- Keep the screenshot of the browser page identical in size to the target; do not scale after capture.

---

## Phase 9 — Video (5–6 days)

**Goal:** a deterministic 15–21 s MP4 per platform with a poster frame.

### Tasks

- [ ] `render/frames.py`: `renderAt(t)` pure function, scene in/out, element enter offsets, easing library (`cubic_out`, `out_back`).
- [ ] Template per ratio with a progress bar and burned-in captions.
- [ ] Frame loop: `Runtime.evaluate(renderAt(t))` → `Page.captureScreenshot({format:"jpeg", quality:95})`.
- [ ] `encode.py`: ffmpeg with BT.709 conversion, `-crf 19`, `-preset slow`, `yuv420p`, `+faststart`, 30 fps.
- [ ] `poster.py`: capture at `duration − 0.8 s`.
- [ ] Parallel frame capture across workers by time range; deterministic reassembly by index.
- [ ] Platform-specific last line (IG bio, WhatsApp reply, LinkedIn/X URL).
- [ ] File-size ceiling check per platform (design Appendix B).

### Tests

- [ ] Same timeline → same frame hashes and same MP4 hash.
- [ ] Duration, resolution, pixel format and colour range asserted with `ffprobe`.
- [ ] Poster is not a blank first frame.

### Exit criteria

15 s LinkedIn (1080 × 1080) and 18 s WhatsApp (1080 × 1920) videos render in under 60 s each, play muted with readable captions, and pass the spec gate.

### Notes

- The colour-range filter is not optional: without it, ink backgrounds wash out on some Android players.
- Do not use CSS transitions or `requestAnimationFrame`; they break determinism.

---

## Phase 10 — Copy and alt text (3–4 days)

**Goal:** five platform-native copy decks that respect hard limits and cite facts.

### Tasks

- [ ] `copy/counts.py`: LinkedIn, X (URL = 23), Instagram, TikTok, WhatsApp counters; grapheme-aware.
- [ ] `copy/deck.py`: one call per platform with `PostSpec`, voice card, facts (tier A/B), banned phrases; returns primary, alternatives[3], thread, short variant, hashtags.
- [ ] Validation loop: reject → one regeneration → fail with reason.
- [ ] `copy/alt.py`: build alt text from `LayoutAST`; spatial hints checked against the AST.
- [ ] `pack/postmd.py`: the 9-section deck from design §11, including sources and omissions.
- [ ] WhatsApp message shapes: status, individual, group, broadcast; no hashtags; no link in status.

### Tests

- [ ] Character counts match the platforms' own behaviour on fixtures (23-char URL, emoji, combining marks).
- [ ] A caption containing a digit not in `facts[]` is rejected.
- [ ] Alt text mentions every visible string.

### Exit criteria

The portfolio produces the same shape of copy as `media/*/post.md`: a LinkedIn post under 3,000, an X hook under 280, an IG caption under 2,200 with 3–10 hashtags, and four WhatsApp messages.

### Notes

- Voice card: person (first/third), tense, formality, sentence length, three sample phrases from the site. Do not imitate another brand.
- Banned phrases are a list in config, not in the prompt, so they can be updated without a prompt change.

---

## Phase 11 — QA gates (5–6 days)

**Goal:** nothing ships that fails a gate, and the report proves it.

### Tasks

- [ ] `qa/ocr.py`: PaddleOCR (extra) with Tesseract fallback; token match ≥ 98%, numbers 100%.
- [ ] `qa/overflow.py`: DOM `scrollHeight`/`clientHeight` per slot at 1× and 2×.
- [ ] `qa/contrast.py`: WCAG on every text/background pair from the AST, not from pixels.
- [ ] `qa/safearea.py`: bounding boxes vs platform masks.
- [ ] `qa/provenance.py`: join every rendered number to a `fact_id` with tier A/B; fail on C/D.
- [ ] `qa/report.py`: `qa.json`, per-asset status, retry policy (variant → density → platform skip).
- [ ] Duplicate detection: perceptual hash across the kit.
- [ ] Brand drift: ΔE < 2 between tokens and rendered swatches.

### Tests

- [ ] Inject a fake number into an AST → provenance gate fails.
- [ ] Inject overflow → gate fails, retry picks a denser variant.
- [ ] Safe-area fixture for Reel and TikTok passes/fails as expected.

### Exit criteria

Every asset in the golden kit passes; a deliberately corrupted kit fails with a precise reason.

### Notes

- OCR is a cross-check, not the source of truth. The AST knows the strings; OCR catches rendering bugs.
- Run QA on the 1× asset, not the 2× capture.

---

## Phase 12 — Pack, export, share (3 days)

**Goal:** a downloadable kit that a stranger can use without reading docs.

### Tasks

- [ ] `pack/manifest.py`: sources, omissions, generated, renderer/template versions.
- [ ] `pack/zip.py`: stream to B2, signed URL, 24 h expiry; include `assets/` source.
- [ ] `pack/contact_sheet.py`: one PNG with every asset and its dimensions.
- [ ] `post.md` included per platform; `README.txt` at the root with the posting order.
- [ ] `POST /v1/kits/:id/export`, `GET /v1/kits/:id`, `GET /v1/kits/:id/assets/:id`.
- [ ] Share links: signed, read-only, 30-day expiry, no auth.

### Tests

- [ ] ZIP structure asserted against design §11.
- [ ] Manifest lists every omission and every tier-B source.
- [ ] Downloaded `cards.html` opens and renders offline.

### Exit criteria

Download the ZIP on a clean machine, open `post.md`, and publish without touching another file.

---

## Phase 13 — Web UI (8–10 days, start in parallel at Phase 7) **[parallel]**

**Goal:** the five screens from design §13, server-rendered with vanilla JS.

### Tasks

- [ ] `templates/base.html`, `static/styles.css`: design tokens, focus states, reduced motion.
- [ ] Start screen: URL, promo type, document upload, plan limits.
- [ ] Analysis screen: SSE or polling over `/v1/runs/:id`; progressive panels.
- [ ] Fact review: two panes, tier chips, source links, conflict grouping, gap cards (answer/upload/search/skip), coverage meter.
- [ ] Design pick: three previews rendered from card 1 at low resolution.
- [ ] Kit preview: platform rows, true aspect ratio, video scrubber, copy editor with live count, provenance tab.
- [ ] Export: contact sheet, file sizes, copy blocks, download, share link.
- [ ] Vanilla JS modules: `api.js`, `sse.js`, `review.js`, `preview.js`, `counts.js`; no framework, no build step.
- [ ] Progressive enhancement: core review works without JS; no dead-end spinners.

### Tests

- [ ] Playwright e2e: sign up → run → answer gap → review → export (fixture site).
- [ ] Keyboard-only pass through fact review.
- [ ] 390 px review layout does not horizontally scroll.

### Exit criteria

A non-technical reviewer completes the five-screen flow without help in under ten minutes.

### Notes

- Server-render the first paint; hydrate only the panels that need it.
- The caption counter must share the Python counting logic via a JSON endpoint, not a reimplementation in JS.

---

## Phase 14 — Orchestration and reliability (4–5 days)

**Goal:** a run is a resumable DAG, not a long function.

### Tasks

- [ ] Celery app with queues: `ingest`, `content`, `resolve`, `render`, `qa`, `pack`; priority for interactive runs.
- [ ] Canvas: chain per stage; `group` + `chord` for per-platform render fan-out.
- [ ] `run_events` per stage; `GET /v1/runs/:id` returns stage, progress, artefacts.
- [ ] Idempotency keys on every POST; render cache keyed by content hash.
- [ ] Retry policy with jitter; dead-letter queue; admin requeue.
- [ ] Webhooks: `run.completed`, `run.failed`, `run.gaps_open`, `search.completed`, `kit.ready`.
- [ ] Graceful shutdown: finish the current asset, release Chrome, ack the task.
- [ ] Run budget guard: token/search/CPU ceilings; fail closed at 2×.

### Tests

- [ ] Kill a worker mid-render; resume completes without duplicate assets.
- [ ] Re-POST the same render request returns the same kit id.
- [ ] A stage failure surfaces as `run.failed` with the stage name.

### Exit criteria

A 30-file, 5-platform run survives a worker restart and completes with every asset accounted for.

### Notes

- One Chrome per worker, reused. Launch cost dominates short renders.
- Do not put model calls inside DB transactions.

---

## Phase 15 — Security, privacy, performance (4–5 days)

**Goal:** safe to expose to strangers.

### Tasks

- [ ] SSRF suite: private ranges, link-local, metadata, redirects, DNS rebinding.
- [ ] Upload suite: MIME mismatch, zip bomb, oversized, macro-enabled Office files.
- [ ] Rate limits per tenant and per IP; login lockout.
- [ ] PII handling: encryption at rest for email/phone; redaction in logs.
- [ ] Retention jobs: 24 h HTML, 30-day documents, 90-day assets, audit log 24 months.
- [ ] Data export and account deletion endpoints.
- [ ] CSP, HSTS, secure cookies, CSRF token on form posts.
- [ ] Load test: 10 concurrent runs on 4 workers; measure p50/p95 and cost.
- [ ] Cost dashboard: per-run tokens, searches, CPU-minutes.

### Tests

- [ ] `tests/e2e/test_security.py` covering every item above.
- [ ] Load test report checked into `docs/perf/`.

### Exit criteria

Security checklist signed off; p95 under 12 minutes at 10 concurrent runs; cost per kit under $0.70.

---

## Phase 16 — Beta and GA (6–8 days)

**Goal:** real users, real sites, no surprises.

### Tasks

- [ ] Golden regression in CI: 6 fixture sites (portfolio, sparse, e-commerce, SaaS, agency, non-English).
- [ ] Blind A/B: 20 reviewers pick the app kit vs the hand-built kit; target ≥ 50% "can't tell".
- [ ] Onboarding email + 3-minute video.
- [ ] Support runbook: common failures (no portrait, blocked crawl, no facts, stalled render).
- [ ] Error budget and alerting: run failure rate, render p95, cost per kit.
- [ ] Public beta launch kit — produced by SnapToSpot, from the product's own site.
- [ ] GA gate: all release criteria from the PRD §16.

### Exit criteria

25 beta users, 70% complete review, 50% export, NPS ≥ 30, no P0 security findings.

---

## Cross-cutting: testing strategy

| Layer | Tool | What it proves |
| --- | --- | --- |
| Unit | pytest | parsers, counters, tier rules, conflict resolution |
| Contract | pytest + JSON Schema | every payload shape; `fact_id` integrity |
| Golden image | Playwright + scikit-image | output matches the hand-built kits (SSIM ≥ 0.98) |
| Golden video | ffprobe + frame hashes | determinism and spec compliance |
| E2E | Playwright | the five screens work |
| Isolation | pytest | no cross-tenant reads |
| Adversarial | pytest fixtures | injection, fake numbers, SSRF, upload abuse |
| Load | locust/k6 | p95 and cost at 10 concurrent runs |

**Fixtures to build early:**
`portfolio` (this repo), `sparse` (no pricing, one quote, no logo), `ecommerce` (price, shipping, product shots), `saas` (pricing tiers, changelog), `blocked` (robots), `spa` (client-rendered).

---

## Cross-cutting: golden regression

The `media/` kits are the baseline. Keep a `tests/golden/` fixture that:

1. loads the portfolio `ContentModel` (checked in as JSON),
2. composes and renders the four LinkedIn cards,
3. compares against `media/linkedin/0*.png` with SSIM,
4. renders 15 s at 1080 × 1080 and asserts duration, size, codec, colour range,
5. diffs `post.md` structure and character counts (not exact wording).

When a template changes intentionally, update the baseline in the same commit and record why in the commit message.

---

## Sequencing summary

| Week | Phases | Milestone |
| --- | --- | --- |
| 1 | 0, 1 | App boots, auth works, schema migrated |
| 2–3 | 2, 3 | First real `SiteProfile` and `ContentModel` |
| 4 | 4 | The app can ask a useful question |
| 5 | 5, 6 | Gaps resolved by documents and search |
| 6–7 | 7, 8 | **First LinkedIn card matches the hand-built kit** |
| 8 | 9 | Video renders deterministically |
| 9 | 10, 11 | Copy decks and QA gates |
| 10 | 12, 13 | Export and the five screens |
| 11 | 14, 15 | Orchestration, security, load |
| 12 | 16 | Beta, GA |

Critical path: **Phase 7 → 8** (composition and stills). Everything else can slip a few days; that cannot.

---

## Definition of done (global)

A feature is done when:

- [ ] It has a test that fails without the change.
- [ ] It is exercised by the fixture site, not only by unit mocks.
- [ ] Its failure mode is defined (what the user sees, what is logged, whether the run continues).
- [ ] Its cost is measured or bounded.
- [ ] It appears in the OpenAPI schema or the README.
- [ ] It respects tiers: no new path can render a tier-C or tier-D fact.
- [ ] It does not touch the `media/` baseline.

---

## First ten commands

```bash
git switch -c feat/snaptospot
mkdir -p app/{api/routes,auth,models,schemas,pipeline,workers,templates,static,asset_templates,prompts}
python -m venv .venv && . .venv/Scripts/activate
pip install -e ".[dev]"
docker compose up -d postgres redis minio
cp .env.example .env
alembic init migrations
uvicorn app.main:app --reload
pytest -q
ruff check . && mypy app
```
