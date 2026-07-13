"""General fallback — replaced by the RAG Knowledge Agent in Phase 3
(docs/01-FEATURES.md F4). Until then: LLM answer if configured, canned reply if not.
"""
from app.agents.state import AgentState
from app.core.llm import get_llm, is_llm_configured

_SYSTEM = (
    "You are the Campus Orchestrator assistant of a smart campus operations system "
    "for an engineering college. Answer briefly and helpfully. If the question needs "
    "campus-specific documents you don't have, say so and suggest what you CAN do: "
    "check schedules/conflicts (Scheduler Agent) or book venues (Facility Agent)."
)


def general_fallback_node(state: AgentState) -> dict:
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "")

    steps = ["GeneralAgent: handling general campus query..."]

    if is_llm_configured():
        try:
            reply = get_llm(temperature=0.4).invoke([("system", _SYSTEM), ("user", query)])
            steps.append("GeneralAgent: composed answer via LLM.")
            return {"steps": steps, "final_response": reply.content}
        except Exception as exc:
            steps.append(f"GeneralAgent: LLM unavailable ({type(exc).__name__}), using standard reply.")

    steps.append("GeneralAgent: generated standard assistant reply (no LLM configured).")
    response = (
        "I can help you coordinate daily campus operations. "
        "Try 'Book Seminar Hall B for Friday 2pm' or 'Check schedule conflicts for CSE-7A'. "
        "(Document-grounded answers arrive with the Knowledge Agent in Phase 3.)"
    )
    return {"steps": steps, "final_response": response}
