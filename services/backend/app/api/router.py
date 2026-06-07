from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from app.agents.graph import compiled_graph

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    agent: str
    response: str
    steps: List[str]
    params: Dict[str, Any]

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "Smart Campus Agent Backend"}

@router.post("/agent/chat", response_model=ChatResponse)
def run_agent_workflow(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    try:
        # Initialize LangGraph state
        initial_state = {
            "messages": [{"role": "user", "content": request.message}],
            "steps": [],
            "params": {},
            "final_response": "",
            "current_action": "general"
        }
        
        # Invoke LangGraph
        result = compiled_graph.invoke(initial_state)
        
        # Retrieve agent category label
        action_agent_map = {
            "facility": "Facility Agent",
            "scheduler": "Scheduler Agent",
            "general": "Campus Orchestrator"
        }
        detected_action = result.get("current_action", "general")
        agent_name = action_agent_map.get(detected_action, "Campus Orchestrator")
        
        return ChatResponse(
            agent=agent_name,
            response=result.get("final_response", "Operation processed successfully."),
            steps=result.get("steps", []),
            params=result.get("params", {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration Error: {str(e)}")
