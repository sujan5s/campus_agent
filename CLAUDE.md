# CLAUDE.md

**START HERE:** Read `docs/README.md`, then `docs/04-ROADMAP.md` before starting work.

**Status (2026-07-14):** Phases 0, 1, 2 complete. Smart Campus Agent System — AI-driven campus ops platform.
- **Supervisor-router** LLM with keyword fallback; swappable providers (Gemini/Claude/OpenAI/Ollama) via `.env` only
- **SQLAlchemy models** (15 tables) + idempotent seeding; JWT auth + role-based access
- **OR-Tools CP-SAT timetable solver** — 8 hard constraints, fairness objective, clash-free verified
- **F1 Timetable Agent** + admin `/setup` (CRUD + CSV) + `/timetable` grid UI
- **F2 Leave & Substitution (flagship)** — proactive trigger → Substitution Agent ranks candidates (subject>dept>free, fairness-weighted) → LangGraph `interrupt()` → HOD approval card → resume with `Command(resume=...)` → notifications. Both paths verified live.
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
- `api/` — router, agent, auth, setup, timetable, leaves (Phase 2), approvals, notifications
- `agents/` — graph, supervisor, state, specialists/ (timetable, substitution, general, stubs)
- `tools/` — timetable, substitution (Phase 2)
- `solver/` — timetable_model (OR-Tools CP-SAT, 8 hard constraints)
- `db/` — models (15 tables), seed, session
- `core/` — llm (swappable), config, security

**Frontend** (`apps/web/src/app/`):
- `login/` — JWT auth UI
- `setup/` — data entry (CRUD, CSV)
- `timetable/` — grid view (MON-FRI × P1-P7)
- `leaves/` — faculty apply + admin approve (Phase 2)
- `approvals/` — HOD plan cards (Phase 2)
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
```

**Note:** If LLM key is missing/invalid, system falls back to deterministic keyword routing — demo never fails. Full semantic routing requires a valid LLM key.

**Data model:** 15 tables in `app/db/models.py`. See code for schema; tools query DB, agents never do raw SQL.

**LangGraph workflow:** Supervisor routes → specialist node (timetable|substitution|general) → tool calls → END. State persisted per `thread_id` for durable resumption. `interrupt()` pauses for human approval (Phase 2).

**Frontend:** React/Next.js dashboard with tabs (overview, chat, setup, timetable, leaves, approvals, inbox). Real-time workflow trace sidebar. Glassmorphic UI (Tailwind + custom glass-*classes).

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
