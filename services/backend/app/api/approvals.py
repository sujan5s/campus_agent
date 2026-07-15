"""Approvals API — the human side of human-in-the-loop (docs/02-ARCHITECTURE.md).

GET lists pending approval cards. POST /{id}/decide resumes the LangGraph
thread stored on the approval row, injecting the human's decision into the
paused interrupt() — the agent then applies or discards its plan.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.graph import compiled_graph
from app.core.security import get_current_user, require_role
from app.db.models import Approval, User
from app.db.session import get_db
from app.tools.exchange import plan_summary

router = APIRouter()


class DecisionIn(BaseModel):
    action: str  # approve | reject


@router.get("", dependencies=[Depends(require_role("admin"))])
def list_approvals(status: str = "pending", db: Session = Depends(get_db)):
    rows = (db.query(Approval).filter(Approval.status == status)
            .order_by(Approval.id.desc()).all())
    out = []
    for a in rows:
        item = {"id": a.id, "kind": a.kind, "ref_id": a.ref_id, "status": a.status,
                "decided_at": a.decided_at.isoformat() if a.decided_at else None}
        if a.kind == "substitution_plan":
            item["plan"] = plan_summary(db, a.ref_id)
        out.append(item)
    return out


@router.post("/{approval_id}/decide", dependencies=[Depends(require_role("admin"))])
def decide(approval_id: int, payload: DecisionIn, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    a = db.get(Approval, approval_id)
    if a is None:
        raise HTTPException(404, "Approval not found")
    if a.status != "pending":
        raise HTTPException(409, f"Already {a.status}")
    if payload.action not in ("approve", "reject"):
        raise HTTPException(422, "action must be approve | reject")
    if not a.langgraph_thread_id:
        raise HTTPException(500, "Approval has no workflow thread to resume")

    # ---- resume the paused graph exactly where interrupt() stopped it ----
    result = compiled_graph.invoke(
        Command(resume={"action": payload.action}),
        config={"configurable": {"thread_id": a.langgraph_thread_id}},
    )

    a.status = "approved" if payload.action == "approve" else "rejected"
    a.approver_id = user.id
    a.decided_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "approval_id": a.id,
        "status": a.status,
        "agent_response": result.get("final_response", ""),
        "steps": result.get("steps", []),
    }
