"""Notification API — in-app inbox (Notification Agent v1, Phase 2).

Frontend polls GET /api/notifications; WebSocket push is a Phase 3 upgrade.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Notification, User
from app.db.session import get_db

router = APIRouter()


@router.get("")
def list_notifications(db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    rows = (db.query(Notification).filter(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc()).limit(50).all())
    return [{
        "id": n.id, "title": n.title, "body": n.body,
        "read": n.read, "created_at": n.created_at.isoformat(),
    } for n in rows]


@router.get("/unread_count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.user_id == user.id,
                                      Notification.read.is_(False)).count()
    return {"unread": n}


@router.post("/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.read = True
    db.commit()
    return {"ok": True}
