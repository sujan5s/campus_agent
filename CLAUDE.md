# CLAUDE.md

**START HERE:** Read `docs/README.md`, then `docs/04-ROADMAP.md` before starting work.

**Status (2026-08-28):** Phases 0, 1, 2, 2.2, 2.3, 2.4, 2.5, 2.6 complete. Smart Campus Agent System — AI-driven campus ops platform.
- **Supervisor-router** LLM with keyword fallback; swappable providers (Gemini/Claude/OpenAI/Ollama) via `.env` only. **System-sourced triggers (leave approval, sweep) skip the LLM** and route deterministically.
- **SQLAlchemy models** (20 tables) + idempotent seeding; JWT auth + role-based access
- **OR-Tools CP-SAT timetable solver** — 12 hard constraint groups + weighted soft objective (fairness, preferred periods, mid-day gaps), clash-free verified. **Regeneration preserves the published timetable by default** (previous placement fed in as hints + a move penalty): adding a subject moves 0 existing lessons and solves in ~0.6s, vs ~8s and a rewritten week for a cold `?fresh=true` re-plan. Every rule is scoped **section > semester > global**, so one solve produces a differently-shaped week per semester
- **Constraint registry (Phase 2.4)** — the `constraints` table is the single source of truth; `POST /api/timetable/generate` takes **no body** and compiles it. `app/tools/constraints.py` owns the `CATALOG` of 14 kinds (allowed scopes + validator against real DB entities + English renderer), CRUD, and `compile_options()`
- **Timetable Assistant (Phase 2.5)** — `POST /api/assistant/interpret` turns one sentence into a whole ordered plan and **creates whatever is missing**: teachers, subjects, rooms, classes, teacher-subject maps, pins, elective bands, rules, and a regeneration. 23 typed ops in `app/tools/ops.py`, each with validate/describe/apply. Forward references work (a rule may scope to a class the same plan creates — pending entities are stubbed into the validator's `Ctx` with negative ids, then re-validated for real at apply time); assigning an unqualified teacher just adds the qualification; emails are derived. Still typed, validated, previewed in English, and applied as one transaction. **Bulk forms** (`add_subjects`/`add_teachers`/… with `{defaults, items}`) keep big requests fast — output tokens are what the admin waits on. Spec: `docs/10-PHASE2.5-PLAN.md`
- **Teacher assignments** — `teaching_assignments` pins `(section, subject) → teacher` (hard); unpinned pairs are still solver-chosen. One teacher may be pinned across semesters; overload surfaces as a precise infeasibility reason
- **Open electives (sem 6/7)** — `elective_groups`/`elective_offerings`: a band reserves the same periods for **every class of the semester** while its baskets run in parallel in reserved rooms
- **F1 Timetable Agent** + admin `/setup` (CRUD + CSV) + `/timetable` grid UI (read-only "Rules in force" summary linking to `/constraints`; elective periods shown as a violet cell listing every basket) + a **Download PDF** button (client-side jsPDF + jspdf-autotable, any role). Rules live on **`/constraints`** (Rules · Teacher assignments · Open electives). Specs: `docs/07-PHASE2.2-PLAN.md`, `docs/08-PHASE2.3-PLAN.md`, `docs/09-PHASE2.4-PLAN.md`.
- **F2 Leave & Substitution (flagship)** — proactive trigger → Substitution Agent builds a **period-exchange** plan (partner of same section swaps their lesson into the leave slot; absent teacher recovers it later in the partner's slot — subject hours preserved, original timetable untouched). The planner now **avoids hectic back-to-back scheduling**: candidates that create same-subject adjacency for students or 3+ consecutive teaching periods are penalised (with a ⚠ warning on the approval card) rather than chosen. → LangGraph `interrupt()` → HOD approval card → resume with `Command(resume=...)` → notifications to partner + returning teacher. Dated overlay via `/api/timetable/effective/{section}?date=` + `/exchanges` page (table view). Spec: `docs/06-EXCHANGE-PLAN.md`. Both paths verified live.
- **LangGraph checkpointer** (durable threads per `thread_id`); **APScheduler safety sweep**
- **Docs:** architecture in `docs/02-ARCHITECTURE.md`, demo script in `docs/05-DEMO-SCRIPT.md`
- **Use `graphify query "<question>"` to navigate code** (graph updated 2026-07-14)

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
- `api/` — router, agent, auth, setup, timetable, constraints (2.4 rulebook), assistant (2.5 NL → plan), leaves, approvals, notifications
- `agents/` — graph, supervisor, state, specialists/ (timetable, substitution, general, stubs)
- `tools/` — timetable, constraints (2.4 registry: CATALOG + compile_options), ops (2.5 op registry: 23 typed operations, plan/run), exchange (2.1 period-exchange, live), substitution (2.0 legacy)
- `solver/` — timetable_model (OR-Tools CP-SAT, H1–H12 + soft objective, scope resolution)
- `db/` — models (20 tables), seed (+ additive `seed_phase24()`), session (+ `ensure_schema()` for additive column migrations)
- `core/` — llm (swappable, + `text_of()` for content-block replies), config, security

**Frontend** (`apps/web/src/app/`):
- `login/` — JWT auth UI
- `setup/` — data entry (CRUD, CSV)
- `timetable/` — grid view (MON-FRI × P1-P7)
- `constraints/` — Ask-in-English assistant + rules by scope, teacher assignments, open electives (2.4/2.5)
- `leaves/` — faculty apply + admin approve (Phase 2)
- `approvals/` — HOD plan cards (Phase 2)
- `exchanges/` — period-exchange board + dated day grid (Phase 2.1)
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
```

**Note:** If LLM key is missing/invalid, system falls back to deterministic keyword routing — demo never fails. Full semantic routing requires a valid LLM key.

**Data model:** 20 tables in `app/db/models.py`. See code for schema; tools query DB, agents never do raw SQL.

**LangGraph workflow:** Supervisor routes → specialist node (timetable|substitution|general) → tool calls → END. State persisted per `thread_id` for durable resumption. `interrupt()` pauses for human approval (Phase 2).

**Frontend:** React/Next.js dashboard with tabs (overview, chat, setup, timetable, constraints, leaves, approvals, inbox). Real-time workflow trace sidebar. Glassmorphic UI (Tailwind + custom glass-*classes).

## Testing

Quick curl test:
```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@campus.edu","password":"admin123"}'
```

Full flow: Start backend + frontend, login at `http://localhost:3000`, navigate Setup → Timetable → Leaves/Approvals/Inbox. Demo script in `docs/05-DEMO-SCRIPT.md`.

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

**Adding an assistant operation:** register an `OpSpec` in `app/tools/ops.py` `OPS` (validate against
`PlanCtx`, describe in English, apply), and list it in `_OP_REFERENCE` in `app/api/assistant.py`. If it
creates an entity later ops may reference, give it a `note` callback so forward references keep working.

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
