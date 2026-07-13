# 04 — Roadmap & Status

> **This file is the project's state.** Whoever works next (any teammate, any AI model)
> reads this first. Check items off with the date when done. Add notes under a phase if a
> decision changed — and update the other docs in the same commit.

**Status legend:** `[ ]` todo · `[x] YYYY-MM-DD` done · `[~]` in progress (add owner)

---

## Phase 0 — Foundation rebuild (≈1 week)

The current code is a working demo skeleton (keyword router, mock nodes, single-page UI).
Phase 0 turns it into the real platform every feature plugs into.

- [ ] Upgrade backend deps: `langgraph>=0.2`, `langchain>=0.3`, add `sqlalchemy`, `alembic`, `ortools`, `chromadb`, `apscheduler` (see 03-TECH-STACK)
- [ ] Create `app/core/llm.py` provider-agnostic factory + extend `Settings` (LLM_PROVIDER, LLM_MODEL, DATABASE_URL)
- [ ] Create `app/db/` — SQLAlchemy models from the 02-ARCHITECTURE data model + `seed.py` with realistic demo data (1 dept, 4 sections, ~12 teachers, ~15 subjects, ~10 rooms)
- [ ] Replace keyword `router_node` with LLM `supervisor.py` (structured-output routing)
- [ ] Add LangGraph checkpointer (SqliteSaver) + thread IDs per conversation
- [ ] JWT auth + user roles; login page in the frontend
- [ ] Restructure per 02-ARCHITECTURE §5 (api routers per domain, specialists/, tools/)
- [ ] Verify: existing chat + workflow-trace UI still works end-to-end against new graph

## Phase 1 — F1 Timetable Generation (≈2 weeks)

- [ ] `solver/timetable_model.py` — OR-Tools CP-SAT model (hard constraints: teacher/room/section clash-free, subject period counts, lab consecutiveness; soft: teacher max hours/day, workload balance)
- [ ] Tools: `solve_timetable`, `get_timetable`, `apply_timetable_diff`
- [ ] Timetable Agent specialist (parse request → solver spec → run → explain result/infeasibility)
- [ ] Admin data-entry UI (subjects, teachers, teacher-subject map, sections, rooms) + CSV import
- [ ] Timetable grid view in dashboard (per section, per teacher)
- [ ] Demo script: generate full timetable live, then make it infeasible and show the explanation

## Phase 2 — F2 Leave & Substitution — the flagship (≈2 weeks)

- [ ] Leave application UI + API; approval card UI for HOD role
- [ ] Substitution Agent: candidate ranking tool (`find_free_teachers` with subject/dept/workload weighting), plan builder producing a timetable diff
- [ ] Proactive trigger: leave-approved event → agent runs automatically (APScheduler + DB hook)
- [ ] Human-in-the-loop: `interrupt()` → approval record → `POST /api/approvals/{id}/decide` resumes the graph thread
- [ ] Notification Agent v1 (in-app inbox + WebSocket push)
- [ ] Demo script: approve a leave, watch the plan appear with zero prompting, approve it, see notifications land

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

## Decision log

Append decisions here so future sessions don't re-litigate them:

- **2026-07-13** — Docs structure created; feature set and architecture defined (docs 01–03).
  Supervisor-pattern LangGraph + typed tools + OR-Tools solver + provider-agnostic LLM layer
  chosen. Flagship demo = proactive leave→substitution flow with human-in-the-loop approval.
