from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes.scheduler import scheduler_node
from app.agents.nodes.facility import facility_node

def router_node(state: AgentState) -> dict:
    """
    Analyzes message query to determine which sub-agent node should execute.
    """
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "").lower()
        
    steps = ["RouterNode: Processing incoming natural language command..."]
    
    # Routing classification
    if any(kw in query for kw in ["book", "reserve", "facility", "room", "hall", "lab"]):
        action = "facility"
        steps.append("RouterNode: Classified as 'Facility Reservation'. Routing to FacilityNode.")
    elif any(kw in query for kw in ["schedule", "task", "timetable", "conflict", "overlap"]):
        action = "scheduler"
        steps.append("RouterNode: Classified as 'Timetabling/Automation'. Routing to SchedulerNode.")
    else:
        action = "general"
        steps.append("RouterNode: Classified as 'General Support'. Routing to GeneralNode.")
        
    return {
        "steps": steps,
        "current_action": action
    }

def general_fallback_node(state: AgentState) -> dict:
    """
    Default node fallback for general campus FAQs.
    """
    steps = ["GeneralFallbackNode: Accessing campus handbook directory..."]
    response = (
        "I can help you coordinate daily campus operations. "
        "Try saying something like 'Book Seminar Hall B for tomorrow' or "
        "'Check class schedule conflicts for Room 302'."
    )
    steps.append("GeneralFallbackNode: Generated standard assistant greeting.")
    return {
        "steps": steps,
        "final_response": response
    }

# Build and Compile Graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("router", router_node)
workflow.add_node("scheduler", scheduler_node)
workflow.add_node("facility", facility_node)
workflow.add_node("general_fallback", general_fallback_node)

# Set router node as entrypoint
workflow.set_entry_point("router")

# Define conditional routing logic
def route_to(state: AgentState) -> str:
    action = state.get("current_action", "general")
    if action == "facility":
        return "facility"
    elif action == "scheduler":
        return "scheduler"
    else:
        return "general_fallback"

# Add conditional edges
workflow.add_conditional_edges(
    "router",
    route_to,
    {
        "facility": "facility",
        "scheduler": "scheduler",
        "general_fallback": "general_fallback"
    }
)

# Connect everything else to END
workflow.add_edge("facility", END)
workflow.add_edge("scheduler", END)
workflow.add_edge("general_fallback", END)

# Compile
compiled_graph = workflow.compile()
