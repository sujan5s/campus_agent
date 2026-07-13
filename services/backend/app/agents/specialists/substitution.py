"""Substitution Agent — the F2 flagship (docs/01-FEATURES.md, research/04+07).

Triggered proactively when a leave is approved (no human prompt). Builds a
minimal-perturbation cover plan, then PAUSES via LangGraph interrupt() until
the HOD approves — the checkpointer stores the paused thread; the Approval row
stores the thread id. POST /api/approvals/{id}/decide resumes this exact node.

NOTE on idempotency: after resume, LangGraph re-executes this node from the
top, so every step before interrupt() must be safe to run twice. build_plan()
and the Approval upsert both check for existing rows.
"""
import re

from langgraph.types import interrupt

from app.agents.state import AgentState
from app.db.models import Approval, Leave
from app.db.session import SessionLocal
from app.tools.substitution import (
    apply_plan, build_plan, plan_summary, reject_plan,
)


def _extract_leave_id(state: AgentState) -> int | None:
    spec = state.get("task_spec") or {}
    if spec.get("leave_id"):
        return int(spec["leave_id"])
    msgs = state.get("messages") or []
    text = ""
    for m in reversed(msgs):
        text = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if text:
            break
    m = re.search(r"leave\s*#?(\d+)", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def substitution_node(state: AgentState, config) -> dict:
    steps = ["SubstitutionAgent: activated by leave-approval event."]
    thread_id = (config.get("configurable") or {}).get("thread_id")

    leave_id = _extract_leave_id(state)
    if leave_id is None:
        return {"steps": steps + ["SubstitutionAgent: no leave id found in request."],
                "final_response": "I couldn't identify which leave to plan for. "
                                  "Trigger me via a leave approval, or say e.g. 'plan substitutions for leave #3'."}

    db = SessionLocal()
    try:
        leave = db.get(Leave, leave_id)
        if leave is None:
            return {"steps": steps + [f"SubstitutionAgent: leave #{leave_id} not found."],
                    "final_response": f"Leave #{leave_id} does not exist."}
        if leave.status != "approved":
            return {"steps": steps + [f"SubstitutionAgent: leave #{leave_id} is '{leave.status}', not approved."],
                    "final_response": f"Leave #{leave_id} is not approved yet — nothing to plan."}

        rows = build_plan(db, leave)   # idempotent
        summary = plan_summary(db, leave_id)
        steps.append(f"SubstitutionAgent: {summary['lessons_affected']} lesson(s) affected; "
                     f"{summary['covered']} covered by ranked candidates "
                     "(subject match > same dept > free, workload-weighted).")

        if not rows:
            return {"steps": steps,
                    "final_response": (f"Leave approved for {summary['teacher']} "
                                       f"({summary['from_date']} → {summary['to_date']}). "
                                       "No scheduled classes fall in this window — no substitutions needed."),
                    "params": summary}

        # Approval record (idempotent) so the HOD sees a card + we can resume
        approval = db.query(Approval).filter(
            Approval.kind == "substitution_plan",
            Approval.ref_id == leave_id,
            Approval.status == "pending").first()
        if approval is None:
            approval = Approval(kind="substitution_plan", ref_id=leave_id,
                                status="pending", langgraph_thread_id=thread_id)
            db.add(approval)
            db.commit()
            db.refresh(approval)
        steps.append(f"SubstitutionAgent: plan awaiting human approval (approval #{approval.id}) — pausing.")
    finally:
        db.close()

    # ---- HUMAN-IN-THE-LOOP: graph pauses here until /approvals/{id}/decide ----
    decision = interrupt({
        "type": "substitution_plan",
        "approval_id": approval.id,
        "plan": summary,
    })

    # ---- resumed with the human's decision ----
    db = SessionLocal()
    try:
        action = (decision or {}).get("action", "reject")
        if action == "approve":
            result = apply_plan(db, leave_id)
            steps.append(f"SubstitutionAgent: plan approved — {result['applied']} substitution(s) "
                         f"confirmed, {result['notified']} teacher(s) notified.")
            response = (
                f"Substitution plan for {summary['teacher']}'s leave is now in effect.\n"
                f"- {result['applied']} lesson(s) reassigned, {summary['covered']} covered\n"
                f"- {result['notified']} substitute teacher(s) notified in their inbox\n"
                f"- {summary['teacher']} has been informed their classes are covered"
            )
        else:
            reject_plan(db, leave_id)
            steps.append("SubstitutionAgent: plan rejected by approver — substitutions discarded.")
            response = ("The substitution plan was rejected. The affected classes remain "
                        "uncovered — an admin can re-trigger planning or arrange cover manually.")
        return {"steps": steps, "final_response": response,
                "params": {**summary, "decision": action}}
    finally:
        db.close()
