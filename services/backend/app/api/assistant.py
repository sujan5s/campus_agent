"""Timetable Assistant API (Phase 2.5) — one sentence in, a whole plan out.

Phase 2.4 could write scheduling *rules* but nothing else, so "add a teacher John
who takes DBMS for CSE-7A" was rejected and the admin went back to the Setup forms
by hand. This endpoint removes that wall: the assistant creates subjects, teachers,
rooms and classes, wires up who teaches what, builds open-elective bands, writes
rules, and can regenerate the timetable — in one request, in dependency order.

What survives from 2.4 is the discipline, not the refusal:

  * the model emits **typed operations**, never SQL and never free text;
  * every op is validated against live data by `app/tools/ops.py`;
  * the whole batch is **previewed in English** and applied on one confirmation;
  * a failure is reported per-op, and the batch commits atomically.
"""
import json
import re
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.llm import get_llm, is_llm_configured, text_of
from app.core.security import require_role
from app.db.models import (
    Constraint, ElectiveGroup, Room, Section, Subject, Teacher, TimeSlot,
)
from app.db.session import get_db
from app.tools import constraints as reg
from app.tools import ops as opsmod

router = APIRouter()
admin_only = Depends(require_role("admin"))

# Generous, because a big plan is a lot of output tokens — but the bulk forms in
# the prompt are what actually keep a request fast; this is only the backstop.
LLM_TIMEOUT_S = 90.0


class PromptIn(BaseModel):
    prompt: str


class OpIn(BaseModel):
    op: str
    params: dict = Field(default_factory=dict)


class ApplyIn(BaseModel):
    ops: list[OpIn]
    prompt: str = ""


# ---------- what the model is told it may do ----------

_OP_REFERENCE = """
BULK FORMS — prefer these whenever you are adding more than one of a thing.
`defaults` is merged into every item, so repeat nothing:
  add_subjects {defaults?:{...}, items:[{code, name, ...}, ...]}
  add_teachers {defaults?:{...}, items:[{name, subjects:[codes], assign_to?}, ...]}
      assign_to = a class name; the teacher is created AND assigned to it for
      each of their subjects, so you need no separate assign_teacher op
  add_rooms    {defaults?:{...}, items:[{name, type, capacity}, ...]}
  add_classes  {defaults?:{...}, items:[{name, semester, strength}, ...]}

DATA — create whatever is missing, do not refuse:
  add_subject     {code, name, dept?, semester, periods_per_week?, needs_lab?}
  edit_subject    {code, name?, semester?, periods_per_week?, needs_lab?}
  remove_subject  {code}
  add_teacher     {name, email?, dept?, max_hours_per_day?, subjects?:[codes]}
  edit_teacher    {name, new_name?, dept?, max_hours_per_day?}
  remove_teacher  {name}
  set_teacher_subjects {teacher, subjects:[codes], mode: add|replace|remove}
  add_room        {name, type: classroom|lab|auditorium|seminar|ground, capacity?}
  edit_room       {name, type?, capacity?}
  remove_room     {name}
  add_class       {name, dept?, semester, strength?}
  edit_class      {name, semester?, strength?}
  remove_class    {name}

WHO TEACHES WHAT:
  assign_teacher  {section, subject, teacher}     ("" teacher = let the solver choose)

OPEN ELECTIVES (one band per semester; options run in parallel):
  add_elective_band   {name, semester, periods_per_week?, needs_block?,
                       options:[{subject, teacher, room, capacity?}]}
  add_elective_option {band, subject, teacher, room, capacity?}
  remove_elective_band {name}

SCHEDULING RULES (kinds and params come from the rule catalog below):
  add_rule     {kind, scope_type: global|semester|section, scope_value, params:{...}}
  edit_rule    {id, params:{...}}      -- id of an existing rule
  remove_rule  {id}
  disable_rule {id}   enable_rule {id}

ACTION:
  generate_timetable {fresh?: false}   -- keeps the current schedule by default
"""

_SYSTEM = """You are the Timetable Assistant of a college operations system.

You own everything about timetable data: subjects, teachers, rooms, classes, who
teaches what, open electives, and the scheduling rules. Your job is to turn one
request into a complete, ordered plan of operations that achieves it.

THE MOST IMPORTANT RULE: if something the admin refers to does not exist yet,
CREATE IT. Never reply that a teacher, subject, room or class is missing — that
is the manual work you exist to eliminate. "Add a teacher John who takes DBMS for
CSE-7A" is a plan: create the subject if needed, create the teacher, assign them.

BE BRIEF. The admin waits on every token you write, so say each thing once:
- use the bulk forms below for more than one subject / teacher / room / class,
  and put everything shared into `defaults`;
- give a teacher `assign_to` instead of writing a separate assign_teacher op;
- omit any parameter whose default is already what you want.

Order matters. Emit operations in dependency order — create a subject before a
teacher who teaches it, create the teacher before assigning them. Later ops may
refer to things earlier ops create.

Changing a timetable does not mean rebuilding it. `generate_timetable {}` keeps
the existing schedule and moves only what your changes force; pass
{"fresh": true} only if the admin explicitly asks for a full re-plan.

Fill in sensible detail rather than asking:
- follow the existing naming conventions you can see in the context (subject codes,
  class names, room names, email style);
- if a subject code is not given, invent one that matches the convention;
- omit email for a new teacher and it is generated from their name;
- defaults: dept CSE, 4 periods/week, 5 max hours/day, 60 capacity/strength.

Be conservative about destruction. Only remove something when the admin clearly
asked to; never remove something merely to replace it if an edit_* op will do.

If the request implies the timetable should change, end the plan with
generate_timetable.

Only use the operations listed below, and only reference rule kinds from the rule
catalog. You never schedule anything yourself: a CP-SAT solver does that, and it
obeys the data and rules you write.

OPERATIONS:
""" + _OP_REFERENCE + """
Reply with JSON only, no prose, exactly:
{"ops": [{"op": "...", "params": {...}}, ...],
 "notes": "one short sentence describing the plan for the admin"}"""


def _entity_context(db: Session) -> dict:
    slots = db.query(TimeSlot).all()
    return {
        "days": [d for d in reg.DAYS if any(s.day == d for s in slots)],
        "periods": sorted({s.period_no for s in slots}),
        "classes": [{"name": s.name, "semester": s.semester, "dept": s.dept,
                     "strength": s.strength}
                    for s in db.query(Section).order_by(Section.name).all()],
        "subjects": [{"code": s.code, "name": s.name, "semester": s.semester,
                      "periods_per_week": s.periods_per_week, "lab": s.needs_lab}
                     for s in db.query(Subject).order_by(Subject.code).all()],
        "teachers": [{"name": t.user.name, "dept": t.dept,
                      "max_hours_per_day": t.max_hours_per_day,
                      "teaches": [s.code for s in t.subjects]}
                     for t in db.query(Teacher).all() if t.user],
        "rooms": [{"name": r.name, "type": r.type, "capacity": r.capacity}
                  for r in db.query(Room).order_by(Room.name).all()],
        "elective_bands": [{"name": g.name, "semester": g.semester,
                            "periods_per_week": g.periods_per_week,
                            "options": [{"subject": o.subject.code,
                                         "teacher": o.teacher.user.name,
                                         "room": o.room.name} for o in g.offerings]}
                           for g in db.query(ElectiveGroup).all()],
        "rule_catalog": [{"kind": k["kind"], "what": k["help"], "scopes": k["scopes"],
                          "params": [f["name"] for f in k["fields"]]}
                         for k in reg.catalog_json()],
        "existing_rules": [{"id": c.id, "kind": c.kind, "scope_type": c.scope_type,
                            "scope_value": c.scope_value, "enabled": c.enabled,
                            "reads_as": c.description}
                           for c in reg.list_constraints(db)],
    }


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace:
            return json.loads(brace.group(0))
        raise


def _ask_llm(db: Session, prompt: str) -> str:
    """One bounded call on a daemon thread — see docs/09 §7 for why not a pool."""
    messages = [
        ("system", _SYSTEM),
        ("user", "Current campus data:\n"
                 + json.dumps(_entity_context(db), ensure_ascii=False)
                 + f"\n\nAdmin says: {prompt}"),
    ]
    box: dict[str, object] = {}

    def work() -> None:
        try:
            box["reply"] = get_llm(temperature=0).invoke(messages)
        except Exception as exc:
            box["error"] = exc

    worker = threading.Thread(target=work, name="assistant-llm", daemon=True)
    worker.start()
    worker.join(LLM_TIMEOUT_S)
    if worker.is_alive():
        raise TimeoutError(f"the model did not answer within {LLM_TIMEOUT_S:.0f}s")
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return text_of(box.get("reply"))


# ---------- endpoints ----------

@router.post("/interpret", dependencies=[admin_only])
def interpret(body: PromptIn, db: Session = Depends(get_db)):
    """Turn a request into a previewed plan. Writes nothing."""
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(422, "Tell me what you want to change.")
    reg.ensure_defaults(db)

    notes, used_llm = "", False
    if is_llm_configured():
        try:
            data = _extract_json(_ask_llm(db, prompt))
            raw_ops = data.get("ops") or []
            notes = str(data.get("notes") or "")
            used_llm = True
        except Exception as exc:
            raw_ops, notes = _fallback(db, prompt)
            notes = (f"The language model could not be reached "
                     f"({str(exc) or type(exc).__name__}). {notes}")
    else:
        raw_ops, notes = _fallback(db, prompt)
        notes = f"No LLM key is configured. {notes}"

    steps = opsmod.plan(db, raw_ops if isinstance(raw_ops, list) else [])
    if not steps:
        notes = notes or ("I could not turn that into a plan — try naming the class, "
                          "teacher or subject involved.")
    return {"prompt": prompt, "ops": steps, "notes": notes, "llm": used_llm,
            "blocked": [s for s in steps if not s.get("ok")]}


@router.post("/apply", dependencies=[admin_only])
def apply(body: ApplyIn, db: Session = Depends(get_db)):
    """Run a previewed plan, in order, in one transaction."""
    done, failed, regenerate = opsmod.run(
        db, [{"op": o.op, "params": o.params} for o in body.ops])

    result: dict = {"applied": done, "failed": failed, "generated": None}
    if regenerate:
        from app.tools.timetable import current_options, generate_timetable
        gen = generate_timetable(options=current_options(db),
                                 preserve=(regenerate != "fresh"))
        result["generated"] = gen
        if gen["status"] in ("optimal", "feasible"):
            moved = gen.get("lessons_moved")
            done.append(
                f"timetable v{gen['version']} — {gen['lessons']} lessons"
                + (f" + {gen['elective_periods']} elective period(s)"
                   if gen.get("elective_periods") else "")
                + (f", {moved} existing lesson(s) moved" if moved is not None
                   else " (planned from scratch)"))
        else:
            failed.append({"op": "generate_timetable",
                           "error": " ".join(gen.get("reasons") or ["Generation failed."])})
    return result


@router.get("/context", dependencies=[admin_only])
def context(db: Session = Depends(get_db)):
    """What the assistant can see, and what it can do — powers the UI hints."""
    return {"entities": _entity_context(db), "operations": opsmod.ops_catalog(),
            "llm": is_llm_configured()}


# ---------- offline fallback ----------

def _fallback(db: Session, prompt: str) -> tuple[list[dict], str]:
    """Deterministic parser for the handful of phrasings worth supporting without
    a model. Emits the same ops and goes through the same validation, so this is a
    narrower front door — not a second system."""
    p = prompt.lower()
    ops: list[dict] = []

    m = re.search(r"add (?:a )?(?:new )?(classroom|lab|room|auditorium|seminar)\s+"
                  r"(?:called |named )?([\w\s-]+?)(?:\s+with|\s+capacity|$)", p)
    if m:
        kind = {"room": "classroom"}.get(m.group(1), m.group(1))
        cap = re.search(r"capacity\s*(?:of\s*)?(\d+)", p)
        ops.append({"op": "add_room", "params": {
            "name": m.group(2).strip().title(), "type": kind,
            "capacity": int(cap.group(1)) if cap else 60}})

    if re.search(r"\b(generate|regenerate|rebuild)\b.*\btimetable\b", p) or \
       re.search(r"\btimetable\b.*\b(generate|regenerate|rebuild)\b", p):
        ops.append({"op": "generate_timetable", "params": {}})

    if not ops:
        # fall back to the Phase 2.4 rule parser for constraint-shaped sentences
        from app.api.constraints import _fallback_ops
        rule_ops, _ = _fallback_ops(db, prompt)
        for r in rule_ops:
            ops.append({"op": "add_rule", "params": {
                "kind": r.get("kind"), "scope_type": r.get("scope_type"),
                "scope_value": r.get("scope_value"), "params": r.get("params") or {}}})

    note = ("Read by the built-in parser, which handles only simple requests — "
            "creating teachers, subjects and classes needs the language model.")
    return ops, note
