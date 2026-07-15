"""Period-exchange tools — F2 flagship, Phase 2.1 (docs/06-EXCHANGE-PLAN.md).

Real-world college practice: when teacher A is on leave, a partner teacher B of
the SAME section moves their own lesson into A's slot on the leave date, and A
recovers the missed lesson later in B's vacated slot. No subject is ever taught
by the wrong teacher; weekly period counts are preserved — lessons just swap
dates.

The original timetable_entries are never mutated. Each exchange is a dated
overlay row in `period_exchanges`, grouped under one plan_id (= "exchange-leave-<id>")
so the HOD approves/rejects the plan atomically. Everything here is idempotent —
the agent node re-runs after interrupt()/resume, so building twice must not
duplicate rows.
"""
from datetime import date as date_t, timedelta

from sqlalchemy.orm import Session

from app.db.models import (
    Leave, Notification, PeriodExchange, Teacher, TimetableEntry,
)
# Reuse the weekday helpers from the legacy module (unchanged logic).
from app.tools.substitution import (
    WEEKDAY_TO_DAY, _latest_version, _leave_dates, _on_leave,
)

DAY_TO_WEEKDAY = {v: k for k, v in WEEKDAY_TO_DAY.items()}


def plan_id_for(leave_id: int) -> str:
    return f"exchange-leave-{leave_id}"


def _slot_time(entry: TimetableEntry) -> str:
    ts = entry.timeslot
    return f"{ts.start.strftime('%H:%M')}–{ts.end.strftime('%H:%M')}"


def _next_date_for_weekday(after: date_t, day: str) -> date_t | None:
    """Nearest date strictly after `after` whose weekday matches `day` (MON..FRI)."""
    target = DAY_TO_WEEKDAY.get(day)
    if target is None:
        return None
    d = after + timedelta(days=1)
    for _ in range(14):  # search up to two weeks out
        if d.weekday() == target:
            return d
        d += timedelta(days=1)
    return None


def _teacher_busy_at(db: Session, ver: int, teacher_id: int, day: str,
                     period_no: int) -> bool:
    """True if the teacher already teaches some section at (day, period) in the
    live timetable."""
    return (
        db.query(TimetableEntry)
        .filter(TimetableEntry.version == ver,
                TimetableEntry.status == "active",
                TimetableEntry.teacher_id == teacher_id)
        .filter(TimetableEntry.timeslot.has(day=day, period_no=period_no))
        .count() > 0
    )


def build_plan(db: Session, leave: Leave) -> list[PeriodExchange]:
    """Create proposed PeriodExchange rows for every lesson the leave disrupts.
    Idempotent: returns the existing plan if one was already built."""
    pid = plan_id_for(leave.id)
    existing = db.query(PeriodExchange).filter(PeriodExchange.plan_id == pid).all()
    if existing:
        return existing

    ver = _latest_version(db)
    if ver is None:
        return []

    # partner weekly load (fairness input): active entries per teacher, latest version
    loads: dict[int, int] = {}
    for e in db.query(TimetableEntry).filter(TimetableEntry.version == ver,
                                             TimetableEntry.status == "active"):
        loads[e.teacher_id] = loads.get(e.teacher_id, 0) + 1

    rows: list[PeriodExchange] = []
    partner_plan_load: dict[int, int] = {}   # exchanges assigned to B within this plan
    # (partner_entry_id, recovery_date) pairs already used in this plan, to avoid reuse
    used_pairs: set[tuple[int, str]] = set()
    # (teacher_id, date, period) occupancy created by this plan's exchanges
    reserved: set[tuple[int, str, int]] = set()

    for on_date in _leave_dates(leave):
        day = WEEKDAY_TO_DAY[on_date.weekday()]
        affected = (
            db.query(TimetableEntry)
            .filter(TimetableEntry.version == ver,
                    TimetableEntry.status == "active",
                    TimetableEntry.teacher_id == leave.teacher_id)
            .all()
        )
        for entry_a in affected:
            if entry_a.timeslot.day != day:
                continue

            # Lab block: splitting a consecutive lab breaks it — HOD handles manually.
            if entry_a.subject.needs_lab:
                rows.append(_no_partner_row(
                    db, pid, leave, entry_a, on_date,
                    "MANUAL HANDLING REQUIRED — lab block cannot be auto-exchanged"))
                continue

            best = _pick_partner(
                db, ver, leave, entry_a, on_date, day, loads,
                partner_plan_load, used_pairs, reserved)

            if best is None:
                rows.append(_no_partner_row(
                    db, pid, leave, entry_a, on_date,
                    "NO EXCHANGE AVAILABLE — needs manual arrangement"))
                continue

            entry_b, recovery_date, rationale = best
            row = PeriodExchange(
                plan_id=pid,
                leave_id=leave.id,
                absent_entry_id=entry_a.id,
                leave_date=on_date,
                partner_entry_id=entry_b.id,
                recovery_date=recovery_date,
                absent_teacher_id=leave.teacher_id,
                partner_teacher_id=entry_b.teacher_id,
                status="proposed",
                rationale=rationale,
            )
            db.add(row)
            rows.append(row)

            # book the two occupancy changes this exchange creates
            partner_plan_load[entry_b.teacher_id] = partner_plan_load.get(entry_b.teacher_id, 0) + 1
            used_pairs.add((entry_b.id, recovery_date.isoformat()))
            reserved.add((entry_b.teacher_id, on_date.isoformat(), entry_a.timeslot.period_no))
            reserved.add((leave.teacher_id, recovery_date.isoformat(), entry_b.timeslot.period_no))

    db.commit()
    return rows


def _no_partner_row(db, pid, leave, entry_a, on_date, rationale) -> PeriodExchange:
    row = PeriodExchange(
        plan_id=pid, leave_id=leave.id, absent_entry_id=entry_a.id,
        leave_date=on_date, partner_entry_id=None, recovery_date=None,
        absent_teacher_id=leave.teacher_id, partner_teacher_id=None,
        status="proposed", rationale=rationale,
    )
    db.add(row)
    return row


def _pick_partner(db, ver, leave, entry_a, on_date, day, loads,
                  partner_plan_load, used_pairs, reserved):
    """Return (entry_b, recovery_date, rationale) for the best exchange, or None."""
    section_id = entry_a.section_id
    a_period = entry_a.timeslot.period_no

    # Candidate partner lessons: same section, different teacher, latest version.
    candidates = (
        db.query(TimetableEntry)
        .filter(TimetableEntry.version == ver,
                TimetableEntry.status == "active",
                TimetableEntry.section_id == section_id,
                TimetableEntry.teacher_id != leave.teacher_id)
        .all()
    )

    best = None
    best_score = None
    seen_pairs: set[tuple[int, str]] = set()

    for entry_b in candidates:
        b = db.get(Teacher, entry_b.teacher_id)
        if b is None:
            continue
        # Never exchange a lab block on the partner side either.
        if entry_b.subject.needs_lab:
            continue

        # B must be free at A's slot on the leave date D.
        if _on_leave(db, b.id, on_date):
            continue
        if _teacher_busy_at(db, ver, b.id, day, a_period):
            continue
        if (b.id, on_date.isoformat(), a_period) in reserved:
            continue

        # Recovery date R: nearest date after leave.to_date on entry_b's weekday.
        recovery_date = _next_date_for_weekday(leave.to_date, entry_b.timeslot.day)
        if recovery_date is None:
            continue
        b_period = entry_b.timeslot.period_no

        # Each (partner lesson, recovery date) pair used at most once per plan.
        pair = (entry_b.id, recovery_date.isoformat())
        if pair in used_pairs or pair in seen_pairs:
            continue

        # A must be free at entry_b's slot on R.
        if _on_leave(db, leave.teacher_id, recovery_date):
            continue
        if _teacher_busy_at(db, ver, leave.teacher_id, entry_b.timeslot.day, b_period):
            continue
        if (leave.teacher_id, recovery_date.isoformat(), b_period) in reserved:
            continue

        seen_pairs.add(pair)

        gap = (recovery_date - on_date).days
        score = 0.0
        score -= 2.0 * gap                                          # prefer nearest recovery
        score -= 0.5 * partner_plan_load.get(b.id, 0)              # spread within plan
        score -= 0.1 * loads.get(b.id, 0)                          # fairness: lighter load
        if best_score is None or score > best_score:
            rationale = (
                f"{b.user.name} teaches {entry_b.subject.code} to this section; "
                f"swap with {entry_b.timeslot.day} P{b_period}, recovery on "
                f"{recovery_date.isoformat()} ({gap} day{'s' if gap != 1 else ''} later)"
            )
            best = (entry_b, recovery_date, rationale)
            best_score = score

    return best


def plan_summary(db: Session, leave_id: int) -> dict:
    """JSON-friendly plan detail for the approval card / interrupt payload."""
    leave = db.get(Leave, leave_id)
    exchanges = db.query(PeriodExchange).filter(
        PeriodExchange.plan_id == plan_id_for(leave_id)).all()
    items = []
    for x in exchanges:
        entry_a = db.get(TimetableEntry, x.absent_entry_id)
        entry_b = db.get(TimetableEntry, x.partner_entry_id) if x.partner_entry_id else None
        partner = db.get(Teacher, x.partner_teacher_id) if x.partner_teacher_id else None
        items.append({
            "exchange_id": x.id,
            "leave_date": x.leave_date.isoformat(),
            "leave_day": entry_a.timeslot.day,
            "leave_period": entry_a.timeslot.period_no,
            "leave_time": _slot_time(entry_a),
            "section": entry_a.section.name,
            "room": entry_a.room.name,
            "missed_subject": entry_a.subject.code,
            "missed_subject_name": entry_a.subject.name,
            "partner": partner.user.name if partner else None,
            "partner_subject": entry_b.subject.code if entry_b else None,
            "partner_subject_name": entry_b.subject.name if entry_b else None,
            "recovery_date": x.recovery_date.isoformat() if x.recovery_date else None,
            "recovery_day": entry_b.timeslot.day if entry_b else None,
            "recovery_period": entry_b.timeslot.period_no if entry_b else None,
            "recovery_time": _slot_time(entry_b) if entry_b else None,
            "rationale": x.rationale,
            "status": x.status,
        })
    original = db.get(Teacher, leave.teacher_id)
    return {
        "leave_id": leave_id,
        "teacher": original.user.name,
        "from_date": leave.from_date.isoformat(),
        "to_date": leave.to_date.isoformat(),
        "reason": leave.reason,
        "lessons_affected": len(items),
        "exchanged": sum(1 for i in items if i["partner"]),
        "items": sorted(items, key=lambda i: (i["leave_date"], i["leave_period"])),
    }


def apply_plan(db: Session, leave_id: int) -> dict:
    """HOD approved: confirm rows + notify both partners and the absent teacher."""
    exchanges = db.query(PeriodExchange).filter(
        PeriodExchange.plan_id == plan_id_for(leave_id),
        PeriodExchange.status == "proposed").all()
    leave = db.get(Leave, leave_id)
    absent = db.get(Teacher, leave.teacher_id)
    notified = 0
    recovery_lines = []

    for x in exchanges:
        x.status = "confirmed"
        entry_a = db.get(TimetableEntry, x.absent_entry_id)
        if not x.partner_entry_id:
            recovery_lines.append(
                f"- {entry_a.subject.code} ({entry_a.timeslot.day} "
                f"P{entry_a.timeslot.period_no}, {x.leave_date.isoformat()}): "
                "no exchange found — arrange manually")
            continue
        entry_b = db.get(TimetableEntry, x.partner_entry_id)
        partner = db.get(Teacher, x.partner_teacher_id)
        # Notify partner B
        db.add(Notification(
            user_id=partner.user_id,
            title="Period exchange scheduled",
            body=(f"On {x.leave_date.isoformat()} ({entry_a.timeslot.day} "
                  f"P{entry_a.timeslot.period_no}, {entry_a.room.name}) you teach "
                  f"{entry_b.subject.code} to {entry_a.section.name} in place of "
                  f"{absent.user.name}. Your {entry_b.timeslot.day} "
                  f"P{entry_b.timeslot.period_no} lesson on "
                  f"{x.recovery_date.isoformat()} will be taken by them "
                  f"({entry_a.subject.code} recovery)."),
        ))
        notified += 1
        recovery_lines.append(
            f"- {entry_a.subject.code} recovered on {x.recovery_date.isoformat()} "
            f"({entry_b.timeslot.day} P{entry_b.timeslot.period_no}), "
            f"swapped with {partner.user.name}")

    # Notify absent teacher A
    db.add(Notification(
        user_id=absent.user_id,
        title="Your leave is covered by period exchanges",
        body=("Your classes during leave "
              f"{leave.from_date.isoformat()} → {leave.to_date.isoformat()} are "
              "covered by period exchanges. Recovery schedule:\n"
              + "\n".join(recovery_lines)),
    ))
    db.commit()
    return {"applied": len(exchanges), "notified": notified,
            "exchanged": sum(1 for x in exchanges if x.partner_entry_id)}


def reject_plan(db: Session, leave_id: int) -> dict:
    exchanges = db.query(PeriodExchange).filter(
        PeriodExchange.plan_id == plan_id_for(leave_id),
        PeriodExchange.status == "proposed").all()
    for x in exchanges:
        x.status = "rejected"
    db.commit()
    return {"rejected": len(exchanges)}
