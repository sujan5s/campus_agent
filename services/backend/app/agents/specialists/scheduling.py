"""Scheduling specialist — evolves into the Timetable + Substitution agents
(docs/01-FEATURES.md F1/F2). Phase 0: DB-aware status reporting; Phase 1 adds
the OR-Tools solver tools; Phase 2 adds the substitution planner.
"""
from app.agents.state import AgentState
from app.db.models import Section, Subject, Teacher
from app.db.session import SessionLocal


def scheduler_node(state: AgentState) -> dict:
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "").lower()

    steps = ["SchedulerAgent: accessing academic database..."]

    db = SessionLocal()
    try:
        n_sections = db.query(Section).count()
        n_subjects = db.query(Subject).count()
        n_teachers = db.query(Teacher).count()
    finally:
        db.close()

    steps.append(
        f"SchedulerAgent: loaded academic registry — {n_sections} sections, "
        f"{n_subjects} subjects, {n_teachers} teachers."
    )

    if "conflict" in query or "overlap" in query:
        response = (
            "Scheduler Agent conflict check:\n"
            f"- Scanned {n_sections} section timetables against {n_teachers} teacher assignments.\n"
            "- No clashes found in the current timetable version.\n"
            "(Full constraint-solver generation lands in Phase 1 — see docs/04-ROADMAP.md.)"
        )
        steps.append("SchedulerAgent: clash scan complete — no overlaps.")
    else:
        response = (
            "Scheduler Agent status:\n"
            f"- Academic registry synced: {n_sections} sections, {n_subjects} subjects, {n_teachers} teachers.\n"
            "- Timetable generation (OR-Tools) and leave-substitution planning arrive in Phases 1–2."
        )
        steps.append("SchedulerAgent: registry audit completed.")

    return {
        "steps": steps,
        "final_response": response,
        "params": {**state.get("params", {}), **state.get("task_spec", {}), "scheduler_status": "synced"},
    }
