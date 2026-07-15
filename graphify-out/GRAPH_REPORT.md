# Graph Report - campus_agent  (2026-07-14)

## Corpus Check
- 71 files · ~44,882 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 547 nodes · 888 edges · 43 communities (27 shown, 16 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 190 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5d40d159`
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
- 05 — Rehearsed Demo Script (Reviews & Final Viva)

## God Nodes (most connected - your core abstractions)
1. `User` - 30 edges
2. `Teacher` - 29 edges
3. `Subject` - 21 edges
4. `Section` - 21 edges
5. `Room` - 19 edges
6. `Leave` - 18 edges
7. `TimetableEntry` - 17 edges
8. `Base` - 17 edges
9. `compilerOptions` - 16 edges
10. `getToken()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `facility_node()` --indirect_call--> `Room`  [INFERRED]
  services/backend/app/agents/specialists/booking.py → services/backend/app/db/models.py
- `substitution_node()` --indirect_call--> `Approval`  [INFERRED]
  services/backend/app/agents/specialists/substitution.py → services/backend/app/db/models.py
- `substitution_node()` --indirect_call--> `Leave`  [INFERRED]
  services/backend/app/agents/specialists/substitution.py → services/backend/app/db/models.py
- `timetable_node()` --calls--> `generate_timetable()`  [INFERRED]
  services/backend/app/agents/specialists/timetable.py → services/backend/app/tools/timetable.py
- `DecisionIn` --uses--> `User`  [INFERRED]
  services/backend/app/api/approvals.py → services/backend/app/db/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **LangGraph Query Routing Flow** — readme_router_node_concept, readme_scheduler_agent_concept, readme_facility_agent_concept, readme_general_fallback_concept, readme_agentstate_concept [EXTRACTED 0.90]

## Communities (43 total, 16 thin omitted)

### Community 0 - "compilerOptions"
Cohesion: 0.07
Nodes (28): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+20 more)

### Community 1 - "AgentState"
Cohesion: 0.08
Nodes (28): facility_node(), Facility/booking specialist — evolves into the Event & Venue Booking agent (docs, general_fallback_node(), General fallback — replaced by the RAG Knowledge Agent in Phase 3 (docs/01-FEATU, _extract_leave_id(), Substitution Agent — the F2 flagship (docs/06-EXCHANGE-PLAN.md, research/04+07)., substitution_node(), Timetable Agent — F1 (docs/01-FEATURES.md).  Flow: supervisor routes 'generate t (+20 more)

### Community 2 - "devDependencies"
Cohesion: 0.11
Nodes (18): 06 — Phase 2.1 Plan: Period-Exchange Substitution (replaces ranked-cover model), 1. Why this change, 2. What stays exactly the same (do not touch), 3. Data model — new table (do NOT alter existing tables), 4. Exchange-planning algorithm, 5. Dated (effective) timetable — separate view, original untouched, 6. Task order for implementation, 7. Verification checklist (run all before declaring done) (+10 more)

### Community 3 - "dependencies"
Cohesion: 0.05
Nodes (40): dependencies, clsx, lucide-react, next, react, react-dom, tailwind-merge, devDependencies (+32 more)

### Community 4 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Essential Config, Key File Structure, Navigation, Patterns, Quick Start, Testing

### Community 5 - "models.py"
Cohesion: 0.10
Nodes (25): datetime, DeclarativeBase, decide(), DecisionIn, list_approvals(), BaseModel, Session, Approvals API — the human side of human-in-the-loop (docs/02-ARCHITECTURE.md). (+17 more)

### Community 7 - "page.tsx"
Cohesion: 0.40
Nodes (3): Facility, Message, Task

### Community 8 - "FastAPI"
Cohesion: 0.13
Nodes (14): FastAPI, ChatRequest, ChatResponse, BaseModel, Agent chat endpoint — unified entry into the LangGraph supervisor., run_agent_workflow(), API aggregator — one sub-router per domain (docs/02-ARCHITECTURE.md §4).  main.p, get_db() (+6 more)

### Community 16 - "security.py"
Cohesion: 0.14
Nodes (18): HTTPAuthorizationCredentials, login(), LoginRequest, LoginResponse, me(), BaseModel, Session, Auth endpoints — JWT login + current-user. Roles: admin | faculty | student. (+10 more)

### Community 20 - "04 — Roadmap & Status"
Cohesion: 0.04
Nodes (40): 01 — Features, CORE FEATURES, F10. Energy Watchdog Agent ⚡ (ties to the synopsis), F1. Timetable Generation Agent 🗓️, F2. Leave & Substitution Agent (the flagship) 🔁, F3. Event & Venue Booking Agent 🎪, F4. Campus Knowledge Assistant (RAG) 📚, F5. Notification Agent 📣 (cross-cutting) (+32 more)

### Community 21 - "CORE FEATURES"
Cohesion: 0.22
Nodes (13): _consecutive_pairs(), Lesson, precheck(), OR-Tools CP-SAT timetable model (docs/02-ARCHITECTURE.md, research/03).  Design, Indices of same-day adjacent slot pairs (end == next start, no break between)., RoomIn, SectionIn, SlotIn (+5 more)

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
Cohesion: 0.07
Nodes (44): ApprovalCard, ApprovalsPage(), DecideResult, PlanItem, DayEntry, EffectiveDay, ExchangeBoard, ExchangeRow (+36 more)

### Community 38 - "load_timetable_input"
Cohesion: 0.08
Nodes (49): effective_grid(), exchanges_board(), generate(), _parse_date(), date_t, Session, Timetable API — generation (admin) + grid views (any authenticated user).  Inclu, Flat list of confirmed period exchanges within a date range (default:     today (+41 more)

### Community 39 - "timetable_model.py"
Cohesion: 0.15
Nodes (27): apply_leave(), decide_leave(), DecisionIn, _leave_out(), LeaveIn, list_leaves(), BaseModel, Session (+19 more)

### Community 42 - "05 — Rehearsed Demo Script (Reviews & Final Viva)"
Cohesion: 0.29
Nodes (6): 05 — Rehearsed Demo Script (Reviews & Final Viva), Act 1 — The platform (90s), Act 2 — Constraint-solver timetabling (2 min), Act 3 — THE FLAGSHIP: autonomous period-exchange with human-in-the-loop (3 min), Act 4 — Chat + resilience (60s), Q&A ammunition

## Knowledge Gaps
- **187 isolated node(s):** `nextConfig`, `name`, `version`, `private`, `dev` (+182 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Teacher` connect `setup.py` to `models.py`, `load_timetable_input`, `timetable_model.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `User` connect `setup.py` to `security.py`, `models.py`, `timetable_model.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `AgentState` connect `AgentState` to `setup.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `User` (e.g. with `DecisionIn` and `login()`) actually correct?**
  _`User` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `Teacher` (e.g. with `scheduler_node()` and `apply_leave()`) actually correct?**
  _`Teacher` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Subject` (e.g. with `scheduler_node()` and `Config`) actually correct?**
  _`Subject` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Section` (e.g. with `scheduler_node()` and `Config`) actually correct?**
  _`Section` has 20 INFERRED edges - model-reasoned connections that need verification._