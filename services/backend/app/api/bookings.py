"""Bookings API — F3 Event & Venue Booking (docs/09-PHASE3-BOOKING-PLAN.md).

POST /bookings is a *deterministic* trigger: the form already carries the intent,
so it invokes the graph with a structured task_spec and the supervisor skips the
LLM (same pattern as leave-approval → Substitution Agent). The agent pauses on
its approval chain; this endpoint surfaces the paused card to the requester.
"""
import uuid
from datetime import date as date_t, datetime, time as time_t, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.graph import compiled_graph
from app.core.security import get_current_user, require_role
from app.db.models import Approval, Booking, Room, User
from app.db.session import get_db
from app.tools.booking import (
    VENUE_TYPES, booking_summary, calendar, cancel_booking, check_availability,
    find_alternatives, resolve_room,
)

router = APIRouter()

CATEGORIES = ["fest", "workshop", "seminar", "sports", "meeting", "event"]


class BookingIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: date_t
    start: time_t
    end: time_t
    headcount: int = Field(default=0, ge=0)
    room_id: int | None = None            # None = let the agent choose a venue
    description: str = ""
    category: str = "event"


def _validate(payload: BookingIn, db: Session) -> Room | None:
    if payload.end <= payload.start:
        raise HTTPException(422, "end must be after start")
    if payload.date < date_t.today():
        raise HTTPException(422, "date is in the past")
    if payload.category not in CATEGORIES:
        raise HTTPException(422, f"category must be one of {', '.join(CATEGORIES)}")
    room = None
    if payload.room_id is not None:
        room = db.get(Room, payload.room_id)
        if room is None:
            raise HTTPException(404, f"Room #{payload.room_id} not found")
    return room


@router.get("/venues")
def venues(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Room).order_by(Room.type, Room.name).all()
    return [{"id": r.id, "name": r.name, "type": r.type, "capacity": r.capacity}
            for r in rows
            if r.type in VENUE_TYPES]


@router.get("/availability")
def availability(date: date_t, start: time_t, end: time_t,
                 room_id: int | None = None, headcount: int = 0,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Live probe for the request form: is this venue free, and if not, what is?"""
    if end <= start:
        raise HTTPException(422, "end must be after start")
    room = db.get(Room, room_id) if room_id is not None else None
    if room_id is not None and room is None:
        raise HTTPException(404, f"Room #{room_id} not found")

    verdict = (check_availability(db, room, date, start, end, headcount)
               if room is not None else None)
    exclude = room.id if room else None
    prefer = room.type if room else None
    alts = find_alternatives(db, date, start, end, headcount,
                             exclude_room_id=exclude, prefer_type=prefer, limit=6)
    return {"requested": verdict, "alternatives": alts}


@router.post("")
def request_booking(payload: BookingIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Hand the request to the Booking Agent; it conflict-checks, may swap the
    venue, and pauses on the approval chain."""
    _validate(payload, db)

    thread_id = f"booking-{user.id}-{uuid.uuid4().hex[:8]}"
    state = {
        "messages": [{"role": "user",
                      "content": (f"Book a venue for '{payload.title}' on "
                                  f"{payload.date.isoformat()} "
                                  f"{payload.start.strftime('%H:%M')}–"
                                  f"{payload.end.strftime('%H:%M')} for "
                                  f"{payload.headcount} people.")}],
        "steps": [], "params": {}, "final_response": "",
        "current_action": "facility", "source": "user",
        "task_spec": {
            "user_id": user.id,
            "booking": {
                "title": payload.title,
                "date": payload.date.isoformat(),
                "start": payload.start.strftime("%H:%M:%S"),
                "end": payload.end.strftime("%H:%M:%S"),
                "headcount": payload.headcount,
                "room_id": payload.room_id,
                "description": payload.description,
                "category": payload.category,
            },
        },
    }
    result = compiled_graph.invoke(state, config={"configurable": {"thread_id": thread_id}})

    intr = result.get("__interrupt__")
    if intr:
        card = intr[0].value if hasattr(intr[0], "value") else intr[0]
        return {"status": "awaiting_approval", **card, "steps": result.get("steps", [])}
    # No interrupt: the agent couldn't place the request (no venue / bad window).
    return {"status": "not_booked", "response": result.get("final_response", ""),
            "steps": result.get("steps", [])}


def _visible(q, user: User):
    return q if user.role == "admin" else q.filter(Booking.requested_by == user.id)


@router.get("")
def list_bookings(status: str | None = None,
                  from_date: date_t | None = Query(None, alias="from"),
                  to_date: date_t | None = Query(None, alias="to"),
                  scope: str = "mine",
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Bookings the caller may see: their own, or everything for an admin.
    scope=all lets any user see the campus-wide list (read-only calendar data)."""
    q = db.query(Booking)
    if status:
        q = q.filter(Booking.status == status)
    if from_date:
        q = q.filter(Booking.date >= from_date)
    if to_date:
        q = q.filter(Booking.date <= to_date)
    if scope != "all":
        q = _visible(q, user)
    rows = q.order_by(Booking.date.desc(), Booking.start).all()
    return [booking_summary(db, b.id) for b in rows]


@router.get("/calendar")
def campus_calendar(from_date: date_t | None = Query(None, alias="from"),
                    to_date: date_t | None = Query(None, alias="to"),
                    include_pending: bool = True,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Campus calendar feed for a date range (defaults to the coming 4 weeks)."""
    start = from_date or date_t.today()
    end = to_date or (start + timedelta(days=27))
    if end < start:
        raise HTTPException(422, "'to' must be on or after 'from'")
    statuses = ("pending", "approved") if include_pending else ("approved",)
    return {"from": start.isoformat(), "to": end.isoformat(),
            "events": calendar(db, start, end, statuses)}


@router.get("/{booking_id}")
def get_booking(booking_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "Booking not found")
    if user.role != "admin" and b.requested_by != user.id:
        raise HTTPException(403, "Not your booking")
    return booking_summary(db, booking_id)


@router.post("/{booking_id}/cancel")
def cancel(booking_id: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    """Organiser or admin releases the venue. Any pending approval card is
    cancelled with it — the paused graph thread simply never resumes."""
    b = db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "Booking not found")
    if user.role != "admin" and b.requested_by != user.id:
        raise HTTPException(403, "Not your booking")
    if b.status in ("cancelled", "rejected"):
        raise HTTPException(409, f"Booking already {b.status}")
    return cancel_booking(db, booking_id, user)
