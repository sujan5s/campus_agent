"""Facility/booking specialist — evolves into the Event & Venue Booking agent
(docs/01-FEATURES.md F3). Phase 0: real room lookup from the DB; Phase 3 adds
conflict detection against bookings + timetable and the approval chain.
"""
import re

from app.agents.state import AgentState
from app.db.models import Room
from app.db.session import SessionLocal


def facility_node(state: AgentState) -> dict:
    query = ""
    if state.get("messages"):
        query = state["messages"][-1].get("content", "").lower()

    task_spec = state.get("task_spec", {})
    steps = ["FacilityAgent: querying campus room registry..."]

    db = SessionLocal()
    try:
        rooms = db.query(Room).all()
        # Prefer the supervisor-extracted room entity, else scan the query text.
        wanted = (task_spec.get("room") or "").lower()
        match = None
        for r in rooms:
            rl = r.name.lower()
            if wanted and (wanted in rl or rl in wanted):
                match = r
                break
        if match is None:
            for r in rooms:
                rl = r.name.lower()
                # Candidate tokens: full name, last word, and hyphen suffix ("lt-302" → "302")
                tokens = {rl, rl.split()[-1], rl.split("-")[-1]}
                # Word-boundary match so "2" doesn't hit inside "2pm" (#phase0 test bug)
                if any(re.search(rf"\b{re.escape(t)}\b", query) for t in tokens):
                    match = r
                    break
        if match is None and ("hall" in query or "seminar" in query):
            match = next((r for r in rooms if r.type == "seminar"), None)
        if match is None and "auditorium" in query:
            match = next((r for r in rooms if r.type == "auditorium"), None)
        if match is None and "lab" in query:
            match = next((r for r in rooms if r.type == "lab"), None)

        room_names = ", ".join(r.name for r in rooms)
    finally:
        db.close()

    if match is None:
        steps.append("FacilityAgent: no specific venue matched — listing registry.")
        response = (
            "Facility Agent: I couldn't match a specific venue in your request.\n"
            f"Available venues: {room_names}.\n"
            "Tell me which one and when, e.g. 'Book Seminar Hall B on Friday 2–5pm'."
        )
        return {"steps": steps, "final_response": response,
                "params": {**state.get("params", {}), **task_spec}}

    steps.append(f"FacilityAgent: matched venue '{match.name}' ({match.type}, capacity {match.capacity}).")

    if "book" in query or "reserve" in query:
        when = " / ".join(v for v in [task_spec.get("date"), task_spec.get("time_range")] if v) or "requested slot"
        response = (
            f"Facility Agent confirmation:\n"
            f"{match.name} ({match.type}, capacity {match.capacity}) provisionally BOOKED for {when}.\n"
            "Conflict checks against the live timetable and the approval chain arrive in Phase 3 "
            "— this booking is a demo write-through for now."
        )
        steps.append(f"FacilityAgent: provisional reservation recorded for {match.name}.")
        action = "booked"
    else:
        response = (
            f"Facility Agent report:\n"
            f"{match.name} is registered as a {match.type} with capacity {match.capacity}.\n"
            "Live availability against bookings + timetable lands in Phase 3."
        )
        steps.append(f"FacilityAgent: returned registry details for {match.name}.")
        action = "status"

    return {
        "steps": steps,
        "final_response": response,
        "params": {**state.get("params", {}), **task_spec,
                   "facility_name": match.name, "action": action},
    }
