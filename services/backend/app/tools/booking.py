"""Booking tools — F3 Event & Venue Booking (docs/09-PHASE3-BOOKING-PLAN.md).

Typed tools only: the Booking Agent calls these, they own the SQL. The one idea
that makes this more than a form is `_class_conflicts` — a venue occupied by a
scheduled class is NOT free, so availability is checked against the live
timetable as well as against other bookings.

Idempotency contract: the agent node re-executes from the top on every
interrupt-resume (same as tools/exchange.py), so `create_request` is keyed by
`request_key` (the graph thread id) and never writes a second row.
"""
import re
from datetime import date as date_t, datetime, time as time_t, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Booking, Event, Notification, Room, TimeSlot, TimetableEntry, User,
)
from app.tools.substitution import WEEKDAY_TO_DAY
from app.tools.timetable import latest_version

# Venue types that can host an event, in the order we'd suggest them.
VENUE_TYPES = ["auditorium", "seminar", "classroom", "lab", "ground"]

# Words in a request that hint at a venue type when no venue is named.
TYPE_HINTS = {
    "auditorium": "auditorium", "audi": "auditorium",
    "seminar": "seminar", "hall": "seminar",
    "lab": "lab", "laboratory": "lab",
    "ground": "ground", "field": "ground", "sports": "ground",
    "classroom": "classroom", "class room": "classroom", "lecture": "classroom",
}


def _mins(t: time_t) -> int:
    return t.hour * 60 + t.minute


def _overlaps(a_start: time_t, a_end: time_t, b_start: time_t, b_end: time_t) -> bool:
    """Half-open overlap: [09:00,10:00) and [10:00,11:00) do NOT clash."""
    return _mins(a_start) < _mins(b_end) and _mins(b_start) < _mins(a_end)


def _hhmm(t: time_t) -> str:
    return t.strftime("%H:%M")


def window_str(start: time_t, end: time_t) -> str:
    return f"{_hhmm(start)}–{_hhmm(end)}"


# --- conflict detection -------------------------------------------------------

def _class_conflicts(db: Session, room_id: int, on_date: date_t,
                     start: time_t, end: time_t) -> list[dict]:
    """Scheduled classes that occupy this room during the window.

    The academic timetable is weekly (MON..FRI × periods), so a date maps to a
    weekday and then to the timeslots overlapping the requested window. Weekends
    have no timeslots -> no class conflicts, which is correct."""
    day = WEEKDAY_TO_DAY.get(on_date.weekday())
    if day is None:
        return []
    ver = latest_version(db)
    if ver is None:
        return []

    slots = db.query(TimeSlot).filter(TimeSlot.day == day).all()
    hit_ids = [s.id for s in slots if _overlaps(start, end, s.start, s.end)]
    if not hit_ids:
        return []

    entries = (db.query(TimetableEntry)
               .filter(TimetableEntry.version == ver,
                       TimetableEntry.status == "active",
                       TimetableEntry.room_id == room_id,
                       TimetableEntry.timeslot_id.in_(hit_ids))
               .all())
    return [{
        "kind": "class",
        "what": f"{e.subject.code} · {e.section.name}",
        "who": e.teacher.user.name,
        "window": window_str(e.timeslot.start, e.timeslot.end),
        "detail": (f"{e.subject.code} ({e.section.name}) with {e.teacher.user.name} "
                   f"is scheduled here {day} P{e.timeslot.period_no} "
                   f"{window_str(e.timeslot.start, e.timeslot.end)}"),
    } for e in entries]


def _booking_conflicts(db: Session, room_id: int, on_date: date_t,
                       start: time_t, end: time_t,
                       exclude_booking_id: int | None = None) -> list[dict]:
    """Other reservations holding this room. Pending counts as held — first come,
    first served; we don't double-promise a venue while a chain is in flight."""
    q = (db.query(Booking)
         .filter(Booking.room_id == room_id,
                 Booking.date == on_date,
                 Booking.status.in_(["pending", "approved"])))
    if exclude_booking_id is not None:
        q = q.filter(Booking.id != exclude_booking_id)
    out = []
    for b in q.all():
        if not _overlaps(start, end, b.start, b.end):
            continue
        title = b.event.title if b.event else "Reserved"
        out.append({
            "kind": "booking",
            "what": title,
            "who": (b.event.organizer.name if b.event and b.event.organizer else "—"),
            "window": window_str(b.start, b.end),
            "detail": (f"'{title}' is already {b.status} here "
                       f"{window_str(b.start, b.end)} (booking #{b.id})"),
        })
    return out


def check_availability(db: Session, room: Room, on_date: date_t, start: time_t,
                       end: time_t, headcount: int = 0,
                       exclude_booking_id: int | None = None) -> dict:
    """Full verdict for one venue: clashes (classes + bookings) and capacity fit."""
    conflicts = (_class_conflicts(db, room.id, on_date, start, end)
                 + _booking_conflicts(db, room.id, on_date, start, end, exclude_booking_id))
    capacity_ok = headcount <= room.capacity
    return {
        "room_id": room.id,
        "room": room.name,
        "type": room.type,
        "capacity": room.capacity,
        "date": on_date.isoformat(),
        "window": window_str(start, end),
        "conflicts": conflicts,
        "capacity_ok": capacity_ok,
        "capacity_note": (None if capacity_ok else
                          f"{room.name} seats {room.capacity}, {headcount} expected"),
        "available": not conflicts and capacity_ok,
    }


# --- venue selection ----------------------------------------------------------

def find_alternatives(db: Session, on_date: date_t, start: time_t, end: time_t,
                      headcount: int = 0, exclude_room_id: int | None = None,
                      prefer_type: str | None = None, limit: int = 4) -> list[dict]:
    """Free venues that fit, tightest capacity first.

    Tightest-fit matters: a 30-person club meeting should not be handed the
    500-seat auditorium just because it happens to be free."""
    rooms = db.query(Room).all()
    out = []
    for r in rooms:
        if exclude_room_id is not None and r.id == exclude_room_id:
            continue
        verdict = check_availability(db, r, on_date, start, end, headcount)
        if not verdict["available"]:
            continue
        out.append({
            **{k: verdict[k] for k in ("room_id", "room", "type", "capacity")},
            "headroom": r.capacity - headcount,
            "why": (f"seats {r.capacity}"
                    + (f" ({r.capacity - headcount} spare)" if headcount else "")
                    + ", free for the whole window"),
        })
    out.sort(key=lambda a: (0 if prefer_type and a["type"] == prefer_type else 1,
                            a["headroom"], a["room"]))
    return out[:limit]


def resolve_room(db: Session, name: str | None) -> Room | None:
    """Fuzzy venue lookup: exact, then substring either way, then token match."""
    if not name:
        return None
    wanted = name.strip().lower()
    rooms = db.query(Room).all()
    for r in rooms:
        if r.name.lower() == wanted:
            return r
    for r in rooms:
        rl = r.name.lower()
        if wanted in rl or rl in wanted:
            return r
    tokens = [t for t in wanted.replace("-", " ").split() if len(t) > 2]
    for r in rooms:
        rl = r.name.lower()
        if tokens and all(t in rl for t in tokens):
            return r
    return None


def _name_tokens(room: Room) -> set[str]:
    """Text fragments that reliably identify a venue. A bare '2' from 'CS Lab 2'
    is NOT one of them — it would match the '2' in '2-5pm'. Short and
    single-digit tokens are dropped; '302' from 'LT-302' is kept."""
    rl = room.name.lower()
    candidates = {rl, rl.split()[-1], rl.split("-")[-1]}
    return {c for c in candidates
            if len(c) >= 3 or (c.isdigit() and len(c) >= 3)}


def resolve_room_in_text(db: Session, text: str) -> Room | None:
    """Find a venue named anywhere inside a free-text request. The longest
    matching fragment wins, so 'Main Auditorium' beats a stray substring."""
    if not text:
        return None
    t = text.lower()
    best: tuple[int, Room] | None = None
    for r in db.query(Room).all():
        for tok in _name_tokens(r):
            if re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", t):
                if best is None or len(tok) > best[0]:
                    best = (len(tok), r)
    return best[1] if best else None


def type_hint_from_text(text: str) -> str | None:
    t = (text or "").lower()
    for word, vtype in TYPE_HINTS.items():
        if word in t:
            return vtype
    return None


def choose_venue(db: Session, *, requested: Room | None, on_date: date_t,
                 start: time_t, end: time_t, headcount: int,
                 prefer_type: str | None = None) -> dict:
    """Pick the venue to book: the requested one if it works, else the best
    alternative. Returns the chosen room, a human rationale, and what was
    rejected — the agent quotes all three back to the requester."""
    requested_verdict = None
    if requested is not None:
        requested_verdict = check_availability(db, requested, on_date, start, end, headcount)
        if requested_verdict["available"]:
            return {
                "room": requested, "rationale":
                    f"{requested.name} is free {window_str(start, end)} on "
                    f"{on_date.isoformat()} — no class and no other booking overlaps, "
                    f"and it seats {requested.capacity}.",
                "requested_verdict": requested_verdict, "alternatives": [],
                "substituted": False,
            }

    prefer = prefer_type or (requested.type if requested else None)
    alts = find_alternatives(db, on_date, start, end, headcount,
                             exclude_room_id=requested.id if requested else None,
                             prefer_type=prefer)
    if not alts:
        return {"room": None, "rationale": "", "requested_verdict": requested_verdict,
                "alternatives": [], "substituted": False}

    best = db.get(Room, alts[0]["room_id"])
    if requested is None and prefer:
        rationale = (f"You asked for a{'n' if prefer[0] in 'aeiou' else ''} {prefer}; "
                     f"{best.name} is the best fit — {alts[0]['why']}.")
    elif requested is None:
        rationale = (f"No specific venue was named, so I picked {best.name} — "
                     f"{alts[0]['why']}.")
    else:
        blockers = requested_verdict["conflicts"]
        reason = (blockers[0]["detail"] if blockers
                  else requested_verdict["capacity_note"])
        rationale = (f"{requested.name} won't work: {reason}. "
                     f"{best.name} is the closest fit — {alts[0]['why']}.")
    return {"room": best, "rationale": rationale,
            "requested_verdict": requested_verdict,
            "alternatives": alts, "substituted": requested is not None}


# --- approval chain -----------------------------------------------------------

def faculty_advisor_for(db: Session, organizer: User) -> User | None:
    """A student's advisor = the teacher who takes the most periods for that
    student's section in the active timetable. Falls back to any faculty user."""
    ver = latest_version(db)
    if organizer.section_id and ver is not None:
        entries = (db.query(TimetableEntry)
                   .filter(TimetableEntry.version == ver,
                           TimetableEntry.status == "active",
                           TimetableEntry.section_id == organizer.section_id)
                   .all())
        counts: dict[int, int] = {}
        for e in entries:
            counts[e.teacher_id] = counts.get(e.teacher_id, 0) + 1
        if counts:
            top = max(counts.items(), key=lambda kv: kv[1])[0]
            entry = next(e for e in entries if e.teacher_id == top)
            return entry.teacher.user
    return db.query(User).filter(User.role == "faculty").order_by(User.id).first()


def approval_chain_for(db: Session, organizer: User) -> list[str]:
    """Student requests need a faculty advisor sign-off before the admin sees
    them; staff requests go straight to the admin (docs/01-FEATURES.md F3)."""
    if organizer.role == "student":
        return ["booking_faculty", "booking_admin"]
    return ["booking_admin"]


def approver_for(db: Session, stage: str, organizer: User) -> User | None:
    if stage == "booking_faculty":
        return faculty_advisor_for(db, organizer)
    return db.query(User).filter(User.role == "admin").order_by(User.id).first()


STAGE_LABEL = {"booking_faculty": "Faculty advisor", "booking_admin": "Administration"}


# --- writes -------------------------------------------------------------------

def find_request(db: Session, request_key: str | None) -> Booking | None:
    """The booking this graph thread already created, if any."""
    if not request_key:
        return None
    return (db.query(Booking).filter(Booking.request_key == request_key)
            .order_by(Booking.id.desc()).first())


def create_request(db: Session, *, request_key: str | None, organizer: User,
                   room: Room, on_date: date_t, start: time_t, end: time_t,
                   title: str, description: str = "", headcount: int = 0,
                   category: str = "event", purpose: str = "",
                   rationale: str = "") -> Booking:
    """Create the Event + pending Booking. Idempotent on `request_key` so a
    resumed graph node never books the same venue twice."""
    existing = find_request(db, request_key)
    if existing is not None:
        return existing

    ev = Event(title=title.strip() or "Campus event", organizer_id=organizer.id,
               description=description.strip(), expected_headcount=headcount,
               category=category)
    db.add(ev)
    db.flush()
    b = Booking(event_id=ev.id, room_id=room.id, date=on_date, start=start, end=end,
                status="pending", requested_by=organizer.id,
                purpose=purpose.strip() or description.strip(), rationale=rationale,
                request_key=request_key)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def booking_summary(db: Session, booking_id: int) -> dict:
    """Payload for the approval card and the agent's response."""
    from app.db.models import Approval  # local import: avoids a cycle at module load

    b = db.get(Booking, booking_id)
    if b is None:
        return {"error": f"Booking #{booking_id} not found"}
    room = db.get(Room, b.room_id)
    ev = b.event
    organizer = db.get(User, b.requested_by) if b.requested_by else None

    stages = []
    for a in (db.query(Approval)
              .filter(Approval.kind.in_(["booking_faculty", "booking_admin"]),
                      Approval.ref_id == b.id)
              .order_by(Approval.id).all()):
        approver = db.get(User, a.approver_id) if a.approver_id else None
        stages.append({"approval_id": a.id, "kind": a.kind,
                       "label": STAGE_LABEL.get(a.kind, a.kind),
                       "status": a.status,
                       "approver": approver.name if approver else None,
                       "decided_at": a.decided_at.isoformat() if a.decided_at else None})

    return {
        "booking_id": b.id,
        "title": ev.title if ev else "Campus event",
        "description": ev.description if ev else "",
        "category": ev.category if ev else "event",
        "headcount": ev.expected_headcount if ev else 0,
        "organizer": organizer.name if organizer else "—",
        "organizer_role": organizer.role if organizer else "—",
        "venue": room.name if room else "?",
        "venue_type": room.type if room else "?",
        "capacity": room.capacity if room else 0,
        "date": b.date.isoformat(),
        "window": window_str(b.start, b.end),
        "status": b.status,
        "purpose": b.purpose,
        "rationale": b.rationale,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "chain": stages,
    }


def _notify(db: Session, user_id: int | None, title: str, body: str) -> int:
    if not user_id:
        return 0
    db.add(Notification(user_id=user_id, title=title, body=body))
    return 1


def confirm_booking(db: Session, booking_id: int) -> dict:
    """Final approval: hold the venue and tell everyone who needs to know."""
    b = db.get(Booking, booking_id)
    if b is None:
        return {"error": f"Booking #{booking_id} not found"}
    if b.status != "approved":
        b.status = "approved"
    s = booking_summary(db, booking_id)
    notified = _notify(
        db, b.requested_by, "Venue booking confirmed",
        (f"'{s['title']}' is confirmed in {s['venue']} on {s['date']}, "
         f"{s['window']} ({s['headcount']} expected).\n"
         "It now appears on the campus calendar."))
    for admin in db.query(User).filter(User.role == "admin").all():
        if admin.id != b.requested_by:
            notified += _notify(
                db, admin.id, "Campus calendar updated",
                (f"'{s['title']}' ({s['organizer']}) booked {s['venue']} on "
                 f"{s['date']}, {s['window']}."))
    db.commit()
    return {"booking_id": b.id, "status": b.status, "notified": notified, "summary": s}


def reject_booking(db: Session, booking_id: int, stage: str = "booking_admin",
                   reason: str = "") -> dict:
    b = db.get(Booking, booking_id)
    if b is None:
        return {"error": f"Booking #{booking_id} not found"}
    b.status = "rejected"
    s = booking_summary(db, booking_id)
    who = STAGE_LABEL.get(stage, "The approver")
    notified = _notify(
        db, b.requested_by, "Venue booking declined",
        (f"'{s['title']}' ({s['venue']}, {s['date']} {s['window']}) was declined by "
         f"{who.lower()}." + (f"\nReason: {reason}" if reason else "")
         + "\nThe venue has been released — you can request a different slot."))
    db.commit()
    return {"booking_id": b.id, "status": b.status, "notified": notified, "summary": s}


def cancel_booking(db: Session, booking_id: int, by_user: User) -> dict:
    b = db.get(Booking, booking_id)
    if b is None:
        return {"error": f"Booking #{booking_id} not found"}
    b.status = "cancelled"
    from app.db.models import Approval

    (db.query(Approval)
     .filter(Approval.kind.in_(["booking_faculty", "booking_admin"]),
             Approval.ref_id == b.id, Approval.status == "pending")
     .update({"status": "cancelled",
              "decided_at": datetime.now(timezone.utc)}, synchronize_session=False))
    s = booking_summary(db, booking_id)
    notified = 0
    if b.requested_by and b.requested_by != by_user.id:
        notified += _notify(db, b.requested_by, "Venue booking cancelled",
                            f"'{s['title']}' ({s['venue']}, {s['date']} "
                            f"{s['window']}) was cancelled by {by_user.name}.")
    db.commit()
    return {"booking_id": b.id, "status": b.status, "notified": notified, "summary": s}


# --- calendar + nag sweep -----------------------------------------------------

def calendar(db: Session, from_date: date_t, to_date: date_t,
             statuses: tuple[str, ...] = ("pending", "approved")) -> list[dict]:
    """Campus calendar feed: every booking in a date range, venue-resolved."""
    rows = (db.query(Booking)
            .filter(Booking.date >= from_date, Booking.date <= to_date,
                    Booking.status.in_(list(statuses)))
            .order_by(Booking.date, Booking.start).all())
    out = []
    for b in rows:
        room = db.get(Room, b.room_id)
        organizer = db.get(User, b.requested_by) if b.requested_by else None
        out.append({
            "booking_id": b.id,
            "title": b.event.title if b.event else "Reserved",
            "category": b.event.category if b.event else "event",
            "headcount": b.event.expected_headcount if b.event else 0,
            "organizer": organizer.name if organizer else "—",
            "venue": room.name if room else "?",
            "venue_type": room.type if room else "?",
            "date": b.date.isoformat(),
            "start": _hhmm(b.start), "end": _hhmm(b.end),
            "window": window_str(b.start, b.end),
            "status": b.status,
        })
    return out


def pending_nags(db: Session, hours: int = 24) -> list[tuple[Booking, "object"]]:
    """(booking, approval) pairs whose current stage has been waiting too long
    and hasn't been nagged inside the same window."""
    from app.db.models import Approval

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=hours)
    # Re-nag window is at least an hour even when hours=0 (the demo setting),
    # so a 30-minute sweep can't spam the same approver every tick.
    renag_cutoff = now - timedelta(hours=max(hours, 1))
    out = []
    for b in db.query(Booking).filter(Booking.status == "pending").all():
        if b.created_at and b.created_at > cutoff:
            continue
        if b.last_nag_at and b.last_nag_at > renag_cutoff:
            continue
        a = (db.query(Approval)
             .filter(Approval.kind.in_(["booking_faculty", "booking_admin"]),
                     Approval.ref_id == b.id, Approval.status == "pending")
             .order_by(Approval.id).first())
        if a is not None:
            out.append((b, a))
    return out


def send_nag(db: Session, booking: Booking, approval) -> int:
    """One reminder to the stage's approver. Records last_nag_at so the sweep
    reminds once per window, not once per sweep tick."""
    s = booking_summary(db, booking.id)
    waiting = ""
    if booking.created_at:
        hrs = int((datetime.now(timezone.utc).replace(tzinfo=None)
                   - booking.created_at).total_seconds() // 3600)
        waiting = f" It has been waiting {hrs}h."
    sent = _notify(
        db, approval.approver_id, "Booking approval still pending",
        (f"'{s['title']}' ({s['organizer']}) needs your decision: {s['venue']} on "
         f"{s['date']}, {s['window']}.{waiting}\nOpen Approvals to approve or decline."))
    booking.last_nag_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return sent
