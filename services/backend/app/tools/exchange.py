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
from dataclasses import dataclass, field
from datetime import date as date_t, timedelta

from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Leave, Notification, PeriodExchange, Teacher, TimeSlot, TimetableEntry,
)
# Reuse the weekday helpers from the legacy module (unchanged logic).
from app.tools.substitution import (
    WEEKDAY_TO_DAY, _latest_version, _leave_dates,
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


# ---- plan context: all DB reads done ONCE, then pure in-memory lookups -------
#
# The adjacency/continuity checks (Phase 2.2) run per candidate per affected
# lesson. Doing them against the DB was an N+1 storm (seconds per plan). We now
# load everything build_plan needs in ~5 queries up front and keep the exact
# same logic, just over dicts/sets. "Adjacent" = time-adjacent: two same-day
# periods whose slots share a boundary (prev.end == next.start); a break breaks
# adjacency — mirrors _consecutive_pairs() in app/solver/timetable_model.py.

def _mins(t) -> int:
    return t.hour * 60 + t.minute


@dataclass
class PlanContext:
    ver: int
    adjacent: dict[tuple[str, int], set[int]] = field(default_factory=dict)      # (day, period) -> adjacent periods
    runs: dict[str, list[list[int]]] = field(default_factory=dict)              # day -> consecutive-period chains
    section_day: dict[tuple[int, str], dict[int, int]] = field(default_factory=dict)  # (section, day) -> {period: subject}
    teacher_day: dict[tuple[int, str], set[int]] = field(default_factory=dict)  # (teacher, day) -> periods taught
    candidates_by_section: dict[int, list[TimetableEntry]] = field(default_factory=dict)
    affected_by_teacher: dict[int, list[TimetableEntry]] = field(default_factory=dict)
    busy: set[tuple[int, str, int]] = field(default_factory=set)                # (teacher, day, period) from base
    loads: dict[int, int] = field(default_factory=dict)                         # weekly load per teacher
    overlay: dict[tuple[int, str], dict[int, int]] = field(default_factory=dict)  # (section, date_iso) -> {period: subject}
    leaves: list[tuple[int, date_t, date_t]] = field(default_factory=list)      # approved (teacher, from, to)
    teacher_name: dict[int, str] = field(default_factory=dict)


def _build_context(db: Session, ver: int) -> PlanContext:
    """Load everything build_plan needs in a handful of queries."""
    ctx = PlanContext(ver=ver)

    # (1) timeslots -> adjacency + consecutive runs per day
    slots_by_day: dict[str, list[TimeSlot]] = {}
    for s in db.query(TimeSlot).order_by(TimeSlot.period_no).all():
        slots_by_day.setdefault(s.day, []).append(s)
    for day, slots in slots_by_day.items():
        slots.sort(key=lambda s: s.period_no)
        # adjacency
        for i, s in enumerate(slots):
            adj: set[int] = set()
            s_start, s_end = _mins(s.start), _mins(s.end)
            for o in slots:
                if o.period_no == s.period_no:
                    continue
                if _mins(o.end) == s_start or _mins(o.start) == s_end:
                    adj.add(o.period_no)
            ctx.adjacent[(day, s.period_no)] = adj
        # runs
        runs: list[list[int]] = []
        cur: list[int] = []
        prev_end = None
        for s in slots:
            start, end = _mins(s.start), _mins(s.end)
            if prev_end is not None and start == prev_end:
                cur.append(s.period_no)
            else:
                if cur:
                    runs.append(cur)
                cur = [s.period_no]
            prev_end = end
        if cur:
            runs.append(cur)
        ctx.runs[day] = runs

    # (2) live timetable entries (eager-loaded) -> section/teacher day maps, busy, loads, candidates
    entries = (
        db.query(TimetableEntry)
        .options(joinedload(TimetableEntry.timeslot),
                 joinedload(TimetableEntry.subject),
                 joinedload(TimetableEntry.section),
                 joinedload(TimetableEntry.room),
                 joinedload(TimetableEntry.teacher).joinedload(Teacher.user))
        .filter(TimetableEntry.version == ver, TimetableEntry.status == "active")
        .order_by(TimetableEntry.id).all()
    )
    for e in entries:
        day, period = e.timeslot.day, e.timeslot.period_no
        ctx.section_day.setdefault((e.section_id, day), {})[period] = e.subject_id
        ctx.teacher_day.setdefault((e.teacher_id, day), set()).add(period)
        ctx.busy.add((e.teacher_id, day, period))
        ctx.loads[e.teacher_id] = ctx.loads.get(e.teacher_id, 0) + 1
        ctx.candidates_by_section.setdefault(e.section_id, []).append(e)
        ctx.affected_by_teacher.setdefault(e.teacher_id, []).append(e)
        if e.teacher and e.teacher.user:
            ctx.teacher_name[e.teacher_id] = e.teacher.user.name

    # (3) confirmed exchanges from other plans -> per-date overlay
    entries_by_id = {e.id: e for e in entries}

    def _resolve(eid):
        return entries_by_id.get(eid) or db.get(TimetableEntry, eid)

    for x in (db.query(PeriodExchange)
              .filter(PeriodExchange.status == "confirmed").all()):
        if not x.partner_entry_id:
            continue
        ea, eb = _resolve(x.absent_entry_id), _resolve(x.partner_entry_id)
        if x.leave_date and ea is not None and eb is not None:
            ctx.overlay.setdefault((ea.section_id, x.leave_date.isoformat()), {})[
                ea.timeslot.period_no] = eb.subject_id
        if x.recovery_date and ea is not None and eb is not None:
            ctx.overlay.setdefault((eb.section_id, x.recovery_date.isoformat()), {})[
                eb.timeslot.period_no] = ea.subject_id

    # (4) approved leaves -> in-memory on-leave check
    for lv in db.query(Leave).filter(Leave.status == "approved").all():
        ctx.leaves.append((lv.teacher_id, lv.from_date, lv.to_date))

    return ctx


def _ctx_on_leave(ctx: PlanContext, teacher_id: int, on_date: date_t) -> bool:
    return any(tid == teacher_id and fr <= on_date <= to
               for (tid, fr, to) in ctx.leaves)


def _ctx_max_consecutive(ctx: PlanContext, day: str, occupied: set[int]) -> int:
    best = 0
    for run in ctx.runs.get(day, []):
        streak = 0
        for p in run:
            streak = streak + 1 if p in occupied else 0
            best = max(best, streak)
    return best


def _ctx_effective_map(ctx: PlanContext, section_id: int, day: str,
                       on_date: date_t,
                       placed: dict[tuple[int, str, int], int]) -> dict[int, int]:
    """Section's *effective* {period_no: subject_id} for a real date: base weekday
    timetable + other plans' confirmed exchanges + this plan's placements."""
    m = dict(ctx.section_day.get((section_id, day), {}))
    ov = ctx.overlay.get((section_id, on_date.isoformat()))
    if ov:
        m.update(ov)
    diso = on_date.isoformat()
    for (sec, d, period), sid in placed.items():
        if sec == section_id and d == diso:
            m[period] = sid
    return m


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

    # One-time load of everything the plan needs; all checks below are in-memory.
    ctx = _build_context(db, ver)

    rows: list[PeriodExchange] = []
    partner_plan_load: dict[int, int] = {}   # exchanges assigned to B within this plan
    # (partner_entry_id, recovery_date) pairs already used in this plan, to avoid reuse
    used_pairs: set[tuple[int, str]] = set()
    # (teacher_id, date, period) occupancy created by this plan's exchanges
    reserved: set[tuple[int, str, int]] = set()
    # (section_id, date, period) -> subject_id placed there by this plan
    placed: dict[tuple[int, str, int], int] = {}

    all_affected = ctx.affected_by_teacher.get(leave.teacher_id, [])
    for on_date in _leave_dates(leave):
        day = WEEKDAY_TO_DAY[on_date.weekday()]
        for entry_a in all_affected:
            if entry_a.timeslot.day != day:
                continue

            # Lab block: splitting a consecutive lab breaks it — HOD handles manually.
            if entry_a.subject.needs_lab:
                rows.append(_no_partner_row(
                    db, pid, leave, entry_a, on_date,
                    "MANUAL HANDLING REQUIRED — lab block cannot be auto-exchanged"))
                continue

            best = _pick_partner(
                ctx, leave, entry_a, on_date, day,
                partner_plan_load, used_pairs, reserved, placed)

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
            # D: B's subject now sits in A's period; R: A's subject sits in B's period
            placed[(entry_a.section_id, on_date.isoformat(),
                    entry_a.timeslot.period_no)] = entry_b.subject_id
            placed[(entry_b.section_id, recovery_date.isoformat(),
                    entry_b.timeslot.period_no)] = entry_a.subject_id

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


def _adjacency_warnings(ctx, leave, entry_a, entry_b, on_date, day,
                        recovery_date, reserved, placed, absent_name):
    """Warnings for continuity problems this exchange would create: same subject
    back-to-back for students, >2 of a subject in one day, or 3+ consecutive
    teaching periods for a teacher. Empty list = a clean, non-hectic swap."""
    section_id = entry_a.section_id
    a_period = entry_a.timeslot.period_no
    b_period = entry_b.timeslot.period_no
    r_day = entry_b.timeslot.day
    warns: list[str] = []

    def _student_checks(day_, on_date_, target_period, incoming_subj, subj_code):
        post = _ctx_effective_map(ctx, section_id, day_, on_date_, placed)
        post[target_period] = incoming_subj
        for adj in ctx.adjacent.get((day_, target_period), set()):
            if post.get(adj) == incoming_subj:
                warns.append(f"back-to-back {subj_code} for students")
                break
        if sum(1 for s in post.values() if s == incoming_subj) > 2:
            warns.append(f"3+ periods of {subj_code} in one day for students")

    # D side: B's subject enters A's period.  R side: A's subject enters B's period.
    _student_checks(day, on_date, a_period, entry_b.subject_id, entry_b.subject.code)
    _student_checks(r_day, recovery_date, b_period, entry_a.subject_id, entry_a.subject.code)

    # Teacher run-length: B on D gains a_period; A on R gains b_period.
    b_periods = set(ctx.teacher_day.get((entry_b.teacher_id, day), set()))
    b_periods |= {p for (tid, d, p) in reserved
                  if tid == entry_b.teacher_id and d == on_date.isoformat()}
    b_periods.add(a_period)
    if _ctx_max_consecutive(ctx, day, b_periods) >= 3:
        warns.append(f"3 consecutive teaching periods for {entry_b.teacher.user.name}")

    a_periods = set(ctx.teacher_day.get((leave.teacher_id, r_day), set()))
    a_periods |= {p for (tid, d, p) in reserved
                  if tid == leave.teacher_id and d == recovery_date.isoformat()}
    a_periods.add(b_period)
    if _ctx_max_consecutive(ctx, r_day, a_periods) >= 3:
        warns.append(f"3 consecutive teaching periods for {absent_name}")

    # dedupe, preserve order
    seen: set[str] = set()
    return [w for w in warns if not (w in seen or seen.add(w))]


def _pick_partner(ctx, leave, entry_a, on_date, day,
                  partner_plan_load, used_pairs, reserved, placed):
    """Return (entry_b, recovery_date, rationale) for the best exchange, or None.

    Candidates that would create hectic back-to-back teaching for students or
    teachers are penalised heavily (not rejected), so a clean swap always wins
    when one exists but a flagged swap still beats "no exchange at all".
    All reads come from the pre-built PlanContext — no DB queries in this loop."""
    section_id = entry_a.section_id
    a_period = entry_a.timeslot.period_no
    absent_name = ctx.teacher_name.get(leave.teacher_id, "the absent teacher")

    # Candidate partner lessons: same section, different teacher (from ctx).
    candidates = [e for e in ctx.candidates_by_section.get(section_id, [])
                  if e.teacher_id != leave.teacher_id]

    best = None
    best_score = None
    seen_pairs: set[tuple[int, str]] = set()

    for entry_b in candidates:
        # Never exchange a lab block on the partner side either.
        if entry_b.subject.needs_lab:
            continue

        # B must be free at A's slot on the leave date D.
        if _ctx_on_leave(ctx, entry_b.teacher_id, on_date):
            continue
        if (entry_b.teacher_id, day, a_period) in ctx.busy:
            continue
        if (entry_b.teacher_id, on_date.isoformat(), a_period) in reserved:
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
        if _ctx_on_leave(ctx, leave.teacher_id, recovery_date):
            continue
        if (leave.teacher_id, entry_b.timeslot.day, b_period) in ctx.busy:
            continue
        if (leave.teacher_id, recovery_date.isoformat(), b_period) in reserved:
            continue

        seen_pairs.add(pair)

        warns = _adjacency_warnings(
            ctx, leave, entry_a, entry_b, on_date, day, recovery_date,
            reserved, placed, absent_name)

        gap = (recovery_date - on_date).days
        score = 0.0
        score -= 100.0 * len(warns)                                # avoid hectic swaps
        score -= 2.0 * gap                                          # prefer nearest recovery
        score -= 0.5 * partner_plan_load.get(entry_b.teacher_id, 0)  # spread within plan
        score -= 0.1 * ctx.loads.get(entry_b.teacher_id, 0)        # fairness: lighter load
        if best_score is None or score > best_score:
            rationale = (
                f"{entry_b.teacher.user.name} teaches {entry_b.subject.code} to this section; "
                f"swap with {entry_b.timeslot.day} P{b_period}, recovery on "
                f"{recovery_date.isoformat()} ({gap} day{'s' if gap != 1 else ''} later)"
            )
            if warns:
                rationale = "⚠ " + "; ".join(warns) + " — " + rationale
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
            "warning": bool(x.rationale and x.rationale.startswith("⚠")),
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
