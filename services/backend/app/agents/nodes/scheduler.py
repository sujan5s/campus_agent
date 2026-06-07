from app.agents.state import AgentState

def scheduler_node(state: AgentState) -> dict:
    """
    Node solver handling daily timetable checks, automated scheduling runs,
    and course conflicts.
    """
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "").lower()
        
    steps = ["SchedulerNode: Accessing daily master timetable databases..."]
    
    # Simple rule-based mock logic
    if "conflict" in query or "overlap" in query:
        response = (
            "Scheduler Agent Conflict Check:\n"
            "- Analyzed Lecture Theater 302 course roster for tomorrow.\n"
            "- Found NO course schedule conflicts. Time slot 10:00 AM - 12:00 PM is clear."
        )
        steps.append("SchedulerNode: Validated course schedule list - No overlaps found.")
    else:
        response = (
            "The Scheduler Agent has completed the schedule audit. "
            "All daily automated class schedules and operations are aligned."
        )
        steps.append("SchedulerNode: Standard schedule review completed successfully.")
        
    return {
        "steps": steps,
        "final_response": response,
        "params": {**state.get("params", {}), "scheduler_status": "synced"}
    }
