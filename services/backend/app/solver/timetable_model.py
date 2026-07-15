"""OR-Tools CP-SAT timetable model (docs/02-ARCHITECTURE.md, research/03).

Design rule: the LLM never solves the timetable — this model does, deterministically.
The LLM's job is upstream (parse the request) and downstream (explain the outcome).

Hard constraints
  H1  every (section, subject) gets exactly periods_per_week lessons
  H2  a section has at most one lesson per timeslot
  H3  a teacher teaches at most one lesson per timeslot (clash-free)
  H4  exactly one qualified teacher per (section, subject)
  H5  lab subjects run as one block of consecutive same-day periods in a lab room;
      lab rooms are clash-free
  H6  each section gets a dedicated home classroom with enough capacity
  H7  teacher daily load <= max_hours_per_day
  H8  at most 2 periods of the same theory subject per day (spread)

Soft objective
  minimize the weekly-load gap between the busiest and idlest teacher (fairness)

Infeasibility: pre-checks produce precise human-readable reasons cheaply; if the
model is still infeasible, CP-SAT assumption literals identify which constraint
groups conflict (research/03 gap: GA papers cannot explain infeasibility).
"""
from dataclasses import dataclass, field

from ortools.sat.python import cp_model


# ---------- plain-data inputs (decoupled from SQLAlchemy) ----------

@dataclass
class SlotIn:
    id: int
    day: str
    period_no: int
    start_min: int  # minutes since midnight — used to detect adjacency
    end_min: int


@dataclass
class SubjectIn:
    id: int
    code: str
    periods_per_week: int
    needs_lab: bool


@dataclass
class TeacherIn:
    id: int
    name: str
    max_hours_per_day: int
    subject_ids: set[int]


@dataclass
class SectionIn:
    id: int
    name: str
    strength: int
    subject_ids: list[int]  # subjects this section takes


@dataclass
class RoomIn:
    id: int
    name: str
    type: str
    capacity: int


@dataclass
class TimetableInput:
    sections: list[SectionIn]
    subjects: dict[int, SubjectIn]
    teachers: list[TeacherIn]
    rooms: list[RoomIn]
    slots: list[SlotIn]


@dataclass
class SectionRules:
    """Per-section overrides of the global SolveOptions (by section id)."""
    half_days: dict[str, int] = field(default_factory=dict)   # {"WED": 4}; overrides global per day
    no_same_subject_consecutive: bool | None = None           # None = inherit the global default


@dataclass
class SolveOptions:
    """Admin-configurable generation constraints.

    no_same_subject_consecutive defaults ON — real timetables should not put the
    same subject in adjacent periods (hectic for students and teachers). Every
    field can be overridden per section via `section_rules`."""
    half_days: dict[str, int] = field(default_factory=dict)   # global default: {"WED": 4}
    no_same_subject_consecutive: bool = True                  # H9 (theory only; labs exempt)
    max_consecutive_teaching: int | None = None               # H10 teacher run cap (global)
    section_rules: dict[int, SectionRules] = field(default_factory=dict)  # by section_id


def _section_half_days(opts: "SolveOptions", sec_id: int) -> dict[str, int]:
    """Global half-days merged with a section's overrides (section wins per day)."""
    hd = dict(opts.half_days)
    sr = opts.section_rules.get(sec_id)
    if sr and sr.half_days:
        hd.update(sr.half_days)
    return hd


def _section_nosc(opts: "SolveOptions", sec_id: int) -> bool:
    """Effective no-same-subject-consecutive flag for one section."""
    sr = opts.section_rules.get(sec_id)
    if sr is not None and sr.no_same_subject_consecutive is not None:
        return sr.no_same_subject_consecutive
    return opts.no_same_subject_consecutive


def _allowed_indices(data: "TimetableInput", opts: "SolveOptions",
                     sec_id: int) -> set[int]:
    """Slot indices a section may use, after applying its effective half-days."""
    hd = _section_half_days(opts, sec_id)
    return {i for i, s in enumerate(data.slots)
            if not (s.day in hd and s.period_no > hd[s.day])}


@dataclass
class Lesson:
    section_id: int
    subject_id: int
    teacher_id: int
    room_id: int
    timeslot_id: int


@dataclass
class SolveResult:
    status: str  # "optimal" | "feasible" | "infeasible" | "error"
    lessons: list[Lesson] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)  # infeasibility reasons
    stats: dict = field(default_factory=dict)


# ---------- pre-solve sanity checks (precise, cheap explanations) ----------

def precheck(data: TimetableInput, opts: "SolveOptions | None" = None) -> list[str]:
    opts = opts or SolveOptions()
    reasons: list[str] = []
    classrooms = [r for r in data.rooms if r.type == "classroom"]
    labs = [r for r in data.rooms if r.type == "lab"]
    pairs = _consecutive_pairs(data.slots)

    if not data.sections:
        reasons.append("No sections defined — add sections in Data Setup.")
    if not data.slots:
        reasons.append("No timeslots defined — seed or add the period grid first.")

    for sec in data.sections:
        allowed = _allowed_indices(data, opts, sec.id)
        need = sum(data.subjects[sid].periods_per_week for sid in sec.subject_ids)
        if need > len(allowed):
            hint = ("its half-day rules leave only" if len(allowed) < len(data.slots)
                    else "only")
            reasons.append(
                f"Section {sec.name} needs {need} periods/week but {hint} "
                f"{len(allowed)} slots — reduce periods_per_week, add slots, "
                f"or relax its half-days."
            )
        if not sec.subject_ids:
            reasons.append(f"Section {sec.name} has no subjects for its dept/semester.")
        # a lab needs at least one consecutive pair fully inside the allowed slots
        for sid in sec.subject_ids:
            if data.subjects[sid].needs_lab and not any(
                    a in allowed and b in allowed for a, b in pairs):
                reasons.append(
                    f"Section {sec.name}'s half-days leave no consecutive block for "
                    f"lab {data.subjects[sid].code} — relax its half-days."
                )

    for sid, subj in data.subjects.items():
        qualified = [t for t in data.teachers if sid in t.subject_ids]
        if any(sid in sec.subject_ids for sec in data.sections) and not qualified:
            reasons.append(
                f"No teacher can teach {subj.code} — map at least one teacher to it in Data Setup."
            )

    if len(classrooms) < len(data.sections):
        reasons.append(
            f"{len(data.sections)} sections need dedicated classrooms but only "
            f"{len(classrooms)} classrooms exist — add rooms of type 'classroom'."
        )
    lab_subjects = [s for s in data.subjects.values()
                    if s.needs_lab and any(s.id in sec.subject_ids for sec in data.sections)]
    if lab_subjects and not labs:
        reasons.append(
            f"Subjects {[s.code for s in lab_subjects]} need a lab but no room of type 'lab' exists."
        )

    # aggregate teacher capacity: total teachable periods vs demand
    demand = sum(data.subjects[sid].periods_per_week
                 for sec in data.sections for sid in sec.subject_ids)
    days = {s.day for s in data.slots}
    supply = sum(t.max_hours_per_day * len(days) for t in data.teachers)
    if demand > supply:
        reasons.append(
            f"Total demand is {demand} periods/week but teachers can cover at most "
            f"{supply} (max_hours_per_day × days) — add teachers or raise limits."
        )
    return reasons


def _consecutive_pairs(slots: list[SlotIn]) -> list[tuple[int, int]]:
    """Indices of same-day adjacent slot pairs (end == next start, no break between)."""
    pairs = []
    by_day: dict[str, list[int]] = {}
    for i, s in enumerate(slots):
        by_day.setdefault(s.day, []).append(i)
    for day_idx in by_day.values():
        day_idx.sort(key=lambda i: slots[i].period_no)
        for a, b in zip(day_idx, day_idx[1:]):
            if slots[a].end_min == slots[b].start_min:
                pairs.append((a, b))
    return pairs


def _consecutive_runs(slots: list[SlotIn]) -> list[list[int]]:
    """Same-day chains of slot indices that are pairwise time-adjacent (a break
    between periods starts a new run). Used for the teacher run-length cap."""
    runs: list[list[int]] = []
    by_day: dict[str, list[int]] = {}
    for i, s in enumerate(slots):
        by_day.setdefault(s.day, []).append(i)
    for day_idx in by_day.values():
        day_idx.sort(key=lambda i: slots[i].period_no)
        cur: list[int] = []
        prev_end = None
        for i in day_idx:
            if prev_end is not None and slots[i].start_min == prev_end:
                cur.append(i)
            else:
                if cur:
                    runs.append(cur)
                cur = [i]
            prev_end = slots[i].end_min
        if cur:
            runs.append(cur)
    return runs


# ---------- the CP-SAT model ----------

def solve(data: TimetableInput, opts: SolveOptions | None = None,
          time_limit_s: float = 20.0) -> SolveResult:
    opts = opts or SolveOptions()

    reasons = precheck(data, opts)
    if reasons:
        return SolveResult(status="infeasible", reasons=reasons)

    m = cp_model.CpModel()
    slots = data.slots
    n_slots = len(slots)
    days = sorted({s.day for s in slots})
    slots_of_day = {d: [i for i, s in enumerate(slots) if s.day == d] for d in days}
    pairs = _consecutive_pairs(slots)
    classrooms = [r for r in data.rooms if r.type == "classroom"]
    labs = [r for r in data.rooms if r.type == "lab"]

    # Per-section allowed slots (half-days remove trailing periods for that section
    # only — global filtering is wrong once one section keeps the full day).
    allowed = {sec.id: _allowed_indices(data, opts, sec.id) for sec in data.sections}
    any_nosc = any(_section_nosc(opts, sec.id) for sec in data.sections)

    # Assumption literals per constraint group -> named infeasibility explanations
    groups = {
        "teacher availability (clash-free teaching)": m.NewBoolVar("g_teacher"),
        "teacher daily hour limits": m.NewBoolVar("g_daily"),
        "lab consecutive-block scheduling": m.NewBoolVar("g_lab"),
        "same-subject daily spread limit": m.NewBoolVar("g_spread"),
        "home classroom allocation": m.NewBoolVar("g_room"),
    }
    if any_nosc:
        groups["no same-subject back-to-back"] = m.NewBoolVar("g_nosc")
    if opts.max_consecutive_teaching is not None:
        groups["teacher consecutive-teaching cap"] = m.NewBoolVar("g_teachrun")
    m.AddAssumptions(list(groups.values()))
    lit_name = {v.Index(): k for k, v in groups.items()}

    # H4: teacher choice per (section, subject)
    y: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for sec in data.sections:
        for sid in sec.subject_ids:
            elig = [t for t in data.teachers if sid in t.subject_ids]
            lits = []
            for t in elig:
                y[(sec.id, sid, t.id)] = m.NewBoolVar(f"y_{sec.id}_{sid}_{t.id}")
                lits.append(y[(sec.id, sid, t.id)])
            m.AddExactlyOne(lits)

    # lesson placement x[(sec,subj,slot)]
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for sec in data.sections:
        sec_allowed = allowed[sec.id]
        sec_nosc = _section_nosc(opts, sec.id)
        for sid in sec.subject_ids:
            subj = data.subjects[sid]
            for si in range(n_slots):
                x[(sec.id, sid, si)] = m.NewBoolVar(f"x_{sec.id}_{sid}_{si}")
                # slots this section may not use (its half-days) are pinned off
                if si not in sec_allowed:
                    m.Add(x[(sec.id, sid, si)] == 0)
            # H1: exact weekly period count
            m.Add(sum(x[(sec.id, sid, si)] for si in range(n_slots))
                  == subj.periods_per_week)

            # H8: spread — at most 2 periods of one subject per day. Applies to
            # labs too so a lab's extra periods can't stack a 3rd next to the block.
            for d in days:
                m.Add(sum(x[(sec.id, sid, si)] for si in slots_of_day[d]) <= 2)\
                    .OnlyEnforceIf(groups["same-subject daily spread limit"])

            if subj.needs_lab:
                # H5: one consecutive pair (labs are seeded/entered as 2 periods)
                p_vars = []
                for pi, (a, b) in enumerate(pairs):
                    pv = m.NewBoolVar(f"p_{sec.id}_{sid}_{pi}")
                    p_vars.append(pv)
                    m.Add(x[(sec.id, sid, a)] == 1).OnlyEnforceIf(pv)
                    m.Add(x[(sec.id, sid, b)] == 1).OnlyEnforceIf(pv)
                m.AddExactlyOne(p_vars).OnlyEnforceIf(groups["lab consecutive-block scheduling"])
            elif sec_nosc:
                # H9: no same-subject back-to-back (per section) — theory only
                for a, b in pairs:
                    m.Add(x[(sec.id, sid, a)] + x[(sec.id, sid, b)] <= 1)\
                        .OnlyEnforceIf(groups["no same-subject back-to-back"])

    # H2: section clash-free
    for sec in data.sections:
        for si in range(n_slots):
            m.Add(sum(x[(sec.id, sid, si)] for sid in sec.subject_ids) <= 1)

    # w = x AND y  (teacher t actually teaching sec/subj at slot si)
    w: dict[tuple[int, int, int, int], cp_model.IntVar] = {}
    for (sec_id, sid, t_id), yv in y.items():
        for si in range(n_slots):
            wv = m.NewBoolVar(f"w_{sec_id}_{sid}_{t_id}_{si}")
            m.AddBoolAnd([x[(sec_id, sid, si)], yv]).OnlyEnforceIf(wv)
            m.AddImplication(wv, x[(sec_id, sid, si)])
            m.AddImplication(wv, yv)
            # tighten: x & y -> w
            m.AddBoolOr([x[(sec_id, sid, si)].Not(), yv.Not(), wv])
            w[(sec_id, sid, t_id, si)] = wv

    # H3: teacher clash-free + H7 daily limit
    for t in data.teachers:
        keys = [k for k in w if k[2] == t.id]
        for si in range(n_slots):
            at_slot = [w[k] for k in keys if k[3] == si]
            if at_slot:
                m.Add(sum(at_slot) <= 1)\
                    .OnlyEnforceIf(groups["teacher availability (clash-free teaching)"])
        for d in days:
            in_day = [w[k] for k in keys if k[3] in slots_of_day[d]]
            if in_day:
                m.Add(sum(in_day) <= t.max_hours_per_day)\
                    .OnlyEnforceIf(groups["teacher daily hour limits"])

    # H10: cap consecutive teaching periods per teacher (optional). In every
    # window of k+1 time-adjacent slots, the teacher teaches at most k of them.
    if opts.max_consecutive_teaching is not None:
        k = opts.max_consecutive_teaching
        runs = _consecutive_runs(slots)
        for t in data.teachers:
            by_slot: dict[int, list] = {}
            for key in (kk for kk in w if kk[2] == t.id):
                by_slot.setdefault(key[3], []).append(w[key])
            for run in runs:
                for start in range(len(run) - k):
                    window = run[start:start + k + 1]
                    terms = [v for si in window for v in by_slot.get(si, [])]
                    if terms:
                        m.Add(sum(terms) <= k)\
                            .OnlyEnforceIf(groups["teacher consecutive-teaching cap"])

    # H6: dedicated home classroom per section (capacity-checked, distinct)
    c: dict[tuple[int, int], cp_model.IntVar] = {}
    for sec in data.sections:
        opts = []
        for r in classrooms:
            if r.capacity >= sec.strength:
                c[(sec.id, r.id)] = m.NewBoolVar(f"c_{sec.id}_{r.id}")
                opts.append(c[(sec.id, r.id)])
        if not opts:
            return SolveResult(status="infeasible", reasons=[
                f"No classroom has capacity >= {sec.strength} for section {sec.name}."])
        m.AddExactlyOne(opts).OnlyEnforceIf(groups["home classroom allocation"])
    for r in classrooms:
        owners = [c[k] for k in c if k[1] == r.id]
        if owners:
            m.Add(sum(owners) <= 1).OnlyEnforceIf(groups["home classroom allocation"])

    # H5b: lab-room choice per lab subject occurrence + lab-room clash-free
    lr: dict[tuple[int, int, int], cp_model.IntVar] = {}
    lab_keys = [(sec, sid) for sec in data.sections for sid in sec.subject_ids
                if data.subjects[sid].needs_lab]
    for sec, sid in lab_keys:
        opts = []
        for r in labs:
            lr[(sec.id, sid, r.id)] = m.NewBoolVar(f"lr_{sec.id}_{sid}_{r.id}")
            opts.append(lr[(sec.id, sid, r.id)])
        m.AddExactlyOne(opts)
    for r in labs:
        for si in range(n_slots):
            using = []
            for sec, sid in lab_keys:
                u = m.NewBoolVar(f"u_{sec.id}_{sid}_{r.id}_{si}")
                m.AddBoolOr([x[(sec.id, sid, si)].Not(),
                             lr[(sec.id, sid, r.id)].Not(), u])
                m.AddImplication(u, x[(sec.id, sid, si)])
                m.AddImplication(u, lr[(sec.id, sid, r.id)])
                using.append(u)
            if using:
                m.Add(sum(using) <= 1)\
                    .OnlyEnforceIf(groups["lab consecutive-block scheduling"])

    # Soft objective: fair weekly loads across teachers
    loads = []
    for t in data.teachers:
        keys = [w[k] for k in w if k[2] == t.id]
        lv = m.NewIntVar(0, n_slots, f"load_{t.id}")
        m.Add(lv == sum(keys) if keys else lv == 0)
        loads.append(lv)
    max_l = m.NewIntVar(0, n_slots, "max_load")
    min_l = m.NewIntVar(0, n_slots, "min_load")
    m.AddMaxEquality(max_l, loads)
    m.AddMinEquality(min_l, loads)
    m.Minimize(max_l - min_l)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 8
    status = solver.Solve(m)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        lessons: list[Lesson] = []
        for sec in data.sections:
            home = next(r.id for r in classrooms
                        if (sec.id, r.id) in c and solver.Value(c[(sec.id, r.id)]))
            for sid in sec.subject_ids:
                subj = data.subjects[sid]
                t_id = next(t.id for t in data.teachers
                            if (sec.id, sid, t.id) in y
                            and solver.Value(y[(sec.id, sid, t.id)]))
                if subj.needs_lab:
                    room_id = next(r.id for r in labs
                                   if solver.Value(lr[(sec.id, sid, r.id)]))
                else:
                    room_id = home
                for si in range(n_slots):
                    if solver.Value(x[(sec.id, sid, si)]):
                        lessons.append(Lesson(sec.id, sid, t_id, room_id, slots[si].id))
        return SolveResult(
            status="optimal" if status == cp_model.OPTIMAL else "feasible",
            lessons=lessons,
            stats={
                "wall_time_s": round(solver.WallTime(), 3),
                "load_gap": int(solver.ObjectiveValue()),
                "lessons": len(lessons),
            },
        )

    if status == cp_model.INFEASIBLE:
        bad = solver.SufficientAssumptionsForInfeasibility()
        named = [lit_name[i] for i in bad if i in lit_name]
        reasons = ([f"Conflicting constraint groups: {', '.join(named)}."] if named
                   else ["Constraints conflict in combination (no single group is to blame)."])
        reasons.append("Typical fixes: add teachers/rooms, raise max_hours_per_day, "
                       "or reduce periods_per_week of a subject.")
        return SolveResult(status="infeasible", reasons=reasons,
                           stats={"wall_time_s": round(solver.WallTime(), 3)})

    return SolveResult(status="error",
                       reasons=[f"Solver stopped: {solver.StatusName(status)}"])
