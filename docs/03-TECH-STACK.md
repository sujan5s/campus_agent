# 03 — Tech Stack

Every choice below optimizes for: **free for students**, **runs on a laptop**, **industry-standard
(good for viva/resume)**, and **no vendor lock-in**.

## Summary table

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 14 + TypeScript + Tailwind** | Already built; industry standard; the glassmorphic dashboard + live agent trace is a demo asset. |
| Backend | **FastAPI + Uvicorn (Python 3.11+)** | Already built; async-native, auto OpenAPI docs, first-class WebSockets. |
| Agent orchestration | **LangGraph ≥ 0.2** (⚠️ upgrade from pinned 0.0.60) | Supervisor pattern, `interrupt()` for human-in-the-loop, checkpointers for durable workflow state. The pinned 0.0.60 predates all of these — upgrading is the first roadmap task. |
| LLM | **Provider-agnostic layer** (below) — default Gemini Flash free tier | No lock-in; free tier covers development; swap providers with one env var. |
| Timetable solving | **Google OR-Tools (CP-SAT)** | Constraint solving is a solver's job, not an LLM's. Free, pip-installable, solves campus-scale timetables in seconds, reports infeasibility causes. |
| Database | **SQLite (dev) → PostgreSQL (demo/prod, free on Supabase/Neon)** | SQLAlchemy makes the swap a connection-string change. SQLite = zero setup for 4 teammates. |
| ORM | **SQLAlchemy 2.x** (+ Alembic migrations) | Standard, typed, works with both DBs. |
| Vector store (RAG) | **ChromaDB (embedded)** | Zero-infra, persists to a local folder, good enough for a campus document corpus. |
| Embeddings | Provider-agnostic: Gemini `text-embedding-004` (free) or `sentence-transformers` fully offline | Same no-lock-in principle as chat models. |
| Background jobs | **APScheduler** | In-process cron; no Redis/Celery needed at this scale. |
| Auth | **JWT (python-jose + passlib)**, roles: admin / faculty / student | Simple, standard, easy to demo role-based behaviour. |
| Realtime | **FastAPI WebSockets** | Already in requirements; streams agent trace + notifications to the dashboard. |
| Notifications | In-app (DB) + SMTP email; **Telegram Bot API** as a stretch | Telegram bot is free and demos beautifully on a phone. |

## ★ The model-agnostic LLM layer (`app/core/llm.py`)

This is a hard architectural rule (see docs/README.md rule 3). The whole system gets its
LLM from one factory, configured entirely by `.env`:

```python
# app/core/llm.py
from langchain.chat_models import init_chat_model
from app.core.config import settings

def get_llm(purpose: str = "default"):
    """All agents get their LLM here. Provider/model chosen by .env only."""
    return init_chat_model(
        model=settings.LLM_MODEL,          # e.g. "gemini-2.5-flash"
        model_provider=settings.LLM_PROVIDER,  # "google_genai" | "anthropic" | "openai" | "ollama"
        temperature=0.1,
    )
```

```env
# .env — switching provider is ONLY this:
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=...

# or:  LLM_PROVIDER=anthropic  LLM_MODEL=claude-sonnet-5      ANTHROPIC_API_KEY=...
# or:  LLM_PROVIDER=openai     LLM_MODEL=gpt-4o-mini          OPENAI_API_KEY=...
# or:  LLM_PROVIDER=ollama     LLM_MODEL=llama3.1             (fully offline demo!)
```

Why this matters for the report/viva: it demonstrates *architecture over API-calling* —
the system's intelligence is in the agent design, tools, and workflows, not in any one
vendor's model. It also future-proofs the project: if a model or free tier disappears
mid-semester, nothing breaks.

Recommended defaults:
- **Development:** Gemini Flash free tier (generous rate limits, structured output support).
- **Offline/demo backup:** Ollama + an 8B model on one teammate's laptop — the demo cannot
  be killed by the venue's Wi-Fi.

## requirements.txt target (backend)

```
fastapi
uvicorn[standard]
langgraph>=0.2
langchain>=0.3
langchain-google-genai        # + langchain-anthropic / langchain-openai as optional extras
pydantic>=2
pydantic-settings
sqlalchemy>=2
alembic
ortools
chromadb
apscheduler
python-jose[cryptography]
passlib[bcrypt]
python-dotenv
websockets
```

(Pin exact versions once the upgrade in Roadmap Phase 0 is done and tested.)
