import uuid
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import router as api_router
from app.db.session import init_db
from app.db.seed import seed


def _substitution_sweep():
    """Proactive safety net (docs/02-ARCHITECTURE.md trigger engine): if a leave
    was approved but no substitution plan exists (e.g. server restarted mid-flow),
    trigger the Substitution Agent. Normal path is the leave-approval API call."""
    from app.agents.graph import compiled_graph
    from app.db.models import Leave, PeriodExchange
    from app.db.session import SessionLocal
    from app.tools.exchange import plan_id_for

    db = SessionLocal()
    try:
        approved = db.query(Leave).filter(Leave.status == "approved").all()
        pending = [lv for lv in approved
                   if db.query(PeriodExchange)
                        .filter(PeriodExchange.plan_id == plan_id_for(lv.id)).count() == 0]
    finally:
        db.close()
    for lv in pending:
        compiled_graph.invoke(
            {"messages": [{"role": "user",
                           "content": f"Plan substitutions for approved leave #{lv.id}"}],
             "steps": [], "params": {}, "final_response": "",
             "current_action": "general", "source": "system",
             "task_spec": {"leave_id": lv.id}},
            config={"configurable": {"thread_id": f"leave-{lv.id}-{uuid.uuid4().hex[:8]}"}},
        )
        print(f"[sweep] Substitution Agent triggered for unplanned approved leave #{lv.id}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if seed():
        print("Database seeded with demo data (see app/db/seed.py for demo logins).")
    scheduler = BackgroundScheduler()
    scheduler.add_job(_substitution_sweep, "interval", minutes=2,
                      id="substitution_sweep", coalesce=True, max_instances=1)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend orchestration services for the Smart Campus Agent System.",
    version="2.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS configuration to allow local Next.js client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open in development; narrow down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API endpoints
app.include_router(api_router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Campus Ops Backend API."}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
