# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **⚠️ START HERE — Design docs & project state:** This is a final-year major project being
> built incrementally. The design target (features, architecture, tech stack) lives in
> **`docs/`** (read `docs/README.md` first) and the current implementation status lives in
> **`docs/04-ROADMAP.md`** — read the roadmap before starting any work, and check items off
> as you complete them. This CLAUDE.md describes the code *as it exists today*; where it
> conflicts with `docs/`, the docs describe where we are heading (e.g. the keyword router
> below is being replaced by an LLM supervisor per `docs/02-ARCHITECTURE.md`).

## Project Overview

**Smart Campus Agent System** (smart-campus-ops) is an AI-driven operations management platform for educational campuses. It features:

- **Frontend**: Next.js React dashboard (TypeScript, Tailwind CSS) with real-time agent orchestration visualization
- **Backend**: Python FastAPI with LangGraph multi-agent orchestration for intelligent task routing
- **Core Problem**: Replaces rigid, reactive campus management systems with intelligent, real-time decision-making

### Architecture Highlights

The system uses a **LangGraph state machine** that routes natural language queries to specialized agent nodes:
- **Router Node**: Classifies user intent (facility/scheduling/general) via keyword detection
- **Scheduler Node**: Handles timetable conflicts and automated task scheduling
- **Facility Node**: Manages room bookings and facility reservations
- **State Flow**: All nodes update a centralized `AgentState` (messages, steps, params, response)

Queries flow: User Input → Router (classify intent) → Conditional Routing → Specialist Node → State Update → Response

## Development Setup

### Prerequisites
- **Node.js 18+** for frontend
- **Python 3.11+** for backend

### Backend (services/backend)

```bash
cd services/backend

# Create and activate virtual environment
python -m venv venv
# Windows (PowerShell): .\venv\Scripts\Activate.ps1
# Windows (CMD): venv\Scripts\activate.bat
# Unix/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python main.py
```

Server starts at `http://localhost:8000`
- Health check: `GET /api/health`
- Main endpoint: `POST /api/agent/chat` (accepts `{"message": "..."}`)

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

### Backend (`services/backend/app`)

```
app/
├── api/
│   └── router.py           # FastAPI routes (/api/health, /api/agent/chat)
├── agents/
│   ├── graph.py            # LangGraph workflow definition (router, scheduler, facility nodes)
│   ├── state.py            # AgentState TypedDict (messages, steps, params, response, action)
│   └── nodes/
│       ├── scheduler.py     # Scheduler agent implementation
│       └── facility.py      # Facility booking agent implementation
└── core/
    └── config.py           # Settings (PROJECT_NAME, API_V1_STR, DEBUG, API keys via .env)
```

**Key Dependencies**: FastAPI, uvicorn, LangGraph, Pydantic, python-dotenv

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

### API Contract

**POST /api/agent/chat** expects:
```json
{
  "message": "Book Room 302 for tomorrow"
}
```

Returns `ChatResponse`:
```json
{
  "agent": "Facility Agent",
  "response": "I have processed your room booking...",
  "steps": ["RouterNode: classified...", "FacilityNode: checking..."],
  "params": {"room_id": "302", "date": "..."}
}
```

### Environment Configuration

Backend reads from `.env` file in `services/backend/`:
```
GEMINI_API_KEY=
OPENAI_API_KEY=
DEBUG=True
HOST=127.0.0.1
PORT=8000
```

### LangGraph State Machine

The state flows through nodes as a `StateGraph`:
1. Entry point is always the `router` node
2. Router updates `current_action` field based on keyword matching
3. Conditional edges route to appropriate specialist node
4. Each node can append to `steps` list and update `params` dict
5. Final response written to `final_response` field
6. All nodes feed to END (final state)

### Frontend Architecture

The dashboard is a **single-page React component** (`page.tsx`) with:
- **Tabs**: overview, chat, scheduler, facilities (controlled by `activeTab` state)
- **Message State**: `messages` array with sender, agent name, text, timestamp, workflow steps
- **Backend Integration**: Polls `/api/health` every 10 seconds; falls back to mock simulation if unreachable
- **Styling**: Tailwind + custom glass-panel/glass-card classes for glassmorphic UI

The chat features a real-time workflow trace sidebar showing LangGraph node execution steps.

## Testing & Verification

### Manual Testing Workflow
1. Start backend: `python main.py` in `services/backend`
2. Start frontend: `npm run dev` in `apps/web`
3. Visit `http://localhost:3000`
4. Dashboard will show "Online" status if backend is reachable
5. Test agent queries in the Chat tab (e.g., "Book Room 302" for facility routing, "Schedule a meeting" for scheduler routing)

### Status Indicators
- Frontend sidebar shows green "Online" if backend health check succeeds
- Falls back to "Demo Mode" with mock responses if backend is unreachable
- Workflow steps in chat sidebar trace actual node execution from LangGraph

## Common Patterns

### Adding a New Agent Node
1. Create `app/agents/nodes/my_agent.py` with a node function
2. Add node to workflow in `app/agents/graph.py`: `workflow.add_node("my_agent", my_agent_node)`
3. Update router keywords to detect intent for your node
4. Add conditional edge from router to your node

### Adding an API Endpoint
1. Add route to `app/api/router.py` using FastAPI decorators
2. Define request/response Pydantic models
3. Import `compiled_graph` if using LangGraph orchestration

### Updating Frontend UI
1. Edit `apps/web/src/app/page.tsx` (all UI is in this single component)
2. Use Tailwind classes; custom components use `glass-panel`, `glass-card`, `glass-input` classes
3. State management is via React `useState` hooks

## Deployment Notes

- **Backend**: Uses uvicorn; set `DEBUG=False` and adjust `HOST` for production
- **Frontend**: Run `npm run build` then `npm start`
- **CORS**: Backend currently allows all origins (`allow_origins=["*"]`); narrow this in production
- **Environment**: Backend reads `.env` from `services/backend/` directory

## Useful Links

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
