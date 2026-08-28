"""Unified operation registry (Phase 2.5) — everything the agent may do to
timetable data, as typed operations.

Phase 2.4 let the LLM write *rules* but nothing else: naming a teacher who did
not exist was an error, so the admin had to go back to the Setup forms and type
it in by hand. That is the repetitive work this system exists to remove. Here the
agent creates the teacher, the subject, the room or the class itself, then keeps
going and uses it.

What is deliberately kept from 2.4 is the *shape* of a write, not the refusal:

    sentence -> typed ops -> validated against live data -> previewed -> applied

Nothing is executed as free text, every op is checked before it runs, and the
admin sees the whole batch in English before it commits. That is one click for a
plan of any size — it is not manual data entry.

Two things make a multi-step sentence work:

* **Forward references.** "add a teacher John who takes CS701 for CSE-7A" is three
  ops, and the second refers to something the first has not created yet. Validation
  walks the batch in order carrying a `pending` set, so a later op may refer to an
  entity an earlier op will create. Application is sequential, so by then it exists.
* **Implied fixups.** Assigning a teacher to a subject they are not yet qualified
  for simply adds the qualification. The admin asked for the outcome; chasing the
  prerequisite is exactly the busywork being removed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    Constraint, ElectiveGroup, ElectiveOffering, Room, Section, Subject, Teacher,
    TeachingAssignment, User,
)
from app.tools import constraints as reg

ROOM_TYPES = ("classroom", "lab", "auditorium", "seminar", "ground")


class OpError(ValueError):
    """An operation that cannot run — the message is shown to the admin."""


# ---------- plan context: live data + what earlier ops will create ----------

class _Stub:
    """A stand-in for an entity an earlier op will create.

    Rules can legitimately mention something being created in the same breath —
    "add a class CSE-2A and cap semester 2 at 5 periods a day". The rule validator
    in `tools/constraints.py` resolves names against `Ctx`, so a pending entity is
    inserted there as a stub carrying only the attributes that validator reads.
    Ids are negative and never persisted: `run()` re-validates against the real
    database, where the entity exists by then and has its real id."""

    def __init__(self, **attrs):
        self.__dict__.update(attrs)


_STUB_ID = -1


def _next_stub_id() -> int:
    global _STUB_ID
    _STUB_ID -= 1
    return _STUB_ID


@dataclass
class PlanCtx:
    """Everything an op needs to validate itself, including the not-yet-real.

    `pending_*` hold the keys earlier ops in the same batch will bring into
    existence, so a batch can build on itself."""
    db: Session
    ctx: reg.Ctx
    pending_teachers: set[str] = field(default_factory=set)   # lowercased names
    pending_subjects: set[str] = field(default_factory=set)   # upper codes
    pending_rooms: set[str] = field(default_factory=set)      # lowercased names
    pending_sections: set[str] = field(default_factory=set)   # lowercased names
    pending_bands: set[str] = field(default_factory=set)      # lowercased names

    def refresh(self) -> None:
        self.ctx = reg.build_ctx(self.db)

    # -- record what an op will create, so later ops (and rules) can use it ----

    def note_subject(self, norm: dict) -> None:
        self.pending_subjects.add(norm["code"])
        self.ctx.subjects_by_code.setdefault(norm["code"], _Stub(
            id=_next_stub_id(), code=norm["code"], name=norm.get("name", norm["code"]),
            semester=norm.get("semester", 0), needs_lab=norm.get("needs_lab", False)))

    def note_teacher(self, norm: dict) -> None:
        name = norm["name"]
        self.pending_teachers.add(name.lower())
        self.ctx.teacher_names.setdefault(name.lower(), _Stub(
            id=_next_stub_id(), user=_Stub(name=name, email=norm.get("email") or ""),
            subjects=[]))

    def note_room(self, norm: dict) -> None:
        self.pending_rooms.add(norm["name"].lower())

    def note_section(self, norm: dict) -> None:
        name, sem = norm["name"], norm["semester"]
        self.pending_sections.add(name.lower())
        self.ctx.sections.setdefault(name, _Stub(
            id=_next_stub_id(), name=name, semester=sem,
            dept=norm.get("dept", "CSE"), strength=norm.get("strength", 60)))
        if sem not in self.ctx.semesters:
            self.ctx.semesters = sorted(self.ctx.semesters + [sem])

    def note_band(self, norm: dict) -> None:
        self.pending_bands.add(norm["name"].lower())
        self.ctx.bands.append(_Stub(
            id=_next_stub_id(), name=norm["name"], semester=norm["semester"],
            periods_per_week=norm.get("periods_per_week", 3)))

    # -- lookups that tolerate "an earlier op is about to make this" ----------

    def teacher_exists(self, name: str) -> bool:
        key = (name or "").strip().lower()
        if not key:
            return False
        if key in self.pending_teachers:
            return True
        if key in self.ctx.teacher_names:
            return True
        return any(key in k for k in self.ctx.teacher_names)

    def subject_exists(self, code: str) -> bool:
        key = (code or "").strip().upper()
        return bool(key) and (key in self.pending_subjects
                              or key in self.ctx.subjects_by_code)

    def room_exists(self, name: str) -> bool:
        key = (name or "").strip().lower()
        return bool(key) and (key in self.pending_rooms or any(
            r.name.strip().lower() == key for r in self.db.query(Room).all()))

    def section_exists(self, name: str) -> bool:
        key = (name or "").strip().lower()
        return bool(key) and (key in self.pending_sections
                              or any(n.lower() == key for n in self.ctx.sections))

    def band_exists(self, name: str) -> bool:
        key = (name or "").strip().lower()
        return bool(key) and (key in self.pending_bands
                              or any(b.name.lower() == key for b in self.ctx.bands))


# ---------- small coercers ----------

def _text(params: dict, key: str, what: str, max_len: int = 200) -> str:
    v = str(params.get(key) or "").strip()
    if not v:
        raise OpError(f"{what} is required.")
    return v[:max_len]


def _int(params: dict, key: str, what: str, lo: int, hi: int, default=None) -> int:
    raw = params.get(key, default)
    if raw is None:
        raise OpError(f"{what} is required.")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise OpError(f"{what} must be a whole number, got '{raw}'.")
    if not lo <= n <= hi:
        raise OpError(f"{what} must be between {lo} and {hi}, got {n}.")
    return n


def _codes(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;\s]+", value)
    return [str(v).strip().upper() for v in value if str(v).strip()]


def _derive_email(db: Session, name: str) -> str:
    """first.last@campus.edu, uniquified — so the admin never has to invent one."""
    slug = re.sub(r"[^a-z\s.]", "", name.lower())
    slug = re.sub(r"^(dr|prof|mr|mrs|ms)\.?\s+", "", slug).strip()
    slug = re.sub(r"\s+", ".", slug) or "faculty"
    base, n = f"{slug}@campus.edu", 1
    email = base
    while db.query(User).filter(User.email == email).first():
        n += 1
        email = f"{slug}{n}@campus.edu"
    return email


def _find_teacher(db: Session, name: str) -> Teacher:
    key = (name or "").strip().lower()
    for t in db.query(Teacher).all():
        if t.user and (t.user.name.strip().lower() == key
                       or t.user.email.strip().lower() == key):
            return t
    hits = [t for t in db.query(Teacher).all()
            if t.user and key and key in t.user.name.strip().lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise OpError(f"'{name}' matches more than one teacher — use the full name.")
    raise OpError(f"No teacher named '{name}'.")


def _find_subject(db: Session, code: str) -> Subject:
    s = db.query(Subject).filter(Subject.code == (code or "").strip().upper()).first()
    if not s:
        raise OpError(f"No subject with code '{code}'.")
    return s


def _find_section(db: Session, name: str) -> Section:
    key = (name or "").strip().lower()
    s = next((x for x in db.query(Section).all() if x.name.lower() == key), None)
    if not s:
        raise OpError(f"No class named '{name}'.")
    return s


def _find_room(db: Session, name: str) -> Room:
    key = (name or "").strip().lower()
    r = next((x for x in db.query(Room).all() if x.name.lower() == key), None)
    if not r:
        raise OpError(f"No room named '{name}'.")
    return r


def _find_band(db: Session, name: str) -> ElectiveGroup:
    key = (name or "").strip().lower()
    g = next((x for x in db.query(ElectiveGroup).all() if x.name.lower() == key), None)
    if not g:
        raise OpError(f"No elective band named '{name}'.")
    return g


def _ensure_qualified(db: Session, teacher: Teacher, subject: Subject) -> bool:
    """Give a teacher a subject they are being asked to teach. Returns True if it
    had to be added — the admin wants the outcome, not the prerequisite."""
    if subject in teacher.subjects:
        return False
    teacher.subjects.append(subject)
    return True


# ---------- the op catalog ----------

@dataclass
class OpSpec:
    key: str
    label: str
    validate: Callable[[PlanCtx, dict], dict]
    describe: Callable[[dict], str]
    apply: Callable[[Session, dict], str]
    destructive: bool = False
    # Called after this op validates, to register what it will create so later
    # ops in the same batch — including rules — can refer to it.
    note: Callable[[PlanCtx, dict], None] | None = None


OPS: dict[str, OpSpec] = {}


def _op(spec: OpSpec) -> None:
    OPS[spec.key] = spec


# --- subjects ---------------------------------------------------------------

def _v_add_subject(pc: PlanCtx, p: dict) -> dict:
    code = _text(p, "code", "Subject code", 20).upper()
    if pc.subject_exists(code):
        raise OpError(f"Subject {code} already exists — edit it instead.")
    return {
        "code": code,
        "name": _text(p, "name", "Subject name", 120),
        "dept": str(p.get("dept") or "CSE").strip()[:50],
        "semester": _int(p, "semester", "Semester", 1, 12),
        "periods_per_week": _int(p, "periods_per_week", "Periods per week", 1, 20, 4),
        "needs_lab": bool(p.get("needs_lab", False)),
    }


def _a_add_subject(db: Session, p: dict) -> str:
    db.add(Subject(code=p["code"], name=p["name"], dept=p["dept"],
                   semester=p["semester"], periods_per_week=p["periods_per_week"],
                   needs_lab=p["needs_lab"]))
    db.flush()
    return f"added subject {p['code']}"


_op(OpSpec(
    key="add_subject", label="Add subject",
    validate=_v_add_subject,
    describe=lambda p: (f"add subject {p['code']} “{p['name']}” — semester {p['semester']}, "
                        f"{p['periods_per_week']} periods/week"
                        + (" (lab)" if p["needs_lab"] else "")),
    apply=_a_add_subject, note=lambda pc, n: pc.note_subject(n),
))


def _v_edit_subject(pc: PlanCtx, p: dict) -> dict:
    code = _text(p, "code", "Subject code", 20).upper()
    if not pc.subject_exists(code):
        raise OpError(f"No subject with code '{code}'.")
    out: dict = {"code": code}
    for key, lo, hi in (("semester", 1, 12), ("periods_per_week", 1, 20)):
        if p.get(key) is not None:
            out[key] = _int(p, key, key.replace("_", " "), lo, hi)
    if p.get("name"):
        out["name"] = str(p["name"]).strip()[:120]
    if p.get("needs_lab") is not None:
        out["needs_lab"] = bool(p["needs_lab"])
    if len(out) == 1:
        raise OpError(f"Nothing to change on {code}.")
    return out


def _a_edit_subject(db: Session, p: dict) -> str:
    s = _find_subject(db, p["code"])
    for k, v in p.items():
        if k != "code":
            setattr(s, k, v)
    return f"updated subject {p['code']}"


_op(OpSpec(
    key="edit_subject", label="Edit subject",
    validate=_v_edit_subject,
    describe=lambda p: f"change subject {p['code']}: " + ", ".join(
        f"{k} → {v}" for k, v in p.items() if k != "code"),
    apply=_a_edit_subject,
))


def _v_remove_subject(pc: PlanCtx, p: dict) -> dict:
    code = _text(p, "code", "Subject code", 20).upper()
    if not pc.subject_exists(code):
        raise OpError(f"No subject with code '{code}'.")
    return {"code": code}


def _a_remove_subject(db: Session, p: dict) -> str:
    s = _find_subject(db, p["code"])
    for t in db.query(Teacher).all():
        if s in t.subjects:
            t.subjects.remove(s)
    for a in db.query(TeachingAssignment).filter(TeachingAssignment.subject_id == s.id):
        db.delete(a)
    for o in db.query(ElectiveOffering).filter(ElectiveOffering.subject_id == s.id):
        db.delete(o)
    db.delete(s)
    return f"removed subject {p['code']}"


_op(OpSpec(
    key="remove_subject", label="Remove subject", destructive=True,
    validate=_v_remove_subject,
    describe=lambda p: f"remove subject {p['code']} (and its teacher mappings and pins)",
    apply=_a_remove_subject,
))


# --- teachers ---------------------------------------------------------------

def _v_add_teacher(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Teacher name", 120)
    if pc.teacher_exists(name):
        raise OpError(f"A teacher matching '{name}' already exists — edit them instead.")
    subjects = _codes(p.get("subjects") or p.get("subject_codes"))
    unknown = [c for c in subjects if not pc.subject_exists(c)]
    if unknown:
        raise OpError(f"{name} would teach unknown subject(s) {', '.join(unknown)} — "
                      f"add those subjects in the same request.")
    return {
        "name": name,
        "email": str(p.get("email") or "").strip()[:200],
        "dept": str(p.get("dept") or "CSE").strip()[:50],
        "max_hours_per_day": _int(p, "max_hours_per_day", "Max hours per day", 1, 12, 5),
        "subjects": subjects,
    }


def _a_add_teacher(db: Session, p: dict) -> str:
    email = p["email"] or _derive_email(db, p["name"])
    if db.query(User).filter(User.email == email).first():
        raise OpError(f"Email '{email}' is already taken.")
    u = User(name=p["name"], email=email, role="faculty",
             password_hash=hash_password("faculty123"))
    db.add(u)
    db.flush()
    t = Teacher(user_id=u.id, dept=p["dept"], max_hours_per_day=p["max_hours_per_day"])
    t.subjects = [_find_subject(db, c) for c in p["subjects"]]
    db.add(t)
    db.flush()
    return f"added teacher {p['name']} ({email})"


_op(OpSpec(
    key="add_teacher", label="Add teacher",
    validate=_v_add_teacher,
    describe=lambda p: (f"add teacher {p['name']} ({p['dept']}, ≤{p['max_hours_per_day']}h/day)"
                        + (f" teaching {', '.join(p['subjects'])}" if p["subjects"]
                           else " — no subjects mapped yet")
                        + ("" if p["email"] else " · email auto-generated")),
    apply=_a_add_teacher, note=lambda pc, n: pc.note_teacher(n),
))


def _v_edit_teacher(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Teacher name", 120)
    if not pc.teacher_exists(name):
        raise OpError(f"No teacher named '{name}'.")
    out: dict = {"name": name}
    if p.get("max_hours_per_day") is not None:
        out["max_hours_per_day"] = _int(p, "max_hours_per_day", "Max hours per day", 1, 12)
    if p.get("dept"):
        out["dept"] = str(p["dept"]).strip()[:50]
    if p.get("new_name"):
        out["new_name"] = str(p["new_name"]).strip()[:120]
    if len(out) == 1:
        raise OpError(f"Nothing to change on {name}.")
    return out


def _a_edit_teacher(db: Session, p: dict) -> str:
    t = _find_teacher(db, p["name"])
    if "max_hours_per_day" in p:
        t.max_hours_per_day = p["max_hours_per_day"]
    if "dept" in p:
        t.dept = p["dept"]
    if "new_name" in p:
        t.user.name = p["new_name"]
    return f"updated teacher {p['name']}"


_op(OpSpec(
    key="edit_teacher", label="Edit teacher",
    validate=_v_edit_teacher,
    describe=lambda p: f"change {p['name']}: " + ", ".join(
        f"{k.replace('new_name', 'name')} → {v}" for k, v in p.items() if k != "name"),
    apply=_a_edit_teacher,
))


def _v_remove_teacher(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Teacher name", 120)
    if not pc.teacher_exists(name):
        raise OpError(f"No teacher named '{name}'.")
    return {"name": name}


def _a_remove_teacher(db: Session, p: dict) -> str:
    t = _find_teacher(db, p["name"])
    for a in db.query(TeachingAssignment).filter(TeachingAssignment.teacher_id == t.id):
        db.delete(a)
    for o in db.query(ElectiveOffering).filter(ElectiveOffering.teacher_id == t.id):
        db.delete(o)
    t.subjects = []
    user = t.user
    db.delete(t)
    if user:
        db.delete(user)
    return f"removed teacher {p['name']}"


_op(OpSpec(
    key="remove_teacher", label="Remove teacher", destructive=True,
    validate=_v_remove_teacher,
    describe=lambda p: f"remove teacher {p['name']} (and their pins and elective options)",
    apply=_a_remove_teacher,
))


def _v_set_teacher_subjects(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "teacher", "Teacher", 120)
    if not pc.teacher_exists(name):
        raise OpError(f"No teacher named '{name}'.")
    subjects = _codes(p.get("subjects") or p.get("subject_codes"))
    if not subjects:
        raise OpError("List at least one subject.")
    unknown = [c for c in subjects if not pc.subject_exists(c)]
    if unknown:
        raise OpError(f"Unknown subject(s): {', '.join(unknown)}.")
    mode = str(p.get("mode") or "add").lower()
    if mode not in ("add", "replace", "remove"):
        raise OpError("mode must be add, replace or remove.")
    return {"teacher": name, "subjects": subjects, "mode": mode}


def _a_set_teacher_subjects(db: Session, p: dict) -> str:
    t = _find_teacher(db, p["teacher"])
    subs = [_find_subject(db, c) for c in p["subjects"]]
    if p["mode"] == "replace":
        t.subjects = subs
    elif p["mode"] == "remove":
        for s in subs:
            if s in t.subjects:
                t.subjects.remove(s)
    else:
        for s in subs:
            if s not in t.subjects:
                t.subjects.append(s)
    return f"{p['mode']} {', '.join(p['subjects'])} for {p['teacher']}"


_op(OpSpec(
    key="set_teacher_subjects", label="Teacher's subjects",
    validate=_v_set_teacher_subjects,
    describe=lambda p: {
        "add": f"let {p['teacher']} also teach {', '.join(p['subjects'])}",
        "replace": f"set {p['teacher']}'s subjects to {', '.join(p['subjects'])}",
        "remove": f"stop {p['teacher']} teaching {', '.join(p['subjects'])}",
    }[p["mode"]],
    apply=_a_set_teacher_subjects,
))


# --- rooms ------------------------------------------------------------------

def _v_add_room(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Room name", 60)
    if pc.room_exists(name):
        raise OpError(f"Room '{name}' already exists — edit it instead.")
    rtype = str(p.get("type") or "classroom").strip().lower()
    if rtype not in ROOM_TYPES:
        raise OpError(f"Room type must be one of {', '.join(ROOM_TYPES)}.")
    return {"name": name, "type": rtype,
            "capacity": _int(p, "capacity", "Capacity", 1, 5000, 60)}


_op(OpSpec(
    key="add_room", label="Add room",
    validate=_v_add_room,
    describe=lambda p: f"add {p['type']} {p['name']} (capacity {p['capacity']})",
    apply=lambda db, p: (db.add(Room(name=p["name"], type=p["type"],
                                     capacity=p["capacity"])), db.flush(),
                         f"added room {p['name']}")[-1],
    note=lambda pc, n: pc.note_room(n),
))


def _v_edit_room(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Room name", 60)
    if not pc.room_exists(name):
        raise OpError(f"No room named '{name}'.")
    out: dict = {"name": name}
    if p.get("capacity") is not None:
        out["capacity"] = _int(p, "capacity", "Capacity", 1, 5000)
    if p.get("type"):
        rtype = str(p["type"]).strip().lower()
        if rtype not in ROOM_TYPES:
            raise OpError(f"Room type must be one of {', '.join(ROOM_TYPES)}.")
        out["type"] = rtype
    if len(out) == 1:
        raise OpError(f"Nothing to change on {name}.")
    return out


def _a_edit_room(db: Session, p: dict) -> str:
    r = _find_room(db, p["name"])
    for k, v in p.items():
        if k != "name":
            setattr(r, k, v)
    return f"updated room {p['name']}"


_op(OpSpec(
    key="edit_room", label="Edit room",
    validate=_v_edit_room,
    describe=lambda p: f"change room {p['name']}: " + ", ".join(
        f"{k} → {v}" for k, v in p.items() if k != "name"),
    apply=_a_edit_room,
))


def _v_remove_room(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Room name", 60)
    if not pc.room_exists(name):
        raise OpError(f"No room named '{name}'.")
    return {"name": name}


def _a_remove_room(db: Session, p: dict) -> str:
    r = _find_room(db, p["name"])
    for o in db.query(ElectiveOffering).filter(ElectiveOffering.room_id == r.id):
        db.delete(o)
    db.delete(r)
    return f"removed room {p['name']}"


_op(OpSpec(
    key="remove_room", label="Remove room", destructive=True,
    validate=_v_remove_room,
    describe=lambda p: f"remove room {p['name']}",
    apply=_a_remove_room,
))


# --- classes (sections) -----------------------------------------------------

def _v_add_class(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Class name", 20)
    if pc.section_exists(name):
        raise OpError(f"Class '{name}' already exists — edit it instead.")
    return {"name": name,
            "dept": str(p.get("dept") or "CSE").strip()[:50],
            "semester": _int(p, "semester", "Semester", 1, 12),
            "strength": _int(p, "strength", "Strength", 1, 500, 60)}


_op(OpSpec(
    key="add_class", label="Add class",
    validate=_v_add_class,
    describe=lambda p: (f"add class {p['name']} — semester {p['semester']}, "
                        f"{p['strength']} students"),
    apply=lambda db, p: (db.add(Section(name=p["name"], dept=p["dept"],
                                        semester=p["semester"], strength=p["strength"])),
                         db.flush(), f"added class {p['name']}")[-1],
    note=lambda pc, n: pc.note_section(n),
))


def _v_edit_class(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Class name", 20)
    if not pc.section_exists(name):
        raise OpError(f"No class named '{name}'.")
    out: dict = {"name": name}
    if p.get("strength") is not None:
        out["strength"] = _int(p, "strength", "Strength", 1, 500)
    if p.get("semester") is not None:
        out["semester"] = _int(p, "semester", "Semester", 1, 12)
    if len(out) == 1:
        raise OpError(f"Nothing to change on {name}.")
    return out


def _a_edit_class(db: Session, p: dict) -> str:
    s = _find_section(db, p["name"])
    for k, v in p.items():
        if k != "name":
            setattr(s, k, v)
    return f"updated class {p['name']}"


_op(OpSpec(
    key="edit_class", label="Edit class",
    validate=_v_edit_class,
    describe=lambda p: f"change class {p['name']}: " + ", ".join(
        f"{k} → {v}" for k, v in p.items() if k != "name"),
    apply=_a_edit_class,
))


def _v_remove_class(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Class name", 20)
    if not pc.section_exists(name):
        raise OpError(f"No class named '{name}'.")
    return {"name": name}


def _a_remove_class(db: Session, p: dict) -> str:
    s = _find_section(db, p["name"])
    for a in db.query(TeachingAssignment).filter(TeachingAssignment.section_id == s.id):
        db.delete(a)
    for c in db.query(Constraint).filter(Constraint.scope_type == "section",
                                         Constraint.scope_value == s.name):
        db.delete(c)
    db.delete(s)
    return f"removed class {p['name']}"


_op(OpSpec(
    key="remove_class", label="Remove class", destructive=True,
    validate=_v_remove_class,
    describe=lambda p: f"remove class {p['name']} (and its pins and rules)",
    apply=_a_remove_class,
))


# --- who teaches what, for which class --------------------------------------

def _v_assign_teacher(pc: PlanCtx, p: dict) -> dict:
    section = _text(p, "section", "Class", 20)
    code = _text(p, "subject", "Subject", 20).upper()
    if not pc.section_exists(section):
        raise OpError(f"No class named '{section}'.")
    if not pc.subject_exists(code):
        raise OpError(f"No subject with code '{code}'.")
    teacher = str(p.get("teacher") or "").strip()
    if teacher and not pc.teacher_exists(teacher):
        raise OpError(f"No teacher named '{teacher}'.")
    return {"section": section, "subject": code, "teacher": teacher}


def _a_assign_teacher(db: Session, p: dict) -> str:
    sec = _find_section(db, p["section"])
    subj = _find_subject(db, p["subject"])
    existing = (db.query(TeachingAssignment)
                .filter(TeachingAssignment.section_id == sec.id,
                        TeachingAssignment.subject_id == subj.id).first())
    if not p["teacher"]:
        if existing:
            db.delete(existing)
        return f"cleared the {sec.name} {subj.code} assignment (solver chooses)"
    t = _find_teacher(db, p["teacher"])
    note = " (also qualified them for it)" if _ensure_qualified(db, t, subj) else ""
    if existing:
        existing.teacher_id = t.id
    else:
        db.add(TeachingAssignment(section_id=sec.id, subject_id=subj.id, teacher_id=t.id))
    return f"{sec.name} {subj.code} → {t.user.name}{note}"


_op(OpSpec(
    key="assign_teacher", label="Assign teacher to a class's subject",
    validate=_v_assign_teacher,
    describe=lambda p: (f"{p['section']} {p['subject']} is taught by {p['teacher']}"
                        if p["teacher"] else
                        f"let the solver choose who teaches {p['subject']} for {p['section']}"),
    apply=_a_assign_teacher,
))


# --- open-elective bands ----------------------------------------------------

def _v_add_band(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Band name", 60)
    if pc.band_exists(name):
        raise OpError(f"An elective band named '{name}' already exists.")
    sem = _int(p, "semester", "Semester", 1, 12)
    options = []
    for o in (p.get("options") or []):
        code = str(o.get("subject") or "").strip().upper()
        teacher = str(o.get("teacher") or "").strip()
        room = str(o.get("room") or "").strip()
        if not pc.subject_exists(code):
            raise OpError(f"{name}: unknown subject '{code}'.")
        if not pc.teacher_exists(teacher):
            raise OpError(f"{name}: unknown teacher '{teacher}'.")
        if not pc.room_exists(room):
            raise OpError(f"{name}: unknown room '{room}'.")
        options.append({"subject": code, "teacher": teacher, "room": room,
                        "capacity": int(o.get("capacity") or 60)})
    rooms = [o["room"].lower() for o in options]
    if len(set(rooms)) != len(rooms):
        raise OpError(f"{name}: parallel options need distinct rooms.")
    teachers = [o["teacher"].lower() for o in options]
    if len(set(teachers)) != len(teachers):
        raise OpError(f"{name}: one teacher cannot run two parallel options.")
    return {"name": name, "semester": sem,
            "dept": str(p.get("dept") or "CSE").strip()[:50],
            "periods_per_week": _int(p, "periods_per_week", "Periods per week", 1, 10, 3),
            "needs_block": bool(p.get("needs_block", False)),
            "options": options}


def _a_add_band(db: Session, p: dict) -> str:
    g = ElectiveGroup(name=p["name"], dept=p["dept"], semester=p["semester"],
                      periods_per_week=p["periods_per_week"],
                      needs_block=p["needs_block"], active=True)
    db.add(g)
    db.flush()
    fixed = 0
    for o in p["options"]:
        subj, t, room = (_find_subject(db, o["subject"]), _find_teacher(db, o["teacher"]),
                         _find_room(db, o["room"]))
        if _ensure_qualified(db, t, subj):
            fixed += 1
        db.add(ElectiveOffering(group_id=g.id, subject_id=subj.id, teacher_id=t.id,
                                room_id=room.id, capacity=o["capacity"]))
    note = f" (qualified {fixed} teacher(s) for their option)" if fixed else ""
    return f"added elective band {p['name']} with {len(p['options'])} option(s){note}"


_op(OpSpec(
    key="add_elective_band", label="Add open-elective band",
    validate=_v_add_band,
    describe=lambda p: (
        f"add open elective {p['name']} for semester {p['semester']} — "
        f"{p['periods_per_week']} period(s)/week"
        + (", options: " + "; ".join(f"{o['subject']} by {o['teacher']} in {o['room']}"
                                     for o in p["options"]) if p["options"]
           else " (no options yet)")),
    apply=_a_add_band, note=lambda pc, n: pc.note_band(n),
))


def _v_add_band_option(pc: PlanCtx, p: dict) -> dict:
    band = _text(p, "band", "Band", 60)
    if not pc.band_exists(band):
        raise OpError(f"No elective band named '{band}'.")
    code = _text(p, "subject", "Subject", 20).upper()
    teacher = _text(p, "teacher", "Teacher", 120)
    room = _text(p, "room", "Room", 60)
    for ok, what, val in ((pc.subject_exists(code), "subject", code),
                          (pc.teacher_exists(teacher), "teacher", teacher),
                          (pc.room_exists(room), "room", room)):
        if not ok:
            raise OpError(f"Unknown {what} '{val}'.")
    return {"band": band, "subject": code, "teacher": teacher, "room": room,
            "capacity": int(p.get("capacity") or 60)}


def _a_add_band_option(db: Session, p: dict) -> str:
    g = _find_band(db, p["band"])
    subj, t, room = (_find_subject(db, p["subject"]), _find_teacher(db, p["teacher"]),
                     _find_room(db, p["room"]))
    if any(o.room_id == room.id for o in g.offerings):
        raise OpError(f"{g.name} already uses {room.name} for another option.")
    if any(o.teacher_id == t.id for o in g.offerings):
        raise OpError(f"{t.user.name} already runs another option in {g.name}.")
    _ensure_qualified(db, t, subj)
    db.add(ElectiveOffering(group_id=g.id, subject_id=subj.id, teacher_id=t.id,
                            room_id=room.id, capacity=p["capacity"]))
    return f"added {subj.code} to {g.name}"


_op(OpSpec(
    key="add_elective_option", label="Add an elective option",
    validate=_v_add_band_option,
    describe=lambda p: (f"add {p['subject']} to {p['band']}, taught by {p['teacher']} "
                        f"in {p['room']}"),
    apply=_a_add_band_option,
))


def _v_remove_band(pc: PlanCtx, p: dict) -> dict:
    name = _text(p, "name", "Band name", 60)
    if not pc.band_exists(name):
        raise OpError(f"No elective band named '{name}'.")
    return {"name": name}


def _a_remove_band(db: Session, p: dict) -> str:
    g = _find_band(db, p["name"])
    db.delete(g)
    return f"removed elective band {p['name']}"


_op(OpSpec(
    key="remove_elective_band", label="Remove elective band", destructive=True,
    validate=_v_remove_band,
    describe=lambda p: f"remove elective band {p['name']} and its options",
    apply=_a_remove_band,
))


# --- rules (delegate to the Phase 2.4 constraint registry) -------------------

def _v_add_constraint(pc: PlanCtx, p: dict) -> dict:
    kind = str(p.get("kind") or "").strip()
    scope_type = str(p.get("scope_type") or "global").strip()
    scope_value = str(p.get("scope_value") or "").strip()
    params = p.get("params") or {}
    try:
        norm, desc, _ = reg.validate(pc.db, kind, scope_type, scope_value, params, pc.ctx)
    except reg.ConstraintError as exc:
        raise OpError(str(exc))
    return {"kind": kind, "scope_type": scope_type, "scope_value": scope_value,
            "params": norm, "_desc": desc}


def _a_add_constraint(db: Session, p: dict) -> str:
    row = reg.create(db, p["kind"], p["scope_type"], p["scope_value"], p["params"],
                     source="llm", commit=False)
    return f"rule: {row.description}"


_op(OpSpec(
    key="add_rule", label="Add scheduling rule",
    validate=_v_add_constraint,
    describe=lambda p: f"rule — {p['_desc']}",
    apply=_a_add_constraint,
))


def _v_edit_constraint(pc: PlanCtx, p: dict) -> dict:
    cid = p.get("id")
    row = pc.db.get(Constraint, int(cid)) if cid else None
    if row is None:
        raise OpError(f"There is no rule #{cid} to change.")
    merged = {**reg.to_dict(row)["params"], **(p.get("params") or {})}
    try:
        _, desc, _ = reg.validate(pc.db, row.kind,
                                  p.get("scope_type") or row.scope_type,
                                  p.get("scope_value") or row.scope_value,
                                  merged, pc.ctx)
    except reg.ConstraintError as exc:
        raise OpError(str(exc))
    return {"id": row.id, "params": p.get("params") or {},
            "scope_type": p.get("scope_type"), "scope_value": p.get("scope_value"),
            "_desc": desc, "_before": row.description}


def _a_edit_constraint(db: Session, p: dict) -> str:
    row = reg.update(db, p["id"], params=p["params"], scope_type=p["scope_type"],
                     scope_value=p["scope_value"], source="llm", commit=False)
    return f"rule updated: {row.description}"


_op(OpSpec(
    key="edit_rule", label="Change a scheduling rule",
    validate=_v_edit_constraint,
    describe=lambda p: f"rule — {p['_desc']}  (was: {p['_before']})",
    apply=_a_edit_constraint,
))


def _v_rule_by_id(pc: PlanCtx, p: dict) -> dict:
    cid = p.get("id")
    row = pc.db.get(Constraint, int(cid)) if cid else None
    if row is None:
        raise OpError(f"There is no rule #{cid}.")
    return {"id": row.id, "_before": row.description}


_op(OpSpec(
    key="remove_rule", label="Remove a scheduling rule", destructive=True,
    validate=_v_rule_by_id,
    describe=lambda p: f"remove rule — {p['_before']}",
    apply=lambda db, p: (reg.delete(db, p["id"], commit=False),
                         f"removed rule: {p['_before']}")[-1],
))

_op(OpSpec(
    key="disable_rule", label="Turn a rule off",
    validate=_v_rule_by_id,
    describe=lambda p: f"turn off — {p['_before']}",
    apply=lambda db, p: (reg.update(db, p["id"], enabled=False, commit=False),
                         f"turned off: {p['_before']}")[-1],
))

_op(OpSpec(
    key="enable_rule", label="Turn a rule on",
    validate=_v_rule_by_id,
    describe=lambda p: f"turn on — {p['_before']}",
    apply=lambda db, p: (reg.update(db, p["id"], enabled=True, commit=False),
                         f"turned on: {p['_before']}")[-1],
))


# --- action -----------------------------------------------------------------

_op(OpSpec(
    key="generate_timetable", label="Generate the timetable",
    validate=lambda pc, p: {"fresh": bool(p.get("fresh", False))},
    describe=lambda p: ("re-plan the whole timetable from scratch" if p.get("fresh")
                        else "update the timetable, moving only what these changes force"),
    # handled by the caller after the commit: "__GENERATE__" keeps the published
    # schedule, "__GENERATE_FRESH__" throws it away and re-plans
    apply=lambda db, p: "__GENERATE_FRESH__" if p.get("fresh") else "__GENERATE__",
))


# ---------- planning: validate a whole batch in order ----------

# Old Phase 2.4 op names, kept working.
_ALIASES = {
    "create": "add_rule", "update": "edit_rule", "delete": "remove_rule",
    "enable": "enable_rule", "disable": "disable_rule",
    "create_constraint": "add_rule", "update_constraint": "edit_rule",
    "delete_constraint": "remove_rule",
    "add_constraint": "add_rule", "edit_constraint": "edit_rule",
    "remove_constraint": "remove_rule",
    "create_teacher": "add_teacher", "create_subject": "add_subject",
    "create_room": "add_room", "create_section": "add_class",
    "add_section": "add_class", "edit_section": "edit_class",
    "remove_section": "remove_class", "map_teacher_subject": "set_teacher_subjects",
    "generate": "generate_timetable",
}


def normalise_key(raw: str) -> str:
    key = str(raw or "").strip().lower()
    return _ALIASES.get(key, key)


# ---------- bulk forms: fewer tokens out of the model ----------
#
# "add 5 subjects and 5 teachers, one subject each" is 15 separate ops written
# out longhand, and output tokens are what the admin waits on — that request
# measured 31s. The model may instead emit three list-shaped ops, which are
# expanded here into exactly the same individual ops before validation, so the
# preview, the per-step errors and the apply path are unchanged.

_BULK = {
    "add_subjects": ("add_subject", "subjects"),
    "add_teachers": ("add_teacher", "teachers"),
    "add_rooms": ("add_room", "rooms"),
    "add_classes": ("add_class", "classes"),
}


def expand(ops: list[dict]) -> list[dict]:
    """Turn any list-shaped op into the individual ops it stands for."""
    out: list[dict] = []
    for raw in ops or []:
        key = normalise_key(raw.get("op"))
        if key not in _BULK:
            out.append(raw)
            continue
        single, alt = _BULK[key]
        params = raw.get("params") or raw
        items = params.get("items") or params.get(alt) or []
        defaults = params.get("defaults") or {}
        if not isinstance(items, list):
            out.append(raw)          # malformed — let plan() report it
            continue
        for item in items:
            if not isinstance(item, dict):
                # a bare string is the entity's name/code
                item = {"code" if single == "add_subject" else "name": str(item)}
            merged = {**defaults, **item}
            # a teacher may carry the class they should be assigned to, folding
            # what would otherwise be a second op per subject into the same item
            assign_to = merged.pop("assign_to", None) or merged.pop("section", None)
            out.append({"op": single, "params": merged})
            if single == "add_teacher" and assign_to:
                for code in _codes(merged.get("subjects")):
                    out.append({"op": "assign_teacher", "params": {
                        "section": assign_to, "subject": code,
                        "teacher": merged.get("name", "")}})
    return out


def plan(db: Session, ops: list[dict]) -> list[dict]:
    """Validate a batch in order, carrying forward what earlier ops will create.

    Returns one preview item per op — never writes. An op that fails validation is
    reported in place and the rest are still checked, so the admin sees the whole
    picture rather than only the first problem."""
    pc = PlanCtx(db=db, ctx=reg.build_ctx(db))
    out: list[dict] = []
    for raw in expand(ops):
        key = normalise_key(raw.get("op"))
        params = raw.get("params") or {}
        # tolerate a model that puts fields at the top level instead of in params
        if not params:
            params = {k: v for k, v in raw.items() if k not in ("op", "params")}
        item: dict = {"op": key, "params": params}
        spec = OPS.get(key)
        if spec is None:
            item.update(ok=False, error=(
                f"'{raw.get('op')}' is not something I can do. Available: "
                f"{', '.join(sorted(OPS))}."))
            out.append(item)
            continue
        item["label"] = spec.label
        item["destructive"] = spec.destructive
        try:
            norm = spec.validate(pc, params)
            item.update(ok=True, params=norm, description=spec.describe(norm))
            if spec.note:
                spec.note(pc, norm)
        except (OpError, reg.ConstraintError) as exc:
            item.update(ok=False, error=str(exc))
        except Exception as exc:  # a malformed op from the model
            item.update(ok=False, error=f"Could not read that step ({type(exc).__name__}).")
        out.append(item)
    return out


def run(db: Session, ops: list[dict]) -> tuple[list[str], list[dict], str | None]:
    """Apply a validated batch, in order, in one transaction.

    Returns (what happened, failures, the regeneration mode requested or None).
    Ops are re-validated as they run — the plan may have been built minutes ago."""
    pc = PlanCtx(db=db, ctx=reg.build_ctx(db))
    done: list[str] = []
    failed: list[dict] = []
    regenerate: str | None = None      # None | "keep" | "fresh"
    for raw in expand(ops):
        key = normalise_key(raw.get("op"))
        spec = OPS.get(key)
        if spec is None:
            failed.append({"op": key, "error": f"Unknown operation '{key}'."})
            continue
        try:
            pc.refresh()                       # earlier ops changed the world
            norm = spec.validate(pc, raw.get("params") or {})
            result = spec.apply(db, norm)
            if result in ("__GENERATE__", "__GENERATE_FRESH__"):
                regenerate = "fresh" if result == "__GENERATE_FRESH__" else "keep"
                continue
            db.flush()
            done.append(result)
        except (OpError, reg.ConstraintError) as exc:
            failed.append({"op": key, "error": str(exc)})
        except Exception as exc:
            failed.append({"op": key, "error": f"{type(exc).__name__}: {exc}"})
    if done:
        db.commit()
    else:
        db.rollback()
    return done, failed, regenerate


def ops_catalog() -> list[dict]:
    """The op vocabulary, for the UI and the model prompt."""
    return [{"op": s.key, "label": s.label, "destructive": s.destructive}
            for s in OPS.values()]
