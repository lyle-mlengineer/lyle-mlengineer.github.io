# SnapToSpot — Progress

The build follows `../docs/steps.md`. Each step ends with a working app, a test run,
and a commit.

**Current step:** 10 complete — copy decks and alt text
**Next step:** 11 — QA gates
**Last updated:** 2026-11-19

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
  the end-to-end analyze endpoint. The Playwright test uses bundled Chromium when
  present, otherwise an installed Chrome or Edge.
- **Live smoke test.** Started the API and a local fixture server, signed up,
  created a site, analysed it, then read the run and profile back:
  `status=succeeded pages=4 assets=4 ai=False`, name `Lyle Okoth`, role
  `Machine Learning Engineer`, accent `#f04080`, value proposition from the home
  page.

**Commit:** `feat(snaptospot): ingest sites and build the first SiteProfile`

### Step 3 — Extraction and content model

- **Contract.** `schemas/content.py` defines `Fact`, `Offering`, `Project`,
  `Proof`, `QuoteRef`, `CTA`, `ContentModel` and `RejectedFact`. Metrics, badges
  and quotes are `*_fact_id` pointers; free text may not introduce a digit that no
  fact supports. `proof[]` only accepts tier A/B facts, and a quote fact must be
  `published_on_site` or `attested`.
- **Deterministic pre-pass.** `pipeline/extract/deterministic.py` finds
  percentages, latency, durations, counts and spelled counts, with as-of dates
  from month + year. It records the exact sentence as `source_quote` and derives
  stable keys (`asr.wer`, `work.projects`, `product.creators`, …). It also reads
  blockquotes plus a following caption into a quote fact, builds projects from
  work-page headings, and collects emails, phones, dates and client names as
  resolver signals.
- **Grounding.** `pipeline/extract/ground.py` normalises Unicode quotes and
  dashes, matches token windows fuzzily at ≥ 0.92, checks every number in the
  value against the quote, and flags `number_mismatch` or
  `unsupported_rounding`. Spelled numbers (`seven` → `7`) count as grounded.
- **LLM pass.** `prompts/extract_v1.md` is the versioned prompt; its SHA-256 is
  stored in `runs.model_versions_json`. `pipeline/extract/llm.py` accepts a draft
  only when every metric/quote cites a crawled `source_id` and the quote exists
  verbatim in that block. The merge pass keeps deterministic candidates first,
  lets the LLM fill empty slots, and quarantines a second value for an occupied
  key with reason `conflict`.
- **Content model.** `pipeline/extract/model.py` assembles the thesis, audience,
  arc, ≤ 4 offerings, ≤ 8 projects, ≤ 4 proof points, one quote and the CTA.
  Anything containing an unsupported number is dropped or neutralised before the
  schema validates.
- **Gaps.** `pipeline/extract/requirements.py` fills `SiteProfile.gaps[]` for
  identity, offer, proof, attribution, recency, visual, commerce and consistency
  slots, with `blocking`/`soft` severity and the rungs already tried.
- **API and storage.** `Run` gains `content_model_json` and
  `model_versions_json` (migration `7b9d2f14c8aa`). `POST .../analyze` stores the
  model, reject reasons, coverage and gap summary; `GET
  /v1/sites/{id}/content-model` returns the latest model.
- **CLI.** `python -m app.cli extract URL --out content.json` writes the model,
  rejected facts, gaps and model versions.
- **Fixtures and tests.** The portfolio fixture now carries seven grounded metrics
  and a named testimonial. Contract tests cover the schema, missing quotes and
  tier-C proof references. Extraction tests cover the seven golden values,
  deterministic stability, prompt hashing, an adversarial “60% faster” → “2×
  faster” rejection, a fabricated quote, contact/date/client signals, and
  sparse-site gap classes. 48 tests pass; ruff is clean.
- **Live smoke test.** The same pipeline through uvicorn returned
  `facts=8, coverage=1.0, llm=False`, all seven metric values and the Daniel Reyes
  quote; the only portfolio gap was `visual.project_shot`.

**Commit:** `feat(snaptospot): extract grounded content models and gaps`

### Step 4 — Gap questions, facts and conflicts

- **Requirement schema.** `pipeline/resolve/schema.py` declares slots for
  `identity`, `offer`, `proof`, `contact`, `visual`, `commerce`, `attribution`
  and `recency`, each with a severity, card impact, question type, safe default
  and the card consequence it unlocks. `requirements.py` now also reports
  missing contact email and contact URL gaps.
- **Questions.** `pipeline/resolve/questions.py` generates at most five
  questions, never asks for an accepted fact, orders deterministically by card
  impact and supports the fixed types `choice`, `number_unit`, `short_text`,
  `url`, `file` and `skip`. Every question defaults to skipping/omitting the
  card, and consistency conflicts can become a choice question.
- **Trust tiers.** `pipeline/resolve/tiers.py` assigns A to site, user answers
  and documents; B or C to web sources from their score and corroboration; and D
  to inference. Request schemas use `extra="forbid"`, so a client-supplied
  `tier` is a 422.
- **Conflicts.** `pipeline/resolve/conflicts.py` implements the design precedence
  table: attested user beats site, site beats document/web, document beats web,
  and two web sources have no winner. Losers are marked `quarantined`, never
  deleted.
- **Storage.** `facts` stores fact candidates with `(run_id, id)` as the primary
  key and a partial unique index `facts_one_accepted` on
  `(run_id, key) WHERE status = 'accepted'`. `gap_answers` stores the canonical
  question JSON next to the answer JSON, so a fact that came from a question
  keeps its context. Migration `c3a8e1f4d920` adds both tables; facts are
  backfilled from existing content models on analyze or lazily on the resolve
  endpoints.
- **API.**
  - `GET /v1/runs/{id}/gaps` — gaps, coverage, blocking keys and ≤ 5 questions;
  - `GET /v1/runs/{id}/facts?status=...` — accepted, quarantined and rejected
    facts;
  - `POST /v1/runs/{id}/answers` — answer or skip questions, create tier-A user
    facts, quarantine a losing fact, rebuild the model and gaps;
  - `POST /v1/runs/{id}/facts/{fact_id}` — accept, override or reject a fact.
    Override requires `attest: true` and records both the old and new value;
  - `POST /v1/runs/{id}/render` — returns 409 with the open blocking gaps, or 202
    `ready` once they are answered or explicitly skipped.
- **Audit.** `gap.answered`, `gap.skipped`, `fact.accepted`, `fact.overridden`,
  `fact.quarantined` and `fact.rejected` are written to `audit_log`.
- **Coverage.** A run with zero candidates starts at `coverage = 0.0`; answers
  add accepted facts and raise coverage. The sparse fixture produces five
  questions and goes from blocked to ready after answering `offer.core` or
  skipping the blocking slot.
- **Tests.** 64 tests pass and ruff is clean. New coverage includes the sparse
  question set, the generator property over four fixtures, the DB partial unique
  index, override attestation and client-tier rejection, conflict precedence,
  skip-unblocks-render, answer validation, audit rows and tenant scoping for all
  new endpoints.
- **Smoke test.** The sparse fixture returned exactly five questions
  (`offer.core`, `proof.metrics`, `proof.quote`, `identity.role`,
  `visual.project_shot`) at coverage `0.0`. Render returned `409 blocked`;
  answering `offer.core` and skipping the rest returned `202 ready` with
  coverage `1.0` and a new capability offering in the content model.

**Commit:** `feat(snaptospot): resolve gaps with questions, facts and conflicts`

### Step 5 — Documents and retrieval

- **Upload safety.** `POST /v1/runs/{id}/documents` accepts multipart files with
  MIME classification from bytes, not the browser header. PDF, DOCX, PPTX,
  Markdown, TXT, CSV and images are supported. The route enforces 10 MB per file,
  40 pages/slides per document and five documents per run, and reports every
  rejection per file. `pipeline/documents/security.py` also rejects executables,
  legacy OLE files, macro-enabled Office packages, embedded active content,
  EICAR payloads, PDF JavaScript and archives with unsafe paths, excessive
  entries or a decompression-bomb ratio. `scan_bytes` is the ClamAV hook: swap
  the function, keep the contract.
- **Parsers.** `pypdf` extracts PDF pages and reports the failing page on a
  malformed or encrypted file; `python-docx` walks headings, paragraphs and
  tables into sections; `python-pptx` turns each slide (and its notes) into a
  page; Markdown splits on headings, CSV on header/row blocks, TXT on form feeds.
  Images go through optional OCR (`SNAP_OCR_ENABLED=true` plus pytesseract) and
  fail with a clear message when OCR is off rather than pretending to read them.
- **Chunking.** `pipeline/documents/chunking.py` packs paragraphs into ~700-token
  chunks with 120-token overlap and never crosses a page or slide boundary, so a
  chunk always maps to one citation. Every chunk stores `document_id`, `page`,
  `ordinal`, `kind`, text and a token estimate.
- **Embeddings.** `pipeline/documents/embeddings.py` calls any OpenAI-compatible
  `/embeddings` endpoint when `SNAP_LLM_API_KEY` is set; without a key, or when the
  provider fails, it uses deterministic local hashing over words, trigrams and
  bigrams. Chunks store the vector in `chunks.embedding`; Postgres uses pgvector
  `vector(1536)` while SQLite stores JSON for local development.
- **Retrieval.** `pipeline/documents/retrieval.py` runs BM25 and vector search in
  parallel, fuses with reciprocal rank fusion, then reranks to the top eight.
  Postgres uses `tsvector`/`ts_rank_cd` and pgvector cosine ordering behind the
  `chunks_fts` GIN and `chunks_embedding` HNSW indexes; SQLite uses Python BM25
  and cosine over the same tenant-filtered candidate set. Numeric gaps get a
  number-density boost so a metric slide can win even when it shares no keywords
  with the question. Every query filters on `tenant_id`, `run_id` and `site_id`
  and excludes expired, unpinned documents.
- **Extraction.** `pipeline/documents/extractor.py` reads only the top three
  chunks per gap. Deterministic matchers reuse the site pass for percentages,
  durations, counts, prices, quotes, roles, locations, contact links and image
  URLs; a configured LLM is the fallback with
  `prompts/document_extract_v1.md` (temperature 0). Every answer must quote the
  chunk verbatim and is grounded again before storage. A null or ungrounded
  answer leaves the gap open for the next rung.
- **Citations and trust.** A document fact stores `source_type="document"`,
  `source` = the filename, `source_page` = the page/slide, `source_id` = the chunk
  id, a verbatim `source_quote`, and tier A from the mechanical tier table.
  Conflicts reuse the fixed precedence table: the site beats a document unless
  the document wins on the recorded rules; losers stay `quarantined`. Document
  quotes carry `permission="brand_document"` and can render the testimonial card.
- **Storage and expiry.** `Document` and `Chunk` models plus migration
  `d5e2b7a9c1f3`; `facts.source_page` added. Files live under
  `SNAP_MEDIA_ROOT/documents/{tenant}/{run}`. `expire_documents` deletes chunks
  and files after 30 days and skips `pinned_to_brand` rows. The CLI command is
  `python -m app.cli expire-documents [--days N] [--tenant ID]`.
- **API.** Upload (with optional `gap_key` and `pin_to_brand`), list, detail with
  chunks, and `POST .../{document_id}/pin`. Upload returns a parse report per file
  (`pages`, `chunks`, `extracted_facts`, `failures[]`) and the refreshed gap
  report. A file that fails every check returns 422 (413 for size) with the reason.
- **Tests.** 72 tests pass and ruff is clean. New coverage: the 12-slide deck
  whose metric only appears on slide 7 returns a tier-A document fact with
  filename, `source_page=7` and the verbatim quote; cross-tenant retrieval returns
  nothing and cross-tenant document reads are 404; a 41-page PDF is rejected with
  both limits named; a malformed PDF fails and leaves the gap open; MIME mismatch,
  size, file-count, pin and expiry are covered; chunking keeps pages and overlap.
- **Smoke test.** Through the HTTP API, a sparse run was analysed, a 12-slide
  PPTX was uploaded for `proof.metrics`, and the resulting fact read back as
  `source_type=document`, `source=growth-deck.pptx`, `source_page=7`,
  `tier=A`, quote `2,100 monthly active creators as of October 2026.`; the gap
  moved from open to resolved.

**Commit:** `feat(snaptospot): ingest documents and cite retrieved facts`

### Step 6 — Web search

- **Provider interface.** `pipeline/resolve/search.py` defines a small
  `SearchProvider` protocol and three adapters: `brave`, `tavily` and `serp`.
  `build_provider` returns `None` unless `SNAP_SEARCH_PROVIDER` is one of those
  names and `SNAP_SEARCH_API_KEY` is set, so a missing key is a normal,
  labelled state rather than an error. Requests time out after 20 s.
- **Query builder.** One query per gap class, drawn from the crawled entities
  (person/org name, role, location, domain, current year). Only public,
  professional classes are searched: identity, offer, proof, commerce and
  recency. Contact, visual, attribution and consistency gaps are deliberately
  excluded. Hard cap of six queries per run; cached hits do not consume it.
- **Fetch and score.** The top three results are fetched through the same SSRF
  guard as the crawler, stripped of nav/header/footer/forms/scripts, and capped
  at 20k characters. Score is exactly
  `0.35 domain_quality + 0.25 first_party + 0.20 recency + 0.20 corroboration`;
  results below `0.65` are discarded before extraction. Recency decays over 24
  months and a metric older than five years scores zero.
- **Extraction.** A deterministic pass handles identity, offer, metrics, price
  and recency; a configured LLM is the fallback with
  `prompts/web_extract_v1.md`, which demands a verbatim quote and forbids
  invented dates. Grounding runs again before storage.
- **Tier rules.** Web facts can never exceed tier B. A tier-B fact requires a
  publication date and either a first-party source or corroboration; anything
  without `published_at` is downgraded to tier C automatically. Tier C facts
  resolve gaps but do not enter `content_model.proof`, so an undated metric is
  never rendered as a card number.
- **Injection defence.** `detect_injection` flags instruction overrides,
  system-prompt requests, role resets, chat markup and schema hijacks. A
  flagged page is skipped, a warning is logged and returned, and the extraction
  prompt receives page text only inside `wrap_untrusted`, which labels it as
  data. The adversarial fixture yields no fact and leaks no schema keys.
- **Log and cache.** Every query is written to `web_queries` (migration
  `e6f3c2a1b8d4`) with the gap, query hash, domain, engine, result metadata and
  scores, but never page bodies. A repeat query on the same
  `(domain, query_hash)` inside seven days reuses the stored result list and is
  marked `cache_hit`; pages themselves live in a process-memory cache.
- **API and degradation.** `POST /v1/runs/{id}/search` returns the refreshed
  facts, query log and gap report. When search is disabled it returns
  `status="disabled"` and the run keeps its questions and documents; a provider
  failure returns `status="degraded"`; a used-up budget returns `"exhausted"`.
  In every case `stats.web_search` and `GapReport.web_search` carry the label.
- **Tests.** 78 tests pass and ruff is clean. New coverage: the injection
  fixture produces a null extraction, a warning and no leaked keys; an undated
  metric is tier C and absent from the proof card; a dated primary page becomes
  tier B with a working URL and `as_of`; search disabled leaves questions and
  documents and is labelled; the query builder caps at six with one per class;
  the score formula and seven-day cache expiry are asserted directly.

**Commit:** `feat(snaptospot): search the web and cite scored sources`

### Step 7 — Design system and composition

- **Directions.** `design/directions.py` ships Editorial Dark, Swiss Paper and
  Signal Grid as complete token sets: background, surface, muted inks, accent,
  text-on-accent, hairlines, display/body/mono families, tracking, transform and
  radius. `direction_for` reads the profile and defaults to Editorial Dark;
  strong data-product or writing signals can choose Signal Grid or Swiss Paper.
- **Brand tokens.** `design/tokens.py` parses the site palette, converts to
  OKLab, drops near-black, near-white and grey clusters, then picks the highest
  `area × chroma` accent that reaches 4.5:1 against the direction background.
  A failing sample falls back to the direction's stock accent instead of shipping
  an unreadable brand colour. Display and body families are only used when they
  are on the pinned list; otherwise the direction family wins. The resulting
  `DesignSystem` is hashed and pinned on `sites.design_system_json` /
  `sites.design_system_hash`, so a later run looks like the same brand. An
  explicit different direction rebuilds it.
- **Platform specs.** `design/platforms.py` holds LinkedIn 1200×1200, X
  1600×900, Instagram 1080×1350, TikTok 1080×1920 and two WhatsApp stills,
  including safe areas, caption limits, link rules and hashtag ranges. Selection
  is data (`spec_for`, `specs_for`), not branching.
- **Templates.** `asset_templates/cards.html` emits HTML + CSS from Jinja
  macros. Every ratio has its own composition classes, and slots are stable:
  `eyebrow`, `headline[]`, `subhead`, `stat[]`, `tile[]`, `media[]`, `quote`,
  `cta` and `qr`. Each number, badge and quote carries `data-fact-id`; the QR is
  a local, deterministic `segno` SVG. Hero portraits get a conic ring,
  face-aware `object-position` and a grayscale-to-warm grade that keeps identity.
- **Density variants.** `compose/layouts.py` selects a template per platform and
  ratio, then an ordered density list: proof 4 → 3 → 2, projects 8 → 6 → 4 → 2
  on 16:9 and 4 → 2 elsewhere, capabilities 4 → 2.
- **Measured fitting.** `compose/fitting.py` renders in Chromium, measures every
  `[data-slot]` box, line count and widow, and binary-searches display type
  between the nominal size and a 60% floor. If the floor still fails, it drops to
  the next density before shrinking further. If even the last density fails, the
  AST is labelled `overflow` with a warning. Without Chromium an estimator
  degrades the run and the response says it was not measured in a browser.
- **AST and provenance.** `compose/ast.py` builds slots only from tier A/B facts;
  a metric older than 90 days without `as_of` is dropped, and tier C/D can never
  render a number, badge or quote. `compose/service.py` composes all requested
  cards, records the design hash, assets and browser flag in
  `runs.stats_json` and `audit_log`.
- **API and storage.** `POST /v1/runs/{id}/compose` accepts
  `{direction, platforms, cards}` and returns the design system, hash,
  `LayoutAST[]`, warnings and `measured_in_browser`. Unknown platforms are 422,
  a missing profile or content model is 409, and another tenant's run is 404.
  Migration `f7a4d9c2e6b1` adds the pinned design columns.
- **Tests.** 135 tests pass and ruff is clean. New coverage: contrast ≥ 4.5:1 in
  all three directions, accent fallback, pinned font mapping, face-aware
  portrait position, hash pinning, 34 template/density snapshots, a 90-character
  headline that shrinks without crossing the floor, density fallback before
  further shrinking, widow rejection, deterministic QR, tier-C/stale-fact
  exclusion, fact ids on every stat and quote, endpoint auth/error cases, and the
  portfolio exit criterion.
- **Exit criterion and smoke test.** The real portfolio model composed four
  LinkedIn cards at 1200×1200 with `direction=editorial_dark`,
  `measured_in_browser=true` and zero overflow. Hero type reduced from 78 px to
  55 px (above the 47 px floor); the other three cards held their nominal sizes.
  The design hash was pinned on the site.

**Commit:** `feat(snaptospot): compose measured cards from brand tokens`

---

### Step 8 — Still rendering

- **Persistent Chromium worker.** `render/chrome.py` keeps one browser and one
  context per worker thread, opens a fresh tab per asset and closes it in a
  `finally`. Launch flags remove GPU rasterisation, LCD subpixel text, scrollbars,
  background networking and colour-profile drift
  (`--disable-gpu`, `--hide-scrollbars`, `--force-color-profile=srgb`,
  `--force-device-scale-factor=1`, `--disable-lcd-text`).
- **Capture contract.** Each card gets `Emulation.setDeviceMetricsOverride`
  at its exact target size with `deviceScaleFactor=2`, then
  `Page.captureScreenshot`. The 2× PNG is reduced once with Lanczos to the
  platform size and re-encoded by Pillow without a timestamp, EXIF or software
  chunk. The screenshot surface is the target size; nothing is scaled after
  capture beyond the specified downsample.
- **Self-contained pages.** `render/assets.py` injects a strict CSP
  (`default-src 'none'`, `img-src data:`, inline styles only), inlines local
  images and fetches remote layout images once into a content-addressed asset
  cache. The page's own context aborts every `http(s)` request, so no font or
  image can come from the network during capture. An unloadable portrait is
  omitted rather than drawn as a grey square.
- **Output contract.** Files use the §11 names
  (`01-announcement.png`, `02-what-i-build.png`, `03-selected-work.png`,
  `04-proof.png`) under
  `var/media/<tenant>/<site>/<run>/stills/<platform>/`. Rendering reads the
  measured `LayoutAST`s persisted by composition; nothing is re-fitted.
- **Content-hash cache.** The key is
  `sha256(content_model_hash, design_system_hash, platform, template_version)`.
  The key names a cache directory and each card is stored under its output name,
  so a repeat request is a disk read and reports `cached=true`.
  `reuse_cache=false` / `--force` recaptures without changing the key.
- **API and CLI.** `POST /v1/runs/{id}/stills` accepts
  `{platforms, cards, reuse_cache}` and returns per-file width, height, SHA-256,
  byte size, cache key and cache flag. A run that has not been composed is 409;
  another tenant's run is 404. `python -m app.cli render --run <id>` does the
  same from the command line.
- **Tests.** 153 tests pass and ruff is clean. New coverage: §11 names and card
  lookup, cache-key sensitivity to all four inputs, canonical content hash,
  strict CSP and no network references in the document, no `@font-face`, the
  same AST rendered twice producing identical SHA-256 and bytes, four 1200×1200
  RGB PNGs with empty metadata, cache hits that never touch Chromium, forced
  recapture, tenant scoping and the render-before-compose 409. The golden gate
  renders `media/linkedin/assets/cards.html` through the same 2×→Lanczos
  pipeline and scores SSIM 0.986–0.988 against all four hand-built PNGs
  (threshold ≥ 0.98).
- **Smoke test.** The real portfolio run recomposed in Chromium and rendered four
  LinkedIn stills at 1200×1200. All four reported `cached=false` on first write,
  then cache hits with identical SHA-256s; the design and content hashes were
  recorded in `runs.stats_json`.

**Commit:** `feat(snaptospot): render deterministic stills`

---

### Step 9 — Video

- **Platform registry.** `design/video.py` holds the five specs as data, never
  branches: LinkedIn 1080×1080/15 s (`launch-video.mp4`), X 1920×1080/15 s,
  Instagram 1080×1920/18 s (`reel.mp4`, `reel-poster.png`), TikTok
  1080×1920/21 s, WhatsApp 1080×1920/18 s (`status-video.mp4`). Each carries its
  own safe area, byte ceiling and closing line. LinkedIn and X close on the URL;
  Instagram points at the bio; TikTok asks for a follow; WhatsApp asks for a
  reply, because a status cannot hold a link.
- **Pure timeline.** `render/frames.py` builds a JSON payload of scene windows
  and ships one `renderAt(t)` function to the page. Nothing reads a clock, a
  random number or `requestAnimationFrame`: frame `n` is `n / fps`, so the same
  timeline always paints the same frame. Scenes cross-fade
  (`CROSSFADE = 0.34 s`) so a boundary never lands on a near-black frame, and
  the progress bar is just `clamp(t / duration)` written to a CSS width.
- **One template, three ratios.** `asset_templates/video.html` renders scenes
  A–D into the same markup and lets ratio classes place the safe areas. Text
  enters with `cubic_out`; the accent rule and portrait use `out_back`. Captions
  are burned in, never fetched: the page carries a strict CSP and aborts every
  network request.
- **Readable hero copy.** A 122 px headline cannot hold a full thesis, so
  `_short_hook` splits the thesis at the first colon or sentence into a hook of
  at most 52 characters and keeps the remainder as the subhead. `_hero_size`
  picks a deterministic size from 148 px down to 72 px from the hook's length
  and longest word, which is what finally stopped scene A from colliding with
  the header on a square frame.
- **Capture.** `ChromeWorker.capture_frames` sets 1× device metrics, calls
  `renderAt(t)` and then `Page.captureScreenshot({format: "jpeg", quality: 95})`.
  Ranges are split by index and reassembled into a dense `{index: bytes}` list,
  so worker completion order cannot reorder frames. Chromium rasterises text
  differently depending on what was painted first, so each worker replays a
  `WARMUP_SECONDS = 2.5` window before its range and discards those frames; with
  that, 1, 2 and 4 workers produce byte-identical frames and one MP4 hash.
- **Deterministic encode.** `render/encode.py` shells out to ffmpeg with
  BT.709 conversion (`scale=in_range=full:out_range=tv:out_color_matrix=bt709`),
  `-crf 19`, `-preset slow`, `yuv420p`, `-r 30`, `+faststart`, `-an`, and the
  bitexact flags (`-fflags +bitexact`, `-flags:v +bitexact`,
  `-map_metadata -1`). `ffprobe` reports the result so a caller can assert
  codec, size, pixel format, colour range and frame count.
- **Poster.** `render/poster.py` captures a 1× PNG at `duration − 0.8 s`; if the
  frame is flat (`stddev < 3`, one grey level above 98.5% or fewer than four
  levels) it retries at `0.72 ×` and then `0.55 ×` duration before reporting
  the poster as blank. A blank poster is a warning, not a shipped thumbnail.
- **Cache and output.** The key is the same
  `(content_model_hash, design_system_hash, platform, template_version)`
  4-tuple, stored under `var/media/video-cache`; files land under
  `var/media/<tenant>/<site>/<run>/videos/<platform>/` with the §11 names. A
  repeat request reports `cached=true` and does not start Chromium.
- **API and CLI.** `POST /v1/runs/{id}/videos` accepts
  `{platforms, reuse_cache, workers}` and returns path, poster, byte sizes,
  SHA-256s, poster timestamp, `within_ceiling` and the ffprobe fields. Workers
  are constrained to 1–8. `python -m app.cli video --run <id> --platform
  linkedin --workers 2` does the same without the API.
- **Tests.** 183 tests pass and ruff is clean. New coverage: easing endpoints,
  index-derived frame times, poster timestamp, range partitioning, cross-faded
  boundaries, a pure render script with no clock/random/rAF, out-of-order range
  reassembly, the full registry and last-line table, short-hook and hero-size
  rules, warnings for missing evidence, strict CSP, blank detection, ceiling
  reporting on cache hits, the exact ffmpeg flag contract, identical frame and
  MP4 hashes across runs, ffprobe BT.709/limited-range output, a non-blank
  poster, cache hits without a browser, auth, tenant scoping, the
  analyse-before-video 409 and the unknown-platform 422.
- **Smoke test.** On the real portfolio run, LinkedIn 1080×1080/15 s rendered in
  **28.1 s** and WhatsApp 1080×1920/18 s in **52.3 s**, both under the 60 s
  exit bar. ffprobe reported `h264`, `yuv420p`, `tv`, `bt709` on all four colour
  fields, 30 fps and 450/540 frames; posters landed at 14.2 s and 17.2 s and
  were non-blank. Frames at every scene boundary were inspected and play with
  readable burned-in captions when muted.

**Commit:** `feat(snaptospot): render deterministic video`

---

## Done

### Step 10 — Copy and alt text

- **Counters.** `app/copy/counts.py` implements grapheme-aware counting for
  LinkedIn, Instagram, TikTok and WhatsApp, and X's weighted length (every URL
  costs 23, wide characters and emoji cost 2). Combining marks, ZWJ emoji,
  skin-tone modifiers and flags stay one character. The five `PostSpec`s live in
  the same module: limits, hashtag ranges, link policy and WhatsApp shapes.
- **Decks.** `app/copy/deck.py` builds a deterministic deck for every platform
  from the thesis, audience, offerings, projects, tier A/B facts and a derived
  voice card. It returns `primary`, exactly three alternatives, a thread for X,
  a short variant, hashtags and WhatsApp's four messages. No deterministic
  sentence introduces a digit outside the fact set.
- **Validation.** Every deck is re-counted with the platform's own counter and
  checked for length, hashtag count and declarations, link placement, banned
  phrases, em-dash overuse and unsupported digits. Thread numbering (`N/`) and
  URLs are stripped before digit checks, so structural numbers never fail.
- **LLM loop.** When `SNAP_LLM_API_KEY` is set, the model drafts against the
  `PostSpec`, voice card and banned list. A rejected draft gets exactly one
  regeneration with the issue list attached; if it still fails, the endpoint
  writes the deterministic deck and reports why in `warnings`. Banned phrases
  stay in config (`SNAP_COPY_BANNED_PHRASES`), not in the prompt.
- **Alt text.** `app/copy/alt.py` walks the `LayoutAST`, mentions every visible
  string in reading order and ignores `tools` and `footnotes` because the card
  template does not render them. Spatial hints are accepted only when the
  measured box agrees; a mismatch is dropped with a warning.
- **`post.md`.** `app/pack/postmd.py` writes the fixed nine sections from design
  §11: header, recommended copy with counts, thread/carousel/short variant or
  WhatsApp shapes, video caption, alt text, posting checklist, files table,
  re-render commands, and sources plus omissions. Tier-B facts appear with
  their URL and dates; open gaps and disclaimers are listed as omissions.
- **API and CLI.** `POST /v1/runs/{id}/copy` accepts `{platforms, use_llm}` and
  writes one `post.md` per platform under
  `var/media/<tenant>/<site>/<run>/posts/<platform>/post.md`.
  `python -m app.cli copy --run <id> --platform linkedin --platform x --no-llm`
  does the same without the API.
- **Tests.** 215 tests pass and ruff is clean. New coverage: grapheme clusters
  and X weighting (23-character URL, emoji, combining marks), every platform's
  deterministic deck and limits, digit/banned/hashtag/link validation, the
  reject-regenerate-fail loop, LLM fallback and acceptance, alt-text coverage
  and spatial hints, the nine `post.md` sections with sources and omissions,
  service output, auth, tenant scoping, the analyse-before-copy 409 and the
  unknown-platform 422.
- **Smoke test.** On the real portfolio run, `--no-llm` wrote LinkedIn 1,281
  characters, an X hook of 170 weighted characters, an Instagram caption of 704
  characters with five hashtags, and four WhatsApp messages (status 233
  characters, no hashtags, no link). All four decks validated and the LinkedIn
  file carried alt text for its four composed cards.

**Commit:** `feat(snaptospot): generate platform copy decks`

---

## Next step

### Step 11 — QA gates

1. `qa/ocr.py`: OCR cross-check with Tesseract/PaddleOCR.
2. `qa/overflow.py`, `qa/contrast.py`, `qa/safearea.py`: DOM, WCAG and platform
   mask gates from the AST.
3. `qa/provenance.py`: join every rendered number to a tier A/B fact.
4. `qa/report.py`: `qa.json`, per-asset status and retry policy.
5. Duplicate detection and brand-drift checks.

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

# browser rendering and card measurement (optional; the app falls back to static
# HTML and an estimator, but measured cards require Chromium)
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
$run.content_model.facts
$run.stats.gaps

Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/sites/$($site.id)/profile" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/sites/$($site.id)/content-model" -Headers $headers
```

Or use the **Authorize** button in `/docs` (flow: password, username = email).
`analyse` is synchronous in this step, so the response already contains the
profile and content model; later it moves behind a worker and the run endpoint is
what the UI polls.

### Content model and grounding

`content_model.facts[]` is the only legal source of a number. Each fact has a
tier (`A`–`D`), `source_id`, `source_quote` and `retrieved_at`; `proof`,
`quote`, offering metrics and project badges are fact pointers. The portfolio
fixture yields seven grounded metrics and one named quote. Rejected candidates
and their reasons are in `stats.rejected_facts`.

### Resolve gaps and answer the interview

```powershell
$gaps = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/gaps" -Headers $headers
$gaps.coverage
$gaps.blocking_open
$gaps.questions | Format-Table key, prompt, default, unlocks

# Answer one question. Omit a slot, or send skip = true, to accept the safe default.
$body = @{
  answers = @(
    @{ key = "offer.core"; value = "Brand strategy for small teams"; attest = $true }
  )
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/answers" `
  -Headers $headers -ContentType 'application/json' -Body $body

# Find fact ids, then accept, override or reject one.
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/facts" -Headers $headers

$override = @{ action = "override"; value = "10.1"; attest = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/facts/f_03" `
  -Headers $headers -ContentType 'application/json' -Body $override

# Render is blocked (409) while a blocking gap is open, then ready (202).
curl.exe -i -X POST "http://127.0.0.1:8000/v1/runs/$($run.id)/render" `
  -H "Authorization: Bearer $($pair.access_token)"
```

An override must include `attest: true`; the old fact is kept with status
`quarantined`. A client-supplied `tier` is rejected. The `gap_answers` table
stores the question and answer together, and `audit_log` records every answer,
skip, override, quarantine and rejection.

### Upload documents and cite a page

Upload a deck, CV, case study or brand guide and let retrieval answer one gap.
`gap_key` is optional; without it the uploader tries every open gap.

```powershell
curl.exe -X POST "http://127.0.0.1:8000/v1/runs/$($run.id)/documents" `
  -H "Authorization: Bearer $($pair.access_token)" `
  -F "files=@growth-deck.pptx" `
  -F "gap_key=proof.metrics"

Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/facts?status=accepted" -Headers $headers
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/documents" -Headers $headers
```

The upload response includes one parse report per file and the refreshed gaps.
A document fact carries the filename, `source_page`, the chunk id and a verbatim
quote. Pin a brand asset so expiry skips it:

```powershell
$docs = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/documents" -Headers $headers
$docId = $docs[0].id
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/documents/$docId/pin" `
  -Headers $headers -ContentType 'application/json' -Body '{"pinned":true}'
```

Run the retention job from the CLI (cron it daily in production):

```powershell
python -m app.cli expire-documents            # uses each document's expires_at
python -m app.cli expire-documents --days 30  # or force by age
```

PDF, DOCX, PPTX, Markdown, TXT and CSV work out of the box. Images need OCR:
install Tesseract plus `pytesseract`, then set `SNAP_OCR_ENABLED=true`. On
Postgres the migration creates the `vector` extension, an HNSW index on
`chunks.embedding` and a GIN index on `to_tsvector('english', text)`; SQLite uses
JSON vectors and Python BM25/cosine so local development needs no services.

### Search the web for a public gap

Configure one provider. Search stays disabled when the provider or key is blank,
and the run is labelled rather than failing:

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

Only public, professional gaps are searched, with one query per class and at
most six per run. A fact needs a score of at least `0.65`, a verbatim quote and
a working URL. Without a publication date the fact is tier C and cannot render a
number; results without a quotable answer leave the gap open for an answer or a
document.

### Compose measured cards

Composition derives (or reuses) the site's design system, builds each card from
tier A/B facts, and measures it in Chromium:

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
$composed.measured_in_browser          # true when Chromium measured the cards
$composed.layouts | Format-Table asset, ratio, measured.fit, measured.headline_pt, measured.overflow
$composed.layouts[3].slots.stats | Format-Table value, unit, label, fact_id, tier
```

- `direction=auto` reuses the direction pinned on the site. Pass an explicit
  direction to rebuild the token set deliberately.
- `fit` is `ok`, `reduced` (display type shrank within the 60% floor),
  `density_reduced` (a lower-density variant was used) or `overflow` (copy must
  be shortened; the response carries a warning).
- Every number, badge and quote in `slots` has a `fact_id`; tier C/D and stale
  undated facts never reach a card.
- Chromium is required for real metrics. Install it once with
  `playwright install chromium`; without it composition still runs with a
  conservative estimate and returns `measured_in_browser=false`.
- Template snapshots live in `tests/fixtures/snapshots/`. Refresh them after an
  intentional design change with
  `$env:SNAP_UPDATE_SNAPSHOTS="1"; pytest -k snapshot; Remove-Item Env:SNAP_UPDATE_SNAPSHOTS`.

### Render deterministic stills

Compose first; rendering reads the persisted measured ASTs and writes the four
LinkedIn PNGs under the tenant-scoped media root:

```powershell
$stills = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/stills" `
  -Headers $headers -ContentType 'application/json' `
  -Body (@{ platforms = @("linkedin") } | ConvertTo-Json)

$stills.renderer_version
$stills.assets | Format-Table filename, width, height, bytes, cached, sha256

# Force a recapture; the cache key stays the same.
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/stills" `
  -Headers $headers -ContentType 'application/json' `
  -Body (@{ platforms = @("linkedin"); reuse_cache = $false } | ConvertTo-Json)
```

Or from the CLI:

```powershell
python -m app.cli render --run $run.id --platform linkedin
python -m app.cli render --run $run.id --platform linkedin --force
```

- Output: `var/media/<tenant>/<site>/<run>/stills/linkedin/01-announcement.png`
  through `04-proof.png`.
- Capture is 2× and downsampled once with Lanczos; PNGs have no metadata and the
  same AST always hashes identically.
- The cache key is
  `(content_model_hash, design_system_hash, platform, template_version)`. A
  second request reports `cached=true`.
- `SNAP_RENDER_FETCH_REMOTE=false` makes rendering fully offline; images that
  cannot be loaded are omitted instead of drawn as broken frames.
- Composing a run is a prerequisite; the endpoint returns 409 otherwise.

### Render deterministic video

Compose first; video builds its own scenes from the content model and writes one
MP4 plus a poster per platform:

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

Or from the CLI:

```powershell
python -m app.cli video --run $run.id --platform linkedin --platform whatsapp
python -m app.cli video --run $run.id --platform linkedin --workers 4 --force
```

- Output: `var/media/<tenant>/<site>/<run>/videos/<platform>/launch-video.mp4`
  (Instagram `reel.mp4`, WhatsApp `status-video.mp4`) plus the platform poster.
- Specs: LinkedIn 1080×1080/15 s, X 1920×1080/15 s, Instagram
  1080×1920/18 s, TikTok 1080×1920/21 s, WhatsApp 1080×1920/18 s, all at 30 fps.
- Capture is 1× JPEG at quality 95; ffmpeg encodes H.264 with BT.709 limited
  range, `-crf 19`, `-preset slow`, `yuv420p` and `+faststart`. ffprobe output is
  returned so the colour and frame count can be checked without another tool.
- `workers` (1–8, default 2) splits the timeline by frame index. Each worker
  replays a 2.5 s warm-up window first, so 1, 2 and 4 workers produce the same
  frames and the same MP4 hash.
- The poster is a PNG at `duration − 0.8 s` (14.2 s for 15 s, 17.2 s for 18 s),
  retried at 72% and 55% of the duration if the frame is flat.
- The cache is keyed by
  `(content_model_hash, design_system_hash, platform, template_version)` under
  `var/media/video-cache`. A repeat request reports `cached=true`; send
  `"reuse_cache": false` or `--force` to re-encode.
- `within_ceiling` compares the file with the platform limit (LinkedIn 5 GB, X
  512 MB, Instagram/TikTok 4 GB, WhatsApp 16 MB) and adds a warning when it is
  exceeded.
- ffmpeg and ffprobe must be on `PATH`; no Python package replaces them.
- Composing a run is a prerequisite; the endpoint returns 409 otherwise.

### Generate copy decks and alt text

Copy needs the content model, not the rendered files. Composed layouts only add
alt text; without them the deck still writes and says so in section 5.

```powershell
$copy = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/runs/$($run.id)/copy" `
  -Headers $headers -ContentType 'application/json' `
  -Body (@{ platforms = @("linkedin", "x", "instagram", "whatsapp"); use_llm = $true } | ConvertTo-Json)

$copy.voice | Format-List person, tense, formality, sentence_length
$copy.files | Format-Table platform, primary_chars, short_chars, source, validated
$copy.decks | ForEach-Object { $_.primary; "" }
```

Or from the CLI, with no model call:

```powershell
python -m app.cli copy --run $run.id --platform linkedin --platform x --no-llm
```

- Output: `var/media/<tenant>/<site>/<run>/posts/<platform>/post.md`, one file
  containing the nine §11 sections.
- X counts every URL as 23 characters and the hook never contains the link.
  Instagram and TikTok say "link in bio"; WhatsApp has no hashtags and no link
  in its status.
- Banned phrases come from `SNAP_COPY_BANNED_PHRASES` (JSON list), not from the
  prompt, so they can change without a prompt version bump.
- A model draft gets one regeneration. If both drafts fail, the deterministic
  deck is written and the response lists the rejection reasons in `warnings`.

### Optional LLM understanding and extraction

Any OpenAI-compatible endpoint works:

```dotenv
SNAP_LLM_API_KEY=sk-...
SNAP_LLM_BASE_URL=https://api.openai.com/v1
SNAP_LLM_MODEL=gpt-4o-mini
```

Leave `SNAP_LLM_API_KEY` blank to use the deterministic heuristics and regex
pass. LLM output is validated against the block tree and falls back
automatically; an inadmissible draft fact is listed with its reject reason.

### CLI

```powershell
python -m app.cli ingest https://lyle-mlengineer.github.io --out var\profile.json
python -m app.cli extract https://lyle-mlengineer.github.io --out var\content.json
python -m app.cli render --run <run-id> --platform linkedin
python -m app.cli video --run <run-id> --platform linkedin --platform whatsapp
python -m app.cli copy --run <run-id> --platform linkedin --platform x --no-llm
```

### Useful settings

```dotenv
SNAP_MAX_PAGES=12
SNAP_USE_PLAYWRIGHT=true
SNAP_CAPTURE_SCREENSHOTS=true
SNAP_FETCH_TIMEOUT_SECONDS=20
SNAP_SSRF_ALLOW_PRIVATE=false   # true only for local fixture servers
SNAP_MEDIA_ROOT=var/media
SNAP_RENDER_FETCH_REMOTE=true   # false keeps rendering fully offline
# Video rendering shells out to ffmpeg/ffprobe on PATH and shares SNAP_MEDIA_ROOT.
SNAP_MAX_UPLOAD_FILES=5
SNAP_MAX_DOCUMENT_BYTES=10485760
SNAP_MAX_DOCUMENT_PAGES=40
SNAP_DOCUMENT_RETENTION_DAYS=30
SNAP_RETRIEVAL_TOP_K=8
SNAP_RETRIEVAL_TOP_CHUNKS=3
SNAP_EMBEDDING_MODEL=text-embedding-3-small
SNAP_EMBEDDING_DIMENSIONS=1536
SNAP_OCR_ENABLED=false
SNAP_SEARCH_PROVIDER=              # brave | tavily | serp; blank disables search
SNAP_SEARCH_API_KEY=
SNAP_SEARCH_TIMEOUT_SECONDS=20
SNAP_WEB_SEARCH_MAX_QUERIES=6
SNAP_WEB_SEARCH_RESULTS=3
SNAP_WEB_SEARCH_CACHE_DAYS=7
SNAP_WEB_SEARCH_MIN_SCORE=0.65
```

No Docker is required for these steps. Postgres is optional:

```powershell
docker compose up -d postgres redis
# set SNAP_DATABASE_URL=postgresql+psycopg://snaptospot:snaptospot@localhost:5432/snaptospot
```
