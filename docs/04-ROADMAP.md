# 04 — Roadmap & Status

> **This file is the project's state.** Whoever works next (any teammate, any AI model)
> reads this first. Check items off with the date when done. Add notes under a phase if a
> decision changed — and update the other docs in the same commit.

**Status legend:** `[ ]` todo · `[x] YYYY-MM-DD` done · `[~]` in progress (add owner)

---

## Phase 0 — Foundation rebuild (≈1 week)

The current code is a working demo skeleton (keyword router, mock nodes, single-page UI).
Phase 0 turns it into the real platform every feature plugs into.

- [x] 2026-07-13 Upgrade backend deps — langgraph 1.2.9, langchain 1.3.13, sqlalchemy 2.0.51, ortools 9.15, apscheduler, PyJWT, passlib (chromadb deferred to Phase 3; alembic deferred until schema stabilizes — using `create_all` for now)
- [x] 2026-07-13 `app/core/llm.py` provider-agnostic factory + extended `Settings` (LLM_PROVIDER/LLM_MODEL/DATABASE_URL/JWT) + `.env.example`
- [x] 2026-07-13 `app/db/` — full SQLAlchemy model set from 02-ARCHITECTURE §3 + idempotent `seed.py` (CSE dept, 2 sections, 6 teachers, 8 subjects, 8 rooms, 35 timeslots, demo logins in seed.py docstring)
- [x] 2026-07-13 Keyword router → `supervisor.py` (LLM structured-output routing with graceful keyword fallback when no/invalid API key — verified live)
- [x] 2026-07-13 LangGraph SqliteSaver checkpointer + per-conversation `thread_id` (returned in ChatResponse)
- [x] 2026-07-13 JWT auth + user roles — backend (login/me endpoints, pbkdf2 hashing, `require_role`) **and** frontend `/login` page (glass UI, token in localStorage, role-aware redirect)
- [x] 2026-07-13 Restructure per 02-ARCHITECTURE §5 — `api/` split (agent, auth, aggregator), `specialists/` (scheduling, booking, general), `db/`, `core/`; fixed main.py self-mount bug
- [x] 2026-07-13 Verified end-to-end via curl: /api/health, all 3 agent routes (facility/scheduler/general with DB-backed responses), auth login + rejection. Frontend visual check still recommended.

## Phase 1 — F1 Timetable Generation (≈2 weeks)

- [x] 2026-07-13 `solver/timetable_model.py` — CP-SAT model: H1-H8 hard constraints (clash-free teachers/sections/rooms, exact period counts, lab consecutive blocks in lab rooms, dedicated home classrooms, teacher daily limits, subject spread ≤2/day) + fairness objective (minimize teacher load gap). Infeasibility explained via prechecks (precise messages) + CP-SAT assumption literals (constraint-group conflicts). Verified: 48 lessons, zero clashes by independent SQL check, load gap 2, solves in ~8s
- [x] 2026-07-13 Tools: `app/tools/timetable.py` — `generate_timetable` (versioned storage), `get_section_grid`, `get_teacher_grid` (feeds Phase 2 substitution). `apply_timetable_diff` deferred to Phase 2 (needed for substitution plans)
- [x] 2026-07-13 Timetable Agent specialist + supervisor route "timetable" + REST: POST /api/timetable/generate (admin, 422+reasons on infeasible), GET /timetable/section/{name}, /teacher/{id}, /status. Chat "Generate a fresh timetable" → Timetable Agent → v3 stored (verified). Infeasibility explanations verified on 3 synthetic cases (no-teacher, demand>capacity, tight daily limits)
- [x] 2026-07-13 Admin data-entry UI (subjects, teachers, teacher-subject map, sections, rooms) + CSV import — `/setup` page (tabbed CRUD, subject-chip picker for teachers, CSV upsert with per-row error reporting + downloadable templates) backed by `app/api/setup.py` (14 endpoints; reads = any authenticated user, writes = admin-only; verified 200/403/401 via curl)
- [x] 2026-07-13 Timetable grid view — `/timetable` page: section selector, MON-FRI × P1-P7 grid with per-subject colors, lab-block markers, teacher+room per cell, admin-only Generate button, infeasibility explanation banner. (Teacher-view UI deferred; API already exists)
- [x] 2026-07-14 Demo script — `docs/05-DEMO-SCRIPT.md` (4 acts + Q&A ammunition)

## Phase 2 — F2 Leave & Substitution — the flagship (≈2 weeks)

- [x] 2026-07-14 Leave application UI + API — `/leaves` page (faculty apply form + admin approve/reject) backed by `app/api/leaves.py`; approving invokes the agent graph inline (source="system")
- [x] 2026-07-14 Substitution Agent — `app/tools/substitution.py` ranks candidates (subject match +3 > same dept +2 > free, minus weekly-load ×0.1 and per-plan-load ×0.5 for fairness/spread), builds plan grouped by `plan_id="leave-<id>"`, idempotent (safe across interrupt re-execution). `app/agents/specialists/substitution.py` node + supervisor route "substitution"
- [x] 2026-07-14 Proactive trigger — leave-approval API invokes agent immediately; APScheduler sweep (every 2 min) re-triggers any approved leave with no plan (restart safety net)
- [x] 2026-07-14 Human-in-the-loop — LangGraph `interrupt()` pauses node; Approval row stores `langgraph_thread_id`; `POST /api/approvals/{id}/decide` resumes with `Command(resume={"action": ...})`. **Verified live: approve path (2 subs confirmed + 3 notifications) and reject path (subs discarded)** — `/approvals` page shows plan cards with rationale per lesson
- [x] 2026-07-14 Notification Agent v1 — in-app inbox (`/inbox` page, 15s polling, unread badges, mark-read) via `app/api/notifications.py`. WebSocket push deferred to Phase 3
- [x] 2026-07-14 Flagship demo flow scripted in `docs/05-DEMO-SCRIPT.md` Act 3 and verified end-to-end twice (leave #1 approve path, leave #2 reject path)

## Phase 2.1 — Period-exchange substitution model (replaces ranked-cover)

Real college practice: teachers **exchange periods** rather than have a stand-in teach the
wrong subject. Partner B (same section) teaches their own lesson in A's leave slot; A recovers
the missed lesson later in B's vacated slot. Subject hours preserved; original timetable never
mutated. Full spec: `docs/06-EXCHANGE-PLAN.md`.

- [x] 2026-07-14 New `PeriodExchange` table (new table only — `create_all` can't alter columns;
  legacy `substitutions` kept as history). `app/tools/exchange.py` (same 5-function interface
  as the old `substitution.py`): partner search = same-section teacher free at A's slot on the
  leave date, with a recovery date on the partner's weekday after leave end; scored by nearest
  recovery > plan-spread > weekly-load fairness; labs excluded (manual); idempotent by `plan_id`
- [x] 2026-07-14 Agent node + approvals API + safety sweep re-pointed to the exchange tools;
  `interrupt()`/resume/Approval flow unchanged. HOD card now shows exchange pairs with recovery
  dates; notifications go to both the partner and the returning teacher
- [x] 2026-07-14 Dated overlay views: `GET /api/timetable/effective/{section}?date=` (single-day
  grid with exchanged cells flagged) + `GET /api/timetable/exchanges?from=&to=` (board). New
  `/exchanges` frontend page (board + effective day grid); `/approvals` card reworked. Original
  `timetable_entries` verified unchanged (312→312) across an approve cycle
- [x] 2026-07-14 Verified live: approve path (2 exchanges, partners teach own subjects on leave
  date, Anita recovers next day; both inboxes correct), reject path (rows rejected, overlay clean),
  idempotency across interrupt/resume (build_plan ran twice, produced 2 rows not 4). TSC clean

## Phase 2.2 — Anti-hectic scheduling: exchange adjacency guard + configurable generation

Two follow-ups from real college practice: keep back-to-back same-subject periods out of both
exchange plans and generated timetables, and let admins encode local rules (half-days, etc.) at
generation time. Full spec: `docs/07-PHASE2.2-PLAN.md`.

- [x] 2026-07-15 Exchange adjacency guard — `_pick_partner` now computes an *effective* per-date
  section map (base timetable + other confirmed exchanges + this plan's in-progress placements) and
  penalises candidates (−100 each, not hard-rejected) that would create same-subject student
  back-to-back, >2 of a subject/day, or 3+ consecutive teaching periods for either teacher. A clean
  swap always wins; an unavoidable one is still proposed but carries a ⚠ rationale + `warning` flag.
  Break-aware adjacency mirrors the solver's `_consecutive_pairs`. Verified: clean flow finds
  non-hectic swaps, forced-adjacency scenario emits the warning, idempotency preserved
- [x] 2026-07-15 Configurable generation constraints — `SolveOptions` (half_days, no_same_subject
  _consecutive→H9, max_consecutive_teaching→H10) threaded through `solve()`/`generate_timetable`;
  half-days implemented by slot filtering (precheck explains infeasibility for free); H9/H10 as
  optional CP-SAT assumption groups (named in infeasibility output). Per-version config persisted in
  new `timetable_configs` table (16th). `POST /generate` takes an optional validated body; `/status`
  returns the active version's config. Verified: each constraint holds in solver output, defaults =
  unchanged behavior, half-day/bad-day validation returns 422
- [x] 2026-07-15 UI — `/timetable` Constraints panel (per-day half-day toggles + last-period, anti-
  consecutive toggle, teacher run-cap input) posts the body and shows a config summary; `/approvals`
  tints ⚠ rows amber; `/exchanges` effective day view rendered as a **table** (period rows). TSC clean

## Phase 2.3 — Per-class constraints, back-to-back off by default, fast plan creation

Three bug/UX fixes surfaced in real use. Full spec: `docs/08-PHASE2.3-PLAN.md`.

- [x] 2026-07-15 **Per-class constraints** — `SolveOptions` gained `section_rules` (by section id):
  global defaults + per-section overrides for half-days and no-back-to-back (`SectionRules`, section
  wins per day). Half-days reimplemented as **per-section allowed-slot sets** (global slot filtering
  was wrong once one class keeps the full day) — disallowed placements pinned `x==0`. `precheck` is
  now per-section and adds a lab consecutive-block feasibility check. `POST /generate` body takes
  `sections: [{section, half_days, no_same_subject_consecutive}]`; config persisted with section
  **names**. Verified: per-section half-day cuts only that class, override beats global, unknown/
  duplicate section → 422, lab-infeasible half-days → precise 422, config round-trips
- [x] 2026-07-15 **No back-to-back by default** — `no_same_subject_consecutive` now defaults **ON**
  (solver, API `GenerateIn`, UI checkbox). The agent/chat path (`timetable_node`) was calling
  `generate_timetable()` bare — it now loads `options_from_config(db)` so chat regeneration keeps the
  admin's rules. Lab hardening: H8 "≤2/day" now applies to lab subjects too (a ppw>2 lab can't stack
  a 3rd period next to its block). Verified: empty body & chat path both yield 0 theory back-to-back;
  explicit `false` opts out; synthetic lab ppw=3 never places 3 adjacent
- [x] 2026-07-15 **Fast plan creation** — two culprits fixed. (a) `supervisor_node` now short-circuits
  system-sourced triggers (leave approval / APScheduler sweep) straight to `substitution` with **no
  LLM call** — the trigger already carries the intent. (b) The Phase 2.2 adjacency guard was an N+1
  query storm (per candidate per lesson); replaced with a `PlanContext` built once (~5 queries,
  everything else in-memory). Differential test vs the old query-based helpers: **0 mismatches** across
  all sections/teachers/days. Measured: leave-approval graph invoke **~7 s → 72 ms**, no LLM in trace,
  interrupt/resume + idempotency unchanged
- [x] 2026-07-15 **Download timetable as PDF** — `/timetable` PDF button (any role) renders the
  current section's grid via client-side jsPDF + jspdf-autotable (dynamic-imported), landscape A4,
  lab cells tinted, title/version/constraints header + app footer. Filename
  `timetable-<section>-v<version>.pdf`. Verified headless: valid `%PDF-`, all autotable hooks run

## Phase 3 — F3 Event Booking + F4 Knowledge RAG (≈2 weeks)

- [ ] Booking tools (availability vs bookings **and** timetable, capacity match, alternatives)
- [ ] Booking Agent + approval chain + 24h-nag cron sweep
- [ ] Campus calendar view in dashboard
- [ ] RAG: `rag/ingest.py` (PDF → chunks → Chroma), `search_documents` tool, Knowledge Agent with citations
- [ ] Document upload UI (admin)

## Phase 4 — Polish + stretch picks (remaining time)

- [ ] Email channel for notifications (SMTP)
- [ ] Pick stretch features by remaining time — recommended order:
  - [ ] F9 Analytics Agent (talk-to-your-data — big wow, ~3 days: read-only SQL tool + chart in UI)
  - [ ] F6 Attendance Sentinel (proactive cron + projection logic over seeded data)
  - [ ] F7 Complaint Triage  ·  [ ] F8 Exam Scheduler  ·  [ ] F10 Energy Watchdog (simulated feed)
- [ ] Harden: CORS narrowed, rate limits, error states in UI
- [ ] Final report + architecture diagrams (export from these docs) + rehearsed demo flow

---

## Research base

Literature review lives in **`research/`** (start at `research/README.md`). It has 5+ real,
citable papers per concept we use (IEEE / ACM / Springer / Elsevier / IEEE Access), a master
concept→code→paper mapping (`research/00-CONCEPT-MAPPING.md`), and a differentiation/gap-analysis
file (`research/09-DIFFERENTIATION.md`) for the novelty slide. **Before final submission, open each
linked paper and confirm exact authors/pages** — links and titles are real but formal citation
details must be verified from the source page.

## Decision log

Append decisions here so future sessions don't re-litigate them:

- **2026-07-13** — Docs structure created; feature set and architecture defined (docs 01–03).
  Supervisor-pattern LangGraph + typed tools + OR-Tools solver + provider-agnostic LLM layer
  chosen. Flagship demo = proactive leave→substitution flow with human-in-the-loop approval.
- **2026-07-13 (Phase 0)** — PyJWT chosen over python-jose (lighter, maintained); pbkdf2_sha256
  over bcrypt (no native build on Windows). chromadb install deferred to Phase 3 (heavy dep,
  unused until RAG). Alembic deferred; `Base.metadata.create_all` until schema stabilizes.
  Supervisor degrades to keyword routing on missing/invalid LLM key — demo never hard-fails.
- **2026-07-13 (Phase 0 — LLM enabled)** — Live Gemini routing now verified end-to-end.
  Two gotchas resolved: (1) new Google AI Studio keys are prefixed `AQ.` not `AIza` — both are
  valid, the old "must be AIza" assumption is wrong; the key must be copied exactly (a mistyped
  copy read as API_KEY_INVALID). (2) `gemini-2.5-flash` returns 404 "no longer available to new
  users" for freshly-created keys — switched `LLM_MODEL` to **`gemini-flash-latest`** (a stable
  alias that auto-tracks the current flash model, so specific-version deprecations won't break us).
  `gemini-2.0-flash` returned 429 RESOURCE_EXHAUSTED (free-tier quota). Verified: supervisor now
  does semantic routing + entity extraction (room/date/subject) across facility/scheduler/general.
