# Graph Report - campus_agent  (2026-07-13)

## Corpus Check
- 59 files · ~36,028 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 445 nodes · 639 edges · 42 communities (26 shown, 16 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74dfbfff`
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
- setup.py
- page.tsx
- load_timetable_input
- timetable_model.py

## God Nodes (most connected - your core abstractions)
1. `Subject` - 21 edges
2. `User` - 20 edges
3. `Section` - 20 edges
4. `Room` - 19 edges
5. `Teacher` - 18 edges
6. `compilerOptions` - 16 edges
7. `Base` - 16 edges
8. `load_timetable_input()` - 12 edges
9. `AgentState` - 10 edges
10. `SubjectIn` - 10 edges

## Surprising Connections (you probably didn't know these)
- `facility_node()` --indirect_call--> `Room`  [INFERRED]
  services/backend/app/agents/specialists/booking.py → services/backend/app/db/models.py
- `timetable_node()` --calls--> `generate_timetable()`  [INFERRED]
  services/backend/app/agents/specialists/timetable.py → services/backend/app/tools/timetable.py
- `LoginRequest` --uses--> `User`  [INFERRED]
  services/backend/app/api/auth.py → services/backend/app/db/models.py
- `UserOut` --uses--> `User`  [INFERRED]
  services/backend/app/api/auth.py → services/backend/app/db/models.py
- `LoginResponse` --uses--> `User`  [INFERRED]
  services/backend/app/api/auth.py → services/backend/app/db/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **LangGraph Query Routing Flow** — readme_router_node_concept, readme_scheduler_agent_concept, readme_facility_agent_concept, readme_general_fallback_concept, readme_agentstate_concept [EXTRACTED 0.90]

## Communities (42 total, 16 thin omitted)

### Community 0 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 1 - "AgentState"
Cohesion: 0.09
Nodes (25): facility_node(), Facility/booking specialist — evolves into the Event & Venue Booking agent (docs, general_fallback_node(), General fallback — replaced by the RAG Knowledge Agent in Phase 3 (docs/01-FEATU, Timetable Agent — F1 (docs/01-FEATURES.md).  Flow: supervisor routes 'generate t, timetable_node(), AgentState, Universal state representation for the Smart Campus Orchestration Graph.     (do (+17 more)

### Community 2 - "devDependencies"
Cohesion: 0.11
Nodes (19): devDependencies, autoprefixer, eslint, eslint-config-next, postcss, tailwindcss, @types/node, @types/react (+11 more)

### Community 3 - "dependencies"
Cohesion: 0.09
Nodes (21): dependencies, clsx, lucide-react, next, react, react-dom, tailwind-merge, name (+13 more)

### Community 4 - "CLAUDE.md"
Cohesion: 0.06
Nodes (29): Adding a domain router (Phase 2+ example: booking approvals), Adding a new feature (Phase 1 example: F1 Timetable generation), Architecture (Phase 0+), Backend, Backend (services/backend), Backend (`services/backend/app`) — Phase 0, Code navigation (graphify knowledge graph), Common Commands (+21 more)

### Community 5 - "models.py"
Cohesion: 0.17
Nodes (15): datetime, DeclarativeBase, Approval, Booking, Document, Event, Leave, Notification (+7 more)

### Community 7 - "page.tsx"
Cohesion: 0.40
Nodes (3): Facility, Message, Task

### Community 8 - "FastAPI"
Cohesion: 0.14
Nodes (12): FastAPI, ChatRequest, ChatResponse, BaseModel, Agent chat endpoint — unified entry into the LangGraph supervisor., run_agent_workflow(), API aggregator — one sub-router per domain (docs/02-ARCHITECTURE.md §4).  main.p, get_db() (+4 more)

### Community 16 - "security.py"
Cohesion: 0.14
Nodes (18): HTTPAuthorizationCredentials, login(), LoginRequest, LoginResponse, me(), BaseModel, Session, Auth endpoints — JWT login + current-user. Roles: admin | faculty | student. (+10 more)

### Community 20 - "04 — Roadmap & Status"
Cohesion: 0.07
Nodes (25): 02 — Architecture, 1. System overview, 2.1 Supervisor pattern, 2.2 The tools layer (critical design rule), 2.3 Proactive trigger engine, 2. Agent workflow (LangGraph), 3. Data model (SQLAlchemy), 4. API surface (FastAPI routers, one per domain) (+17 more)

### Community 21 - "CORE FEATURES"
Cohesion: 0.13
Nodes (14): 01 — Features, CORE FEATURES, F10. Energy Watchdog Agent ⚡ (ties to the synopsis), F1. Timetable Generation Agent 🗓️, F2. Leave & Substitution Agent (the flagship) 🔁, F3. Event & Venue Booking Agent 🎪, F4. Campus Knowledge Assistant (RAG) 📚, F5. Notification Agent 📣 (cross-cutting) (+6 more)

### Community 22 - "02 — Architecture"
Cohesion: 0.05
Nodes (40): 00 — Master Concept Mapping, Concept → Implementation → Literature, Ready-to-fill reference list (IEEE style skeleton), The "we took / we changed" summary (for the Limitations & Contribution slide), 02 — LLM Orchestration, Supervisor-Router Pattern & Tool Calling, How it maps to our project, Papers — Orchestration & supervisor-router, Papers — Tool / function calling & intent classification (+32 more)

### Community 23 - "Smart Campus Agent System (smart-campus-ops)"
Cohesion: 0.20
Nodes (9): 1. Backend Service, 2. Web Application, Architecture, Components, License, Project Overview, Setup & Running, Smart Campus Agent System (smart-campus-ops) (+1 more)

### Community 24 - "graph.py"
Cohesion: 0.50
Nodes (3): _make_checkpointer(), LangGraph workflow assembly + durable checkpointer (docs/02-ARCHITECTURE.md §2)., SqliteSaver if available, else in-memory (never blocks startup).

### Community 36 - "setup.py"
Cohesion: 0.16
Nodes (42): Scheduling specialist — evolves into the Timetable + Substitution agents (docs/0, scheduler_node(), Config, create_room(), create_section(), create_subject(), create_teacher(), delete_room() (+34 more)

### Community 37 - "page.tsx"
Cohesion: 0.11
Nodes (26): LoginPage(), LoginResponse, CSV_TEMPLATES, ImportResult, Room, ROOM_TYPES, Section, SetupPage() (+18 more)

### Community 38 - "load_timetable_input"
Cohesion: 0.15
Nodes (21): generate(), Session, Timetable API — generation (admin) + grid views (any authenticated user)., Run the CP-SAT solver on current master data. Stores a new version on success., section_grid(), status(), teacher_grid(), TimeSlot (+13 more)

### Community 39 - "timetable_model.py"
Cohesion: 0.22
Nodes (13): _consecutive_pairs(), Lesson, precheck(), OR-Tools CP-SAT timetable model (docs/02-ARCHITECTURE.md, research/03).  Design, Indices of same-day adjacent slot pairs (end == next start, no break between)., RoomIn, SectionIn, SlotIn (+5 more)

## Knowledge Gaps
- **170 isolated node(s):** `nextConfig`, `name`, `version`, `private`, `dev` (+165 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AgentState` connect `AgentState` to `setup.py`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `generate_timetable()` connect `load_timetable_input` to `AgentState`, `timetable_model.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `load_timetable_input()` connect `load_timetable_input` to `setup.py`, `timetable_model.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `Subject` (e.g. with `scheduler_node()` and `Config`) actually correct?**
  _`Subject` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `User` (e.g. with `login()` and `LoginRequest`) actually correct?**
  _`User` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Section` (e.g. with `scheduler_node()` and `Config`) actually correct?**
  _`Section` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Room` (e.g. with `facility_node()` and `Config`) actually correct?**
  _`Room` has 18 INFERRED edges - model-reasoned connections that need verification._