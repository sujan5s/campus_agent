"""Booking Agent — F3 Event & Venue Booking (docs/09-PHASE3-BOOKING-PLAN.md).

Two ways in, one node:
  * the /bookings form  — a structured, already-validated request (no LLM needed)
  * free-text chat      — "Need the auditorium on 21 Aug, 2-5pm, ~120 people"

It checks the venue against other bookings AND the live class timetable, swaps in
the best alternative when the requested venue fails, then PAUSES on an approval
chain via LangGraph interrupt(): student requests need a faculty advisor and then
an admin; staff requests need only an admin. Each stage resumes on the same
durable thread from POST /api/approvals/{id}/decide.

IDEMPOTENCY: the node re-executes from the top on every resume, so the Booking
row is keyed by request_key (the thread id) and Approval rows by (kind, ref_id).
"""
import re
from datetime import date as date_t, datetime, time as time_t, timedelta

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.core.llm import get_llm, is_llm_configured
from app.db.models import Approval, Room, User
from app.db.session import SessionLocal
from app.tools.booking import (
    STAGE_LABEL, approval_chain_for, approver_for, booking_summary, cancel_booking,
    check_availability, choose_venue, confirm_booking, create_request,
    find_alternatives, find_request, reject_booking, resolve_room,
    resolve_room_in_text, type_hint_from_text, window_str,
)

BOOK_VERBS = ("book", "reserve", "reservation", "need the", "want the", "hold the",
              "schedule the", "arrange the", "get the", "use the", "have the")

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}


class BookingRequest(BaseModel):
    """Structured booking fields the LLM pulls out of a free-text request."""

    venue: str | None = Field(None, description="Venue/room name asked for, verbatim, if any")
    date: str | None = Field(None, description="Event date as YYYY-MM-DD if it can be resolved, else as said")
    start_time: str | None = Field(None, description="Start time as 24h HH:MM")
    end_time: str | None = Field(None, description="End time as 24h HH:MM")
    headcount: int | None = Field(None, description="Expected number of attendees")
    title: str | None = Field(None, description="Short event title, e.g. 'Coding Club Hackathon'")
    category: str | None = Field(None, description="One of: fest, workshop, seminar, sports, meeting, event")
    intent: str = Field("book", description="'book' to reserve, 'check' to only ask about availability")


# --- parsing helpers ----------------------------------------------------------

def _forward(day: int, month: int, today: date_t) -> date_t | None:
    """A bare day+month resolves to the next such date, never a past one."""
    for year in (today.year, today.year + 1):
        try:
            candidate = date_t(year, month, day)
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def _parse_date(text: str | None, today: date_t) -> date_t | None:
    """ISO, '21 Aug', 'Aug 21', 'tomorrow', 'next friday' -> a date."""
    if not text:
        return None
    t = text.strip().lower()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return date_t(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if "today" in t:
        return today
    if "tomorrow" in t:
        return today + timedelta(days=1)
    m = re.search(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([a-z]{3,9})", t)
    if not m:
        m2 = re.search(r"([a-z]{3,9})\s+(\d{1,2})", t)
        if m2 and m2.group(1)[:3] in _MONTHS:
            m = None
            day, mon = int(m2.group(2)), _MONTHS[m2.group(1)[:3]]
            return _forward(day, mon, today)
    if m and m.group(2)[:3] in _MONTHS:
        return _forward(int(m.group(1)), _MONTHS[m.group(2)[:3]], today)
    for name, idx in _WEEKDAYS.items():
        if name in t:
            ahead = (idx - today.weekday()) % 7 or 7
            return today + timedelta(days=ahead)
    return None


def _parse_clock(raw: str, meridiem: str | None, other_meridiem: str | None) -> time_t | None:
    """'2', '2:30', '14:00' + an am/pm hint -> a time. Campus-day heuristic:
    a bare 1-7 with no meridiem means the afternoon."""
    raw = raw.strip()
    if ":" in raw:
        hh, mm = raw.split(":", 1)
        hour, minute = int(hh), int(mm[:2])
    else:
        hour, minute = int(raw), 0
    mer = meridiem or other_meridiem
    if mer == "pm" and hour < 12:
        hour += 12
    elif mer == "am" and hour == 12:
        hour = 0
    elif mer is None and 1 <= hour <= 7:
        hour += 12          # "2-5" on a campus day is the afternoon
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return time_t(hour, minute)


_ISO_DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
_RANGE_WORDS = re.compile(r"\s+(?:to|till|until|upto|and)\s+")


def _parse_window(text: str | None) -> tuple[time_t | None, time_t | None]:
    """'2-5pm', '2 pm to 5 pm', 'from 14:00 to 17:00', 'between 10 and 1' ->
    (start, end). ISO dates are stripped first: '2026-08-27' otherwise reads as
    a perfectly good time range."""
    if not text:
        return None, None
    t = text.strip().lower().replace("–", "-").replace("—", "-")
    t = _ISO_DATE.sub(" ", t)
    t = re.sub(r"\b(?:from|between)\b", " ", t)
    t = _RANGE_WORDS.sub("-", t)
    m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*-\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)?", t)
    if m:
        start = _parse_clock(m.group(1), m.group(2), m.group(4))
        end = _parse_clock(m.group(3), m.group(4), m.group(2))
        return start, end
    m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)\b", t)  # single anchored time
    if m:
        return _parse_clock(m.group(1), m.group(2), None), None
    m = re.search(r"\bat\s+(\d{1,2}(?::\d{2})?)", t)
    if m:
        return _parse_clock(m.group(1), None, None), None
    return None, None


def _guess_title(text: str) -> str | None:
    """'...for the coding club hackathon, ~120 people' -> 'Coding Club Hackathon'."""
    m = re.search(r"\bfor\s+(?:the\s+|our\s+|a\s+)?([a-z][a-z0-9 '&-]{3,60}?)"
                  r"(?=[,.;]|\s+(?:with|about|around|approx|roughly|~|\d)|$)",
                  text, re.IGNORECASE)
    if not m:
        return None
    title = " ".join(m.group(1).split())
    # "for 120 people" / "for tomorrow" aren't titles
    if title.lower().split()[0] in {"people", "students", "tomorrow", "today"}:
        return None
    return title.title()


def _heuristic_request(text: str, today: date_t) -> BookingRequest:
    """Deterministic extraction — used when no LLM key is configured, so the
    demo never depends on a provider being up (docs/03-TECH-STACK.md)."""
    t = text.lower()
    head = None
    m = re.search(r"(?:~|about|around|approx\.?|roughly)?\s*(\d{2,4})\s*(?:people|persons|"
                  r"attendees|students|participants|pax|head)", t)
    if m:
        head = int(m.group(1))
    start, end = _parse_window(text)
    when = _parse_date(text, today)
    intent = "book" if any(v in t for v in BOOK_VERBS) else "check"
    return BookingRequest(
        venue=None, date=when.isoformat() if when else None,
        start_time=start.strftime("%H:%M") if start else None,
        end_time=end.strftime("%H:%M") if end else None,
        headcount=head, title=_guess_title(text), category=None, intent=intent)


def _extract(state: AgentState, text: str, today: date_t) -> BookingRequest:
    """LLM-first structured extraction with a heuristic fallback; supervisor
    entities (room/date/time_range) fill any remaining gaps."""
    spec = state.get("task_spec") or {}
    req: BookingRequest
    if is_llm_configured():
        try:
            llm = get_llm().with_structured_output(BookingRequest)
            req = llm.invoke([
                ("system",
                 "Extract the venue-booking request. Today is "
                 f"{today.isoformat()}; resolve relative dates against it and return "
                 "24-hour times. If the user is only asking whether something is free, "
                 "set intent='check'."),
                ("user", text)])
        except Exception:
            req = _heuristic_request(text, today)
    else:
        req = _heuristic_request(text, today)

    heur = _heuristic_request(text, today)
    req.venue = req.venue or spec.get("room")
    req.date = req.date or spec.get("date") or heur.date
    if not req.start_time:
        s, e = _parse_window(spec.get("time_range") or "")
        req.start_time = req.start_time or (s.strftime("%H:%M") if s else heur.start_time)
        req.end_time = req.end_time or (e.strftime("%H:%M") if e else heur.end_time)
    req.headcount = req.headcount or heur.headcount
    req.title = req.title or heur.title
    return req


def _as_time(value: str | None) -> time_t | None:
    if not value:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})", value.strip())
    if m:
        try:
            return time_t(int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    s, _ = _parse_window(value)
    return s


def _fmt_conflicts(conflicts: list[dict]) -> str:
    return "\n".join(f"  • {c['detail']}" for c in conflicts)


def _fmt_alternatives(alts: list[dict]) -> str:
    return "\n".join(f"  • {a['room']} ({a['type']}, {a['why']})" for a in alts)


# --- the node -----------------------------------------------------------------

def booking_node(state: AgentState, config) -> dict:
    steps = ["BookingAgent: parsing venue request..."]
    thread_id = (config.get("configurable") or {}).get("thread_id")
    spec = state.get("task_spec") or {}

    text = ""
    for m in reversed(state.get("messages") or []):
        text = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        if text:
            break

    today = date_t.today()
    structured = spec.get("booking")  # form path: already validated by the API

    db = SessionLocal()
    try:
        organizer = db.get(User, spec["user_id"]) if spec.get("user_id") else None

        if structured:
            on_date = date_t.fromisoformat(structured["date"])
            start = time_t.fromisoformat(structured["start"])
            end = time_t.fromisoformat(structured["end"])
            headcount = int(structured.get("headcount") or 0)
            title = structured.get("title") or "Campus event"
            description = structured.get("description") or ""
            category = structured.get("category") or "event"
            requested = db.get(Room, structured["room_id"]) if structured.get("room_id") else None
            prefer_type = requested.type if requested else None
            intent = "book"
            steps.append(f"BookingAgent: structured request — {title}, {on_date.isoformat()}, "
                         f"{window_str(start, end)}, {headcount} expected.")
        else:
            req = _extract(state, text, today)
            on_date = _parse_date(req.date, today)
            start, end = _as_time(req.start_time), _as_time(req.end_time)
            if start and not end:
                end = time_t((start.hour + 2) % 24, start.minute)  # assume a 2h event
            headcount = req.headcount or 0
            title = req.title or "Campus event"
            description = text.strip()
            category = req.category or "event"
            requested = (resolve_room(db, req.venue)
                         or resolve_room_in_text(db, text))
            prefer_type = type_hint_from_text(req.venue or text)
            intent = req.intent if req.intent in ("book", "check") else "book"
            steps.append(
                "BookingAgent: extracted "
                f"venue={requested.name if requested else prefer_type or '—'}, "
                f"date={on_date.isoformat() if on_date else '—'}, "
                f"window={window_str(start, end) if start and end else '—'}, "
                f"headcount={headcount or '—'}, intent={intent}.")

        # --- not enough to act on: ask, never guess a booking into existence ---
        if on_date is None or start is None or end is None:
            venues = ", ".join(f"{r.name} ({r.type}, {r.capacity})" for r in db.query(Room).all())
            missing = [n for n, v in [("a date", on_date), ("a start time", start),
                                      ("an end time", end)] if v is None]
            steps.append(f"BookingAgent: incomplete request — missing {', '.join(missing)}.")
            return {"steps": steps, "current_action": "facility",
                    "final_response": (
                        "I need " + " and ".join(missing) + " before I can check a venue.\n"
                        f"Venues on campus: {venues}.\n"
                        "Try: 'Book Seminar Hall B on 2026-09-04, 14:00-17:00 for ~120 people'."),
                    "params": {**state.get("params", {}), "needs": missing}}

        if on_date < today:
            steps.append(f"BookingAgent: rejected — {on_date.isoformat()} is in the past.")
            return {"steps": steps, "current_action": "facility",
                    "final_response": (f"{on_date.isoformat()} has already passed — "
                                       "venues can only be booked from today onwards."),
                    "params": {**state.get("params", {})}}

        if end <= start:
            steps.append("BookingAgent: rejected — end time is not after start time.")
            return {"steps": steps, "current_action": "facility",
                    "final_response": (f"That window doesn't work: {window_str(start, end)} "
                                       "ends before it starts."),
                    "params": {**state.get("params", {})}}

        # --- availability question: report, don't write ------------------------
        if intent == "check" or organizer is None:
            if requested is not None:
                verdict = check_availability(db, requested, on_date, start, end, headcount)
                alts = ([] if verdict["available"] else
                        find_alternatives(db, on_date, start, end, headcount,
                                          exclude_room_id=requested.id, prefer_type=prefer_type))
                steps.append(f"BookingAgent: checked {requested.name} against "
                             f"{len(verdict['conflicts'])} clash source(s) — "
                             f"{'free' if verdict['available'] else 'not free'}.")
                if verdict["available"]:
                    body = (f"{requested.name} is FREE on {on_date.isoformat()}, "
                            f"{window_str(start, end)} — no class and no other booking "
                            f"overlaps, capacity {requested.capacity}.")
                else:
                    body = (f"{requested.name} is NOT available on {on_date.isoformat()}, "
                            f"{window_str(start, end)}:\n" + _fmt_conflicts(verdict["conflicts"]))
                    if verdict["capacity_note"]:
                        body += f"\n  • capacity: {verdict['capacity_note']}"
                    if alts:
                        body += "\nFree instead:\n" + _fmt_alternatives(alts)
            else:
                alts = find_alternatives(db, on_date, start, end, headcount,
                                         prefer_type=prefer_type, limit=6)
                steps.append(f"BookingAgent: scanned the venue registry — {len(alts)} free.")
                body = (("Free on " + on_date.isoformat() + ", "
                         + window_str(start, end) + ":\n" + _fmt_alternatives(alts))
                        if alts else
                        f"Nothing is free on {on_date.isoformat()}, {window_str(start, end)}"
                        + (f" for {headcount} people." if headcount else "."))
            if organizer is None and intent == "book":
                body += "\n\n(Sign in to turn this into an actual booking request.)"
            return {"steps": steps, "current_action": "facility", "final_response": body,
                    "params": {**state.get("params", {}), "date": on_date.isoformat(),
                               "window": window_str(start, end), "action": "availability"}}

        # --- booking intent: pick a venue --------------------------------------
        # On an interrupt-resume this node runs again from the top. If it already
        # placed a booking on this thread, re-read it instead of re-planning: the
        # held venue is now occupied *by this very booking*, so a fresh
        # choose_venue() would narrate a venue we never actually took.
        held = find_request(db, thread_id)
        if held is not None:
            booking = held
            room = db.get(Room, booking.room_id)
            alternatives = find_alternatives(db, on_date, start, end, headcount,
                                             exclude_room_id=room.id,
                                             prefer_type=prefer_type)
            steps.append(f"BookingAgent: resuming — booking #{booking.id} already "
                         f"holds {room.name}, no re-planning needed.")
        else:
            pick = choose_venue(db, requested=requested, on_date=on_date, start=start,
                                end=end, headcount=headcount, prefer_type=prefer_type)
            if pick["room"] is None:
                rv = pick["requested_verdict"]
                steps.append("BookingAgent: no venue on campus satisfies the request.")
                body = (f"I couldn't find any venue for {on_date.isoformat()}, "
                        f"{window_str(start, end)}"
                        + (f" that seats {headcount}" if headcount else "") + ".")
                if rv and rv["conflicts"]:
                    body += (f"\n{rv['room']} is blocked by:\n"
                             + _fmt_conflicts(rv["conflicts"]))
                body += ("\nTry a different time window or split the event across "
                         "two venues.")
                return {"steps": steps, "current_action": "facility",
                        "final_response": body,
                        "params": {**state.get("params", {}), "action": "no_venue"}}

            room = pick["room"]
            if pick["substituted"]:
                steps.append(f"BookingAgent: {requested.name} unavailable → proposing "
                             f"{room.name} instead.")
            else:
                steps.append(f"BookingAgent: {room.name} is clear — no class, "
                             "no booking overlap.")
            booking = create_request(
                db, request_key=thread_id, organizer=organizer, room=room,
                on_date=on_date, start=start, end=end, title=title,
                description=description, headcount=headcount, category=category,
                purpose=description, rationale=pick["rationale"])
            alternatives = pick["alternatives"]

        chain = approval_chain_for(db, organizer)
        booking_id = booking.id
        organizer_id = organizer.id
        summary = booking_summary(db, booking_id)
        steps.append(f"BookingAgent: booking #{booking_id} pending; approval chain = "
                     + " → ".join(STAGE_LABEL[st] for st in chain) + ".")
    finally:
        db.close()

    # ---- HUMAN-IN-THE-LOOP: one interrupt per stage, same durable thread ----
    for stage in chain:
        db = SessionLocal()
        try:
            approval = (db.query(Approval)
                        .filter(Approval.kind == stage, Approval.ref_id == booking_id)
                        .first())
            if approval is None:
                approver = approver_for(db, stage, db.get(User, organizer_id))
                approval = Approval(kind=stage, ref_id=booking_id, status="pending",
                                    approver_id=approver.id if approver else None,
                                    langgraph_thread_id=thread_id)
                db.add(approval)
                db.commit()
                db.refresh(approval)
            approval_id = approval.id
            # `steps` rides along in the card: a node that interrupts never
            # returns, so its state update (and therefore its trace) is discarded
            # — the approval UI would otherwise show no agent reasoning at all.
            card = {"type": stage, "approval_id": approval_id,
                    "stage": STAGE_LABEL[stage],
                    "stage_index": chain.index(stage) + 1, "stages": len(chain),
                    "booking": booking_summary(db, booking_id),
                    "alternatives": alternatives, "steps": steps}
        finally:
            db.close()

        decision = interrupt(card)

        action = (decision or {}).get("action", "reject")
        db = SessionLocal()
        try:
            if action != "approve":
                reason = (decision or {}).get("reason", "")
                result = reject_booking(db, booking_id, stage=stage, reason=reason)
                steps.append(f"BookingAgent: declined at the {STAGE_LABEL[stage].lower()} "
                             f"stage — venue released, organiser notified.")
                return {"steps": steps, "current_action": "facility",
                        "final_response": (
                            f"Booking #{booking_id} ('{summary['title']}', {summary['venue']}, "
                            f"{summary['date']} {summary['window']}) was declined by "
                            f"{STAGE_LABEL[stage].lower()}."
                            + (f"\nReason: {reason}" if reason else "")
                            + "\nThe venue is free again and the organiser has been notified."),
                        "params": {**result.get("summary", summary), "decision": "rejected"}}
            steps.append(f"BookingAgent: {STAGE_LABEL[stage].lower()} approved (approval "
                         f"#{approval_id}).")
        finally:
            db.close()

    db = SessionLocal()
    try:
        result = confirm_booking(db, booking_id)
        final = result["summary"]
    finally:
        db.close()

    steps.append(f"BookingAgent: booking #{booking_id} confirmed; {result['notified']} "
                 "notification(s) sent; event is on the campus calendar.")
    return {
        "steps": steps, "current_action": "facility",
        "final_response": (
            f"'{final['title']}' is CONFIRMED.\n"
            f"- Venue: {final['venue']} ({final['venue_type']}, seats {final['capacity']})\n"
            f"- When: {final['date']}, {final['window']}\n"
            f"- Expected: {final['headcount'] or '—'} · Organiser: {final['organizer']}\n"
            f"- Cleared: {' → '.join(STAGE_LABEL[s] for s in chain)}\n"
            f"- {final['rationale']}\n"
            "It now appears on the campus calendar."),
        "params": {**final, "decision": "approved"},
    }


# Back-compat: graph.py registered this node as `facility_node` in Phase 0.
facility_node = booking_node
