"""Agent chat endpoint — unified entry into the LangGraph supervisor."""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.graph import compiled_graph, checkpointer
from app.core.security import get_optional_user

router = APIRouter()

AGENT_NAMES = {
    "timetable": "Timetable Agent",
    "substitution": "Substitution Agent",
    "facility": "Booking Agent",
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
    # Set when the agent paused for a human decision (e.g. a booking approval
    # chain) — the UI renders the pending card instead of a plain reply.
    awaiting_approval: Optional[Dict[str, Any]] = None


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "Smart Campus Agent Backend"}


@router.post("/agent/chat", response_model=ChatResponse)
def run_agent_workflow(request: ChatRequest, user=Depends(get_optional_user)):
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
            # The booking agent needs an organiser identity to write anything;
            # anonymous chat still works, it just answers availability questions.
            "task_spec": {"user_id": user.id} if user else {},
        }

        result = compiled_graph.invoke(initial_state, config=config)

        detected_action = result.get("current_action", "general")
        intr = result.get("__interrupt__")
        pending = None
        response = result.get("final_response", "Operation processed successfully.")
        if intr:
            pending = intr[0].value if hasattr(intr[0], "value") else intr[0]
            booking = (pending or {}).get("booking") or {}
            response = (
                f"Request logged as booking #{booking.get('booking_id', '?')} — "
                f"{booking.get('venue', 'venue')} on {booking.get('date', '')}, "
                f"{booking.get('window', '')}.\n{booking.get('rationale', '')}\n"
                f"It is now with {pending.get('stage', 'the approver')} for approval "
                f"(stage {pending.get('stage_index', 1)} of {pending.get('stages', 1)}).")

        # A node that pauses on interrupt() never returns, so its trace isn't in
        # state — the card carries it instead (see specialists/booking.py).
        steps = result.get("steps", [])[prior_steps:]
        if pending and pending.get("steps"):
            steps = steps + list(pending["steps"])

        return ChatResponse(
            agent=AGENT_NAMES.get(detected_action, "Campus Orchestrator"),
            response=response,
            awaiting_approval=pending,
            steps=steps,
            params=result.get("params", {}),
            thread_id=thread_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration Error: {str(e)}")
