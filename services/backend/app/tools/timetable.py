"""Typed timetable tools (docs/02-ARCHITECTURE.md §2.2).

Agents and API routes call these; nothing else touches the solver or the
timetable tables directly. Every mutation is versioned — history is preserved.
"""
import json

from sqlalchemy.orm import Session

from app.db.models import (
    Room, Section, Subject, Teacher, TimeSlot, TimetableConfig, TimetableEntry,
)
from app.db.session import SessionLocal
from app.solver.timetable_model import (
    RoomIn, SectionIn, SectionRules, SlotIn, SubjectIn, TeacherIn,
    TimetableInput, SolveOptions, SolveResult, solve,
)


def _minutes(t) -> int:
    return t.hour * 60 + t.minute


def load_timetable_input(db: Session) -> TimetableInput:
    """Assemble solver input from the DB. Sections take all subjects that match
    their dept + semester (the campus convention)."""
    subjects = {s.id: SubjectIn(s.id, s.code, s.periods_per_week, s.needs_lab)
                for s in db.query(Subject).all()}
    sections = []
    for sec in db.query(Section).all():
        sids = [s.id for s in db.query(Subject)
                .filter(Subject.dept == sec.dept, Subject.semester == sec.semester)]
        sections.append(SectionIn(sec.id, sec.name, sec.strength, sids))
    teachers = [TeacherIn(t.id, t.user.name, t.max_hours_per_day,
                          {s.id for s in t.subjects})
                for t in db.query(Teacher).all()]
    rooms = [RoomIn(r.id, r.name, r.type, r.capacity) for r in db.query(Room).all()]
    slots = [SlotIn(s.id, s.day, s.period_no, _minutes(s.start), _minutes(s.end))
             for s in db.query(TimeSlot).order_by(TimeSlot.id).all()]
    return TimetableInput(sections=sections, subjects=subjects,
                          teachers=teachers, rooms=rooms, slots=slots)


def _options_to_dict(db: Session, options: SolveOptions) -> dict:
    """SolveOptions -> JSON-friendly dict with section *names* (not ids) as keys,
    so persisted config is readable and stable across regenerations."""
    id_to_name = {s.id: s.name for s in db.query(Section).all()}
    section_rules = {}
    for sec_id, sr in options.section_rules.items():
        name = id_to_name.get(sec_id, str(sec_id))
        section_rules[name] = {
            "half_days": dict(sr.half_days),
            "no_same_subject_consecutive": sr.no_same_subject_consecutive,
        }
    return {
        "half_days": dict(options.half_days),
        "no_same_subject_consecutive": options.no_same_subject_consecutive,
        "max_consecutive_teaching": options.max_consecutive_teaching,
        "section_rules": section_rules,
    }


def _options_from_dict(db: Session, cfg: dict) -> SolveOptions:
    """Inverse of _options_to_dict — rebuild SolveOptions with section ids."""
    name_to_id = {s.name: s.id for s in db.query(Section).all()}
    section_rules: dict[int, SectionRules] = {}
    for name, sr in (cfg.get("section_rules") or {}).items():
        sec_id = name_to_id.get(name)
        if sec_id is None:
            continue
        section_rules[sec_id] = SectionRules(
            half_days={k: int(v) for k, v in (sr.get("half_days") or {}).items()},
            no_same_subject_consecutive=sr.get("no_same_subject_consecutive"),
        )
    return SolveOptions(
        half_days={k: int(v) for k, v in (cfg.get("half_days") or {}).items()},
        no_same_subject_consecutive=cfg.get("no_same_subject_consecutive", True),
        max_consecutive_teaching=cfg.get("max_consecutive_teaching"),
        section_rules=section_rules,
    )


def generate_timetable(time_limit_s: float = 8.0,
                       options: SolveOptions | None = None) -> dict:
    """Run the CP-SAT solver on current master data; on success store the result
    as a new timetable version and record the SolveOptions that produced it.
    Returns a JSON-friendly summary either way."""
    options = options or SolveOptions()
    db = SessionLocal()
    try:
        data = load_timetable_input(db)
        result: SolveResult = solve(data, opts=options, time_limit_s=time_limit_s)

        if result.status in ("optimal", "feasible"):
            prev = db.query(TimetableEntry.version)\
                     .order_by(TimetableEntry.version.desc()).first()
            version = (prev[0] + 1) if prev else 1
            for les in result.lessons:
                db.add(TimetableEntry(
                    section_id=les.section_id, subject_id=les.subject_id,
                    teacher_id=les.teacher_id, room_id=les.room_id,
                    timeslot_id=les.timeslot_id, status="active", version=version,
                ))
            cfg = _options_to_dict(db, options)
            db.add(TimetableConfig(version=version, config_json=json.dumps(cfg)))
            db.commit()
            return {
                "status": result.status,
                "version": version,
                **result.stats,
                "sections": len(data.sections),
                "teachers": len(data.teachers),
                "config": cfg,
            }
        return {"status": result.status, "reasons": result.reasons, **result.stats}
    finally:
        db.close()


def get_version_config(db: Session, version: int) -> dict:
    """The SolveOptions JSON that produced a timetable version ({} if none)."""
    row = (db.query(TimetableConfig)
           .filter(TimetableConfig.version == version).first())
    return json.loads(row.config_json) if row else {}


def options_from_config(db: Session, version: int | None = None) -> SolveOptions:
    """Rebuild the SolveOptions that produced a version (latest if None). Falls
    back to defaults (which keep no-same-subject-consecutive ON) when there is no
    stored config — so agent/chat regeneration still avoids back-to-back periods."""
    if version is None:
        version = latest_version(db)
    if version is None:
        return SolveOptions()
    cfg = get_version_config(db, version)
    return _options_from_dict(db, cfg) if cfg else SolveOptions()


def latest_version(db: Session) -> int | None:
    row = db.query(TimetableEntry.version)\
            .order_by(TimetableEntry.version.desc()).first()
    return row[0] if row else None


def get_section_grid(db: Session, section_name: str) -> dict:
    """Latest-version grid for one section: {days, periods, cells{day-period: lesson}}."""
    sec = db.query(Section).filter(Section.name == section_name).first()
    if not sec:
        return {"error": f"Section '{section_name}' not found"}
    ver = latest_version(db)
    if ver is None:
        return {"error": "No timetable generated yet"}
    entries = (db.query(TimetableEntry)
               .filter(TimetableEntry.section_id == sec.id,
                       TimetableEntry.version == ver,
                       TimetableEntry.status == "active").all())
    cells = {}
    for e in entries:
        key = f"{e.timeslot.day}-{e.timeslot.period_no}"
        cells[key] = {
            "subject_code": e.subject.code,
            "subject_name": e.subject.name,
            "teacher": e.teacher.user.name,
            "room": e.room.name,
            "is_lab": e.subject.needs_lab,
        }
    slots = db.query(TimeSlot).order_by(TimeSlot.id).all()
    days, periods = [], {}
    for s in slots:
        if s.day not in days:
            days.append(s.day)
        periods[s.period_no] = f"{s.start.strftime('%H:%M')}–{s.end.strftime('%H:%M')}"
    return {"section": sec.name, "version": ver, "days": days,
            "periods": periods, "cells": cells}


def get_teacher_grid(db: Session, teacher_id: int) -> dict:
    """Latest-version grid for one teacher (used by substitution planning in Phase 2)."""
    t = db.get(Teacher, teacher_id)
    if not t:
        return {"error": f"Teacher {teacher_id} not found"}
    ver = latest_version(db)
    if ver is None:
        return {"error": "No timetable generated yet"}
    entries = (db.query(TimetableEntry)
               .filter(TimetableEntry.teacher_id == teacher_id,
                       TimetableEntry.version == ver,
                       TimetableEntry.status == "active").all())
    cells = {}
    for e in entries:
        key = f"{e.timeslot.day}-{e.timeslot.period_no}"
        cells[key] = {
            "subject_code": e.subject.code,
            "section": e.section.name,
            "room": e.room.name,
        }
    return {"teacher": t.user.name, "version": ver, "cells": cells,
            "weekly_load": len(entries)}
