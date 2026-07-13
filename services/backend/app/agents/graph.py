"""LangGraph workflow assembly + durable checkpointer (docs/02-ARCHITECTURE.md §2).

Entry point: supervisor (LLM routing) → specialist → END.
Checkpointer: SqliteSaver — conversation threads survive restarts and enable
interrupt()/resume for human-in-the-loop approvals (Phase 2).
"""
import sqlite3

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node, route_to
from app.agents.specialists.scheduling import scheduler_node
from app.agents.specialists.booking import facility_node
from app.agents.specialists.general import general_fallback_node
from app.agents.specialists.timetable import timetable_node
from app.agents.specialists.substitution import substitution_node
from app.core.config import settings


def _make_checkpointer():
    """SqliteSaver if available, else in-memory (never blocks startup)."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(settings.CHECKPOINT_DB, check_same_thread=False)
        return SqliteSaver(conn)
    except ImportError:
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except ImportError:  # very old langgraph — run without persistence
            return None


# Build and compile graph
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("scheduler", scheduler_node)
workflow.add_node("facility", facility_node)
workflow.add_node("general_fallback", general_fallback_node)
workflow.add_node("timetable", timetable_node)
workflow.add_node("substitution", substitution_node)

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    route_to,
    {
        "timetable": "timetable",
        "substitution": "substitution",
        "facility": "facility",
        "scheduler": "scheduler",
        "general_fallback": "general_fallback",
    },
)

workflow.add_edge("timetable", END)
workflow.add_edge("substitution", END)
workflow.add_edge("facility", END)
workflow.add_edge("scheduler", END)
workflow.add_edge("general_fallback", END)

checkpointer = _make_checkpointer()
compiled_graph = workflow.compile(checkpointer=checkpointer)
