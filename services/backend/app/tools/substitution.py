"""Substitution tools — F2 flagship (docs/01-FEATURES.md, research/04).

Minimal-perturbation timetable repair: when a leave is approved, find the
affected lessons and rank substitute candidates per lesson:

    teaches-the-same-subject  >  same department  >  any free teacher,
    tie-broken by lightest current workload (fairness) and fewest
    assignments already taken in this plan (spread).

All rows are grouped under one plan_id (= "leave-<id>") so the human approves
or rejects the plan atomically. Everything here is idempotent — the agent node
re-runs after interrupt()/resume, so building twice must not duplicate rows.
"""
from datetime import date as date_t, timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    Leave, Notification, Substitution, Teacher, TimetableEntry, User,
)

WEEKDAY_TO_DAY = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI"}


def plan_id_for(leave_id: int) -> str:
    return f"leave-{leave_id}"


def _latest_version(db: Session) -> int | None:
    row = db.query(TimetableEntry.version).order_by(TimetableEntry.version.desc()).first()
    return row[0] if row else None


def _leave_dates(leave: Leave) -> list[date_t]:
    """Working days (MON-FRI) covered by the leave."""
    out, d = [], leave.from_date
    while d <= leave.to_date:
        if d.weekday() <= 4:
            out.append(d)
        d += timedelta(days=1)
    return out


def _on_leave(db: Session, teacher_id: int, on_date: date_t) -> bool:
    return db.query(Leave).filter(
        Leave.teacher_id == teacher_id,
        Leave.status == "approved",
        Leave.from_date <= on_date,
        Leave.to_date >= on_date,
    ).count() > 0


def build_plan(db: Session, leave: Leave) -> list[Substitution]:
    """Create proposed Substitution rows for every lesson the leave disrupts.
    Idempotent: returns the existing plan if one was already built."""
    pid = plan_id_for(leave.id)
    existing = db.query(Substitution).filter(Substitution.plan_id == pid).all()
    if existing:
        return existing

    ver = _latest_version(db)
    if ver is None:
        return []

    # teacher weekly load (fairness input): entries per teacher in latest version
    loads: dict[int, int] = {}
    for e in db.query(TimetableEntry).filter(TimetableEntry.version == ver,
                                             TimetableEntry.status == "active"):
        loads[e.teacher_id] = loads.get(e.teacher_id, 0) + 1

    teachers = db.query(Teacher).all()
    plan_load: dict[int, int] = {}  # substitutions taken within THIS plan
    rows: list[Substitution] = []

    for on_date in _leave_dates(leave):
        day = WEEKDAY_TO_DAY[on_date.weekday()]
        affected = (
            db.query(TimetableEntry)
            .filter(TimetableEntry.version == ver,
                    TimetableEntry.status == "active",
                    TimetableEntry.teacher_id == leave.teacher_id)
            .all()
        )
        for entry in affected:
            if entry.timeslot.day != day:
                continue
            best, best_score = None, None
            for cand in teachers:
                if cand.id == leave.teacher_id or _on_leave(db, cand.id, on_date):
                    continue
                # busy = teaches any section at this timeslot in the live timetable
                busy = db.query(TimetableEntry).filter(
                    TimetableEntry.version == ver,
                    TimetableEntry.status == "active",
                    TimetableEntry.teacher_id == cand.id,
                    TimetableEntry.timeslot_id == entry.timeslot_id,
                ).count() > 0
                if busy:
                    continue
                # already proposed elsewhere at this date+slot inside this plan
                if any(r.substitute_teacher_id == cand.id
                       and r.date == on_date
                       and db.get(TimetableEntry, r.timetable_entry_id).timeslot_id == entry.timeslot_id
                       for r in rows):
                    continue
                subject_ids = {s.id for s in cand.subjects}
                score = 0.0
                if entry.subject_id in subject_ids:
                    score += 3.0
                if cand.dept == entry.teacher.dept:
                    score += 2.0
                score -= loads.get(cand.id, 0) * 0.1          # prefer lighter weekly load
                score -= plan_load.get(cand.id, 0) * 0.5      # spread within the plan
                if best_score is None or score > best_score:
                    best, best_score = cand, score
            sub = Substitution(
                timetable_entry_id=entry.id,
                date=on_date,
                original_teacher_id=leave.teacher_id,
                substitute_teacher_id=best.id if best else None,
                status="proposed",
                plan_id=pid,
            )
            if best:
                plan_load[best.id] = plan_load.get(best.id, 0) + 1
            db.add(sub)
            rows.append(sub)

    db.commit()
    return rows


def plan_summary(db: Session, leave_id: int) -> dict:
    """JSON-friendly plan detail for the approval card / interrupt payload."""
    leave = db.get(Leave, leave_id)
    subs = db.query(Substitution).filter(
        Substitution.plan_id == plan_id_for(leave_id)).all()
    items = []
    for s in subs:
        entry = db.get(TimetableEntry, s.timetable_entry_id)
        cand = db.get(Teacher, s.substitute_teacher_id) if s.substitute_teacher_id else None
        subject_match = bool(cand and entry.subject_id in {x.id for x in cand.subjects})
        items.append({
            "substitution_id": s.id,
            "date": s.date.isoformat(),
            "day": entry.timeslot.day,
            "period": entry.timeslot.period_no,
            "time": f"{entry.timeslot.start.strftime('%H:%M')}–{entry.timeslot.end.strftime('%H:%M')}",
            "section": entry.section.name,
            "subject": entry.subject.code,
            "subject_name": entry.subject.name,
            "room": entry.room.name,
            "original": entry.teacher.user.name,
            "substitute": cand.user.name if cand else None,
            "rationale": (
                "teaches this subject" if subject_match
                else "same department, free at this hour" if cand and cand.dept == entry.teacher.dept
                else "free at this hour" if cand
                else "NO COVER AVAILABLE — class needs rescheduling or self-study"
            ),
            "status": s.status,
        })
    original = db.get(Teacher, leave.teacher_id)
    return {
        "leave_id": leave_id,
        "teacher": original.user.name,
        "from_date": leave.from_date.isoformat(),
        "to_date": leave.to_date.isoformat(),
        "reason": leave.reason,
        "lessons_affected": len(items),
        "covered": sum(1 for i in items if i["substitute"]),
        "items": sorted(items, key=lambda i: (i["date"], i["period"])),
    }


def apply_plan(db: Session, leave_id: int) -> dict:
    """HOD approved: confirm rows + notify everyone affected."""
    subs = db.query(Substitution).filter(
        Substitution.plan_id == plan_id_for(leave_id),
        Substitution.status == "proposed").all()
    notified = 0
    for s in subs:
        s.status = "approved"
        entry = db.get(TimetableEntry, s.timetable_entry_id)
        if s.substitute_teacher_id:
            cand = db.get(Teacher, s.substitute_teacher_id)
            db.add(Notification(
                user_id=cand.user_id,
                title="Substitution assigned",
                body=(f"You cover {entry.subject.code} for {entry.section.name} on "
                      f"{s.date.isoformat()} ({entry.timeslot.day} P{entry.timeslot.period_no}, "
                      f"{entry.room.name}). Original: {entry.teacher.user.name}."),
            ))
            notified += 1
    leave = db.get(Leave, leave_id)
    original = db.get(Teacher, leave.teacher_id)
    db.add(Notification(
        user_id=original.user_id,
        title="Your classes are covered",
        body=(f"Substitutions for your leave {leave.from_date.isoformat()} to "
              f"{leave.to_date.isoformat()} were approved. "
              f"{sum(1 for s in subs if s.substitute_teacher_id)} of {len(subs)} lessons covered."),
    ))
    db.commit()
    return {"applied": len(subs), "notified": notified}


def reject_plan(db: Session, leave_id: int) -> dict:
    subs = db.query(Substitution).filter(
        Substitution.plan_id == plan_id_for(leave_id),
        Substitution.status == "proposed").all()
    for s in subs:
        s.status = "rejected"
    db.commit()
    return {"rejected": len(subs)}


def notify_user(db: Session, user: User, title: str, body: str) -> None:
    db.add(Notification(user_id=user.id, title=title, body=body))
    db.commit()
