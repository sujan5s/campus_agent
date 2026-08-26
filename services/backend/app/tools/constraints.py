"""Constraint registry (Phase 2.4) — the single source of truth for how the
timetable is generated.

Before this module, generation rules lived in one request body and were only
visible as a JSON snapshot after the fact. Now every rule is a `Constraint` row
that can be listed, edited, disabled, deleted — by an admin in the UI or by the
LLM from a sentence — and the solver is fed by compiling those rows.

Three things live here:

* **CATALOG** — the whitelist of constraint kinds. Each entry knows its allowed
  scopes, how to validate + normalise its params against real DB entities, and
  how to render itself as an English sentence. The LLM may only emit kinds from
  this catalog, and its params go through the same validator as the UI form, so
  a hallucinated teacher or an out-of-range period is rejected, never stored.
* **CRUD helpers** — used by the API and by the LLM apply path.
* **compile_options()** — registry rows -> `SolveOptions` for the CP-SAT model,
  resolving scope (section > semester > global).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.models import (
    Constraint, ElectiveGroup, Section, Subject, Teacher, TimeSlot, TimetableConfig,
)
from app.solver.timetable_model import (
    ElectivePin, PreferredPeriods, ScopeRules, SlotBan, SolveOptions,
)

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class ConstraintError(ValueError):
    """A constraint that cannot be stored — message is shown to the admin."""


# ---------- the entity context every validator works against ----------

@dataclass
class Ctx:
    """Real master data, so a constraint can never point at something absent."""
    days: list[str]
    periods: list[int]
    sections: dict[str, Section]      # by name
    semesters: list[int]
    subjects_by_code: dict[str, Subject]
    subjects_by_id: dict[int, Subject]
    teachers_by_id: dict[int, Teacher]
    teacher_names: dict[str, Teacher]  # lowercased name and email
    bands: list[ElectiveGroup]         # open-elective bands

    @property
    def max_period(self) -> int:
        return max(self.periods) if self.periods else 0

    def bands_of_semester(self, sem: int) -> list[ElectiveGroup]:
        return [b for b in self.bands if b.semester == sem]


def build_ctx(db: Session) -> Ctx:
    slots = db.query(TimeSlot).all()
    days = [d for d in DAYS if any(s.day == d for s in slots)]
    periods = sorted({s.period_no for s in slots})
    sections = {s.name: s for s in db.query(Section).all()}
    subjects = db.query(Subject).all()
    teachers = db.query(Teacher).all()
    names: dict[str, Teacher] = {}
    for t in teachers:
        if t.user:
            names[t.user.name.strip().lower()] = t
            names[t.user.email.strip().lower()] = t
    return Ctx(
        days=days,
        periods=periods,
        sections=sections,
        semesters=sorted({s.semester for s in sections.values()}),
        subjects_by_code={s.code.upper(): s for s in subjects},
        subjects_by_id={s.id: s for s in subjects},
        teachers_by_id={t.id: t for t in teachers},
        teacher_names=names,
        bands=db.query(ElectiveGroup).order_by(ElectiveGroup.name).all(),
    )


# ---------- small param coercers ----------

def _day(ctx: Ctx, value: Any, field: str = "day") -> str:
    d = str(value or "").strip().upper()[:3]
    if d not in ctx.days:
        raise ConstraintError(
            f"'{value}' is not a teaching day — expected one of {', '.join(ctx.days)}.")
    return d


def _days(ctx: Ctx, value: Any) -> list[str]:
    if value in (None, "", [], "all"):
        return []
    if isinstance(value, str):
        value = [p for p in value.replace(",", " ").split() if p]
    return sorted({_day(ctx, v) for v in value}, key=ctx.days.index)


def _period(ctx: Ctx, value: Any) -> int:
    try:
        p = int(str(value).upper().lstrip("P"))
    except (TypeError, ValueError):
        raise ConstraintError(f"'{value}' is not a period number.")
    if p not in ctx.periods:
        raise ConstraintError(
            f"P{p} does not exist — the grid has P{min(ctx.periods)}–P{ctx.max_period}.")
    return p


def _periods(ctx: Ctx, value: Any) -> list[int]:
    if value in (None, "", [], "all"):
        return []
    if isinstance(value, (str, int)):
        value = [p for p in str(value).replace(",", " ").split() if p]
    return sorted({_period(ctx, v) for v in value})


def _positive_int(value: Any, field: str, lo: int = 1, hi: int = 60) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ConstraintError(f"{field} must be a whole number, got '{value}'.")
    if not lo <= n <= hi:
        raise ConstraintError(f"{field} must be between {lo} and {hi}, got {n}.")
    return n


def _bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("true", "yes", "1", "on"):
        return True
    if s in ("false", "no", "0", "off"):
        return False
    raise ConstraintError(f"{field} must be true or false, got '{value}'.")


def _teacher(ctx: Ctx, params: dict) -> Teacher:
    tid = params.get("teacher_id")
    if tid is not None:
        t = ctx.teachers_by_id.get(int(tid))
        if t:
            return t
    raw = str(params.get("teacher") or params.get("teacher_name") or "").strip()
    if raw:
        t = ctx.teacher_names.get(raw.lower())
        if t:
            return t
        # forgiving match: "Anita Rao" vs "Dr. Anita Rao"
        hits = [v for k, v in ctx.teacher_names.items() if raw.lower() in k]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ConstraintError(f"'{raw}' matches more than one teacher — use the full name.")
    raise ConstraintError(f"No teacher matches '{raw or tid}'. Add them in Data Setup first.")


def _subject(ctx: Ctx, params: dict) -> Subject:
    sid = params.get("subject_id")
    if sid is not None:
        s = ctx.subjects_by_id.get(int(sid))
        if s:
            return s
    raw = str(params.get("subject") or params.get("subject_code") or "").strip()
    if raw:
        s = ctx.subjects_by_code.get(raw.upper())
        if s:
            return s
        hits = [v for v in ctx.subjects_by_id.values() if raw.lower() in v.name.lower()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ConstraintError(f"'{raw}' matches several subjects — use the subject code.")
    raise ConstraintError(f"No subject matches '{raw or sid}'. Add it in Data Setup first.")


# ---------- the catalog ----------

@dataclass
class Kind:
    key: str
    label: str
    help: str
    scopes: tuple[str, ...]                     # global | semester | section
    fields: list[dict]                          # UI form hints
    validate: Callable[[Ctx, dict], dict]
    describe: Callable[[dict], str]
    priority: str = "hard"
    unique_per_scope: bool = False              # one row per scope replaces the old


def _f(name: str, ftype: str, label: str, **extra) -> dict:
    return {"name": name, "type": ftype, "label": label, **extra}


CATALOG: dict[str, Kind] = {}


def _register(k: Kind) -> None:
    CATALOG[k.key] = k


_register(Kind(
    key="half_day",
    label="Half day",
    help="A day ends after the given period; later periods are unused for that scope.",
    scopes=("global", "semester", "section"),
    fields=[_f("day", "day", "Day"), _f("last_period", "period", "Last teaching period")],
    validate=lambda ctx, p: {
        "day": _day(ctx, p.get("day")),
        "last_period": (lambda v: v if v < ctx.max_period else _raise(
            f"A half day must end before P{ctx.max_period}; use P1–P{ctx.max_period - 1}."))(
            _period(ctx, p.get("last_period"))),
    },
    describe=lambda p: f"{p['day']} ends after P{p['last_period']}",
))

_register(Kind(
    key="no_same_subject_consecutive",
    label="No same-subject back-to-back",
    help="A theory subject may not occupy two adjacent periods (labs are exempt).",
    scopes=("global", "semester", "section"),
    fields=[_f("value", "bool", "Enforced")],
    unique_per_scope=True,
    validate=lambda ctx, p: {"value": _bool(p.get("value", True), "value")},
    describe=lambda p: ("no same-subject back-to-back periods" if p["value"]
                        else "same-subject back-to-back periods allowed"),
))

_register(Kind(
    key="max_consecutive_teaching",
    label="Teacher consecutive-teaching cap",
    help="A teacher of this scope's classes never teaches more than N periods in a row.",
    scopes=("global", "semester", "section"),
    fields=[_f("value", "int", "Max periods in a row", min=1, max=10)],
    unique_per_scope=True,
    validate=lambda ctx, p: {"value": _positive_int(p.get("value"), "value", 1, 10)},
    describe=lambda p: f"at most {p['value']} consecutive teaching periods per teacher",
))

_register(Kind(
    key="subject_daily_max",
    label="Same-subject periods per day",
    help="At most N periods of one subject on the same day.",
    scopes=("global", "semester", "section"),
    fields=[_f("value", "int", "Max per day", min=1, max=6)],
    unique_per_scope=True,
    validate=lambda ctx, p: {"value": _positive_int(p.get("value"), "value", 1, 6)},
    describe=lambda p: f"at most {p['value']} period(s) of the same subject per day",
))

_register(Kind(
    key="max_periods_per_day",
    label="Class periods per day",
    help="A class never has more than N periods on any day (open electives included).",
    scopes=("global", "semester", "section"),
    fields=[_f("value", "int", "Max periods per day", min=1, max=12)],
    unique_per_scope=True,
    validate=lambda ctx, p: {"value": _positive_int(p.get("value"), "value", 1, 12)},
    describe=lambda p: f"at most {p['value']} periods per day for the class",
))

_register(Kind(
    key="class_slot_ban",
    label="Class free at",
    help="This class has no scheduled period at the given days/periods.",
    scopes=("section", "semester"),
    fields=[_f("days", "days", "Days (blank = every day)"),
            _f("periods", "periods", "Periods (blank = whole day)")],
    validate=lambda ctx, p: {"days": _days(ctx, p.get("days")),
                             "periods": _periods(ctx, p.get("periods"))},
    describe=lambda p: "free at " + _when(p),
))

_register(Kind(
    key="teacher_unavailable",
    label="Teacher unavailable",
    help="This teacher is never scheduled at the given days/periods.",
    scopes=("global",),
    fields=[_f("teacher", "teacher", "Teacher"),
            _f("days", "days", "Days (blank = every day)"),
            _f("periods", "periods", "Periods (blank = whole day)")],
    validate=lambda ctx, p: (lambda t: {
        "teacher_id": t.id, "teacher_name": t.user.name,
        "days": _days(ctx, p.get("days")), "periods": _periods(ctx, p.get("periods")),
    })(_teacher(ctx, p)),
    describe=lambda p: f"{p['teacher_name']} is unavailable " + _when(p),
))

_register(Kind(
    key="teacher_max_daily",
    label="Teacher daily hour limit",
    help="Overrides this teacher's max periods per day.",
    scopes=("global",),
    fields=[_f("teacher", "teacher", "Teacher"),
            _f("value", "int", "Max periods per day", min=1, max=12)],
    validate=lambda ctx, p: (lambda t: {
        "teacher_id": t.id, "teacher_name": t.user.name,
        "value": _positive_int(p.get("value"), "value", 1, 12),
    })(_teacher(ctx, p)),
    describe=lambda p: f"{p['teacher_name']} teaches at most {p['value']} period(s) per day",
))

_register(Kind(
    key="teacher_max_weekly",
    label="Teacher weekly hour limit",
    help="Caps this teacher's total periods per week across every section.",
    scopes=("global",),
    fields=[_f("teacher", "teacher", "Teacher"),
            _f("value", "int", "Max periods per week", min=1, max=45)],
    validate=lambda ctx, p: (lambda t: {
        "teacher_id": t.id, "teacher_name": t.user.name,
        "value": _positive_int(p.get("value"), "value", 1, 45),
    })(_teacher(ctx, p)),
    describe=lambda p: f"{p['teacher_name']} teaches at most {p['value']} period(s) per week",
))

_register(Kind(
    key="teacher_max_consecutive",
    label="Teacher run cap (one teacher)",
    help="This teacher never teaches more than N periods in a row.",
    scopes=("global",),
    fields=[_f("teacher", "teacher", "Teacher"),
            _f("value", "int", "Max periods in a row", min=1, max=10)],
    validate=lambda ctx, p: (lambda t: {
        "teacher_id": t.id, "teacher_name": t.user.name,
        "value": _positive_int(p.get("value"), "value", 1, 10),
    })(_teacher(ctx, p)),
    describe=lambda p: f"{p['teacher_name']} teaches at most {p['value']} period(s) in a row",
))

_register(Kind(
    key="subject_slot_ban",
    label="Subject not at",
    help="This subject is never scheduled at the given days/periods.",
    scopes=("global",),
    fields=[_f("subject", "subject", "Subject"),
            _f("days", "days", "Days (blank = every day)"),
            _f("periods", "periods", "Periods (blank = whole day)")],
    validate=lambda ctx, p: (lambda s: {
        "subject_id": s.id, "subject_code": s.code,
        "days": _days(ctx, p.get("days")), "periods": _periods(ctx, p.get("periods")),
    })(_subject(ctx, p)),
    describe=lambda p: f"{p['subject_code']} is never scheduled " + _when(p),
))

_register(Kind(
    key="subject_preferred_periods",
    label="Subject preferred periods",
    help="Soft: the solver tries to place this subject inside these periods.",
    scopes=("global",),
    priority="soft",
    fields=[_f("subject", "subject", "Subject"),
            _f("periods", "periods", "Preferred periods"),
            _f("days", "days", "Preferred days (blank = any)")],
    validate=lambda ctx, p: (lambda s: {
        "subject_id": s.id, "subject_code": s.code,
        "periods": _periods(ctx, p.get("periods")), "days": _days(ctx, p.get("days")),
    })(_subject(ctx, p)),
    describe=lambda p: f"prefer {p['subject_code']} " + (_when(p) or "anywhere"),
))

_register(Kind(
    key="elective_fixed_slots",
    label="Open elective at fixed periods",
    help=("Pin this semester's open-elective band to specific periods, e.g. MON and TUE "
          "period 3. Band periods beyond the pinned ones are still placed by the solver."),
    scopes=("semester",),
    fields=[_f("band", "band", "Elective band"),
            _f("days", "days", "Days"),
            _f("periods", "periods", "Periods")],
    validate=lambda ctx, p: _fixed_slots_params(ctx, p),
    describe=lambda p: (f"{p['band_name']} runs at "
                        + ", ".join(f"{d}-P{n}" for d, n in
                                    ((d, n) for d in p["days"] for n in p["periods"]))),
))

_register(Kind(
    key="avoid_gaps",
    label="Avoid free periods mid-day",
    help="Soft: penalise a free period that has classes both before and after it.",
    scopes=("global",),
    priority="soft",
    unique_per_scope=True,
    fields=[_f("weight", "int", "Strength", min=1, max=10)],
    validate=lambda ctx, p: {"weight": _positive_int(p.get("weight", 2), "weight", 1, 10)},
    describe=lambda p: f"avoid mid-day free periods (strength {p['weight']})",
))


def _raise(msg: str):
    raise ConstraintError(msg)


# Reserved param key: `validate()` injects the resolved scope semester here so a
# kind whose meaning depends on its scope (a band belongs to a semester) can see
# it. It is stripped again before the params are stored.
SCOPE_SEMESTER = "__scope_semester__"


def _band(ctx: Ctx, params: dict) -> ElectiveGroup:
    """Resolve the elective band a rule refers to, within its scope semester."""
    sem = params.get(SCOPE_SEMESTER)
    candidates = ctx.bands_of_semester(sem) if sem is not None else ctx.bands
    if not candidates:
        raise ConstraintError(
            f"Semester {sem} has no open-elective band yet — create one on the "
            f"Open electives tab first.")
    raw = str(params.get("band") or params.get("band_name") or "").strip()
    if params.get("band_id") is not None:
        hit = next((b for b in candidates if b.id == int(params["band_id"])), None)
        if hit:
            return hit
    if raw:
        hit = next((b for b in candidates if b.name.lower() == raw.lower()), None)
        if hit:
            return hit
        raise ConstraintError(
            f"No elective band named '{raw}' in semester {sem} — "
            f"existing: {', '.join(b.name for b in candidates)}.")
    if len(candidates) == 1:
        return candidates[0]          # unambiguous: don't make the admin name it
    raise ConstraintError(
        f"Semester {sem} has several elective bands "
        f"({', '.join(b.name for b in candidates)}) — say which one.")


def _fixed_slots_params(ctx: Ctx, p: dict) -> dict:
    band = _band(ctx, p)
    days = _days(ctx, p.get("days"))
    periods = _periods(ctx, p.get("periods"))
    if not days or not periods:
        raise ConstraintError(
            "Pick at least one day and one period — 'the elective is at MON and TUE "
            "period 3' fixes two slots.")
    return {"band_id": band.id, "band_name": band.name,
            "days": days, "periods": periods}


def _when(p: dict) -> str:
    """'on MON, WED at P1, P2' from a days/periods param pair."""
    bits = []
    if p.get("days"):
        bits.append("on " + ", ".join(p["days"]))
    if p.get("periods"):
        bits.append("at " + ", ".join(f"P{n}" for n in p["periods"]))
    return " ".join(bits) if bits else "at any time"


def catalog_json() -> list[dict]:
    """Machine-readable catalog for the UI form and the LLM prompt."""
    return [{
        "kind": k.key, "label": k.label, "help": k.help,
        "scopes": list(k.scopes), "fields": k.fields,
        "priority": k.priority, "unique_per_scope": k.unique_per_scope,
    } for k in CATALOG.values()]


# ---------- validation of a whole constraint ----------

def validate(db: Session, kind: str, scope_type: str, scope_value: str,
             params: dict, ctx: Ctx | None = None) -> tuple[dict, str, str]:
    """Check one constraint end to end. Returns (normalised params, description,
    priority). Raises ConstraintError with an admin-readable message."""
    ctx = ctx or build_ctx(db)
    spec = CATALOG.get(kind)
    if spec is None:
        raise ConstraintError(
            f"Unknown constraint type '{kind}'. Supported: {', '.join(CATALOG)}.")
    scope_type = (scope_type or "global").lower()
    if scope_type not in spec.scopes:
        raise ConstraintError(
            f"'{spec.label}' cannot be scoped to a {scope_type} — "
            f"allowed: {', '.join(spec.scopes)}.")

    scope_value = str(scope_value or "").strip()
    if scope_type == "global":
        scope_value = ""
    elif scope_type == "semester":
        try:
            sem = int(str(scope_value).lower().replace("sem", "").strip())
        except ValueError:
            raise ConstraintError(f"'{scope_value}' is not a semester number.")
        if sem not in ctx.semesters:
            raise ConstraintError(
                f"No section is in semester {sem} — existing semesters: "
                f"{', '.join(map(str, ctx.semesters)) or 'none'}.")
        scope_value = str(sem)
    elif scope_type == "section":
        match = next((n for n in ctx.sections if n.lower() == scope_value.lower()), None)
        if match is None:
            raise ConstraintError(
                f"No class named '{scope_value}' — existing: {', '.join(ctx.sections) or 'none'}.")
        scope_value = match
    else:
        raise ConstraintError(f"scope_type must be global, semester or section (got '{scope_type}').")

    # a kind whose meaning depends on its scope (an elective band belongs to a
    # semester) reads the resolved semester from this reserved key
    incoming = dict(params or {})
    if scope_type == "semester":
        incoming[SCOPE_SEMESTER] = int(scope_value)
    norm = spec.validate(ctx, incoming)
    norm.pop(SCOPE_SEMESTER, None)
    where = {"global": "all classes", "semester": f"semester {scope_value}",
             "section": scope_value}[scope_type]
    return norm, f"{where}: {spec.describe(norm)}", spec.priority


# ---------- CRUD ----------

def to_dict(c: Constraint) -> dict:
    return {
        "id": c.id, "kind": c.kind, "label": CATALOG[c.kind].label if c.kind in CATALOG else c.kind,
        "scope_type": c.scope_type, "scope_value": c.scope_value,
        "params": json.loads(c.params_json or "{}"),
        "priority": c.priority, "weight": c.weight, "enabled": c.enabled,
        "source": c.source, "origin_prompt": c.origin_prompt,
        "description": c.description,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def list_constraints(db: Session) -> list[Constraint]:
    order = {"global": 0, "semester": 1, "section": 2}
    rows = db.query(Constraint).all()
    return sorted(rows, key=lambda c: (order.get(c.scope_type, 3), c.scope_value, c.kind, c.id))


def create(db: Session, kind: str, scope_type: str, scope_value: str, params: dict,
           source: str = "ui", origin_prompt: str = "", enabled: bool = True,
           ctx: Ctx | None = None, commit: bool = True) -> Constraint:
    norm, desc, priority = validate(db, kind, scope_type, scope_value, params, ctx)
    spec = CATALOG[kind]
    if spec.unique_per_scope:
        # one row per scope: rewrite the existing one instead of stacking duplicates
        existing = (db.query(Constraint)
                    .filter(Constraint.kind == kind,
                            Constraint.scope_type == scope_type,
                            Constraint.scope_value == (scope_value if scope_type != "global" else ""))
                    .first())
        if existing:
            existing.params_json = json.dumps(norm)
            existing.description = desc
            existing.enabled = enabled
            existing.source = source
            existing.origin_prompt = origin_prompt or existing.origin_prompt
            if commit:
                db.commit()
            return existing

    # Stating the same rule twice (re-running a prompt, double-clicking Add) must
    # not litter the rulebook with identical rows — re-enable the existing one.
    same = next((c for c in db.query(Constraint).filter(
        Constraint.kind == kind,
        Constraint.scope_type == scope_type,
        Constraint.scope_value == (scope_value if scope_type != "global" else ""),
    ).all() if json.loads(c.params_json or "{}") == norm), None)
    if same is not None:
        same.enabled = enabled
        same.origin_prompt = origin_prompt or same.origin_prompt
        if commit:
            db.commit()
        return same

    row = Constraint(
        kind=kind, scope_type=scope_type,
        scope_value="" if scope_type == "global" else str(scope_value),
        params_json=json.dumps(norm), priority=priority,
        weight=int(norm.get("weight", 1)), enabled=enabled,
        source=source, origin_prompt=origin_prompt, description=desc,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def update(db: Session, cid: int, *, params: dict | None = None,
           scope_type: str | None = None, scope_value: str | None = None,
           enabled: bool | None = None, source: str | None = None,
           origin_prompt: str = "", ctx: Ctx | None = None,
           commit: bool = True) -> Constraint:
    row = db.get(Constraint, cid)
    if row is None:
        raise ConstraintError(f"Constraint {cid} no longer exists.")
    new_scope_type = scope_type or row.scope_type
    new_scope_value = row.scope_value if scope_value is None else scope_value
    merged = json.loads(row.params_json or "{}")
    if params:
        merged.update(params)
    norm, desc, priority = validate(db, row.kind, new_scope_type, new_scope_value, merged, ctx)
    row.scope_type = new_scope_type
    row.scope_value = "" if new_scope_type == "global" else str(new_scope_value)
    row.params_json = json.dumps(norm)
    row.description = desc
    row.priority = priority
    row.weight = int(norm.get("weight", row.weight))
    if enabled is not None:
        row.enabled = enabled
    if source:
        row.source = source
    if origin_prompt:
        row.origin_prompt = origin_prompt
    if commit:
        db.commit()
    return row


def delete(db: Session, cid: int, commit: bool = True) -> None:
    row = db.get(Constraint, cid)
    if row is None:
        raise ConstraintError(f"Constraint {cid} no longer exists.")
    db.delete(row)
    if commit:
        db.commit()


# ---------- registry -> SolveOptions ----------

def _scope_rules(bucket: dict[Any, ScopeRules], key: Any) -> ScopeRules:
    if key not in bucket:
        bucket[key] = ScopeRules()
    return bucket[key]


def compile_options(db: Session) -> SolveOptions:
    """Turn every enabled constraint row into the solver's SolveOptions."""
    opts = SolveOptions()
    sections = {s.name: s for s in db.query(Section).all()}
    sem_rules: dict[int, ScopeRules] = {}
    sec_rules: dict[int, ScopeRules] = {}
    # per-teacher caps are applied to TeacherIn by the loader, so collect them here
    opts_teacher_caps: dict[int, dict[str, int]] = {}

    for c in db.query(Constraint).filter(Constraint.enabled.is_(True)).all():
        if c.kind not in CATALOG:
            continue  # a kind removed from the catalog is ignored, not fatal
        p = json.loads(c.params_json or "{}")

        target: ScopeRules | None
        if c.scope_type == "global":
            target = None
        elif c.scope_type == "semester":
            try:
                target = _scope_rules(sem_rules, int(c.scope_value))
            except ValueError:
                continue
        else:
            sec = sections.get(c.scope_value)
            if sec is None:
                continue  # section renamed/removed — rule quietly stops applying
            target = _scope_rules(sec_rules, sec.id)

        if c.kind == "half_day":
            if target is None:
                opts.half_days[p["day"]] = p["last_period"]
            else:
                target.half_days[p["day"]] = p["last_period"]
        elif c.kind == "no_same_subject_consecutive":
            if target is None:
                opts.no_same_subject_consecutive = bool(p["value"])
            else:
                target.no_same_subject_consecutive = bool(p["value"])
        elif c.kind == "max_consecutive_teaching":
            if target is None:
                opts.max_consecutive_teaching = int(p["value"])
            else:
                target.max_consecutive_teaching = int(p["value"])
        elif c.kind == "subject_daily_max":
            if target is None:
                opts.subject_daily_max = int(p["value"])
            else:
                target.subject_daily_max = int(p["value"])
        elif c.kind == "max_periods_per_day":
            if target is None:
                opts.max_periods_per_day = int(p["value"])
            else:
                target.max_periods_per_day = int(p["value"])
        elif c.kind == "class_slot_ban":
            targets = ([sections[c.scope_value].id] if c.scope_type == "section"
                       else [s.id for s in sections.values()
                             if str(s.semester) == c.scope_value])
            for sec_id in targets:
                opts.bans.append(SlotBan(target="section", ref_id=sec_id,
                                         days=p.get("days", []), periods=p.get("periods", []),
                                         label=c.description))
        elif c.kind == "teacher_unavailable":
            opts.bans.append(SlotBan(target="teacher", ref_id=int(p["teacher_id"]),
                                     days=p.get("days", []), periods=p.get("periods", []),
                                     label=c.description))
        elif c.kind == "subject_slot_ban":
            opts.bans.append(SlotBan(target="subject", ref_id=int(p["subject_id"]),
                                     days=p.get("days", []), periods=p.get("periods", []),
                                     label=c.description))
        elif c.kind == "subject_preferred_periods":
            opts.preferred.append(PreferredPeriods(
                subject_id=int(p["subject_id"]), periods=p.get("periods", []),
                days=p.get("days", []), weight=c.weight or 1, label=c.description))
        elif c.kind == "elective_fixed_slots":
            opts.elective_pins.append(ElectivePin(
                group_id=int(p["band_id"]),
                slots=[(d, n) for d in p.get("days", []) for n in p.get("periods", [])],
                label=c.description))
        elif c.kind == "avoid_gaps":
            opts.avoid_gaps_weight = int(p.get("weight", 2))
        elif c.kind in ("teacher_max_daily", "teacher_max_weekly", "teacher_max_consecutive"):
            opts_teacher_caps.setdefault(int(p["teacher_id"]), {})[c.kind] = int(p["value"])

    opts.semester_rules = sem_rules
    opts.section_rules = sec_rules
    opts.teacher_caps = opts_teacher_caps  # consumed by load_timetable_input()
    return opts


def summary(db: Session) -> list[str]:
    """One line per active rule — used in flash messages and the PDF header."""
    return [c.description for c in list_constraints(db) if c.enabled]


# ---------- bootstrapping ----------

def ensure_defaults(db: Session) -> int:
    """Seed the registry the first time it is used.

    Carries over the constraints of the most recent generated version (Phase 2.2/
    2.3 stored them as a JSON snapshot), so upgrading an existing database keeps
    generating the same timetable it did before. Returns rows created."""
    if db.query(Constraint).count() > 0:
        return 0
    ctx = build_ctx(db)
    created = 0
    cfg: dict = {}
    row = (db.query(TimetableConfig).order_by(TimetableConfig.version.desc()).first())
    if row:
        try:
            cfg = json.loads(row.config_json or "{}")
        except json.JSONDecodeError:
            cfg = {}

    def add(kind, scope_type, scope_value, params):
        nonlocal created
        try:
            create(db, kind, scope_type, scope_value, params,
                   source="seed", ctx=ctx, commit=False)
            created += 1
        except ConstraintError:
            pass  # a stale snapshot value (deleted section, changed grid) is skipped

    add("no_same_subject_consecutive", "global", "",
        {"value": cfg.get("no_same_subject_consecutive", True)})
    for day, last in (cfg.get("half_days") or {}).items():
        add("half_day", "global", "", {"day": day, "last_period": last})
    if cfg.get("max_consecutive_teaching"):
        add("max_consecutive_teaching", "global", "", {"value": cfg["max_consecutive_teaching"]})
    for name, sr in (cfg.get("section_rules") or {}).items():
        for day, last in (sr.get("half_days") or {}).items():
            add("half_day", "section", name, {"day": day, "last_period": last})
        if sr.get("no_same_subject_consecutive") is not None:
            add("no_same_subject_consecutive", "section", name,
                {"value": sr["no_same_subject_consecutive"]})
    db.commit()
    return created
