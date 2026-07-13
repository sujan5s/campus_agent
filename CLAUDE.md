# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **⚠️ START HERE — Design docs & project state:** This is a final-year major project being
> built incrementally. The design target (features, architecture, tech stack) lives in
> **`docs/`** (read `docs/README.md` first) and the current implementation status lives in
> **`docs/04-ROADMAP.md`** — read the roadmap before starting any work, and check items off
> as you complete them. This CLAUDE.md describes the code *as it exists today*.
> 
> **Phase 0 (2026-07-13) is complete.** The backend is now a real platform with:
> - Provider-agnostic LLM layer in `app/core/llm.py` (swap Gemini/Claude/OpenAI/Ollama via .env only)
> - Full SQLAlchemy data model + idempotent seeding
> - LLM supervisor with structured-output routing (keyword fallback if no API key)
> - SqliteSaver checkpointers for durable conversation threads
> - JWT auth + role-based access control
> - Split API routers per domain (agent, auth, extensible for phases 1+)
> 
> **Before starting work on any phase:**
> 1. Check `docs/04-ROADMAP.md` for what's done ✅ vs what's next.
> 2. Read `docs/02-ARCHITECTURE.md` for the design you're implementing.
> 3. Use `graphify query "<question>"` to orient on the code (knowledge graph updated 2026-07-13).

## Project Overview

**Smart Campus Agent System** (smart-campus-ops) is an AI-driven operations management platform for educational campuses. It features:

- **Frontend**: Next.js React dashboard (TypeScript, Tailwind CSS) with real-time agent orchestration visualization
- **Backend**: Python FastAPI with LangGraph multi-agent orchestration for intelligent task routing
- **Core Problem**: Replaces rigid, reactive campus management systems with intelligent, real-time decision-making

### Architecture (Phase 0+)

**Entry points:**
- Chat API (`POST /api/agent/chat`) — user message → supervisor
- Proactive triggers (Phase 2+) — system events (leave approved, scheduled cron) → supervisor
- Thread-based — conversations are keyed by `thread_id`, persisted to `checkpoints.db`

**Flow:**
1. User/system sends `{"message": "...", "thread_id": "uuid"}` to `POST /api/agent/chat`
2. **Supervisor node** (LLM with structured output) classifies intent → `{route: "facility"|"scheduler"|"general", task_spec: {...}}`
   - Falls back to keyword heuristics if LLM provider is unconfigured or unreachable (demo never fails)
3. **Conditional routing** → specialist node (scheduling, booking, or general)
4. **Specialist nodes** access real DB (rooms, teachers, sections, subjects) and call typed **tools** (coming Phase 1+)
5. **Response** includes agent name, final text, execution steps (trace), and extracted params; returned with the same `thread_id`

**Key design rules (docs/03-TECH-STACK.md):**
- No hardcoded LLM provider — all calls via `app/core/llm.py`, provider set by `.env` (LLM_PROVIDER, LLM_MODEL, GOOGLE_API_KEY | ANTHROPIC_API_KEY | OPENAI_API_KEY)
- All agent actions are typed tools (Phase 1+) — the LLM orchestrates, tools enforce rules and permissions
- State: `AgentState` (messages, steps, params, final_response, source, task_spec, current_action)

## Development Setup

### Prerequisites
- **Node.js 18+** for frontend
- **Python 3.11+** for backend

### Backend (services/backend)

**Already set up** (Phase 0 complete). To run:

```bash
cd services/backend
# venv already created; activate it:
# Windows (PowerShell): .\venv\Scripts\Activate.ps1
# Windows (CMD): venv\Scripts\activate.bat
# Unix/macOS: source venv/bin/activate

# (re)install deps if you change requirements.txt:
pip install -r requirements.txt

# Run development server (includes auto-seeding if DB is empty):
python main.py
```

Server starts at `http://localhost:8000`. On first run, `app/db/seed.py` auto-runs and seeds demo data.

**Endpoints:**
- `GET /api/health` — server status
- `POST /api/agent/chat` — main agent endpoint:
  ```json
  {
    "message": "Book Seminar Hall B for Friday 2pm",
    "thread_id": "optional-uuid-to-resume-conversation"
  }
  ```
  Returns `ChatResponse` with `agent`, `response`, `steps`, `params`, `thread_id`
- `POST /api/auth/login` — JWT token:
  ```json
  {
    "email": "admin@campus.edu",
    "password": "admin123"
  }
  ```
  Returns `{"access_token": "...", "token_type": "bearer", "user": {...}}`
- `GET /api/auth/me` — current user (requires Bearer token)

### Frontend (apps/web)

```bash
cd apps/web

# Install dependencies
npm install

# Run development server
npm run dev
```

Dashboard starts at `http://localhost:3000`

## Common Commands

### Backend

| Command | Purpose |
|---------|---------|
| `python main.py` | Run FastAPI dev server (watches for changes if DEBUG=True in .env) |
| `pip install -r requirements.txt` | Install Python dependencies |
| `pip freeze > requirements.txt` | Update dependencies list |

### Frontend

| Command | Purpose |
|---------|---------|
| `npm run dev` | Start Next.js dev server with hot reload |
| `npm run build` | Production build |
| `npm start` | Run production build locally |
| `npm run lint` | Run ESLint on code |

## Key File Structure

### Backend (`services/backend/app`) — Phase 0

```
app/
├── api/
│   ├── router.py           # API aggregator (includes agent, auth; extensible)
│   ├── agent.py            # POST /api/agent/chat (supervisor → specialist)
│   └── auth.py             # POST /api/auth/login, GET /api/auth/me
├── agents/
│   ├── graph.py            # LangGraph StateGraph + SqliteSaver checkpointer (durable threads)
│   ├── supervisor.py       # Supervisor node — LLM structured routing (or keyword fallback)
│   ├── state.py            # AgentState TypedDict
│   └── specialists/        # Each domain = one .py file (scheduling, booking, general for now)
├── db/
│   ├── session.py          # SQLAlchemy engine, SessionLocal, get_db() dependency
│   ├── models.py           # 15 tables (users, teachers, subjects, sections, rooms, timeslots, timetable_entries, leaves, substitutions, events, bookings, approvals, documents, notifications + stretch tables as comments)
│   └── seed.py             # Idempotent seeding — runs on startup (CSE dept, 2 sections, 6 teachers, 8 subjects, 8 rooms, demo logins)
└── core/
    ├── config.py           # Settings: LLM_PROVIDER, LLM_MODEL, DATABASE_URL, JWT_SECRET, all from .env
    ├── llm.py              # ★ Provider-agnostic LLM factory — only place that imports LLM SDKs
    └── security.py         # JWT + pbkdf2 password hashing + require_role() dependency
```

**Key Dependencies**: FastAPI, uvicorn, LangGraph 1.2.9+, SQLAlchemy 2, ortools, APScheduler, PyJWT, passlib

**Demo logins** (seeded on startup):
- `admin@campus.edu` / `admin123` (role: admin)
- `anita.rao@campus.edu` / `faculty123` (role: faculty)
- `student@campus.edu` / `student123` (role: student)

### Frontend (`apps/web`)

```
apps/web/
├── src/
│   └── app/
│       ├── layout.tsx      # Root layout wrapper
│       └── page.tsx        # Main dashboard component (all 4 tabs: overview, chat, scheduler, facilities)
├── tailwind.config.ts      # Tailwind configuration
├── package.json            # Node dependencies (react, next, lucide-react, tailwind)
└── tsconfig.json           # TypeScript config
```

**Key Dependencies**: React 18, Next.js 14, Tailwind CSS, lucide-react (icons)

## Important Implementation Details

### Data Model

**Core tables** (from `app/db/models.py`):
- `users` — email, role (admin|faculty|student), password_hash
- `teachers` — dept, max_hours_per_day, subjects (M-M)
- `subjects` — code, name, dept, semester, periods_per_week, needs_lab
- `sections` — name, dept, semester, strength
- `rooms` — name, type (classroom|lab|auditorium|seminar|ground), capacity
- `timeslots` — day (MON-FRI), period_no, start, end
- `timetable_entries` — section, subject, teacher, room, timeslot, status, version (versioned timetables)
- `leaves` — teacher, from_date, to_date, status (pending|approved|rejected)
- `substitutions` — timetable_entry, date, original_teacher, substitute_teacher, plan_id (grouped changes)
- `approvals` — kind, ref_id, approver, status, langgraph_thread_id (resumes paused graphs for human-in-the-loop)
- `bookings`, `events`, `documents`, `notifications` (Phase 2+)

Phase 1+ tools will query these directly; agents never do raw SQL.

### Environment Configuration

Backend reads from `.env` file in `services/backend/`. Copy `.env.example` to `.env` and fill in:

```bash
# LLM provider (see docs/03-TECH-STACK.md — swapping providers is ONLY changing these 3 lines):
LLM_PROVIDER=google_genai            # google_genai | anthropic | openai | ollama
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=                      # free tier at aistudio.google.com/apikey
# OR: ANTHROPIC_API_KEY=             # free trial at claude.ai
# OR: OPENAI_API_KEY=                # pay-as-you-go
# For ollama: no key needed, run locally: ollama run llama3.1

# Server
DEBUG=True
HOST=127.0.0.1
PORT=8000

# Auth
JWT_SECRET=change-me-in-production

# Database (defaults to SQLite; change for PostgreSQL in Phase 2+)
# DATABASE_URL=sqlite:///./campus.db
```

**⚠️ Important:** If LLM_PROVIDER is not configured or the key is invalid, the system falls back to **keyword routing** (the old heuristic) — no hard failures. This means the demo works everywhere, but structured-output routing is disabled. To enable it, get a free LLM key (see above) and set it.

### LangGraph Workflow (Phase 0)

The state flows through nodes as a `StateGraph` with checkpointer:

```
Supervisor (LLM structured routing or keyword fallback)
  ↓
Conditional edge based on current_action
  ├→ Scheduler node (timetable, conflicts, leaves)
  ├→ Facility node (room bookings, availability)
  └→ General node (fallback, RAG Phase 3+)
  ↓
END
```

**State updates:** Each node appends to the `steps` list (via Annotated[..., operator.add], a reducer that concatenates). This makes the execution trace visible in the frontend and enables durable checkpointing.

**Thread ID & resumption (Phase 2+):** When a specialist node needs human approval (e.g., "substitution plan proposed"), it calls `interrupt()` and stores the thread ID in the `approvals` table with a `langgraph_thread_id`. When the human clicks Approve/Reject, the workflow resumes from that exact point with full context.

### Frontend Architecture

The dashboard is a **single-page React component** (`page.tsx`) with:
- **Tabs**: overview, chat, scheduler, facilities (controlled by `activeTab` state)
- **Message State**: `messages` array with sender, agent name, text, timestamp, workflow steps
- **Backend Integration**: Polls `/api/health` every 10 seconds; falls back to mock simulation if unreachable
- **Styling**: Tailwind + custom glass-panel/glass-card classes for glassmorphic UI

The chat features a real-time workflow trace sidebar showing LangGraph node execution steps.

## Testing & Verification

### Quick backend test (no frontend)

```bash
cd services/backend
python main.py &  # start in background

# Test agent chat (facility routing)
curl -X POST http://127.0.0.1:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Book Seminar Hall B for Friday 2pm"}'

# Test login
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@campus.edu","password":"admin123"}'

# Test protected endpoint (use the Bearer token from login)
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/auth/me
```

### Full manual testing workflow

1. **Terminal 1** — Start backend:
   ```bash
   cd services/backend
   python main.py
   ```
   DB seeds on startup. See `/api/health` return `{"status":"ok",...}`

2. **Terminal 2** — Start frontend:
   ```bash
   cd apps/web
   npm run dev
   ```

3. **Browser** — Visit `http://localhost:3000`
   - Click "Login" (if implemented in Phase 0.5), use demo credentials above
   - Chat tab: type "Book Seminar Hall B for Friday 2pm" → Facility Agent routes + matches DB room
   - Scheduler tab: type "Check conflicts for CSE-7A" → Scheduler Agent loads real section

4. **Expected behavior:**
   - Agent trace sidebar shows supervisor + specialist node steps
   - DB rooms/teachers/subjects loaded live
   - JWT auth protects sensitive endpoints (coming Phase 2+)

## Common Patterns (Phase 0+)

### Adding a new feature (Phase 1 example: F1 Timetable generation)

1. **Define specialist node** in `app/agents/specialists/timetable.py`:
   ```python
   def timetable_node(state: AgentState) -> dict:
       spec = state.get("task_spec", {})  # extracted by supervisor
       # Call tools (Phase 1+): solve_timetable(spec), get_timetable(), apply_timetable_diff()
       # Tools live in app/tools/ and are called by the LLM inside this node
       steps.append("TimetableAgent: solver ran; timetable generated.")
       return {"steps": steps, "final_response": response, "params": {...}}
   ```
2. **Register in graph** (`app/agents/graph.py`):
   ```python
   workflow.add_node("timetable", timetable_node)
   workflow.add_conditional_edges("supervisor", route_to, {"timetable": "timetable", ...})
   workflow.add_edge("timetable", END)
   ```
3. **Supervisor auto-routes** — it sees "generate timetable" in the message and returns `route: "timetable"`. No keyword matching to update.

### Adding a domain router (Phase 2+ example: booking approvals)

1. Create `app/api/bookings.py` with routes for creating, listing, approving bookings
2. Include in `app/api/router.py`: `router.include_router(bookings.router, prefix="/bookings")`
3. Routes use `Depends(get_current_user)` for auth and `Depends(get_db)` for DB access
4. Agents invoke these via tools (Phase 1+), not directly

### Working with the database

- Use `SessionLocal()` to get a session (or `Depends(get_db)` in FastAPI routes)
- Query: `db.query(Teacher).filter(Teacher.dept == "CSE").all()`
- Create: `t = Teacher(...); db.add(t); db.commit()`
- **Do NOT modify shared state in agent code** — agents call tools; tools update the DB

## What's next (Phases 1–4)

See `docs/04-ROADMAP.md` for detailed checkpoints. The main roadmap:

- **Phase 1** (2 weeks): F1 Timetable generation — OR-Tools CP-SAT solver + `solve_timetable` tool + Timetable Agent + demo UI
- **Phase 2** (2 weeks): F2 Leave & Substitution (the flagship) — proactive triggers + human-in-the-loop approval chain via `interrupt()` + Substitution Agent
- **Phase 3** (2 weeks): F3 Event Booking + F4 Knowledge RAG (chromadb) + Notification Agent v1
- **Phase 4** (remaining): Email notifications + stretch features (Analytics Agent, Attendance Sentinel, Exam Scheduler, etc.)

**How to start a phase:**
1. Read the phase docs in `docs/01-FEATURES.md` (feature description) and `docs/02-ARCHITECTURE.md` (technical design)
2. Create `app/agents/specialists/<feature>.py` if adding a new specialist node
3. Create `app/tools/<feature>.py` for typed tools the agent will call
4. Add test data to `app/db/seed.py` if needed
5. Add routes in a new `app/api/<feature>.py` if needed
6. Check off the roadmap when done

## Deployment Notes

- **Backend**: Uses uvicorn; set `DEBUG=False` and adjust `HOST` for production
- **Frontend**: Run `npm run build` then `npm start`
- **CORS**: Backend currently allows all origins (`allow_origins=["*"]`); **narrow this before demo/deployment**
- **Database**: SQLite works for this semester; PostgreSQL (Supabase/Neon free tier) for scaling
- **Checkpoints**: Default to SQLite file; for multi-instance deployment switch to PostgreSQL checkpointer in Phase 2+
- **Environment**: Backend reads `.env` from `services/backend/` directory; frontend `.env.local` (Phase 0.5+)

## Phase 0 — What you have now (2026-07-13)

**A real, running platform:** Every component is production-ready skeleton code, not mockups.

| Component | Status | Notes |
|---|---|---|
| Backend → `/api/health` | ✅ Live | Uvicorn server, FastAPI app, DB auto-seeds on startup |
| `POST /api/agent/chat` | ✅ Live | Supervisor routes to 3 specialists; all return real DB data. Keyword fallback if LLM unconfigured. |
| Database | ✅ Live | SQLAlchemy + SQLite. 15 tables. Seeded with CSE dept (2 sections, 6 teachers, 8 subjects, 8 rooms). |
| Auth | ✅ Live | JWT login + bearer tokens. `require_role()` dependency for admin-only routes. |
| LangGraph checkpointer | ✅ Live | Durable conversation threads in `checkpoints.db`. Thread ID returned per chat. |
| LLM factory | ✅ Live | `app/core/llm.py` — swap provider via `.env` only. Graceful fallback if key invalid. |
| Frontend login page | ❌ Pending | Roadmap item Phase 0.5 |
| Phase 1 tools | ❌ Pending | OR-Tools, timetable solver, substitution planner — Phase 1 |

**Verified working:** facility/scheduler/general routing, DB room matching (fixed token bug), JWT login/rejection, conversation persistence.

## Useful Links

- **Project** — Start with `docs/README.md` (read this on every new session)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangelo.io/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/20/)
- [Google OR-Tools](https://developers.google.com/optimization)
- [Google AI Studio (free Gemini key)](https://aistudio.google.com/apikey)
- [Claude API (Anthropic)](https://console.anthropic.com/)
- [OpenAI API](https://platform.openai.com/)

## Code navigation (graphify knowledge graph)

This project has a knowledge graph at `graphify-out/` with 288 nodes, 312 edges, 36 communities (Phase 0).

**Before reading raw source files or grepping, use graphify to orient yourself:**

```bash
# Find all uses of a concept
graphify query "how are database models used in the supervisor"

# Trace a relationship
graphify path "supervisor_node" "agent_state"

# Understand a concept
graphify explain "provider-agnostic LLM layer"
```

Returns a scoped subgraph — much faster than full grep. The output includes source files and line numbers.

**Rules:**
- For "How does X work?" or "What calls Y?" — **always start with `graphify query`** to scope the answer
- If graphify is unavailable, fall back to:
  - `graphify-out/GRAPH_REPORT.md` for architecture overview
  - `grep -r "symbol" app/` for specific names
- After you modify code, keep the graph current:
  ```bash
  cd /path/to/repo
  python -m graphify update .
  ```
  (AST-only, no LLM cost — takes ~10 seconds)
