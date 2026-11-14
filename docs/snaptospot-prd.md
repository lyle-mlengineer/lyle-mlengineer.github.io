# SnapToSpot — Product Requirements Document

**Version:** 1.0
**Status:** Approved for build
**Owner:** Lyle Okoth
**Date:** November 2026
**Companion documents:** `docs/snaptospot-design.md` (technical design), `docs/steps.md` (implementation plan)
**Reference artefacts:** `media/linkedin/`, `media/twitter/`, `media/instagram/`, `media/whatsapp/`

---

## 1. Summary

SnapToSpot turns a website into a launch-ready social campaign: four stills, a short video, a poster frame and a copy deck for each of five platforms, built only from facts the site (or its owner) can support.

The product exists because the alternative is a choice between two bad options. A designer costs money and time. A generative image tool produces a poster that looks plausible and contains numbers nobody can defend — "23.4% → 11.2%" in a beautiful typeface. SnapToSpot takes the third path: the model writes the words and picks the structure, a deterministic renderer sets the type, and every number on every card traces back to a source span.

**One-line pitch:** paste a URL, approve the facts, get a campaign that looks like a designer read your site.

**What "done" means for v1:** a new user pastes a URL and, in under five minutes, exports a five-platform kit that passes every quality gate, whose quality is indistinguishable from the hand-built kits in `media/`.

---

## 2. Problem

### 2.1 Who hurts

| Segment | Pain | Current workaround | Cost of the workaround |
| --- | --- | --- | --- |
| Solo founder / indie engineer | shipped something, needs a launch today | Canva template + screenshots | 3–6 hours, generic look, inconsistent crops |
| Freelancer / consultant | needs to look established | reused old post, or nothing | invisible between engagements |
| Small agency | 10 client launches a month | junior designer + copywriter | $300–800 per launch, 3–5 days |
| Developer-tools marketer | needs native assets per platform | one 16:9 image cropped five ways | wrong safe areas, unreadable at thumbnail |

### 2.2 Why existing tools fail

1. **Generative image tools invent facts.** Text is unreliable; numbers are worse. A wrong metric on a founder's launch card is a credibility loss, not a design flaw.
2. **Template tools produce template output.** Every kit looks like the same Canva layout with different colours.
3. **"AI social manager" tools write copy, not design.** They produce a caption and a stock image, not a campaign system.
4. **One asset, five crops.** A 16:9 hero cropped to 9:16 loses the subject or the headline, and ignores platform safe areas.

### 2.3 The insight

A website is already a brand system: palette, type, tone, proof, screenshots, contact details. What it lacks is *composition for each platform* and *the discipline to omit what it cannot prove*. SnapToSpot supplies both.

---

## 3. Goals and non-goals

### 3.1 Goals (v1)

| ID | Goal | Measure |
| --- | --- | --- |
| G1 | Produce a five-platform kit from one URL | 20 stills + 5 videos + 5 posters + 5 copy decks per run |
| G2 | Never render an unsupported fact | 100% of rendered numbers map to tier A/B; 0 tier C/D |
| G3 | Look native on each platform | no shared crop between ratios; per-platform composition |
| G4 | Be fast enough to feel like a product | p50 < 5 min end to end; first preview < 90 s |
| G5 | Resolve missing information honestly | gaps answered, searched, retrieved or disclosed — never invented |
| G6 | Be cheap enough to give away | < $0.70 per full kit at list model prices |
| G7 | Be editable | every kit ships its HTML source and a re-render command |

### 3.2 Non-goals (v1)

- Video editing timeline or manual motion design.
- Multi-page websites beyond 12 pages, or authenticated/paywalled content.
- Generating faces, people, products or logos.
- Audio, voiceover or music.
- Native publishing to TikTok or WhatsApp (no post API; export + share sheet only).
- Multi-language output (English only in v1; Swahili in v2).
- Team collaboration, comments or approval chains (v3).
- Custom template authoring by users (v3).

### 3.3 Success metrics

**North star:** kits exported per week.

| Layer | Metric | Target |
| --- | --- | --- |
| Activation | URL → first preview in one session | > 80% |
| Activation | Fact review completed | > 70% of started runs |
| Quality | Assets passing all gates with no human edit | > 85% |
| Quality | Claim coverage at review | > 90% |
| Trust | Tier-B facts edited or rejected at review | < 5% |
| Trust | Runs abandoned at fact review | < 15% |
| Speed | URL → kit, p50 / p95 | < 5 min / < 12 min |
| Product | Kit → export | > 60% |
| Product | Second kit within 30 days | > 40% |
| Cost | Blended cost per kit | < $0.70 |
| Outcome | Median engagement lift vs the customer's previous post | tracked, never promised |

---

## 4. Personas

### P1 — Ada, solo technical founder
Ships a developer tool. Has a good README and a bad landing page. Needs a launch campaign for Product Hunt and LinkedIn by Thursday. Will pay $29/month if the output does not embarrass her in front of investors. Cares about: correct numbers, her own face, not looking like a template.

### P2 — Marcus, freelance ML engineer
Between contracts. Wants a portfolio that reads as a studio. Has a personal site with projects but no testimonials. Needs proof-shaped assets without inventing proof. Cares about: speed, editability, not sounding like a marketer.

### P3 — Priya, agency account lead
Runs launches for 8 clients. Needs 5 kits a month, consistent quality, white-label export, and a way to show the client what was claimed and where it came from. Cares about: turnaround, provenance report, bulk runs.

### P4 — Tom, developer-relations marketer
Has a product site with screenshots, pricing and a changelog. Needs platform-native assets for a release. Cares about: safe areas, correct crops, copy that does not oversell.

### Jobs to be done

| When… | I want to… | So I can… |
| --- | --- | --- |
| I ship a feature | generate a launch kit from my site | post everywhere the same day |
| a client signs | produce a campaign without a designer | protect my margin |
| I update my portfolio | refresh my social proof | look current to recruiters |
| a metric changes | regenerate only the affected cards | avoid redoing the whole kit |
| my site lacks a testimonial | have the app ask me or leave it out | avoid fake proof |

---

## 5. User journeys

### 5.1 First run (happy path)

1. Sign up with email + password (OAuth2 password grant, JWT session).
2. Paste URL, choose "person" or "product".
3. Watch the analysis panel fill: pages → brand → portrait → facts → gaps.
4. Answer up to five gap questions (or accept the conservative defaults).
5. Review facts: tier chips, source sentences, conflicts grouped.
6. Pick one of three art directions (previewed on card 1).
7. Watch render progress per platform.
8. Review the kit: four stills, video scrubber, copy with live character count.
9. Export ZIP, or copy the post deck.
10. Receive `manifest.json` listing sources and omissions.

**Time budget:** 90 s to first preview, 5 min to export.

### 5.2 Thin site (missing information path)

1. Extraction finds no pricing, one quote, no client logos, no portrait.
2. Fact review opens with four gap cards on the right.
3. User answers one (the metric date), uploads a deck for two more, skips the logo.
4. The resolver fills three facts at tier A, records one omission.
5. Composer selects a lower-density proof card; no logo wall, quote rendered as text.
6. Export lists the omission with its reason.

### 5.3 Return run

1. Open the site from the dashboard.
2. Cached identity and contact facts load instantly; only metrics are re-checked against the site hash.
3. Change one fact, re-render one platform.
4. Only the changed assets re-render; the rest are served from the content-hash cache.

### 5.4 Agency bulk run (v1.1, designed for now)

1. Upload a CSV of 20 URLs.
2. Runs queue at lower priority than interactive runs.
3. Each kit produces a provenance report the agency can forward to the client.
4. White-label export removes SnapToSpot branding.

---

## 6. Functional requirements

Priorities: **P0** = required for launch, **P1** = required for a good launch, **P2** = next.

### 6.1 Accounts and access

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-1.1 | Email + password sign-up and sign-in using OAuth2 password grant | P0 | `POST /v1/token` returns access + refresh JWT; Argon2id hashes; refresh rotates on use |
| FR-1.2 | Tenant isolation | P0 | no query can return another tenant's site, run, document or asset; enforced in the repository layer and tested |
| FR-1.3 | Session expiry and revocation | P1 | 15-min access token, 30-day refresh; "sign out everywhere" revokes all refresh tokens |
| FR-1.4 | Password reset by email | P1 | single-use token, 30-min expiry, rate-limited |
| FR-1.5 | Plan limits | P1 | Free: 1 platform, 3 kits/month, watermark; Pro: 5 platforms, 20 kits; enforced at queue time |

### 6.2 Site analysis

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-2.1 | Crawl up to 12 pages by intent | P0 | home, about, work, services, pricing, contact discovered; robots.txt obeyed; sitemap used |
| FR-2.2 | Render JavaScript before extraction | P0 | pages that mount content client-side produce non-empty text |
| FR-2.3 | Extract brand | P0 | palette (hex, area, contrast), fonts, logo, OG image |
| FR-2.4 | Extract entities | P0 | person name, role, location; org; email, phone, URL |
| FR-2.5 | Classify images | P0 | portrait, product shot, logo, decorative, stock; portrait has a face bbox |
| FR-2.6 | Capture screenshots | P0 | one 2× screenshot per project card candidate; no cross-domain capture |
| FR-2.7 | Produce `SiteProfile` with `gaps[]` | P0 | schema-valid; every block has a stable `source_id` |
| FR-2.8 | Progressive analysis events | P1 | UI receives page/brand/portrait/fact/gap counts as they complete |

### 6.3 Gap resolution

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-3.1 | Declare gaps from a requirement schema | P0 | missing slots become gaps with class and severity; no ad-hoc guessing |
| FR-3.2 | Ask the user | P0 | ≤ 5 questions, each with a default and a stated consequence; answers stored with `attested` |
| FR-3.3 | Document upload and retrieval | P0 | PDF/DOCX/PPTX/MD/CSV/TXT/PNG; 5 files, 40 pages, 10 MB each; hybrid retrieval; verbatim quote required |
| FR-3.4 | Web search | P1 | ≤ 6 queries; candidates scored ≥ 0.65; result capped at tier B; URL + date stored |
| FR-3.5 | Trust tiers A–D | P0 | tier assigned from `source_type`; tier C/D stripped before composition |
| FR-3.6 | Conflict detection | P0 | conflicting facts grouped in review; only one accepted per key |
| FR-3.7 | Omission disclosure | P0 | every skipped blocking gap appears in `manifest.json` with a reason |
| FR-3.8 | Caching and TTL | P1 | second run for the same domain skips crawl and questions; TTLs per §8.7.7 of the design |
| FR-3.9 | Degraded modes | P1 | no search key → questions + documents still work; timeout at 45 s returns partial and continues in background |

### 6.4 Fact review

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-4.1 | Show source beside every fact | P0 | sentence + page URL, document page, answer timestamp, or web URL |
| FR-4.2 | Tier chips | P0 | `A·site`, `A·you`, `A·deck`, `B·web` visible on every row |
| FR-4.3 | Keep / edit / remove | P0 | edit requires attestation; removal updates coverage immediately |
| FR-4.4 | Conflict UI | P0 | exactly one value selectable; the rejected value stays visible |
| FR-4.5 | Gap panel | P0 | answer, upload, search, skip per gap; skip states which card is dropped |
| FR-4.6 | Nothing renders before approval | P0 | render endpoint returns 409 while a blocking gap is open or a fact is unapproved |
| FR-4.7 | Two-tap approve for structured sites | P2 | JSON-LD + consistent numbers allows bulk approve |

### 6.5 Design and composition

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-5.1 | Three art directions | P0 | Editorial Dark, Swiss Paper, Signal Grid; each a full token set |
| FR-5.2 | Brand-seeded default | P0 | accent chosen by OKLab clustering with ≥ 4.5:1 contrast, else stock accent |
| FR-5.3 | Per-platform composition | P0 | 1:1, 16:9, 4:5, 9:16 each have their own layout variant, not a crop |
| FR-5.4 | Density variants | P0 | proof card supports 4/3/2 stats; projects support 8/6/4/2 tiles |
| FR-5.5 | Text fitting by measurement | P0 | binary search on font size; min 60% of nominal; reduce density before shrinking further |
| FR-5.6 | Safe areas | P0 | Instagram/Reel 260 top + 420 bottom; TikTok 130/320/120; WhatsApp 300 bottom |
| FR-5.7 | Deterministic render | P0 | same inputs produce byte-identical output; no `Date.now()`, no `Math.random()` unseeded |
| FR-5.8 | Design system memory | P1 | tokens stored per site; second run reuses them unless the user asks to refresh |

### 6.6 Video

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-6.1 | Scene timeline from `ContentModel` | P0 | 4 scenes mapping to the card arc; 15 s (LinkedIn/X), 18 s (IG/WhatsApp), 21 s (TikTok) |
| FR-6.2 | Deterministic `renderAt(t)` | P0 | pure function of `t`; no CSS transitions, rAF or timers |
| FR-6.3 | Frame capture and encode | P0 | 30 fps, H.264, yuv420p, BT.709, faststart; colour range converted to avoid washed-out darks |
| FR-6.4 | Poster frame | P0 | captured at `duration − 0.8 s` |
| FR-6.5 | Burned-in captions | P0 | works muted; no audio track in v1 |
| FR-6.6 | Platform-specific closing line | P0 | IG "link in bio", WhatsApp "reply to this status", LinkedIn/X URL |

### 6.7 Copy

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-7.1 | Per-platform copy deck | P0 | primary, 3 alternatives, thread (X), short variant, hashtags, alt text |
| FR-7.2 | Hard character budgets | P0 | counted the way the platform counts; X URL = 23 chars; reject or regenerate on overflow |
| FR-7.3 | Claims only from `facts[]` | P0 | any digit in copy must reference an accepted tier A/B fact |
| FR-7.4 | Banned phrases | P1 | "excited to announce", "game-changer", "revolutionary", "unlock", em-dash overuse |
| FR-7.5 | Alt text from the layout tree | P0 | every visible string represented; spatial context checked against the AST |
| FR-7.6 | `post.md` structure | P0 | 9 sections: header, copy, thread/carousel, video caption, alt text, posting order, files, re-render, sources/omissions |
| FR-7.7 | Editability | P0 | the user can copy any block and change it; no locked text |

### 6.8 Render, QA and export

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-8.1 | Render stills at 2× then downsample | P0 | type crisp at 1×; PNG output |
| FR-8.2 | Per-asset render cache | P1 | keyed by `(content_model_hash, design_system_hash, platform, template_version)` |
| FR-8.3 | QA gates | P0 | OCR ≥ 98%, 0 overflow, contrast, thumbnail, safe area, provenance, alt text, spec, brand drift, duplicate |
| FR-8.4 | Provenance gate | P0 | 100% of numbers resolve to a `fact_id`; zero tier C/D |
| FR-8.5 | QA report | P0 | `qa.json` per kit; UI shows green/amber per asset |
| FR-8.6 | ZIP export | P0 | `media/<platform>/` structure + `manifest.json` + `post.md` + `assets/` + contact sheet |
| FR-8.7 | Share links | P1 | signed URLs, 30-day expiry, no auth required to view |
| FR-8.8 | Contact sheet | P1 | one PNG showing every asset in the kit |

### 6.9 Publishing (v1.1)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-9.1 | LinkedIn and X OAuth connect | P2 | scopes limited to post creation; token encrypted at rest |
| FR-9.2 | Review-before-publish | P2 | exact text, image and alt text shown before the API call |
| FR-9.3 | Export-first for IG/TikTok/WhatsApp | P0 | share sheet + copy blocks; no fake "published" state |

---

## 7. Platform requirements

| | LinkedIn | X | Instagram | TikTok | WhatsApp |
| --- | --- | --- | --- | --- | --- |
| Still | 1200 × 1200 | 1600 × 900 | 1080 × 1350 | 1080 × 1920 cover | 1080 × 1920 status |
| Secondary | 1080 × 1350 | 1080 × 1080 | 1080 × 1080 | — | 1080 × 1080 share |
| Video | 1080 × 1080 / 15 s | 1920 × 1080 / 15 s | 1080 × 1920 / 18 s | 1080 × 1920 / 21 s | 1080 × 1920 / 18 s |
| Caption | 3,000 | 280 (25k) | 2,200 | 2,200 | status caption, ~700 |
| Hashtags | 3–5 | 0–2 | 3–10 | 3–5 | 0 |
| Link | clickable | clickable, down-ranked | bio only | bio only | not clickable |
| Copy shape | post + article variant | thread of 5 | caption + carousel | caption + hook | personal message |

Requirements:

- FR-10.1: every asset is exported at the exact registry size; the UI shows dimensions on every tile.
- FR-10.2: no platform asset is a crop of another platform's asset.
- FR-10.3: the platform registry is data (`PlatformSpec`), versioned, with `last_verified`; CI fails when a spec is stale.
- FR-10.4: WhatsApp has no hashtags, no link in the status, and a phone/QR share card, because it is forwarded in chats.

---

## 8. AI requirements

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| FR-11.1 | One task per model call | P0 | extraction, resolution, copy and alt text are separate prompts |
| FR-11.2 | Structured output only | P0 | JSON Schema validated; invalid output retried once, then failed |
| FR-11.3 | Verbatim citations | P0 | every fact has `source_quote`; fuzzy match ≥ 0.92 against the source |
| FR-11.4 | Numbers are never paraphrased | P0 | number-in-quote check; banned roundings |
| FR-11.5 | No model-assigned tiers | P0 | tier derived from `source_type` server-side; a model claiming tier A for a web fact fails validation |
| FR-11.6 | Fetched text is data | P0 | prompt-injection wrapper; instruction echo test in CI |
| FR-11.7 | No synthetic people | P0 | hard block on any generative model that outputs a face; code path does not exist |
| FR-11.8 | Model/prompt versioning | P0 | `model_versions_json` stored per run; prompt versions in git |
| FR-11.9 | Cost ceilings | P1 | per-run token and query budgets; run fails closed at 2× budget |

---

## 9. Non-functional requirements

### 9.1 Performance

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-1 | URL → first preview | < 90 s p50 |
| NFR-2 | URL → full kit | < 5 min p50, < 12 min p95 |
| NFR-3 | Still render per asset | < 3 s |
| NFR-4 | 15 s video at 1080² | < 60 s |
| NFR-5 | Fact review interaction | < 200 ms per action |
| NFR-6 | Second run (cached facts) | < 90 s |

### 9.2 Reliability

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-7 | Run success rate (excluding user error) | > 97% |
| NFR-8 | Resumability | a failed run resumes at the last good stage, never from zero |
| NFR-9 | Idempotency | every POST accepts `Idempotency-Key`; render is content-hash keyed |
| NFR-10 | Data durability | Postgres PITR; B2 object versioning for 7 days |

### 9.3 Security

| ID | Requirement |
| --- | --- |
| NFR-11 | TLS everywhere; HSTS; secure, httpOnly, SameSite=Lax cookies for the web session |
| NFR-12 | Argon2id password hashing; breach-list check at sign-up |
| NFR-13 | Tenant isolation tested with a dedicated suite (attempt cross-tenant reads for every endpoint) |
| NFR-14 | SSRF protection: block private IP ranges, link-local, metadata endpoints, non-http schemes |
| NFR-15 | Upload scanning: MIME sniffing, size limits, decompression-bomb guard, malware scan |
| NFR-16 | Secrets in environment/secret manager only; never in logs |
| NFR-17 | Rate limits: 10 runs/hour per tenant, 20 login attempts/hour per IP |

### 9.4 Privacy and legal

| ID | Requirement |
| --- | --- |
| NFR-18 | Raw HTML and screenshots deleted after 24 h; documents after 30 days unless pinned |
| NFR-19 | PII extracted only from the site's own contact section, encrypted, never rendered unless opted in |
| NFR-20 | Search restricted to professional, public facts; no queries for private personal data |
| NFR-21 | Client logos require an explicit permission attestation |
| NFR-22 | Data export and account deletion within 30 days (GDPR-style) |
| NFR-23 | Generated imagery limited to abstract backgrounds and listed in `manifest.json` |

### 9.5 Accessibility

| ID | Requirement |
| --- | --- |
| NFR-24 | Every generated asset has alt text derived from the layout tree |
| NFR-25 | The app UI meets WCAG 2.2 AA: keyboard navigable, focus visible, contrast ≥ 4.5:1 |
| NFR-26 | Video captions burned in; no information conveyed by colour alone |

### 9.6 Observability

| ID | Requirement |
| --- | --- |
| NFR-27 | OpenTelemetry traces per stage; render duration is the key SLI |
| NFR-28 | Sentry for exceptions with tenant and run context (no PII) |
| NFR-29 | Per-run cost recorded (tokens, searches, CPU-minutes) |
| NFR-30 | Audit log for fact edits, overrides, omissions and publishes |

---

## 10. UX requirements

### 10.1 Screens

| Screen | Required states |
| --- | --- |
| Start | empty, invalid URL, blocked by robots, queued |
| Analysis | progressive panels, partial failure, retry per panel |
| Fact review | no gaps, 1–5 gaps, conflict, all-skipped, source-unreachable |
| Design pick | 3 previews, locked brand colours |
| Render | per-platform progress, per-asset retry, cancel |
| Kit preview | stills, video scrubber, copy with live count, provenance tab |
| Export | ZIP building, share link, publish handoff |

### 10.2 Rules

- FR-12.1: previews render at true aspect ratio; the container never silently crops.
- FR-12.2: the caption editor counts characters exactly as the platform does.
- FR-12.3: every asset tile shows its dimensions and file size.
- FR-12.4: any web-sourced fact is marked in the preview, not only in the manifest.
- FR-12.5: destructive actions (remove fact, skip gap) state their consequence before confirming.
- FR-12.6: the app works on a 1280 px laptop and a 390 px phone for review (render stays desktop-first).

---

## 11. Data and retention

| Data | Store | Retention |
| --- | --- | --- |
| Account, tenant, plan | Postgres | account lifetime |
| Site profile, design tokens | Postgres | until site deleted |
| Raw HTML, screenshots | B2 | 24 h |
| Facts, gaps, answers | Postgres | run + 12 months for brand memory |
| Documents, chunks, embeddings | B2 + pgvector | 30 days (pinned: until unpinned) |
| Web query log | Postgres | 90 days |
| Rendered assets | B2 + CDN | 90 days, or until deleted |
| QA reports, manifests | Postgres + B2 | 12 months |
| Audit log | Postgres | 24 months |

---

## 12. Integrations

| Integration | Purpose | Failure mode |
| --- | --- | --- |
| LLM provider (frontier) | extraction, content model, copy | retry, fall back to smaller model for copy only |
| Embedding model | document retrieval | skip RAG, ask the user |
| Reranker | retrieval quality | use RRF order |
| Search API (Brave/Serp/Tavily) | web facts | skip rung 4, label run |
| Backblaze B2 | objects | retry with backoff; run pauses, does not fail |
| CDN | asset delivery | signed origin fallback |
| SMTP/ESP | password reset, kit ready | queue and retry |
| LinkedIn / X API (v1.1) | publishing | export fallback |
| Payment provider | plans | read-only mode on outage |

---

## 13. Pricing and packaging

| Plan | Price | Limits |
| --- | --- | --- |
| Free | $0 | 1 platform, 3 kits/month, watermark, no video |
| Pro | $29/month | 5 platforms, 20 kits/month, video, no watermark |
| Studio | $99/month | unlimited kits, brand memory, 5 seats, white-label |
| Agency | $299/month | bulk runs, API access, custom templates, provenance reports |

Cost floor per kit is $0.63 (design §16), so Pro is profitable at 8 kits/month and up. Free tier is a marketing cost capped by the 3-kit limit.

---

## 14. Analytics events

| Event | Properties |
| --- | --- |
| `run.started` | site_id, plan, promo_type |
| `analysis.panel_ready` | panel, duration_ms |
| `gaps.detected` | count, classes[] |
| `gap.resolved` | gap_key, strategy (answer/document/search/skip), duration_ms |
| `fact.reviewed` | action (keep/edit/remove), tier, source_type |
| `direction.selected` | direction, was_default |
| `render.completed` | platform, asset_count, duration_ms |
| `qa.failed` | gate, asset_id, retry_count |
| `kit.exported` | platform_count, format |
| `kit.shared` | channel |
| `publish.succeeded` | platform |
| `cost.recorded` | run_id, llm_usd, search_usd, compute_usd |

No event contains raw fact values, emails, phone numbers or document names.

---

## 15. Launch plan

| Stage | Audience | Exit criteria |
| --- | --- | --- |
| Internal alpha | 5 sites, team only | golden-kit regression passes; < 3 P0 bugs |
| Private beta | 25 users, waitlist | 70% complete fact review; 50% export; NPS ≥ 30 |
| Public beta | Product Hunt + LinkedIn | 97% run success; cost < $0.70; support load < 5 tickets/day |
| v1 GA | all plans | 85% assets pass with no edit; p95 < 12 min |

Rollout is feature-flagged: `gap_web_search`, `gap_documents`, `video`, `publish_linkedin`.

---

## 16. Acceptance and release criteria

A release is shippable when:

1. All P0 requirements are implemented and covered by an automated test.
2. The golden-kit regression renders the four LinkedIn cards and the 15 s video from `ContentModel` fixtures and matches the hand-built `media/linkedin/` assets within perceptual tolerance (SSIM ≥ 0.98 for stills; frame-level diff reviewed for video).
3. The provenance gate passes on every kit in the regression set, including a deliberately sparse fixture site.
4. A cross-tenant isolation suite passes for every endpoint.
5. Prompt-injection fixtures produce null extractions, not instruction echo.
6. p50 and p95 latency targets met on a 4 vCPU worker.
7. Cost per kit measured and under budget.
8. `docs/snaptospot-design.md`, `docs/steps.md` and the OpenAPI schema are current.

---

## 17. Risks, assumptions, dependencies

### 17.1 Assumptions

- Users have a public website that represents them accurately.
- Frontier models remain good enough for structured extraction at these prices.
- Platform specs change slowly enough that a quarterly review plus CI staleness check is sufficient.
- Users will answer up to five questions if each one visibly improves the kit.

### 17.2 Dependencies

- Search API contract and quota.
- LLM provider JSON-schema support.
- Chrome headless stability in containers (pinned image).
- B2 S3-compatible API behaviour for multipart uploads.

### 17.3 Top risks

| Risk | Mitigation |
| --- | --- |
| Model writes a plausible wrong fact | `fact_id`-only schema, grounding gate, human review, provenance QA |
| Web search returns an outdated figure | tier-B cap, mandatory date, visible citation, recency decay |
| Kits look samey | three directions, density variants, per-brand tokens, "surprise me" |
| Fact review drop-off | conservative defaults, ≤ 5 questions, two-tap approve for structured sites |
| Render cost | stills first, content-hash cache, CRF tuning, video on demand |
| Legal challenge over likeness | absolute no-synthetic-person policy, consent ledger |
| Platform spec drift | registry as data, `last_verified`, nightly doc check |

---

## 18. Traceability

| PRD area | Design document |
| --- | --- |
| FR-2 site analysis | §6.1–6.2, §7.1 |
| FR-3 gap resolution | §6.2.1, §8.7 |
| FR-4 fact review | §13 |
| FR-5 design/composition | §6.5–6.6, §7.3–7.4, §9.2 |
| FR-6 video | §7.5, §9.3–9.5 |
| FR-7 copy | §6.8, §8.4–8.5, §11 |
| FR-8 QA/export | §11–12 |
| FR-10 platforms | §10, Appendix B |
| FR-11 AI | §8.1–8.3, Appendix A |
| NFR security/privacy | §17 |
| Cost/pricing | §16 |

---

## 19. Open product questions

1. Should web search ship in v1 at all, given that a wrong tier-B fact costs more trust than an unanswered question?
2. Is five questions the right ceiling, or should it adapt to account history?
3. Does the free tier include video? It is the most expensive asset and the most shareable.
4. Should the kit include a "how this was made" page for agencies to forward?
5. WhatsApp has no post API: is "download + share sheet" acceptable, or does the product need a desktop helper?

---

## 20. Glossary

| Term | Meaning |
| --- | --- |
| Kit | all assets and copy for one site, one campaign |
| Asset | one rendered file: still, video or poster |
| Fact | a value that may render, with source, tier and confidence |
| Gap | a required slot the sources could not fill |
| Tier A/B/C/D | attested, corroborated, reported, inferred |
| `ContentModel` | the AI's structured campaign plan, facts referenced by id |
| `LayoutAST` | the resolved, measured composition for one asset |
| Golden kit | the hand-built reference kit used as a regression baseline |
