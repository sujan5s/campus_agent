# CLAUDE.md

**START HERE:** Read `docs/README.md`, then `docs/04-ROADMAP.md` before starting work.

**Status (2026-08-25):** Phases 0, 1, 2, 2.2, 2.3 complete; Phase 3 **F3 (Event Booking) complete**, F4 (RAG) not started. Smart Campus Agent System — AI-driven campus ops platform.
- **Supervisor-router** LLM with keyword fallback; swappable providers (Gemini/Claude/OpenAI/Ollama) via `.env` only. **System-sourced triggers (leave approval, sweep) and structured booking-form requests skip the LLM** and route deterministically.
- **SQLAlchemy models** (16 tables) + idempotent seeding; JWT auth + role-based access
- **OR-Tools CP-SAT timetable solver** — 8 base hard constraints + optional admin constraints (H9 no same-subject back-to-back — **ON by default**, H10 teacher consecutive-teaching cap, half-days), all configurable **per class** (`section_rules`: global defaults + per-section overrides), fairness objective, clash-free verified
- **F1 Timetable Agent** + admin `/setup` (CRUD + CSV) + `/timetable` grid UI with a **Constraints panel** (scope selector: all-classes vs per-class; half-days, anti-consecutive, teacher run cap) and a **Download PDF** button (client-side jsPDF + jspdf-autotable, per-section grid, any role); config stored per version in `timetable_configs`. Specs: `docs/07-PHASE2.2-PLAN.md`, `docs/08-PHASE2.3-PLAN.md`.
- **F2 Leave & Substitution (flagship)** — proactive trigger → Substitution Agent builds a **period-exchange** plan (partner of same section swaps their lesson into the leave slot; absent teacher recovers it later in the partner's slot — subject hours preserved, original timetable untouched). The planner now **avoids hectic back-to-back scheduling**: candidates that create same-subject adjacency for students or 3+ consecutive teaching periods are penalised (with a ⚠ warning on the approval card) rather than chosen. → LangGraph `interrupt()` → HOD approval card → resume with `Command(resume=...)` → notifications to partner + returning teacher. Dated overlay via `/api/timetable/effective/{section}?date=` + `/exchanges` page (table view). Spec: `docs/06-EXCHANGE-PLAN.md`. Both paths verified live.
- **F3 Event & Venue Booking** — `/bookings` form or free-text chat → Booking Agent checks conflicts against **other bookings AND the class timetable** (a hall holding a lecture is not free), matches capacity, and re-plans onto the **tightest-fitting** free venue when the request fails, quoting the blocking class/booking. Then a **multi-stage approval chain implemented as sequential `interrupt()`s on one durable thread**: students go faculty advisor → admin (the advisor is *derived* from the timetable, not configured), staff go straight to admin. `/bookings` also has a live pre-submit availability probe and a 4-week campus calendar. Nag sweep reminds the current stage's approver after 24 h. Spec: `docs/09-PHASE3-BOOKING-PLAN.md`.
- **LangGraph checkpointer** (durable threads per `thread_id`); **APScheduler sweeps** (substitution safety net, booking nag)
- **Docs:** architecture in `docs/02-ARCHITECTURE.md`, demo script in `docs/05-DEMO-SCRIPT.md`
- **Use `graphify query "<question>"` to navigate code** (graph updated 2026-07-14 — predates Phase 3; re-run `python -m graphify update .`)

## Quick Start

**Backend** (Python 3.11+):
```bash
cd services/backend
pip install -r requirements.txt
python main.py  # starts at http://localhost:8000; auto-seeds DB
```

**Frontend** (Node.js 18+):
```bash
cd apps/web
npm install
npm run dev  # starts at http://localhost:3000
```

**Demo logins** (seeded on startup):
- `admin@campus.edu` / `admin123`
- `anita.rao@campus.edu` / `faculty123` (faculty)
- `student@campus.edu` / `student123`

**All endpoints:** `http://localhost:8000/openapi.json` (Swagger UI at `/docs`)

## Key File Structure

**Backend** (`services/backend/app/`):
- `api/` — router, agent, auth, setup, timetable, leaves (Phase 2), approvals, bookings (Phase 3), notifications
- `agents/` — graph, supervisor, state, specialists/ (timetable, substitution, booking, general, stubs)
- `tools/` — timetable, exchange (Phase 2.1 period-exchange, live), booking (Phase 3), substitution (Phase 2.0 legacy)
- `solver/` — timetable_model (OR-Tools CP-SAT, 8 hard constraints)
- `db/` — models (16 tables), seed, session (`_ensure_columns` = idempotent SQLite ADD COLUMN shim; `create_all` only creates missing *tables*)
- `core/` — llm (swappable), config, security

**Frontend** (`apps/web/src/app/`):
- `login/` — JWT auth UI
- `setup/` — data entry (CRUD, CSV)
- `timetable/` — grid view (MON-FRI × P1-P7)
- `leaves/` — faculty apply + admin approve (Phase 2)
- `approvals/` — HOD plan cards (Phase 2)
- `exchanges/` — period-exchange board + dated day grid (Phase 2.1)
- `bookings/` — venue request form with live availability probe + campus calendar (Phase 3)
- `inbox/` — notifications (Phase 2)

## Essential Config

**Backend `.env`** (read from `services/backend/`; copy `.env.example`):
```bash
LLM_PROVIDER=google_genai              # google_genai | anthropic | openai | ollama
LLM_MODEL=gemini-flash-latest          # see docs/03-TECH-STACK.md for current stable models
GOOGLE_API_KEY=...                     # get free key at aistudio.google.com/apikey
# OR: ANTHROPIC_API_KEY=...            # OR: OPENAI_API_KEY=...

DEBUG=True
HOST=127.0.0.1
PORT=8000
JWT_SECRET=change-me-in-production

BOOKING_NAG_HOURS=24                   # remind a stalled booking approver after N hours
BOOKING_SWEEP_MINUTES=30               # how often the nag sweep runs
```

**Note:** If LLM key is missing/invalid, system falls back to deterministic keyword routing — demo never fails. Full semantic routing requires a valid LLM key.

**Data model:** 16 tables in `app/db/models.py`. See code for schema; tools query DB, agents never do raw SQL.

**LangGraph workflow:** Supervisor routes → specialist node (timetable|substitution|facility|general) → tool calls → END. State persisted per `thread_id` for durable resumption. `interrupt()` pauses for human approval (Phase 2). A node may interrupt **more than once** — the booking approval chain does — so the node re-executes from the top on every resume and **everything before an interrupt must be idempotent** (`PeriodExchange.plan_id`, `Booking.request_key`, `Approval` by `(kind, ref_id)`).

**Frontend:** React/Next.js dashboard with tabs (overview, chat, setup, timetable, leaves, approvals, exchanges, bookings, inbox). Real-time workflow trace sidebar. Glassmorphic UI (Tailwind + custom glass-*classes).

## Testing

Quick curl test:
```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@campus.edu","password":"admin123"}'
```

Full flow: Start backend + frontend, login at `http://localhost:3000`, navigate Setup → Timetable → Leaves/Approvals/Exchanges/Bookings/Inbox. Demo script in `docs/05-DEMO-SCRIPT.md`.

## Patterns

**Adding a specialist node:**
1. Define in `app/agents/specialists/node_name.py`
2. Register in `app/agents/graph.py`: `workflow.add_node("name", node_func); workflow.add_edge("name", END)`
3. Supervisor auto-routes on intent; no keyword matching to update
4. Use typed tools in `app/tools/` — agents call tools, tools modify DB

**Adding an API router:** Create `app/api/domain.py`, include in `app/api/router.py`, use `Depends(get_current_user)` and `Depends(get_db)`.

**Next phases:** See `docs/04-ROADMAP.md`. Remaining in Phase 3: **F4 Knowledge RAG** (`rag/ingest.py` → Chroma, `search_documents` tool, Knowledge Agent with citations, admin upload UI) + WebSocket notifications.

## Navigation

**Graphify knowledge graph** at `graphify-out/` (Phase 0+1+2, ~550 nodes). **Always use it first:**
```bash
graphify query "how does X work"                       # find all uses of a concept
graphify explain "feature name"                        # understand a concept
graphify path "node_A" "node_B"                        # trace a relationship
```
Much faster than grep; links to source files + line numbers. After code changes: `python -m graphify update .`

**Docs:** `docs/README.md` (entry), `docs/02-ARCHITECTURE.md` (design), `docs/04-ROADMAP.md` (status).

**External:** [LangGraph](https://langchain-ai.github.io/langgraph/), [FastAPI](https://fastapi.tiangelo.io/), [SQLAlchemy](https://docs.sqlalchemy.org/), [OR-Tools](https://developers.google.com/optimization)
