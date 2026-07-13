"""Leave API — apply (faculty), list, decide (admin).

Approving a leave is the PROACTIVE TRIGGER for the Substitution Agent
(docs/02-ARCHITECTURE.md): the API immediately invokes the agent graph with a
system-sourced message; the agent plans cover and pauses for HOD approval.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.graph import compiled_graph
from app.core.security import get_current_user, require_role
from app.db.models import Leave, Teacher, User
from app.db.session import get_db

router = APIRouter()


class LeaveIn(BaseModel):
    from_date: date
    to_date: date
    reason: str


class DecisionIn(BaseModel):
    action: str  # approve | reject


def _leave_out(db: Session, lv: Leave) -> dict:
    t = db.get(Teacher, lv.teacher_id)
    return {
        "id": lv.id,
        "teacher_id": lv.teacher_id,
        "teacher": t.user.name if t else "?",
        "from_date": lv.from_date.isoformat(),
        "to_date": lv.to_date.isoformat(),
        "reason": lv.reason,
        "status": lv.status,
        "created_at": lv.created_at.isoformat(),
    }


@router.post("")
def apply_leave(payload: LeaveIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
    if teacher is None:
        raise HTTPException(403, "Only faculty members can apply for leave")
    if payload.to_date < payload.from_date:
        raise HTTPException(422, "to_date must be on or after from_date")
    lv = Leave(teacher_id=teacher.id, from_date=payload.from_date,
               to_date=payload.to_date, reason=payload.reason.strip())
    db.add(lv)
    db.commit()
    db.refresh(lv)
    return _leave_out(db, lv)


@router.get("")
def list_leaves(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Leave).order_by(Leave.created_at.desc())
    if user.role != "admin":
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher is None:
            return []
        q = q.filter(Leave.teacher_id == teacher.id)
    return [_leave_out(db, lv) for lv in q.all()]


@router.post("/{leave_id}/decide", dependencies=[Depends(require_role("admin"))])
def decide_leave(leave_id: int, payload: DecisionIn, db: Session = Depends(get_db)):
    lv = db.get(Leave, leave_id)
    if lv is None:
        raise HTTPException(404, "Leave not found")
    if lv.status != "pending":
        raise HTTPException(409, f"Leave already {lv.status}")
    if payload.action not in ("approve", "reject"):
        raise HTTPException(422, "action must be approve | reject")

    lv.status = "approved" if payload.action == "approve" else "rejected"
    db.commit()

    if lv.status == "rejected":
        return {"leave": _leave_out(db, lv), "agent": None}

    # ---- proactive trigger: leave approved -> Substitution Agent, no prompt ----
    thread_id = f"leave-{lv.id}-{uuid.uuid4().hex[:8]}"
    state = {
        "messages": [{"role": "user",
                      "content": f"Plan substitutions for approved leave #{lv.id}"}],
        "steps": [], "params": {}, "final_response": "",
        "current_action": "general", "source": "system",
        "task_spec": {"leave_id": lv.id},
    }
    result = compiled_graph.invoke(
        state, config={"configurable": {"thread_id": thread_id}})

    # The agent normally pauses at interrupt() — surface the plan it proposed
    intr = result.get("__interrupt__")
    if intr:
        payload_out = intr[0].value if hasattr(intr[0], "value") else intr[0]
        return {"leave": _leave_out(db, lv),
                "agent": {"status": "awaiting_approval", **payload_out,
                          "steps": result.get("steps", [])}}
    return {"leave": _leave_out(db, lv),
            "agent": {"status": "done",
                      "response": result.get("final_response", ""),
                      "steps": result.get("steps", [])}}
