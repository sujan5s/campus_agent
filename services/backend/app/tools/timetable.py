"""Typed timetable tools (docs/02-ARCHITECTURE.md §2.2).

Agents and API routes call these; nothing else touches the solver or the
timetable tables directly. Every mutation is versioned — history is preserved.
"""
from sqlalchemy.orm import Session

from app.db.models import Room, Section, Subject, Teacher, TimeSlot, TimetableEntry
from app.db.session import SessionLocal
from app.solver.timetable_model import (
    RoomIn, SectionIn, SlotIn, SubjectIn, TeacherIn, TimetableInput,
    SolveResult, solve,
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


def generate_timetable(time_limit_s: float = 8.0) -> dict:
    """Run the CP-SAT solver on current master data; on success store the result
    as a new timetable version. Returns a JSON-friendly summary either way."""
    db = SessionLocal()
    try:
        data = load_timetable_input(db)
        result: SolveResult = solve(data, time_limit_s=time_limit_s)

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
            db.commit()
            return {
                "status": result.status,
                "version": version,
                **result.stats,
                "sections": len(data.sections),
                "teachers": len(data.teachers),
            }
        return {"status": result.status, "reasons": result.reasons, **result.stats}
    finally:
        db.close()


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
