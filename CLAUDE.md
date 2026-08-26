# CLAUDE.md

**START HERE:** Read `docs/README.md`, then `docs/04-ROADMAP.md` before starting work.

**Status (2026-08-25):** Phases 0, 1, 2, 2.2, 2.3, 2.4 complete. Smart Campus Agent System — AI-driven campus ops platform.
- **Supervisor-router** LLM with keyword fallback; swappable providers (Gemini/Claude/OpenAI/Ollama) via `.env` only. **System-sourced triggers (leave approval, sweep) skip the LLM** and route deterministically.
- **SQLAlchemy models** (20 tables) + idempotent seeding; JWT auth + role-based access
- **OR-Tools CP-SAT timetable solver** — 12 hard constraint groups + weighted soft objective (fairness, preferred periods, mid-day gaps), clash-free verified. Every rule is scoped **section > semester > global**, so one solve produces a differently-shaped week per semester
- **Constraint registry (Phase 2.4)** — the `constraints` table is the single source of truth; `POST /api/timetable/generate` takes **no body** and compiles it. `app/tools/constraints.py` owns the `CATALOG` of 14 kinds (allowed scopes + validator against real DB entities + English renderer), CRUD, and `compile_options()`. An admin can add a rule from a form **or from a sentence** — `POST /api/constraints/interpret` gives the LLM the catalog *and the current rules with their ids*, so it can edit or delete an existing rule, and every op is validated and previewed before `/apply` commits it
- **Teacher assignments** — `teaching_assignments` pins `(section, subject) → teacher` (hard); unpinned pairs are still solver-chosen. One teacher may be pinned across semesters; overload surfaces as a precise infeasibility reason
- **Open electives (sem 6/7)** — `elective_groups`/`elective_offerings`: a band reserves the same periods for **every class of the semester** while its baskets run in parallel in reserved rooms
- **F1 Timetable Agent** + admin `/setup` (CRUD + CSV) + `/timetable` grid UI (read-only "Rules in force" summary linking to `/constraints`; elective periods shown as a violet cell listing every basket) + a **Download PDF** button (client-side jsPDF + jspdf-autotable, any role). Rules live on **`/constraints`** (Rules · Teacher assignments · Open electives). Specs: `docs/07-PHASE2.2-PLAN.md`, `docs/08-PHASE2.3-PLAN.md`, `docs/09-PHASE2.4-PLAN.md`.
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
- `api/` — router, agent, auth, setup, timetable, constraints (Phase 2.4), leaves, approvals, notifications
- `agents/` — graph, supervisor, state, specialists/ (timetable, substitution, general, stubs)
- `tools/` — timetable, constraints (Phase 2.4 registry: CATALOG + compile_options), exchange (Phase 2.1 period-exchange, live), substitution (Phase 2.0 legacy)
- `solver/` — timetable_model (OR-Tools CP-SAT, H1–H12 + soft objective, scope resolution)
- `db/` — models (20 tables), seed (+ additive `seed_phase24()`), session (+ `ensure_schema()` for additive column migrations)
- `core/` — llm (swappable, + `text_of()` for content-block replies), config, security

**Frontend** (`apps/web/src/app/`):
- `login/` — JWT auth UI
- `setup/` — data entry (CRUD, CSV)
- `timetable/` — grid view (MON-FRI × P1-P7)
- `constraints/` — the rulebook: rules by scope + Ask-AI, teacher assignments, open electives (Phase 2.4)
- `leaves/` — faculty apply + admin approve (Phase 2)
- `approvals/` — HOD plan cards (Phase 2)
- `exchanges/` — period-exchange board + dated day grid (Phase 2.1)
- `bookings/` — venue request form with live availability probe + campus calendar (Phase 3)
- `inbox/` — notifications (Phase 2)

## Essential Config

**Backend `.env`** (read from `services/backend/`; copy `.env.example`):
```bash
LLM_PROVIDER=google_genai              # google_genai | anthropic | openai | ollama
LLM_MODEL=gemini-3.6-flash             # NOT gemini-flash-latest — it hangs on generateContent
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

**Data model:** 20 tables in `app/db/models.py`. See code for schema; tools query DB, agents never do raw SQL.

**LangGraph workflow:** Supervisor routes → specialist node (timetable|substitution|facility|general) → tool calls → END. State persisted per `thread_id` for durable resumption. `interrupt()` pauses for human approval (Phase 2). A node may interrupt **more than once** — the booking approval chain does — so the node re-executes from the top on every resume and **everything before an interrupt must be idempotent** (`PeriodExchange.plan_id`, `Booking.request_key`, `Approval` by `(kind, ref_id)`).

**Frontend:** React/Next.js dashboard with tabs (overview, chat, setup, timetable, constraints, leaves, approvals, inbox). Real-time workflow trace sidebar. Glassmorphic UI (Tailwind + custom glass-*classes).

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

**Adding a constraint kind:** register a `Kind` in `app/tools/constraints.py` `CATALOG` (scopes,
form fields, validator, renderer), handle it in `compile_options()`, and enforce it in
`app/solver/timetable_model.py` under its own assumption literal. The UI form and the LLM prompt are
generated from the catalog — neither needs touching.

**Next phases:** See `docs/04-ROADMAP.md`. Phase 3 is F3 Event Booking + F4 Knowledge RAG + WebSocket notifications.

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
