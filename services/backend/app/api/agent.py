"""Agent chat endpoint — unified entry into the LangGraph supervisor."""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.graph import compiled_graph, checkpointer

router = APIRouter()

AGENT_NAMES = {
    "facility": "Facility Agent",
    "scheduler": "Scheduler Agent",
    "general": "Campus Orchestrator",
}


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None  # continue an existing conversation thread


class ChatResponse(BaseModel):
    agent: str
    response: str
    steps: List[str]
    params: Dict[str, Any]
    thread_id: str


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "Smart Campus Agent Backend"}


@router.post("/agent/chat", response_model=ChatResponse)
def run_agent_workflow(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # steps uses an additive reducer: on a resumed thread it accumulates,
        # so remember how many steps existed before this turn and return the delta.
        prior_steps = 0
        if checkpointer is not None:
            snapshot = compiled_graph.get_state(config)
            if snapshot and snapshot.values:
                prior_steps = len(snapshot.values.get("steps", []))

        initial_state = {
            "messages": [{"role": "user", "content": request.message}],
            "steps": [],
            "params": {},
            "final_response": "",
            "current_action": "general",
            "source": "user",
            "task_spec": {},
        }

        result = compiled_graph.invoke(initial_state, config=config)

        detected_action = result.get("current_action", "general")
        return ChatResponse(
            agent=AGENT_NAMES.get(detected_action, "Campus Orchestrator"),
            response=result.get("final_response", "Operation processed successfully."),
            steps=result.get("steps", [])[prior_steps:],
            params=result.get("params", {}),
            thread_id=thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration Error: {str(e)}")
