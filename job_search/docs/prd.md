# Skipper — Product Requirements Document

**Version:** 1.0
**Status:** Approved for build
**Owner:** Lyle Okoth
**Date:** November 2026
**Companion documents:** `design.md` (technical design), `steps.md` (build order), `../progress.md` (build log)
**Source brief:** `../../job_search.md`

---

## 1. Summary

Skipper is a private job-search agent. Give it a job — a link to a company careers page, a link to a job board, or the description pasted as text — and it produces the whole application pack: a summary of the role, research on the company, a tailored CV in PDF and DOCX, a cover letter, the email to send, prepared answers for *tell me about yourself*, *work history* and *projects you are proud of*, and likely technical and behavioural interview questions with answers.

A dashboard tracks every job and its application status. The public portfolio stays as it is; a rebuilt portfolio-style landing page hosts the entry point to the app, and the dashboard is behind a username and password.

**One-line pitch:** paste a job, get the pack, keep the pipeline moving.

---

## 2. Problem

### 2.1 Who hurts

| Who | Pain | Today's workaround | Cost |
| --- | --- | --- | --- |
| Lyle (primary) | Each application needs a tailored CV, a letter, an email and interview prep | Manual rewrites per role, copy-paste from old CVs | 2–4 hours per application; tailors fewer roles; forgets follow-ups |
| Same person, at scale | 10–30 open applications | A spreadsheet plus browser tabs | No single view of what is ready, applied, or waiting |
| Same person, interview eve | Interview in 12 hours | Ad-hoc reading of the job post | Weak answers, missed must-have topics |

### 2.2 Why existing tools fail

1. **Generic AI chat** produces a plausible letter with invented metrics ("improved accuracy by 35%") that cannot be defended in an interview. Tailoring must be grounded in real, maintained facts.
2. **CV builders** reformat one static CV; they do not decide what to emphasise for *this* role.
3. **Job trackers** are spreadsheets with a UI. They do not know what the job asked for, so they cannot prepare you for it.
4. **Application autofillers** optimise the click, not the content. A wrong CV submitted faster is worse.

### 2.3 The insight

The expensive part of applying is not typing. It is **re-deciding the same eleven things for every role**: what this job is, who this company is, which of my projects map to it, how to phrase my summary, what to leave out, what they will ask. That is a fixed pipeline with fixed inputs (the posting + a maintained portfolio). Automate it once, ground every claim in the portfolio, and keep a status board on top.

---

## 3. Goals and success measures

| ID | Goal | Measure (v1) |
| --- | --- | --- |
| G1 | One input produces a complete pack | 12 artifact types produced from a single URL or paste, ≥ 90% of runs |
| G2 | Never fabricate | 100% of employers, dates, degrees and metrics trace to the portfolio corpus or the posting; 0 invented numbers in reviewed output |
| G3 | Fast enough to use | p50 paste → pack < 6 minutes; progress visible within 3 seconds of starting |
| G4 | Track applications without a spreadsheet | Every job has a status and, once applied, a next action; dashboard answers "what needs me today?" in one screen |
| G5 | Interview prep that matches the job | Technical questions cover ≥ 80% of the posting's must-have skills |
| G6 | One product, not two | Landing page and app share the portfolio's visual language and pass the same responsive checks |
| G7 | Resumable by its owner | A new agent/engineer can continue from `progress.md` + `steps.md` without asking questions |

### 3.1 Non-goals (v1)

- Submitting applications automatically.
- Sending email (drafts and `mailto:` only).
- Multiple users, sharing or public profiles.
- Mobile apps, notifications, calendar sync.
- Support for postings that only exist as images/PDF or behind a login.
- Public API for third parties.

---

## 4. Personas

**Lyle — ML engineer, Nairobi.** Four years across software, data and ML; specialist in speech and audio AI. Applies for ML Engineer, AI Engineer, Data Engineer and occasional research roles. Works from a phone as often as a laptop. Cares about accuracy of claims more than volume of output.

**Future maintainer.** Another agent or engineer picking up the repo. Needs one file that says what is done, what is next, how to run it and where the seams are.

---

## 5. User journeys

### J1 — Add a job from a link (primary)

1. On the dashboard, press **Add job**.
2. Paste a careers-page URL, press **Analyse**.
3. Modal closes; the job page opens with a progress panel: "Reading the posting · Extracting details · Researching Acme · Writing your CV …".
4. Within minutes the panel completes and the page fills with artifacts: CV (PDF/DOCX), cover letter, email, five interview/spoken documents, company brief and summary.
5. The status advances from *reviewing* to *ready* automatically; Lyle downloads the CV and letter, copies the email, and marks the job **Applied** when sent.

**Acceptance:** no second form; job and run are created by one action; every artifact is reachable from the job page; a failed step reports which step and why.

### J2 — Add a job from text

Same as J1 but the **Paste text** tab takes the description (200–60,000 chars). Company is inferred; the job is flagged "no link" and the UI does not pretend to have a posting URL.

### J3 — Watch, cancel, retry

While a run is going, the job page shows the step list, elapsed time and **Cancel**. Cancel stops at the next step boundary and keeps completed artifacts. A failed required step shows a plain-English reason and **Retry**, which re-runs only that step and its dependants.

### J4 — Review and adjust an artifact

Open **Cover letter** → read → **Edit** → save. The edit becomes a new version; the old version remains downloadable. **Regenerate** re-runs only that skill using the same upstream context. The UI always shows which version is current.

### J5 — Track the application

From the job page or the jobs table, set status: *reviewing → preparing → ready → applied → interviewing → offer / rejected / withdrawn*. Each change is recorded with a timestamp. Set a next action ("Follow up with recruiter", "Interview 2 on Thursday"). Dashboard shows jobs with a next action today/overdue and jobs applied more than 7 days ago.

### J6 — Reuse company research

Open a company from any job → see research (summary, products, tech stack, recent news with sources), all jobs at that company and personal notes. A second application at the same company reuses the stored research and cites it.

### J7 — Sign in

Landing page → **Dashboard** → login page → username + password → dashboard. Wrong credentials show one generic message and are throttled. Sessions expire after 12 hours; **Sign out** clears the cookie server-side.

### J8 — Recover after a restart

If the server restarted mid-run, the job page says the run was interrupted and offers **Resume**. Resume skips completed skills and continues from the first incomplete one.

---

## 6. Functional requirements

### 6.1 Ingestion

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | Accept a job URL (http/https) or pasted text (200–60,000 chars) | Must |
| FR-2 | Fetch and read the posting from a company site, careers page or job-board page that serves HTML | Must |
| FR-3 | Extract a clean description; keep the raw text permanently for provenance | Must |
| FR-4 | Detect unreadable/JS-only pages and ask for pasted text instead of failing silently | Must |
| FR-5 | Resolve and create/attach the company; dedupe jobs by company + title + location | Must |
| FR-6 | Respect `robots.txt` for any page other than the one the user supplied | Must |
| FR-7 | Reject private/loopback hosts (SSRF) and cap size, redirects and time | Must |

### 6.2 Agent skills

| ID | Skill | Requirement | Priority |
| --- | --- | --- | --- |
| FR-8 | Job extraction | Structured details: title, company, location, work mode, type, seniority, salary, responsibilities, must/nice-to-have, keywords, deadline, red flags | Must |
| FR-9 | Job summary | 200-word summary + "what you'd do", "what they want", fit signals, gaps | Must |
| FR-10 | Company research | Summary, industry, size, HQ, products, tech stack, culture signals, recent news **with source URLs**, likely interview style, talking points, open questions | Must |
| FR-11 | CV writing | Tailored CV grounded in the portfolio; exported as both PDF and DOCX; ATS-friendly single column | Must |
| FR-12 | Cover letter | 250–350 words, company-specific, grounded; PDF + DOCX | Must |
| FR-13 | Email | Subject + 120–180 word body + attachment list, ready to copy | Must |
| FR-14 | Tell me about yourself | 60–90 second first-person answer + delivery notes | Must |
| FR-15 | Work history | Narrative answer + timeline of roles with proof points | Must |
| FR-16 | Proud project | 1–3 projects chosen for *this* job, with problem, build, impact, stack | Must |
| FR-17 | Technical interview | 10–14 likely questions with written answers and follow-ups, mapped to the posting's must-haves | Must |
| FR-18 | Behavioural interview | 8–10 likely questions with STAR answers drawn from the portfolio | Must |
| FR-19 | Every skill output is schema-validated; invalid output is repaired once, then reported as a step failure | Must |
| FR-20 | Skills are individually re-runnable without re-running the whole pack | Must |
| FR-21 | Failures of optional skills do not destroy a usable pack | Must |

### 6.3 Runs and progress

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-22 | Heavy work runs in the background; the HTTP request returns in < 1 s | Must |
| FR-23 | Progress is observable: overall %, current step, per-step status, elapsed time | Must |
| FR-24 | Front end polls for progress and stops on terminal states | Must |
| FR-25 | Runs can be cancelled; completed artifacts are kept | Must |
| FR-26 | Interrupted runs are detected at startup and can be resumed | Must |
| FR-27 | Only one active run per job (409 otherwise) | Must |
| FR-28 | Every run records tokens and duration, shown on the job page | Should |

### 6.4 Dashboard, jobs and companies

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-29 | Dashboard shows counts by status, jobs needing action and recent activity | Must |
| FR-30 | Jobs list supports status filter, company filter and text search; paginates | Must |
| FR-31 | Job page shows brief, summary, status control, next action, artifacts, run history and timeline | Must |
| FR-32 | Artifacts can be read in-app, copied, downloaded, edited (new version) and regenerated | Must |
| FR-33 | Companies list with job counts; company page with research, jobs and editable notes | Must |
| FR-34 | Status changes are recorded with timestamps and shown as a timeline | Must |
| FR-35 | Deleting a job archives it; archived jobs are hidden but recoverable | Should |
| FR-36 | Data export (JSON) and portfolio reindex from settings | Should |

### 6.5 Landing page and access

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-37 | `/` serves a new portfolio-style landing page with a Dashboard entry point | Must |
| FR-38 | The original static portfolio at the repository root is not modified | Must |
| FR-39 | Dashboard, jobs and companies require a username and password | Must |
| FR-40 | Login is throttled and CSRF-protected; session cookie is HttpOnly and expires | Must |
| FR-41 | The landing page works with no session, no DB access and no provider keys | Must |
| FR-42 | Theme toggle, navigation and layout match the portfolio in both themes and at 320–1440 px | Must |

### 6.6 Providers

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-43 | LLM access goes through a provider interface; Groq with `openai/gpt-oss-120b` / `gpt-oss-20b` is the v1 implementation | Must |
| FR-44 | A fake provider allows the whole app to run and be tested with no API key | Must |
| FR-45 | Web search goes through a provider interface with Serper and DuckDuckGo implementations; `auto` prefers Serper when configured | Must |
| FR-46 | Provider errors, rate limits and timeouts are retried, then reported without corrupting the run | Must |

---

## 7. UX requirements

### 7.1 Visual language

- Inherit the portfolio exactly: Poppins, hue 340 palette, 0.5–1 rem radii, soft shadows, chips for attributes, light/dark themes, section title + subtitle rhythm.
- The landing page must look like the same site as the portfolio, not a template. The app must look like the same product as the landing page.
- No new fonts, no icon library beyond Unicons, no external CSS/JS on app pages.

### 7.2 Interaction

- **Add job** is reachable from every app page in one click/tap.
- Progress is visible within 3 seconds of starting; the user never has to guess whether anything happened.
- Long operations show per-step names in plain language ("Researching Acme", not "company_research").
- Every destructive or expensive action (cancel, regenerate, archive) confirms inline, not with `window.confirm`.
- Empty states say what to do next, in one sentence, with one action.
- Errors state: what failed, whether work is lost, and the next action. No stack traces, no error codes alone.

### 7.3 Responsive and accessible

- 320 px: single column, no horizontal scroll, tables become cards, bottom tab bar.
- 768 px: two-column details, icon rail.
- 1024 px+: fixed side rail, artifact tabs, side-by-side document and metadata.
- Keyboard: all controls reachable, visible focus, Escape closes modals, focus returns to the trigger.
- Contrast ≥ 4.5:1; status colour always paired with text; `aria-live` on progress; `prefers-reduced-motion` respected.

---

## 8. Content requirements

Every generated document must:

1. Be written for one specific job and one specific company, using their real name and real requirements.
2. Contain no placeholders (`[Company]`, `Lorem`, `N/A`) and no emoji.
3. Use only portfolio facts for Lyle (employers, dates, degrees, projects, metrics) — identical wording for any number that already exists in the portfolio.
4. Use only job-posting facts for the role and only cited sources for the company; unknown values are omitted rather than guessed.
5. Read like a person wrote it: no "passionate", "synergy", "rockstar", "I am excited to apply" boilerplate openers.
6. Be bounded: CV ≤ 2 pages, cover letter ≤ 1 page / 350 words, email ≤ 180 words, spoken answers 150–220 words, technical answers ≤ 250 words each.
7. Mark anything the model could not verify in a separate `unverified_claims` list rather than embedding it.

---

## 9. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-1 | Runs on one small VPS or a laptop; no Redis, no Postgres, no Node build step |
| NFR-2 | Cold start < 2 s; page HTML < 120 KB; polling endpoint p95 < 15 ms |
| NFR-3 | Survives restart with an honest `interrupted` state and a resume path |
| NFR-4 | SQLAlchemy 2.0 ORM over SQLite in WAL mode; models are the schema, with forward-only Alembic revisions before the first deployed schema change; DB and artifacts documented for backup |
| NFR-5 | Secrets only from environment; never logged or rendered |
| NFR-6 | Untrusted scraped content is treated as data (prompt-injection resistant) and never rendered as HTML |
| NFR-7 | Rate limits on login, job creation and regeneration |
| NFR-8 | Test suite runs offline with fake providers in < 60 s |
| NFR-9 | Works in current Chrome, Firefox, Safari and mobile browsers (last two majors) |
| NFR-10 | No analytics, no third-party scripts, no data sent anywhere except the configured LLM and search providers |

---

## 10. Release plan

| Release | Contents | Exit criterion |
| --- | --- | --- |
| **R0 — Skeleton** | App factory, DB schema, auth, landing page, empty dashboard | Login works; landing renders in both themes at 320/768/1440 |
| **R1 — Vertical slice** | Add job from text/URL → extraction → summary → CV DOCX/PDF → job page with polling | One real posting produces a usable CV end to end |
| **R2 — Full pack** | All eleven skills, company research, artifacts, regeneration | Fixture run produces 12 current artifacts and status `ready` |
| **R3 — Tracking** | Dashboard counters, status machine, next actions, timeline, companies pages | A week of real applications can be run from the dashboard alone |
| **R4 — Hardening** | Resume, cancel, limits, backups, docs, responsive/accessibility pass | All NFRs verified; README sufficient for a fresh clone |

---

## 11. Metrics

Tracked locally in SQLite and shown on `/settings` (no external analytics):

- Runs per week, success rate, median duration, median tokens per run.
- Artifacts downloaded per pack; artifacts edited before sending (a high edit rate means prompts need work).
- Jobs by status; median days from *ready* to *applied*; follow-ups overdue.
- Extraction failure rate by source type (board vs company site vs paste).

**v1 targets:** ≥ 90% run success, ≥ 60% of packs reaching *applied*, 0 reported fabricated claims, < 6 min median pack.

---

## 12. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Scraping breaks on JS-heavy boards | High | Medium | Paste fallback with clear copy; Playwright deferred |
| Fabricated claims damage credibility | Medium | High | Portfolio-grounded prompts, numeric post-checks, `unverified_claims` surfaced |
| LLM cost/rate limits | Medium | Medium | Small tier for prose, large tier only where it pays, cache, token budget |
| Background job lost on restart | Medium | Low | Interrupted sweep + resume |
| Prompt quality plateau | Medium | Medium | Prompt versioning, prompt-hash tests, edit-rate metric |
| Scope creep into a "job platform" | Medium | Medium | Explicit non-goals; single user; no auto-apply |
| LibreOffice missing in deployment | Medium | Low | reportlab fallback; readiness reports mode |

---

## 13. Open questions

1. Should the pack include a short "why this company" answer for screening forms? (Candidate for v1.1.)
2. Should cover letters be generated in a house voice profile (stored in `data/portfolio/writing.md`)? (Yes, likely; prompt already references the writing sample.)
3. Do we need per-application snapshots of artifacts (what exactly was sent), rather than only current versions? (Design §26.3.)
4. Should the dashboard support a weekly digest email? (Out of scope: no email sending.)
5. Is a second LLM provider (OpenRouter/Ollama) needed for offline use? (Seam exists; fake provider covers tests.)
