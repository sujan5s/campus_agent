# Graph Report - .  (2026-07-13)

## Corpus Check
- Corpus is ~5,904 words - fits in a single context window. You may not need a graph.

## Summary
- 129 nodes · 129 edges · 20 communities (14 shown, 6 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.92)
- Token cost: 4,200 input · 2,100 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `AgentState` - 9 edges
3. `scripts` - 5 edges
4. `include` - 5 edges
5. `Router Node (Intent Classification)` - 5 edges
6. `POST /api/agent/chat Contract` - 5 edges
7. `lib` - 4 edges
8. `router_node()` - 4 edges
9. `general_fallback_node()` - 4 edges
10. `facility_node()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Next.js Campus Dashboard` --conceptually_related_to--> `Dashboard()`  [INFERRED]
  README.md → apps/web/src/app/page.tsx
- `Router Node (Intent Classification)` --conceptually_related_to--> `router_node()`  [INFERRED]
  README.md → services/backend/app/agents/graph.py
- `General Fallback Node` --conceptually_related_to--> `general_fallback_node()`  [INFERRED]
  README.md → services/backend/app/agents/graph.py
- `Facility Agent Node` --conceptually_related_to--> `facility_node()`  [INFERRED]
  README.md → services/backend/app/agents/nodes/facility.py
- `Scheduler Agent Node` --conceptually_related_to--> `scheduler_node()`  [INFERRED]
  README.md → services/backend/app/agents/nodes/scheduler.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **LangGraph Query Routing Flow** — readme_router_node_concept, readme_scheduler_agent_concept, readme_facility_agent_concept, readme_general_fallback_concept, readme_agentstate_concept [EXTRACTED 0.90]
- **Campus Specialist Agent Nodes** — services_backend_app_agents_graph_router_node, services_backend_app_agents_nodes_scheduler_scheduler_node, services_backend_app_agents_nodes_facility_facility_node, services_backend_app_agents_graph_general_fallback_node [INFERRED 0.85]

## Communities (20 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (21): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+13 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (17): AgentState (Centralized State), Facility Agent Node, General Fallback Node, Router Node (Intent Classification), Scheduler Agent Node, general_fallback_node(), Default node fallback for general campus FAQs., Analyzes message query to determine which sub-agent node should execute. (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (19): devDependencies, autoprefixer, eslint, eslint-config-next, postcss, tailwindcss, @types/node, @types/react (+11 more)

### Community 3 - "Community 3"
Cohesion: 0.15
Nodes (13): dependencies, clsx, lucide-react, next, react, react-dom, tailwind-merge, clsx (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.22
Nodes (8): name, private, scripts, build, dev, lint, start, version

### Community 5 - "Community 5"
Cohesion: 0.25
Nodes (7): exclude, include, next-env.d.ts, .next/types/**/*.ts, node_modules, **/*.ts, **/*.tsx

### Community 6 - "Community 6"
Cohesion: 0.52
Nodes (5): BaseModel, POST /api/agent/chat Contract, ChatRequest, ChatResponse, run_agent_workflow()

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (5): Dashboard(), Facility, Message, Task, Next.js Campus Dashboard

### Community 8 - "Community 8"
Cohesion: 0.40
Nodes (3): FastAPI Backend Service, LangGraph Multi-Agent Orchestration, Smart Campus Agent System

## Knowledge Gaps
- **53 isolated node(s):** `nextConfig`, `name`, `version`, `private`, `dev` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `Community 2` to `Community 4`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `dependencies` connect `Community 3` to `Community 4`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `LangGraph Multi-Agent Orchestration` connect `Community 8` to `Community 1`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **What connects `nextConfig`, `name`, `version` to the rest of the system?**
  _53 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._