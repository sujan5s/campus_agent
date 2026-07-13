from typing import TypedDict, List, Annotated, Dict, Any
import operator


class AgentState(TypedDict):
    """
    Universal state representation for the Smart Campus Orchestration Graph.
    (docs/02-ARCHITECTURE.md §2 — keep field names stable: the frontend trace UI reads them.)
    """
    # Conversation logs or messages
    messages: List[Dict[str, str]]

    # Active action category decided by the Supervisor
    current_action: str

    # Path of node steps executed (standard LangGraph reducer list concatenation)
    steps: Annotated[List[str], operator.add]

    # Extracted data variables (e.g., room numbers, reservation titles, target times)
    params: Dict[str, Any]

    # Final combined text response output
    final_response: str

    # --- Phase 0 additions ---
    # Who initiated this run: "user" (chat) or "system" (proactive trigger)
    source: str

    # Structured task spec extracted by the Supervisor (entities like room, date, time)
    task_spec: Dict[str, Any]
