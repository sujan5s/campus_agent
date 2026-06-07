from typing import TypedDict, List, Annotated, Dict, Any
import operator

class AgentState(TypedDict):
    """
    Universal state representation for the Smart Campus Orchestration Graph.
    """
    # Conversation logs or messages
    messages: List[Dict[str, str]]
    
    # Active action category detected by Router
    current_action: str
    
    # Path of node steps executed (using standard LangGraph reducer list concatenation)
    steps: Annotated[List[str], operator.add]
    
    # Extracted data variables (e.g., room numbers, reservation titles, target times)
    params: Dict[str, Any]
    
    # Final combined text response output
    final_response: str
