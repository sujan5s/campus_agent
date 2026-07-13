# Graph Report - campus_agent  (2026-07-13)

## Corpus Check
- 38 files · ~12,805 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 288 nodes · 312 edges · 36 communities (20 shown, 16 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 40 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bcf8be77`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- compilerOptions
- AgentState
- devDependencies
- dependencies
- CLAUDE.md
- models.py
- POST /api/agent/chat Contract
- page.tsx
- FastAPI
- layout.tsx
- Settings
- next.config.mjs
- next-env.d.ts
- postcss.config.mjs
- tailwind.config.ts
- security.py
- 04 — Roadmap & Status
- CORE FEATURES
- 02 — Architecture
- Smart Campus Agent System (smart-campus-ops)
- graph.py
- AgentState (Centralized State)
- Facility Agent Node
- FastAPI Backend Service
- Next.js Campus Dashboard
- General Fallback Node
- LangGraph Multi-Agent Orchestration
- Router Node (Intent Classification)
- Scheduler Agent Node
- Smart Campus Agent System

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `Base` - 16 edges
3. `seed()` - 10 edges
4. `AgentState` - 9 edges
5. `User` - 9 edges
6. `login()` - 8 edges
7. `supervisor_node()` - 7 edges
8. `02 — Architecture` - 7 edges
9. `04 — Roadmap & Status` - 7 edges
10. `get_current_user()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `seed()` --calls--> `hash_password()`  [INFERRED]
  services/backend/app/db/seed.py → services/backend/app/core/security.py
- `facility_node()` --indirect_call--> `Room`  [INFERRED]
  services/backend/app/agents/specialists/booking.py → services/backend/app/db/models.py
- `login()` --calls--> `create_access_token()`  [INFERRED]
  services/backend/app/api/auth.py → services/backend/app/core/security.py
- `login()` --calls--> `verify_password()`  [INFERRED]
  services/backend/app/api/auth.py → services/backend/app/core/security.py
- `User` --uses--> `Base`  [INFERRED]
  services/backend/app/db/models.py → services/backend/app/db/session.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **LangGraph Query Routing Flow** — readme_router_node_concept, readme_scheduler_agent_concept, readme_facility_agent_concept, readme_general_fallback_concept, readme_agentstate_concept [EXTRACTED 0.90]

## Communities (36 total, 16 thin omitted)

### Community 0 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 1 - "AgentState"
Cohesion: 0.10
Nodes (23): facility_node(), Facility/booking specialist — evolves into the Event & Venue Booking agent (docs, general_fallback_node(), General fallback — replaced by the RAG Knowledge Agent in Phase 3 (docs/01-FEATU, AgentState, Universal state representation for the Smart Campus Orchestration Graph.     (do, _keyword_fallback(), BaseModel (+15 more)

### Community 2 - "devDependencies"
Cohesion: 0.11
Nodes (19): devDependencies, autoprefixer, eslint, eslint-config-next, postcss, tailwindcss, @types/node, @types/react (+11 more)

### Community 3 - "dependencies"
Cohesion: 0.09
Nodes (21): dependencies, clsx, lucide-react, next, react, react-dom, tailwind-merge, name (+13 more)

### Community 4 - "CLAUDE.md"
Cohesion: 0.07
Nodes (27): Adding a New Agent Node, Adding an API Endpoint, API Contract, Architecture Highlights, Backend, Backend (services/backend), Backend (`services/backend/app`), Common Commands (+19 more)

### Community 5 - "models.py"
Cohesion: 0.12
Nodes (25): datetime, DeclarativeBase, Scheduling specialist — evolves into the Timetable + Substitution agents (docs/0, scheduler_node(), Approval, Booking, Document, Event (+17 more)

### Community 7 - "page.tsx"
Cohesion: 0.40
Nodes (3): Facility, Message, Task

### Community 8 - "FastAPI"
Cohesion: 0.14
Nodes (12): FastAPI, ChatRequest, ChatResponse, BaseModel, Agent chat endpoint — unified entry into the LangGraph supervisor., run_agent_workflow(), API aggregator — one sub-router per domain (docs/02-ARCHITECTURE.md §4).  main.p, get_db() (+4 more)

### Community 16 - "security.py"
Cohesion: 0.15
Nodes (20): HTTPAuthorizationCredentials, login(), LoginRequest, LoginResponse, me(), BaseModel, Session, Auth endpoints — JWT login + current-user. Roles: admin | faculty | student. (+12 more)

### Community 20 - "04 — Roadmap & Status"
Cohesion: 0.11
Nodes (14): 03 — Tech Stack, requirements.txt target (backend), Summary table, ★ The model-agnostic LLM layer (`app/core/llm.py`), 04 — Roadmap & Status, Decision log, Phase 0 — Foundation rebuild (≈1 week), Phase 1 — F1 Timetable Generation (≈2 weeks) (+6 more)

### Community 21 - "CORE FEATURES"
Cohesion: 0.13
Nodes (14): 01 — Features, CORE FEATURES, F10. Energy Watchdog Agent ⚡ (ties to the synopsis), F1. Timetable Generation Agent 🗓️, F2. Leave & Substitution Agent (the flagship) 🔁, F3. Event & Venue Booking Agent 🎪, F4. Campus Knowledge Assistant (RAG) 📚, F5. Notification Agent 📣 (cross-cutting) (+6 more)

### Community 22 - "02 — Architecture"
Cohesion: 0.20
Nodes (10): 02 — Architecture, 1. System overview, 2.1 Supervisor pattern, 2.2 The tools layer (critical design rule), 2.3 Proactive trigger engine, 2. Agent workflow (LangGraph), 3. Data model (SQLAlchemy), 4. API surface (FastAPI routers, one per domain) (+2 more)

### Community 23 - "Smart Campus Agent System (smart-campus-ops)"
Cohesion: 0.20
Nodes (9): 1. Backend Service, 2. Web Application, Architecture, Components, License, Project Overview, Setup & Running, Smart Campus Agent System (smart-campus-ops) (+1 more)

### Community 24 - "graph.py"
Cohesion: 0.50
Nodes (3): _make_checkpointer(), LangGraph workflow assembly + durable checkpointer (docs/02-ARCHITECTURE.md §2)., SqliteSaver if available, else in-memory (never blocks startup).

## Knowledge Gaps
- **118 isolated node(s):** `nextConfig`, `name`, `version`, `private`, `dev` (+113 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AgentState` connect `AgentState` to `models.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `scheduler_node()` connect `models.py` to `AgentState`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `seed()` connect `models.py` to `security.py`, `FastAPI`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `Base` (e.g. with `Approval` and `Booking`) actually correct?**
  _`Base` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `seed()` (e.g. with `hash_password()` and `Room`) actually correct?**
  _`seed()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `nextConfig`, `name`, `version` to the rest of the system?**
  _118 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.06896551724137931 - nodes in this community are weakly interconnected._