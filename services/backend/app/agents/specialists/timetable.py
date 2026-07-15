"""Timetable Agent — F1 (docs/01-FEATURES.md).

Flow: supervisor routes 'generate timetable' here → this node calls the
solve tool (OR-Tools CP-SAT, never the LLM) → on success reports stats; on
infeasibility the LLM turns the solver's precise reasons into a plain-language
explanation with suggested fixes (the capability GA-based literature lacks,
research/03).
"""
from app.agents.state import AgentState
from app.core.llm import get_llm, is_llm_configured
from app.db.session import SessionLocal
from app.tools.timetable import generate_timetable, options_from_config

_EXPLAIN_SYSTEM = (
    "You are the Timetable Agent of a smart campus system. The constraint solver "
    "found the timetable INFEASIBLE. Rewrite the technical reasons below as a short, "
    "friendly explanation for a college admin: what is blocking, and 2-3 concrete "
    "fixes (e.g. add a teacher mapping, add a room, reduce periods). Max 120 words."
)


def timetable_node(state: AgentState) -> dict:
    steps = ["TimetableAgent: loading master data (sections, subjects, teachers, rooms, slots)..."]

    # Reuse the constraints the admin last generated with (half-days, no
    # back-to-back, teacher caps) so chat regeneration doesn't silently drop them.
    db = SessionLocal()
    try:
        options = options_from_config(db)
    finally:
        db.close()
    result = generate_timetable(options=options)
    steps.append("TimetableAgent: CP-SAT solver executed "
                 f"({result.get('wall_time_s', '?')}s).")

    if result["status"] in ("optimal", "feasible"):
        steps.append(
            f"TimetableAgent: stored version {result['version']} — "
            f"{result['lessons']} lessons, teacher load gap {result['load_gap']}."
        )
        response = (
            f"Timetable generated successfully (version {result['version']}).\n"
            f"- {result['lessons']} lessons scheduled across {result['sections']} sections\n"
            f"- Provably clash-free (teachers, sections, rooms)\n"
            f"- Teacher weekly-load gap: {result['load_gap']} period(s)\n"
            f"- Solve time: {result['wall_time_s']}s\n"
            "View it in the Timetable tab."
        )
        return {"steps": steps, "final_response": response,
                "params": {**state.get("params", {}), **result}}

    # infeasible path — explain it
    reasons = result.get("reasons", ["Unknown solver failure."])
    steps.append(f"TimetableAgent: INFEASIBLE — {len(reasons)} reason(s) identified.")
    explanation = None
    if is_llm_configured():
        try:
            reply = get_llm(temperature=0.3).invoke(
                [("system", _EXPLAIN_SYSTEM), ("user", "\n".join(reasons))])
            explanation = reply.content if isinstance(reply.content, str) else str(reply.content)
            steps.append("TimetableAgent: composed plain-language explanation via LLM.")
        except Exception as exc:
            steps.append(f"TimetableAgent: LLM unavailable ({type(exc).__name__}), using raw reasons.")
    response = explanation or (
        "Timetable generation is currently impossible:\n- " + "\n- ".join(reasons)
    )
    return {"steps": steps, "final_response": response,
            "params": {**state.get("params", {}), "status": "infeasible"}}
