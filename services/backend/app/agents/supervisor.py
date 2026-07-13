"""Supervisor node — LLM structured-output routing (docs/02-ARCHITECTURE.md §2.1).

Replaces the Phase-0-era keyword router. If no LLM provider is configured
(no API key on this machine), it degrades gracefully to the old keyword
heuristic so the system always runs — see docs/03-TECH-STACK.md.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.core.config import settings
from app.core.llm import get_llm, is_llm_configured


class RouteDecision(BaseModel):
    """Structured routing decision returned by the supervisor LLM."""

    route: Literal["timetable", "substitution", "scheduler", "facility", "general"] = Field(
        description=(
            "timetable: generate/regenerate/rebuild the weekly class timetable. "
            "substitution: plan/arrange substitute teachers for an approved leave (message mentions a leave id). "
            "scheduler: schedule conflicts, checks, teacher leave status questions. "
            "facility: booking/reserving/availability of rooms, halls, labs, auditoriums, grounds, events. "
            "general: anything else (campus info, FAQs, greetings)."
        )
    )
    room: Optional[str] = Field(None, description="Room/venue name mentioned, if any")
    date: Optional[str] = Field(None, description="Date mentioned, if any (ISO or as said)")
    time_range: Optional[str] = Field(None, description="Time or time range mentioned, if any")
    subject: Optional[str] = Field(None, description="Subject/course mentioned, if any")
    reasoning: str = Field(description="One short sentence explaining the routing choice")


_SUPERVISOR_SYSTEM = (
    "You are the supervisor of a smart campus operations multi-agent system. "
    "Classify the user's request, extract any entities, and route it to the right specialist."
)


def _keyword_fallback(query: str) -> tuple[str, str]:
    """Deterministic routing used when no LLM provider is configured."""
    q = query.lower()
    if "substitut" in q and ("leave" in q or "plan" in q):
        return "substitution", "keyword match: substitution planning"
    if "timetable" in q and any(kw in q for kw in ["generate", "create", "build", "make", "regenerate"]):
        return "timetable", "keyword match: timetable generation"
    if any(kw in q for kw in ["book", "reserve", "facility", "room", "hall", "lab", "auditorium", "ground", "event"]):
        return "facility", "keyword match: facility/booking terms"
    if any(kw in q for kw in ["schedule", "task", "timetable", "conflict", "overlap", "leave", "substitut"]):
        return "scheduler", "keyword match: scheduling terms"
    return "general", "no domain keywords matched"


def supervisor_node(state: AgentState) -> dict:
    """Classify intent + extract entities. LLM-first, heuristic fallback."""
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "")

    steps = ["Supervisor: analyzing incoming request..."]
    task_spec: dict = {}

    if is_llm_configured():
        try:
            llm = get_llm().with_structured_output(RouteDecision)
            decision: RouteDecision = llm.invoke(
                [("system", _SUPERVISOR_SYSTEM), ("user", query)]
            )
            action = decision.route
            task_spec = {
                k: v
                for k, v in {
                    "room": decision.room,
                    "date": decision.date,
                    "time_range": decision.time_range,
                    "subject": decision.subject,
                }.items()
                if v
            }
            steps.append(
                f"Supervisor: LLM routing via {settings.LLM_PROVIDER}/{settings.LLM_MODEL} "
                f"→ '{action}' ({decision.reasoning})"
            )
        except Exception as exc:  # provider outage/quota — never take the demo down
            action, why = _keyword_fallback(query)
            steps.append(f"Supervisor: LLM unavailable ({type(exc).__name__}), heuristic fallback → '{action}' ({why})")
    else:
        action, why = _keyword_fallback(query)
        steps.append(f"Supervisor: no LLM key configured, heuristic routing → '{action}' ({why})")

    return {
        "steps": steps,
        "current_action": action,
        # merge, don't replace — system triggers pre-seed task_spec (e.g. leave_id)
        "task_spec": {**(state.get("task_spec") or {}), **task_spec},
    }


def route_to(state: AgentState) -> str:
    action = state.get("current_action", "general")
    if action == "timetable":
        return "timetable"
    if action == "substitution":
        return "substitution"
    if action == "facility":
        return "facility"
    if action == "scheduler":
        return "scheduler"
    return "general_fallback"
