"""Timetable API — generation (admin) + grid views (any authenticated user).

Includes the Phase 2.1 dated (effective) views that overlay confirmed period
exchanges on top of the original timetable — the original entries are never
mutated (docs/06-EXCHANGE-PLAN.md §5)."""
from datetime import date as date_t, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_role
from app.db.models import PeriodExchange, Section, TimeSlot, TimetableEntry
from app.db.session import get_db
from app.solver.timetable_model import SolveOptions, SectionRules
from app.tools.substitution import WEEKDAY_TO_DAY
from app.tools.timetable import (
    generate_timetable, get_section_grid, get_teacher_grid,
    get_version_config, latest_version,
)

router = APIRouter()


class HalfDayIn(BaseModel):
    day: str                                    # MON..FRI
    last_period: int = Field(ge=1)              # day ends after this period


class SectionRulesIn(BaseModel):
    section: str                                # section name, e.g. "CSE-7A"
    half_days: list[HalfDayIn] = []
    no_same_subject_consecutive: bool | None = None   # None = inherit global


class GenerateIn(BaseModel):
    half_days: list[HalfDayIn] = []
    no_same_subject_consecutive: bool = True    # default ON — avoid back-to-back subjects
    max_consecutive_teaching: int | None = Field(default=None, ge=1)
    sections: list[SectionRulesIn] = []         # per-section overrides


def _parse_date(s: str) -> date_t:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")


def _slot_time(entry: TimetableEntry) -> str:
    ts = entry.timeslot
    return f"{ts.start.strftime('%H:%M')}–{ts.end.strftime('%H:%M')}"


@router.post("/generate", dependencies=[Depends(require_role("admin"))])
def generate(body: GenerateIn | None = None, db: Session = Depends(get_db)):
    """Run the CP-SAT solver on current master data. Stores a new version on
    success. An optional body carries admin constraints (half-days, no
    back-to-back subjects, teacher run cap); no body = default generation."""
    body = body or GenerateIn()
    opts = _build_options(db, body)
    result = generate_timetable(options=opts)
    if result["status"] in ("optimal", "feasible"):
        return result
    # infeasible / error → 422 with the precise reasons for the UI to display
    raise HTTPException(status_code=422, detail=result)


def _build_options(db: Session, body: GenerateIn) -> SolveOptions:
    """Validate the request against the real slot grid and map it to SolveOptions."""
    grid: dict[str, list[int]] = {}
    for s in db.query(TimeSlot).all():
        grid.setdefault(s.day, []).append(s.period_no)

    def _half_days(items: list[HalfDayIn], where: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for hd in items:
            if hd.day not in grid:
                raise HTTPException(422, f"{where}Day '{hd.day}' has no timeslots.")
            max_p = max(grid[hd.day])
            if hd.last_period < 1 or hd.last_period >= max_p:
                raise HTTPException(
                    422, f"{where}{hd.day}: last_period must be 1..{max_p - 1} "
                    f"(the day has periods up to P{max_p}).")
            out[hd.day] = hd.last_period
        return out

    name_to_id = {s.name: s.id for s in db.query(Section).all()}
    section_rules: dict[int, SectionRules] = {}
    for sr in body.sections:
        sec_id = name_to_id.get(sr.section)
        if sec_id is None:
            raise HTTPException(422, f"Unknown section '{sr.section}'.")
        if sec_id in section_rules:
            raise HTTPException(422, f"Duplicate rules for section '{sr.section}'.")
        section_rules[sec_id] = SectionRules(
            half_days=_half_days(sr.half_days, f"Section {sr.section}: "),
            no_same_subject_consecutive=sr.no_same_subject_consecutive,
        )

    return SolveOptions(
        half_days=_half_days(body.half_days, ""),
        no_same_subject_consecutive=body.no_same_subject_consecutive,
        max_consecutive_teaching=body.max_consecutive_teaching,
        section_rules=section_rules,
    )


@router.get("/status")
def status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    ver = latest_version(db)
    return {"latest_version": ver,
            "config": get_version_config(db, ver) if ver is not None else {}}


@router.get("/section/{name}")
def section_grid(name: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    grid = get_section_grid(db, name)
    if "error" in grid:
        raise HTTPException(status_code=404, detail=grid["error"])
    return grid


@router.get("/teacher/{tid}")
def teacher_grid(tid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    grid = get_teacher_grid(db, tid)
    if "error" in grid:
        raise HTTPException(status_code=404, detail=grid["error"])
    return grid


@router.get("/effective/{section_name}")
def effective_grid(section_name: str, date: str,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Single-day grid for a section on a given date, with confirmed period
    exchanges overlaid. The original timetable is never modified — this is a
    dated overlay only (docs/06-EXCHANGE-PLAN.md §5)."""
    on_date = _parse_date(date)
    sec = db.query(Section).filter(Section.name == section_name).first()
    if not sec:
        raise HTTPException(404, f"Section '{section_name}' not found")
    ver = latest_version(db)
    if ver is None:
        raise HTTPException(404, "No timetable generated yet")

    weekday = on_date.weekday()
    if weekday > 4:  # SAT/SUN
        return {"section": sec.name, "date": on_date.isoformat(),
                "day": None, "periods": {}, "entries": [],
                "note": "Weekend — no scheduled periods."}
    day = WEEKDAY_TO_DAY[weekday]

    base = (db.query(TimetableEntry)
            .filter(TimetableEntry.section_id == sec.id,
                    TimetableEntry.version == ver,
                    TimetableEntry.status == "active").all())
    base = [e for e in base if e.timeslot.day == day]

    # Confirmed exchanges touching this date (either side).
    confirmed = (db.query(PeriodExchange)
                 .filter(PeriodExchange.status == "confirmed").all())
    leave_side = {x.absent_entry_id: x for x in confirmed if x.leave_date == on_date}
    recovery_side = {x.partner_entry_id: x for x in confirmed if x.recovery_date == on_date}

    entries = []
    for e in base:
        item = {
            "period": e.timeslot.period_no,
            "time": _slot_time(e),
            "subject": e.subject.code,
            "subject_name": e.subject.name,
            "teacher": e.teacher.user.name,
            "room": e.room.name,
            "exchanged": False,
        }
        if e.id in leave_side:
            # A's slot is taken by partner B teaching B's own subject.
            x = leave_side[e.id]
            entry_b = db.get(TimetableEntry, x.partner_entry_id)
            item["exchanged"] = True
            item["subject"] = entry_b.subject.code
            item["subject_name"] = entry_b.subject.name
            item["teacher"] = entry_b.teacher.user.name
            item["swap"] = {
                "role": "exchanged_in",
                "with": e.teacher.user.name,
                "their_subject": e.subject.code,
                "counterpart_date": x.recovery_date.isoformat() if x.recovery_date else None,
                "counterpart_period": entry_b.timeslot.period_no,
                "counterpart_day": entry_b.timeslot.day,
            }
        elif e.id in recovery_side:
            # B's slot hosts A recovering A's own missed subject.
            x = recovery_side[e.id]
            entry_a = db.get(TimetableEntry, x.absent_entry_id)
            item["exchanged"] = True
            item["subject"] = entry_a.subject.code
            item["subject_name"] = entry_a.subject.name
            item["teacher"] = entry_a.teacher.user.name
            item["swap"] = {
                "role": "recovery",
                "with": e.teacher.user.name,
                "their_subject": e.subject.code,
                "counterpart_date": x.leave_date.isoformat(),
                "counterpart_period": entry_a.timeslot.period_no,
                "counterpart_day": entry_a.timeslot.day,
            }
        entries.append(item)

    entries.sort(key=lambda i: i["period"])
    periods = {i["period"]: i["time"] for i in entries}
    return {"section": sec.name, "date": on_date.isoformat(), "day": day,
            "version": ver, "periods": periods, "entries": entries}


@router.get("/exchanges")
def exchanges_board(
    db: Session = Depends(get_db), user=Depends(get_current_user),
    from_: str | None = Query(None, alias="from"), to: str | None = None,
):
    """Flat list of confirmed period exchanges within a date range (default:
    today → +14 days), each carrying both the leave-date side and the recovery
    side. Powers the 'who got exchanged, on which date' board."""
    start = _parse_date(from_) if from_ else date_t.today()
    end = _parse_date(to) if to else start + timedelta(days=14)

    confirmed = (db.query(PeriodExchange)
                 .filter(PeriodExchange.status == "confirmed").all())
    out = []
    for x in confirmed:
        if not x.partner_entry_id:
            continue
        in_range = (start <= x.leave_date <= end) or (
            x.recovery_date is not None and start <= x.recovery_date <= end)
        if not in_range:
            continue
        entry_a = db.get(TimetableEntry, x.absent_entry_id)
        entry_b = db.get(TimetableEntry, x.partner_entry_id)
        out.append({
            "exchange_id": x.id,
            "section": entry_a.section.name,
            # Leave-date side: partner teaches their own subject in place of A
            "leave_date": x.leave_date.isoformat(),
            "leave_day": entry_a.timeslot.day,
            "leave_period": entry_a.timeslot.period_no,
            "leave_time": _slot_time(entry_a),
            "leave_room": entry_a.room.name,
            "partner": entry_b.teacher.user.name,
            "partner_subject": entry_b.subject.code,
            "absent": entry_a.teacher.user.name,
            "missed_subject": entry_a.subject.code,
            # Recovery side: A teaches A's own missed subject in B's slot
            "recovery_date": x.recovery_date.isoformat() if x.recovery_date else None,
            "recovery_day": entry_b.timeslot.day,
            "recovery_period": entry_b.timeslot.period_no,
            "recovery_time": _slot_time(entry_b),
            "recovery_room": entry_b.room.name,
        })
    out.sort(key=lambda i: (i["leave_date"], i["leave_period"]))
    return {"from": start.isoformat(), "to": end.isoformat(), "exchanges": out}
