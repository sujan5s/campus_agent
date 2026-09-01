"""Constraints API (Phase 2.4) — the editable rulebook behind timetable generation.

Reads are open to any authenticated user (everyone may see why their timetable
looks the way it does); writes are admin-only.

This module owns the rulebook itself: the list, the catalog behind it, and the
form-driven CRUD. Natural language moved out in Phase 2.5 — the assistant now
creates teachers, subjects, rooms and classes as well as rules, so it lives in
`app/api/assistant.py`. The `/interpret` and `/apply` routes here are thin
delegates kept for older clients.
"""
import json
import re
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.llm import get_llm, is_llm_configured, text_of
from app.core.security import get_current_user, require_role
from app.db.models import (
    Constraint, ElectiveGroup, Section, Subject, Teacher, TimeSlot,
)
from app.db.session import get_db
from app.tools import constraints as reg

router = APIRouter()

admin_only = Depends(require_role("admin"))
any_user = Depends(get_current_user)


# ---------- schemas ----------

class ConstraintIn(BaseModel):
    kind: str
    scope_type: str = "global"
    scope_value: str = ""
    params: dict = Field(default_factory=dict)
    enabled: bool = True


class ConstraintPatch(BaseModel):
    params: dict | None = None
    scope_type: str | None = None
    scope_value: str | None = None
    enabled: bool | None = None


class PromptIn(BaseModel):
    prompt: str


class OpIn(BaseModel):
    op: str                                   # create | update | delete | enable | disable
    id: int | None = None
    kind: str | None = None
    scope_type: str | None = None
    scope_value: str | None = None
    params: dict = Field(default_factory=dict)


class ApplyIn(BaseModel):
    ops: list[OpIn]
    prompt: str = ""


# ---------- read ----------

def _context(db: Session) -> dict:
    """Entities a constraint may refer to — drives the UI pickers and the LLM prompt."""
    slots = db.query(TimeSlot).all()
    sections = db.query(Section).order_by(Section.name).all()
    return {
        "days": [d for d in reg.DAYS if any(s.day == d for s in slots)],
        "periods": sorted({s.period_no for s in slots}),
        "sections": [{"id": s.id, "name": s.name, "semester": s.semester, "dept": s.dept}
                     for s in sections],
        "semesters": sorted({s.semester for s in sections}),
        "subjects": [{"id": s.id, "code": s.code, "name": s.name, "semester": s.semester}
                     for s in db.query(Subject).order_by(Subject.code).all()],
        "teachers": [{"id": t.id, "name": t.user.name} for t in db.query(Teacher).all()
                     if t.user],
        "bands": [{"id": b.id, "name": b.name, "semester": b.semester,
                   "periods_per_week": b.periods_per_week, "active": b.active}
                  for b in db.query(ElectiveGroup).order_by(ElectiveGroup.name).all()],
    }


@router.get("")
def list_all(db: Session = Depends(get_db), user=any_user):
    reg.ensure_defaults(db)
    return {
        "constraints": [reg.to_dict(c) for c in reg.list_constraints(db)],
        "catalog": reg.catalog_json(),
        "context": _context(db),
        "llm": is_llm_configured(),
    }


# ---------- write ----------

@router.post("", dependencies=[admin_only])
def create_one(body: ConstraintIn, db: Session = Depends(get_db)):
    try:
        row = reg.create(db, body.kind, body.scope_type, body.scope_value,
                         body.params, source="ui", enabled=body.enabled)
    except reg.ConstraintError as exc:
        raise HTTPException(422, str(exc))
    return reg.to_dict(row)


@router.patch("/{cid}", dependencies=[admin_only])
def update_one(cid: int, body: ConstraintPatch, db: Session = Depends(get_db)):
    try:
        row = reg.update(db, cid, params=body.params, scope_type=body.scope_type,
                         scope_value=body.scope_value, enabled=body.enabled)
    except reg.ConstraintError as exc:
        raise HTTPException(422, str(exc))
    return reg.to_dict(row)


@router.delete("/{cid}", dependencies=[admin_only])
def delete_one(cid: int, db: Session = Depends(get_db)):
    try:
        reg.delete(db, cid)
    except reg.ConstraintError as exc:
        raise HTTPException(404, str(exc))
    return {"ok": True, "deleted": cid}


# ---------- natural language -> typed ops ----------

_SYSTEM = """You are the Constraints Agent of a college timetable system.

Turn the admin's sentence into operations over an existing constraint registry.
You NEVER schedule anything yourself — a CP-SAT solver does that. Your only job
is to emit rules it will obey.

Rules:
- Use ONLY the constraint kinds in the catalog. Never invent a kind or a param.
- Refer only to sections, semesters, subjects and teachers that appear in the
  context. If the admin names something that does not exist, do not guess —
  return no op for it and explain in "notes".
- If the request changes a rule that already exists, emit an "update" (or
  "delete"/"disable") for that rule's id instead of creating a duplicate.
- Scope: "global" = every class, "semester" (scope_value = the number, e.g. "7"),
  "section" (scope_value = the class name, e.g. "CSE-7A"). Pick the narrowest
  scope the admin actually asked for.
- Several rules in one sentence => several ops.

Reply with JSON only, no prose, in exactly this shape:
{"ops": [{"op": "create|update|delete|enable|disable", "id": <int, for existing
rules>, "kind": "...", "scope_type": "...", "scope_value": "...",
"params": {...}}], "notes": "one short sentence for the admin"}"""


def _llm_context_blob(db: Session) -> str:
    ctx = _context(db)
    rows = [{"id": c.id, "kind": c.kind, "scope_type": c.scope_type,
             "scope_value": c.scope_value, "enabled": c.enabled,
             "params": json.loads(c.params_json or "{}"), "reads_as": c.description}
            for c in reg.list_constraints(db)]
    catalog = [{"kind": k["kind"], "what": k["help"], "scopes": k["scopes"],
                "params": [f["name"] for f in k["fields"]]}
               for k in reg.catalog_json()]
    return json.dumps({
        "catalog": catalog,
        "existing_constraints": rows,
        "days": ctx["days"], "periods": ctx["periods"],
        "sections": [{"name": s["name"], "semester": s["semester"]} for s in ctx["sections"]],
        "semesters": ctx["semesters"],
        "subjects": [s["code"] for s in ctx["subjects"]],
        "teachers": [t["name"] for t in ctx["teachers"]],
        "elective_bands": ctx["bands"],
    }, ensure_ascii=False)


def _extract_json(text: str) -> dict:
    """Tolerate ```json fences and stray prose around the object."""
    text = text.strip()
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


_WEEKDAY_WORDS = {"MON": "monday", "TUE": "tuesday", "WED": "wednesday",
                  "THU": "thursday", "FRI": "friday", "SAT": "saturday",
                  "SUN": "sunday"}


def _fallback_ops(db: Session, prompt: str) -> tuple[list[dict], str]:
    """Deterministic mini-parser for the common phrasings.

    Used when no LLM key is configured *and* when the provider cannot be reached —
    the demo must still work on a machine with no key or no network."""
    p = prompt.lower()
    ctx = reg.build_ctx(db)
    ops: list[dict] = []

    scope_type, scope_value = "global", ""
    sec = next((n for n in ctx.sections if n.lower() in p), None)
    if sec:
        scope_type, scope_value = "section", sec
    else:
        sem = re.search(r"(?:sem|semester)\s*(\d+)", p)
        if sem and int(sem.group(1)) in ctx.semesters:
            scope_type, scope_value = "semester", sem.group(1)

    day = next((d for d in ctx.days
                if d.lower() in p or _WEEKDAY_WORDS.get(d, "\0") in p), None)

    # "semester 5" and "CSE-7A" must not donate their digits as the period/limit,
    # so drop whatever named the scope before hunting for a number.
    rest = re.sub(r"(?:sem|semester)\s*\d+", " ", p)
    if sec:
        rest = rest.replace(sec.lower(), " ")

    def number() -> int | None:
        """The number the rule is about — one written as a period wins."""
        m = (re.search(r"(?:period|periods|p)\s*(\d+)", rest)
             or re.search(r"\bp(\d+)\b", rest)
             or re.search(r"(\d+)", rest))
        return int(m.group(1)) if m else None

    def all_days() -> list[str]:
        return [d for d in ctx.days
                if d.lower() in p or _WEEKDAY_WORDS.get(d, "\0") in p]

    def all_periods() -> list[int]:
        """Every period the sentence names — 'P3', 'period 3', '3rd hour'."""
        found = {int(m) for m in re.findall(r"\bp\s*(\d+)\b", rest)}
        found |= {int(m) for m in re.findall(r"(?:period|hour)s?\s*(\d+)", rest)}
        found |= {int(m) for m in
                  re.findall(r"(\d+)\s*(?:st|nd|rd|th)\s*(?:period|hour)", rest)}
        return sorted(found)

    n = number()
    if "elective" in p:
        days, periods = all_days(), all_periods()
        if days and periods:
            ops.append({"op": "create", "kind": "elective_fixed_slots",
                        "scope_type": scope_type, "scope_value": scope_value,
                        "params": {"days": days, "periods": periods}})
    elif "half day" in p or "half-day" in p:
        if day and n is not None:
            ops.append({"op": "create", "kind": "half_day", "scope_type": scope_type,
                        "scope_value": scope_value,
                        "params": {"day": day, "last_period": n}})
    elif "back to back" in p or "back-to-back" in p or "consecutive subject" in p:
        allow = any(w in p for w in ("allow", "permit", "ok", "fine"))
        ops.append({"op": "create", "kind": "no_same_subject_consecutive",
                    "scope_type": scope_type, "scope_value": scope_value,
                    "params": {"value": not allow}})
    elif "in a row" in p or "consecutive" in p:
        if n is not None:
            ops.append({"op": "create", "kind": "max_consecutive_teaching",
                        "scope_type": scope_type, "scope_value": scope_value,
                        "params": {"value": n}})
    elif "per day" in p or "a day" in p or "each day" in p:
        if n is not None:
            ops.append({"op": "create", "kind": "max_periods_per_day",
                        "scope_type": scope_type, "scope_value": scope_value,
                        "params": {"value": n}})
    elif "gap" in p or "free period" in p:
        ops.append({"op": "create", "kind": "avoid_gaps", "scope_type": "global",
                    "scope_value": "", "params": {"weight": 2}})

    note = ("Read by the built-in parser, which only understands simple phrasings — "
            "use the Add-constraint form for anything it missed.")
    return ops, note


def _preview(db: Session, ops: list[dict]) -> list[dict]:
    """Validate each op and render what it would do. Never writes."""
    ctx = reg.build_ctx(db)
    out = []
    for raw in ops:
        op = str(raw.get("op") or "create").lower()
        item: dict = {"op": op, "id": raw.get("id"), "kind": raw.get("kind"),
                      "scope_type": raw.get("scope_type") or "global",
                      "scope_value": raw.get("scope_value") or "",
                      "params": raw.get("params") or {}}
        try:
            if op in ("delete", "enable", "disable"):
                row = db.get(Constraint, item["id"]) if item["id"] else None
                if row is None:
                    raise reg.ConstraintError(
                        f"There is no constraint #{item['id']} to {op}.")
                item["kind"] = row.kind
                verb = {"delete": "Remove", "enable": "Turn on", "disable": "Turn off"}[op]
                item["description"] = f"{verb} — {row.description}"
                item["before"] = row.description
            elif op == "update":
                row = db.get(Constraint, item["id"]) if item["id"] else None
                if row is None:
                    raise reg.ConstraintError(
                        f"There is no constraint #{item['id']} to update.")
                merged = json.loads(row.params_json or "{}")
                merged.update(item["params"])
                _, desc, _ = reg.validate(db, row.kind,
                                          item["scope_type"] or row.scope_type,
                                          item["scope_value"] or row.scope_value,
                                          merged, ctx)
                item["kind"] = row.kind
                item["before"] = row.description
                item["description"] = desc
            else:
                item["op"] = "create"
                _, desc, _ = reg.validate(db, item["kind"], item["scope_type"],
                                          item["scope_value"], item["params"], ctx)
                item["description"] = desc
            item["ok"] = True
        except reg.ConstraintError as exc:
            item["ok"] = False
            item["error"] = str(exc)
        except Exception as exc:  # a malformed op from the model
            item["ok"] = False
            item["error"] = f"Could not read that rule ({type(exc).__name__})."
        out.append(item)
    return out


LLM_TIMEOUT_S = 30.0


def _ask_llm(db: Session, prompt: str) -> str:
    """One LLM call, bounded by a deadline.

    A provider that stops responding (rate limit, network stall) would otherwise
    hang this request — and the admin's browser — indefinitely. On timeout we
    raise and the caller degrades to the deterministic parser.

    A *daemon* thread, deliberately: the LangChain call has no cancellation, so
    on timeout the worker is left to finish on its own. A ThreadPoolExecutor
    worker is non-daemon and would then block interpreter exit (and uvicorn's
    auto-reload) until the provider eventually answers.
    """
    messages = [
        ("system", _SYSTEM),
        ("user", f"Context:\n{_llm_context_blob(db)}\n\nAdmin says: {prompt}"),
    ]
    box: dict[str, object] = {}

    def run() -> None:
        try:
            box["reply"] = get_llm(temperature=0).invoke(messages)
        except Exception as exc:  # surfaced on the calling thread below
            box["error"] = exc

    worker = threading.Thread(target=run, name="constraint-llm", daemon=True)
    worker.start()
    worker.join(LLM_TIMEOUT_S)
    if worker.is_alive():
        raise TimeoutError(f"the model did not answer within {LLM_TIMEOUT_S:.0f}s")
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return text_of(box.get("reply"))


@router.post("/interpret", dependencies=[admin_only])
def interpret(body: PromptIn, db: Session = Depends(get_db)):
    """Deprecated alias for `POST /api/assistant/interpret`.

    Phase 2.5 widened this from "edit a rule" to "do anything to timetable data",
    so the implementation moved to `app/api/assistant.py`. Kept as a delegate so
    an older client keeps working — there is only one implementation."""
    from app.api.assistant import PromptIn as APrompt, interpret as _interpret

    return _interpret(APrompt(prompt=body.prompt), db)


@router.post("/apply", dependencies=[admin_only])
def apply(body: "ApplyIn", db: Session = Depends(get_db)):
    """Deprecated alias for `POST /api/assistant/apply` — see `interpret` above."""
    from app.api.assistant import ApplyIn as AApply, OpIn as AOp, apply as _apply

    ops = [AOp(op=o.op or "", params=o.params or {}) for o in body.ops]
    return _apply(AApply(ops=ops, prompt=body.prompt), db)
