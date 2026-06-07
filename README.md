# Smart Campus Agent System (smart-campus-ops)

A multi-agent, automated operations and scheduling system designed to optimize daily campus activities. Powered by a Next.js frontend and a FastAPI backend with LangGraph multi-agent orchestration.

## Project Overview

The **Agentic AI-Driven Smart Campus Operations Management System** addresses the limitations of traditional, reactive campus management systems. Modern educational campuses operate as complex ecosystems, managing scheduling, resource allocation, and facility operations. However, legacy systems are often rigid, disjointed, and heavily dependent on manual supervision, leading to delayed responses, timetable conflicts, and high operational costs.

This project introduces an **Agentic AI-driven campus management framework** that enables intelligent, real-time monitoring and decision-making. By utilizing multiple autonomous, collaborative agents—specializing in areas like scheduling and facility coordination—the system proactively manages campus operations, adapts dynamically to changing conditions, and ensures efficient resource utilization with minimal human intervention.

## Architecture

### Visual Flow Diagram
```mermaid
graph TD
    User([User Query]) --> Router[Router Node]
    
    subgraph "Orchestration Layer (LangGraph)"
        Router -->|Intent: Scheduling/Tasks| Scheduler[Scheduler Agent Node]
        Router -->|Intent: Room Bookings| Facility[Facility Agent Node]
        Router -->|Intent: General Info| General[General Fallback Node]
    end
    
    subgraph "State Storage"
        State[(AgentState)]
    end
    
    Scheduler -.->|Update State| State
    Facility -.->|Update State| State
    General -.->|Update State| State
    
    State --> Output[Consolidated Response]
    
    style User fill:#3b5cfa,stroke:#1b2ad9,stroke-width:2px,color:#fff
    style Router fill:#6366f1,stroke:#4f46e5,stroke-width:2px,color:#fff
    style Scheduler fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff
    style Facility fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff
    style General fill:#6b7280,stroke:#374151,stroke-width:2px,color:#fff
    style State fill:#ec4899,stroke:#be185d,stroke-width:2px,color:#fff
    style Output fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff
```

```
smart-campus-ops/
├── apps/
│   └── web/            # Next.js Client Dashboard (TypeScript, Tailwind)
└── services/
    └── backend/        # Orchestration Engine & Server (Python 3.11+, FastAPI, LangGraph)
```

### Components

1. **Frontend (apps/web)**: Next.js frontend built with Tailwind CSS. It provides a visual dashboard for administrators and students to interact with campus agents, view scheduled operations, check room bookings, and trigger automated scripts.
2. **Backend (services/backend)**: Python backend running FastAPI. It hosts REST endpoints, manages real-time WebSockets, and compiles a LangGraph multi-agent orchestration workflow to route queries and delegate tasks (e.g., room booking, timetable scheduling).

## Setup & Running

### 1. Backend Service
Make sure you have Python 3.11+ installed.
```bash
cd services/backend
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\python main.py

# Alternatively, activate the virtualenv first:
# Windows (PowerShell): .\venv\Scripts\Activate.ps1
# Windows (CMD): venv\Scripts\activate.bat
# Unix/macOS: source venv/bin/activate

pip install -r requirements.txt
python main.py
```
*The server will start at `http://localhost:8000`.*

### 2. Web Application
Make sure you have Node.js 18+ installed.
```bash
cd apps/web
npm install
npm run dev
```
*The client dashboard will start at `http://localhost:3000`.*

## License
MIT
