"""Typed timetable tools (docs/02-ARCHITECTURE.md §2.2).

Agents and API routes call these; nothing else touches the solver or the
timetable tables directly. Every mutation is versioned — history is preserved.
"""
import json

from sqlalchemy.orm import Session

from app.db.models import (
    Constraint, ElectiveGroup, Room, Section, Subject, Teacher, TeachingAssignment,
    TimeSlot, TimetableConfig, TimetableEntry,
)
from app.db.session import SessionLocal
from app.solver.timetable_model import (
    ElectiveGroupIn, ElectiveOfferingIn, RoomIn, ScopeRules, SectionIn, SectionRules,
    SlotIn, SubjectIn, TeacherIn, TimetableInput, SolveOptions, SolveResult, solve,
)


def _minutes(t) -> int:
    return t.hour * 60 + t.minute


def load_timetable_input(db: Session,
                         options: SolveOptions | None = None) -> TimetableInput:
    """Assemble solver input from the DB. Sections take all subjects that match
    their dept + semester (the campus convention), minus anything offered inside
    an open-elective band — those periods belong to the band, not to one class.

    `options` only supplies the per-teacher caps compiled from the constraint
    registry; every other rule is read by the solver itself."""
    options = options or SolveOptions()
    subjects = {s.id: SubjectIn(s.id, s.code, s.periods_per_week, s.needs_lab)
                for s in db.query(Subject).all()}

    # --- open-elective bands (Phase 2.4) -----------------------------------
    electives: list[ElectiveGroupIn] = []
    elective_subject_ids: set[int] = set()
    for g in db.query(ElectiveGroup).filter(ElectiveGroup.active.is_(True)).all():
        offerings = [ElectiveOfferingIn(o.id, o.subject_id, o.subject.code,
                                        o.teacher_id, o.room_id)
                     for o in g.offerings]
        if not offerings:
            continue
        elective_subject_ids.update(o.subject_id for o in offerings)
        electives.append(ElectiveGroupIn(
            id=g.id, name=g.name, semester=g.semester,
            periods_per_week=g.periods_per_week, needs_block=g.needs_block,
            offerings=offerings))

    sections = []
    for sec in db.query(Section).all():
        sids = [s.id for s in db.query(Subject)
                .filter(Subject.dept == sec.dept, Subject.semester == sec.semester)
                if s.id not in elective_subject_ids]
        sections.append(SectionIn(sec.id, sec.name, sec.strength, sids,
                                  semester=sec.semester))

    caps = options.teacher_caps or {}
    teachers = []
    for t in db.query(Teacher).all():
        cap = caps.get(t.id, {})
        teachers.append(TeacherIn(
            id=t.id, name=t.user.name,
            max_hours_per_day=cap.get("teacher_max_daily", t.max_hours_per_day),
            subject_ids={s.id for s in t.subjects},
            max_consecutive=cap.get("teacher_max_consecutive"),
            max_hours_per_week=cap.get("teacher_max_weekly"),
        ))

    rooms = [RoomIn(r.id, r.name, r.type, r.capacity) for r in db.query(Room).all()]
    slots = [SlotIn(s.id, s.day, s.period_no, _minutes(s.start), _minutes(s.end))
             for s in db.query(TimeSlot).order_by(TimeSlot.id).all()]

    # --- admin teacher pins (Phase 2.4) ------------------------------------
    assignments = {(a.section_id, a.subject_id): a.teacher_id
                   for a in db.query(TeachingAssignment).all()}

    return TimetableInput(sections=sections, subjects=subjects,
                          teachers=teachers, rooms=rooms, slots=slots,
                          assignments=assignments, electives=electives)


def _options_to_dict(db: Session, options: SolveOptions) -> dict:
    """SolveOptions -> JSON-friendly snapshot of what produced one version.

    Section/semester keys are *names and numbers*, not ids, so the record stays
    readable after data changes. The `rules` list is the plain-English form shown
    in the UI and the PDF header. The legacy top-level keys are kept so Phase 2.2
    /2.3 readers (and `_options_from_dict`) still work."""
    id_to_name = {sec.id: sec.name for sec in db.query(Section).all()}

    def scope_dict(sr: ScopeRules) -> dict:
        return {
            "half_days": dict(sr.half_days),
            "no_same_subject_consecutive": sr.no_same_subject_consecutive,
            "max_consecutive_teaching": sr.max_consecutive_teaching,
            "subject_daily_max": sr.subject_daily_max,
            "max_periods_per_day": sr.max_periods_per_day,
        }

    return {
        "half_days": dict(options.half_days),
        "no_same_subject_consecutive": options.no_same_subject_consecutive,
        "max_consecutive_teaching": options.max_consecutive_teaching,
        "subject_daily_max": options.subject_daily_max,
        "max_periods_per_day": options.max_periods_per_day,
        "semester_rules": {str(sem): scope_dict(sr)
                           for sem, sr in options.semester_rules.items()},
        "section_rules": {id_to_name.get(sid, str(sid)): scope_dict(sr)
                          for sid, sr in options.section_rules.items()},
        "bans": [{"target": b.target, "ref_id": b.ref_id, "days": b.days,
                  "periods": b.periods, "label": b.label} for b in options.bans],
        "preferred": [{"subject_id": pr.subject_id, "periods": pr.periods,
                       "days": pr.days, "weight": pr.weight, "label": pr.label}
                      for pr in options.preferred],
        "avoid_gaps_weight": options.avoid_gaps_weight,
        "rules": [c.description for c in db.query(Constraint)
                  .filter(Constraint.enabled.is_(True)).all()],
    }


def _options_from_dict(db: Session, cfg: dict) -> SolveOptions:
    """Inverse of _options_to_dict — rebuild SolveOptions with section ids.

    Only used to read *historic* versions; live generation compiles the registry
    instead (see `current_options`)."""
    name_to_id = {sec.name: sec.id for sec in db.query(Section).all()}

    def scope(sr: dict) -> ScopeRules:
        return ScopeRules(
            half_days={k: int(v) for k, v in (sr.get("half_days") or {}).items()},
            no_same_subject_consecutive=sr.get("no_same_subject_consecutive"),
            max_consecutive_teaching=sr.get("max_consecutive_teaching"),
            subject_daily_max=sr.get("subject_daily_max"),
            max_periods_per_day=sr.get("max_periods_per_day"),
        )

    section_rules: dict[int, ScopeRules] = {}
    for name, sr in (cfg.get("section_rules") or {}).items():
        sec_id = name_to_id.get(name)
        if sec_id is not None:
            section_rules[sec_id] = scope(sr)
    semester_rules: dict[int, ScopeRules] = {}
    for sem, sr in (cfg.get("semester_rules") or {}).items():
        try:
            semester_rules[int(sem)] = scope(sr)
        except (TypeError, ValueError):
            continue
    return SolveOptions(
        half_days={k: int(v) for k, v in (cfg.get("half_days") or {}).items()},
        no_same_subject_consecutive=cfg.get("no_same_subject_consecutive", True),
        max_consecutive_teaching=cfg.get("max_consecutive_teaching"),
        subject_daily_max=cfg.get("subject_daily_max", 2),
        max_periods_per_day=cfg.get("max_periods_per_day"),
        semester_rules=semester_rules,
        section_rules=section_rules,
        avoid_gaps_weight=cfg.get("avoid_gaps_weight", 0),
    )


def current_options(db: Session) -> SolveOptions:
    """The rules generation should use *now*: the constraint registry, compiled.

    Imported lazily because `tools.constraints` imports the solver types too."""
    from app.tools.constraints import compile_options, ensure_defaults

    ensure_defaults(db)
    return compile_options(db)


def generate_timetable(time_limit_s: float = 8.0,
                       options: SolveOptions | None = None) -> dict:
    """Run the CP-SAT solver on current master data; on success store the result
    as a new timetable version and record the rules that produced it.

    `options` defaults to the compiled constraint registry — callers no longer
    need to assemble rules by hand. Returns a JSON-friendly summary either way."""
    db = SessionLocal()
    try:
        if options is None:
            options = current_options(db)
        data = load_timetable_input(db, options)
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
            # Open-elective bands: one row per section of the semester per band
            # period, tagged with the group. subject/teacher/room point at the
            # first basket so every existing reader (grids, exchanges, PDF) keeps
            # working; the UI expands the full basket list from the tag.
            groups = {g.id: g for g in db.query(ElectiveGroup).all()}
            for place in result.electives:
                g = groups.get(place.group_id)
                if not g or not g.offerings:
                    continue
                head = g.offerings[0]
                for sec in db.query(Section).filter(Section.semester == g.semester):
                    db.add(TimetableEntry(
                        section_id=sec.id, subject_id=head.subject_id,
                        teacher_id=head.teacher_id, room_id=head.room_id,
                        timeslot_id=place.timeslot_id, status="active",
                        version=version, elective_group_id=g.id,
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
    """Rules for a *specific* historic version, rebuilt from its snapshot.

    With no version this returns the live registry (`current_options`) — chat and
    agent regeneration therefore always use the admin's current constraints
    rather than a frozen copy of an old run."""
    if version is None:
        return current_options(db)
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
        cell = {
            "subject_code": e.subject.code,
            "subject_name": e.subject.name,
            "teacher": e.teacher.user.name,
            "room": e.room.name,
            "is_lab": e.subject.needs_lab,
        }
        if e.elective_group_id:
            # An open-elective period: the whole semester sits here and the
            # baskets run in parallel, so the cell shows the band, not one subject.
            g = db.get(ElectiveGroup, e.elective_group_id)
            if g:
                cell.update({
                    "subject_code": g.name,
                    "subject_name": f"Open Elective ({g.name})",
                    "teacher": f"{len(g.offerings)} parallel option(s)",
                    "room": "various",
                    "is_lab": False,
                    "elective": {
                        "group": g.name,
                        "offerings": [{
                            "subject_code": o.subject.code,
                            "subject_name": o.subject.name,
                            "teacher": o.teacher.user.name,
                            "room": o.room.name,
                        } for o in g.offerings],
                    },
                })
        cells[key] = cell
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
