"""OR-Tools CP-SAT timetable model (docs/02-ARCHITECTURE.md, research/03).

Design rule: the LLM never solves the timetable — this model does, deterministically.
The LLM's job is upstream (turn a request into typed constraint rows) and
downstream (explain the outcome).

Hard constraints
  H1  every (section, subject) gets exactly periods_per_week lessons
  H2  a section has at most one lesson per timeslot
  H3  a teacher teaches at most one lesson per timeslot (clash-free), counting
      open-elective duty
  H4  exactly one qualified teacher per (section, subject) — *pinned* to the
      admin's choice when a TeachingAssignment exists
  H5  lab subjects run as one block of consecutive same-day periods in a lab room;
      lab rooms are clash-free
  H6  each section gets a dedicated home classroom with enough capacity
  H7  teacher daily load <= max_hours_per_day (weekly cap optional)
  H8  at most `subject_daily_max` periods of the same subject per day (spread)
  H9  no same-subject back-to-back (theory only, scoped, ON by default)
  H10 optional cap on a teacher's consecutive teaching periods
  H11 open-elective bands: every section of the semester is idle during the band,
      while the group's offerings run in parallel in distinct reserved rooms
  H12 availability bans: a teacher / subject / section is forbidden at given slots

Soft objective
  fairness (weekly-load gap between busiest and idlest teacher)
  + preferred-period misses + mid-day gaps, each weighted

Scope resolution for every scoped rule is **section > semester > global**, which
is what lets one solve produce a genuinely different shape of week per semester.

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
    max_consecutive: int | None = None   # per-teacher override of the global cap
    max_hours_per_week: int | None = None


@dataclass
class SectionIn:
    id: int
    name: str
    strength: int
    subject_ids: list[int]  # regular subjects (elective-band subjects excluded)
    semester: int = 0


@dataclass
class RoomIn:
    id: int
    name: str
    type: str
    capacity: int


@dataclass
class ElectiveOfferingIn:
    """One basket of an elective band — runs in parallel with its siblings."""
    id: int
    subject_id: int
    subject_code: str
    teacher_id: int
    room_id: int


@dataclass
class ElectiveGroupIn:
    id: int
    name: str
    semester: int
    periods_per_week: int
    needs_block: bool
    offerings: list[ElectiveOfferingIn] = field(default_factory=list)


@dataclass
class TimetableInput:
    sections: list[SectionIn]
    subjects: dict[int, SubjectIn]
    teachers: list[TeacherIn]
    rooms: list[RoomIn]
    slots: list[SlotIn]
    # (section_id, subject_id) -> teacher_id, pinned by the admin (H4)
    assignments: dict[tuple[int, int], int] = field(default_factory=dict)
    electives: list[ElectiveGroupIn] = field(default_factory=list)


# ---------- admin-configurable rules ----------

@dataclass
class ScopeRules:
    """Overrides that apply at one scope (a section, or a whole semester).

    Every field is None/empty when that scope says nothing — the next scope up
    then decides (section > semester > global)."""
    half_days: dict[str, int] = field(default_factory=dict)   # {"WED": 4}
    no_same_subject_consecutive: bool | None = None
    max_consecutive_teaching: int | None = None
    subject_daily_max: int | None = None
    max_periods_per_day: int | None = None                    # cap on a section's day


# Kept as an alias: `SectionRules` is the name the Phase 2.3 API/tools import.
SectionRules = ScopeRules


@dataclass
class SlotBan:
    """Forbid one target from being scheduled at the given day/period combos.
    Empty `days` means every day; empty `periods` means every period."""
    target: str                                   # teacher | subject | section
    ref_id: int
    days: list[str] = field(default_factory=list)
    periods: list[int] = field(default_factory=list)
    label: str = ""                               # for messages


@dataclass
class PreferredPeriods:
    """Soft: try to place a subject inside these periods (and days, if given)."""
    subject_id: int
    periods: list[int] = field(default_factory=list)
    days: list[str] = field(default_factory=list)
    weight: int = 1
    label: str = ""


@dataclass
class ElectivePin:
    """Hard: this elective band must occupy exactly these (day, period) slots.

    Any band periods beyond the pinned ones stay free for the solver to place —
    pin two slots of a three-period band and the third still floats."""
    group_id: int
    slots: list[tuple[str, int]] = field(default_factory=list)
    label: str = ""


@dataclass
class SolveOptions:
    """Compiled generation rules. Built from the constraint registry by
    `app/tools/constraints.py` — the API no longer hand-assembles this.

    The top-level fields are the *global* defaults; `semester_rules` and
    `section_rules` override them for a semester or a single class."""
    half_days: dict[str, int] = field(default_factory=dict)
    no_same_subject_consecutive: bool = True                  # H9
    max_consecutive_teaching: int | None = None               # H10
    subject_daily_max: int = 2                                # H8
    max_periods_per_day: int | None = None
    semester_rules: dict[int, ScopeRules] = field(default_factory=dict)  # by semester
    section_rules: dict[int, ScopeRules] = field(default_factory=dict)   # by section_id
    bans: list[SlotBan] = field(default_factory=list)                    # H12
    elective_pins: list[ElectivePin] = field(default_factory=list)       # H11 fixed slots
    preferred: list[PreferredPeriods] = field(default_factory=list)      # soft
    avoid_gaps_weight: int = 0                                           # soft, 0 = off
    # Per-teacher overrides applied to TeacherIn by the input loader, not read by
    # the model itself: {teacher_id: {"teacher_max_daily": 4, ...}}
    teacher_caps: dict[int, dict[str, int]] = field(default_factory=dict)


# ---------- scope resolution ----------

def _resolve(opts: SolveOptions, sec: SectionIn) -> ScopeRules:
    """Effective rules for one section: global <- semester <- section."""
    sem = opts.semester_rules.get(sec.semester)
    own = opts.section_rules.get(sec.id)

    half_days = dict(opts.half_days)
    for src in (sem, own):
        if src and src.half_days:
            half_days.update(src.half_days)

    def pick(attr, default):
        for src in (own, sem):
            if src is not None and getattr(src, attr) is not None:
                return getattr(src, attr)
        return default

    return ScopeRules(
        half_days=half_days,
        no_same_subject_consecutive=pick("no_same_subject_consecutive",
                                         opts.no_same_subject_consecutive),
        max_consecutive_teaching=pick("max_consecutive_teaching",
                                      opts.max_consecutive_teaching),
        subject_daily_max=pick("subject_daily_max", opts.subject_daily_max),
        max_periods_per_day=pick("max_periods_per_day", opts.max_periods_per_day),
    )


def _allowed_indices(data: TimetableInput, rules: ScopeRules) -> set[int]:
    """Slot indices a section may use, after applying its effective half-days."""
    hd = rules.half_days
    return {i for i, s in enumerate(data.slots)
            if not (s.day in hd and s.period_no > hd[s.day])}


def _ban_slots(data: TimetableInput, ban: SlotBan) -> set[int]:
    """Slot indices a ban covers."""
    return {i for i, s in enumerate(data.slots)
            if (not ban.days or s.day in ban.days)
            and (not ban.periods or s.period_no in ban.periods)}


@dataclass
class Lesson:
    section_id: int
    subject_id: int
    teacher_id: int
    room_id: int
    timeslot_id: int


@dataclass
class ElectivePlacement:
    """The band occupies this slot; every section of the semester sits in it."""
    group_id: int
    timeslot_id: int


@dataclass
class SolveResult:
    status: str  # "optimal" | "feasible" | "infeasible" | "error"
    lessons: list[Lesson] = field(default_factory=list)
    electives: list[ElectivePlacement] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)  # infeasibility reasons
    stats: dict = field(default_factory=dict)


# ---------- pre-solve sanity checks (precise, cheap explanations) ----------

def precheck(data: TimetableInput, opts: "SolveOptions | None" = None) -> list[str]:
    opts = opts or SolveOptions()
    reasons: list[str] = []
    elective_rooms = {o.room_id for g in data.electives for o in g.offerings}
    classrooms = [r for r in data.rooms
                  if r.type == "classroom" and r.id not in elective_rooms]
    labs = [r for r in data.rooms if r.type == "lab"]
    pairs = _consecutive_pairs(data.slots)
    teachers_by_id = {t.id: t for t in data.teachers}
    rooms_by_id = {r.id: r for r in data.rooms}

    if not data.sections:
        reasons.append("No sections defined — add sections in Data Setup.")
    if not data.slots:
        reasons.append("No timeslots defined — seed or add the period grid first.")

    # elective bands per semester (their periods come out of every section's week)
    oe_by_sem: dict[int, int] = {}
    for g in data.electives:
        oe_by_sem[g.semester] = oe_by_sem.get(g.semester, 0) + g.periods_per_week

    for sec in data.sections:
        rules = _resolve(opts, sec)
        allowed = _allowed_indices(data, rules)
        # a section-scoped ban shrinks the week further
        for ban in opts.bans:
            if ban.target == "section" and ban.ref_id == sec.id:
                allowed -= _ban_slots(data, ban)
        need = sum(data.subjects[sid].periods_per_week for sid in sec.subject_ids)
        oe = oe_by_sem.get(sec.semester, 0)
        if need + oe > len(allowed):
            extra = f" plus {oe} open-elective period(s)" if oe else ""
            hint = ("its rules leave only" if len(allowed) < len(data.slots) else "only")
            reasons.append(
                f"Section {sec.name} needs {need} periods/week{extra} but {hint} "
                f"{len(allowed)} slots — reduce periods_per_week, add slots, "
                f"or relax its half-days/bans."
            )
        if not sec.subject_ids and not oe:
            reasons.append(f"Section {sec.name} has no subjects for its dept/semester.")
        if rules.max_periods_per_day is not None:
            days = {data.slots[i].day for i in allowed}
            cap = rules.max_periods_per_day * len(days)
            if need + oe > cap:
                reasons.append(
                    f"Section {sec.name} needs {need + oe} periods/week but its "
                    f"'at most {rules.max_periods_per_day} periods per day' rule "
                    f"allows at most {cap} — raise the cap or cut periods."
                )
        # a lab needs at least one consecutive pair fully inside the allowed slots
        for sid in sec.subject_ids:
            if data.subjects[sid].needs_lab and not any(
                    a in allowed and b in allowed for a, b in pairs):
                reasons.append(
                    f"Section {sec.name}'s rules leave no consecutive block for "
                    f"lab {data.subjects[sid].code} — relax its half-days/bans."
                )

    for sid, subj in data.subjects.items():
        qualified = [t for t in data.teachers if sid in t.subject_ids]
        if any(sid in sec.subject_ids for sec in data.sections) and not qualified:
            reasons.append(
                f"No teacher can teach {subj.code} — map at least one teacher to it in Data Setup."
            )

    # pinned teacher assignments must be real and qualified
    sec_by_id = {s.id: s for s in data.sections}
    for (sec_id, sid), t_id in data.assignments.items():
        sec = sec_by_id.get(sec_id)
        if sec is None or sid not in sec.subject_ids:
            continue  # stale pin (subject moved semester / became an elective) — ignored
        t = teachers_by_id.get(t_id)
        code = data.subjects[sid].code
        if t is None:
            reasons.append(f"{sec.name} · {code} is assigned to a teacher that no longer exists.")
        elif sid not in t.subject_ids:
            reasons.append(
                f"{sec.name} · {code} is assigned to {t.name}, who is not mapped to "
                f"{code} — add the subject to that teacher in Data Setup, or change the assignment."
            )

    # a pinned teacher's total pinned load must fit their week (they may be pinned
    # in several semesters at once — that is normal, overload is not)
    days_all = {s.day for s in data.slots}
    pinned_load: dict[int, int] = {}
    for (sec_id, sid), t_id in data.assignments.items():
        sec = sec_by_id.get(sec_id)
        if sec and sid in sec.subject_ids:
            pinned_load[t_id] = pinned_load.get(t_id, 0) + data.subjects[sid].periods_per_week
    for t_id, load in pinned_load.items():
        t = teachers_by_id.get(t_id)
        if not t:
            continue
        cap = min(t.max_hours_per_day * len(days_all),
                  t.max_hours_per_week or 10 ** 6, len(data.slots))
        if load > cap:
            reasons.append(
                f"{t.name} is assigned {load} periods/week across all sections but can "
                f"teach at most {cap} — reassign a subject or raise their limits."
            )

    # elective bands
    for g in data.electives:
        secs = [s for s in data.sections if s.semester == g.semester]
        if not secs:
            reasons.append(
                f"Elective band {g.name} targets semester {g.semester}, which has no sections.")
        if not g.offerings:
            reasons.append(f"Elective band {g.name} has no offerings — add at least one subject.")
        seen_rooms, seen_teachers = set(), set()
        for o in g.offerings:
            t = teachers_by_id.get(o.teacher_id)
            if t is None:
                reasons.append(f"{g.name} · {o.subject_code} has no valid teacher.")
            elif o.subject_id not in t.subject_ids:
                reasons.append(
                    f"{g.name} · {o.subject_code} is taught by {t.name}, who is not mapped "
                    f"to that subject — fix the teacher-subject map in Data Setup.")
            if o.room_id in seen_rooms:
                reasons.append(
                    f"{g.name}: two offerings share room "
                    f"{rooms_by_id.get(o.room_id).name if o.room_id in rooms_by_id else o.room_id} "
                    f"— parallel baskets need distinct rooms.")
            if o.teacher_id in seen_teachers:
                reasons.append(f"{g.name}: one teacher is listed for two parallel offerings.")
            seen_rooms.add(o.room_id)
            seen_teachers.add(o.teacher_id)
        if g.needs_block and g.periods_per_week < 2:
            reasons.append(f"Elective band {g.name} asks for a consecutive block but is only "
                           f"{g.periods_per_week} period long.")
        # fixed slots must fit the band, exist in the grid, and survive half-days
        real_slots = {(s.day, s.period_no) for s in data.slots}
        for pin in opts.elective_pins:
            if pin.group_id != g.id:
                continue
            if len(pin.slots) > g.periods_per_week:
                reasons.append(
                    f"{g.name} is fixed to {len(pin.slots)} slot(s) but runs only "
                    f"{g.periods_per_week} period(s)/week — raise the band's periods "
                    f"per week or pin fewer slots.")
            missing = [f"{d}-P{p}" for d, p in pin.slots if (d, p) not in real_slots]
            if missing:
                reasons.append(
                    f"{g.name} is fixed to {', '.join(missing)}, which the period grid "
                    f"does not have.")
            for sec in secs:
                blocked = [f"{d}-P{p}" for d, p in pin.slots
                           if not any(data.slots[i].day == d and data.slots[i].period_no == p
                                      for i in _allowed_indices(data, _resolve(opts, sec)))]
                if blocked:
                    reasons.append(
                        f"{g.name} is fixed to {', '.join(sorted(set(blocked)))}, but "
                        f"{sec.name} does not teach then (its half-day rules) — the whole "
                        f"semester must be free for the band.")
                    break

    if len(classrooms) < len(data.sections):
        taken = len({r for r in elective_rooms
                     if r in rooms_by_id and rooms_by_id[r].type == "classroom"})
        note = (f" ({taken} classroom(s) are reserved for elective baskets)" if taken else "")
        reasons.append(
            f"{len(data.sections)} sections need dedicated classrooms but only "
            f"{len(classrooms)} are available{note} — add rooms of type 'classroom'."
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
    demand += sum(g.periods_per_week * len(g.offerings) for g in data.electives)
    supply = sum(min(t.max_hours_per_day * len(days_all),
                     t.max_hours_per_week or 10 ** 6) for t in data.teachers)
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
    electives = [g for g in data.electives
                 if any(s.semester == g.semester for s in data.sections)]
    elective_rooms = {o.room_id for g in electives for o in g.offerings}
    # A room hosting an elective basket is reserved for it and leaves the
    # home-classroom pool, so no section can own it (precheck guards the count).
    classrooms = [r for r in data.rooms
                  if r.type == "classroom" and r.id not in elective_rooms]
    labs = [r for r in data.rooms if r.type == "lab"]

    rules = {sec.id: _resolve(opts, sec) for sec in data.sections}
    allowed = {sec.id: _allowed_indices(data, rules[sec.id]) for sec in data.sections}

    # H12 bans, indexed by target
    banned_slots_teacher: dict[int, set[int]] = {}
    banned_slots_subject: dict[int, set[int]] = {}
    banned_slots_section: dict[int, set[int]] = {}
    for ban in opts.bans:
        bucket = {"teacher": banned_slots_teacher, "subject": banned_slots_subject,
                  "section": banned_slots_section}.get(ban.target)
        if bucket is not None:
            bucket.setdefault(ban.ref_id, set()).update(_ban_slots(data, ban))
    for sec_id, banned in banned_slots_section.items():
        if sec_id in allowed:
            allowed[sec_id] -= banned

    any_nosc = any(rules[sec.id].no_same_subject_consecutive for sec in data.sections)
    any_run_cap = (opts.max_consecutive_teaching is not None
                   or any(r.max_consecutive_teaching is not None for r in rules.values())
                   or any(t.max_consecutive is not None for t in data.teachers))

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
    if any_run_cap:
        groups["teacher consecutive-teaching cap"] = m.NewBoolVar("g_teachrun")
    if data.assignments:
        groups["pinned teacher assignments"] = m.NewBoolVar("g_pin")
    if electives:
        groups["open-elective bands"] = m.NewBoolVar("g_oe")
    if opts.bans:
        groups["availability bans (teacher/subject/class)"] = m.NewBoolVar("g_ban")
    if any(r.max_periods_per_day is not None for r in rules.values()):
        groups["per-day period caps"] = m.NewBoolVar("g_daycap")
    m.AddAssumptions(list(groups.values()))
    lit_name = {v.Index(): k for k, v in groups.items()}

    # H4: teacher choice per (section, subject) — pinned when the admin assigned one
    y: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for sec in data.sections:
        for sid in sec.subject_ids:
            elig = [t for t in data.teachers if sid in t.subject_ids]
            lits = []
            for t in elig:
                y[(sec.id, sid, t.id)] = m.NewBoolVar(f"y_{sec.id}_{sid}_{t.id}")
                lits.append(y[(sec.id, sid, t.id)])
            m.AddExactlyOne(lits)
            pinned = data.assignments.get((sec.id, sid))
            if pinned is not None and (sec.id, sid, pinned) in y:
                # H11: honour the admin's choice exactly; unassigned pairs stay free.
                m.Add(y[(sec.id, sid, pinned)] == 1)\
                    .OnlyEnforceIf(groups["pinned teacher assignments"])

    # lesson placement x[(sec,subj,slot)]
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for sec in data.sections:
        sec_allowed = allowed[sec.id]
        r = rules[sec.id]
        for sid in sec.subject_ids:
            subj = data.subjects[sid]
            subj_banned = banned_slots_subject.get(sid, set())
            for si in range(n_slots):
                x[(sec.id, sid, si)] = m.NewBoolVar(f"x_{sec.id}_{sid}_{si}")
                # slots this section may not use (half-days, section bans) are pinned off
                if si not in sec_allowed:
                    m.Add(x[(sec.id, sid, si)] == 0)
                elif si in subj_banned:
                    m.Add(x[(sec.id, sid, si)] == 0)\
                        .OnlyEnforceIf(groups["availability bans (teacher/subject/class)"])
            # H1: exact weekly period count
            m.Add(sum(x[(sec.id, sid, si)] for si in range(n_slots))
                  == subj.periods_per_week)

            # H8: spread — at most N periods of one subject per day. Applies to
            # labs too so a lab's extra periods can't stack a 3rd next to the block.
            cap = max(r.subject_daily_max or 2, 2 if subj.needs_lab else 1)
            for d in days:
                m.Add(sum(x[(sec.id, sid, si)] for si in slots_of_day[d]) <= cap)\
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
            elif r.no_same_subject_consecutive:
                # H9: no same-subject back-to-back (per section) — theory only
                for a, b in pairs:
                    m.Add(x[(sec.id, sid, a)] + x[(sec.id, sid, b)] <= 1)\
                        .OnlyEnforceIf(groups["no same-subject back-to-back"])

    # H11: open-elective bands — one set of slots per band, shared by the semester
    gv: dict[tuple[int, int], cp_model.IntVar] = {}
    for g in electives:
        sem_secs = [s for s in data.sections if s.semester == g.semester]
        # the band may only sit where *every* section of the semester is available
        band_allowed = set(range(n_slots))
        for s in sem_secs:
            band_allowed &= allowed[s.id]
        for si in range(n_slots):
            gv[(g.id, si)] = m.NewBoolVar(f"g_{g.id}_{si}")
            if si not in band_allowed:
                m.Add(gv[(g.id, si)] == 0)
            else:
                # a banned teacher in any basket blocks the whole band at that slot
                if any(si in banned_slots_teacher.get(o.teacher_id, set())
                       for o in g.offerings):
                    m.Add(gv[(g.id, si)] == 0)\
                        .OnlyEnforceIf(groups["availability bans (teacher/subject/class)"])
        m.Add(sum(gv[(g.id, si)] for si in range(n_slots)) == g.periods_per_week)\
            .OnlyEnforceIf(groups["open-elective bands"])
        if g.needs_block:
            blk = []
            for pi, (a, b) in enumerate(pairs):
                bv = m.NewBoolVar(f"gb_{g.id}_{pi}")
                blk.append(bv)
                m.Add(gv[(g.id, a)] == 1).OnlyEnforceIf(bv)
                m.Add(gv[(g.id, b)] == 1).OnlyEnforceIf(bv)
            m.AddAtLeastOne(blk).OnlyEnforceIf(groups["open-elective bands"])

        # the admin may nail the band to specific slots ("sem 7 open elective is
        # MON P3 and TUE P3"); any remaining band periods still float
        for pin in opts.elective_pins:
            if pin.group_id != g.id:
                continue
            for si, s in enumerate(slots):
                if (s.day, s.period_no) in pin.slots:
                    m.Add(gv[(g.id, si)] == 1)\
                        .OnlyEnforceIf(groups["open-elective bands"])

    # H2: section clash-free — a section is *busy* during its semester's bands
    band_of_section: dict[int, list[int]] = {}
    for sec in data.sections:
        band_of_section[sec.id] = [g.id for g in electives if g.semester == sec.semester]
    for sec in data.sections:
        for si in range(n_slots):
            terms = [x[(sec.id, sid, si)] for sid in sec.subject_ids]
            terms += [gv[(gid, si)] for gid in band_of_section[sec.id]]
            if terms:
                m.Add(sum(terms) <= 1)

    # per-day period cap for a section (e.g. "sem 3 has at most 5 classes a day")
    for sec in data.sections:
        cap = rules[sec.id].max_periods_per_day
        if cap is None:
            continue
        for d in days:
            terms = [x[(sec.id, sid, si)] for sid in sec.subject_ids for si in slots_of_day[d]]
            terms += [gv[(gid, si)] for gid in band_of_section[sec.id] for si in slots_of_day[d]]
            if terms:
                m.Add(sum(terms) <= cap).OnlyEnforceIf(groups["per-day period caps"])

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

    # every teacher's busy terms per slot: regular lessons + elective duty
    busy: dict[int, dict[int, list]] = {t.id: {} for t in data.teachers}
    for key, var in w.items():
        busy.setdefault(key[2], {}).setdefault(key[3], []).append(var)
    for g in electives:
        for o in g.offerings:
            for si in range(n_slots):
                busy.setdefault(o.teacher_id, {}).setdefault(si, []).append(gv[(g.id, si)])

    # H3: teacher clash-free + H7 daily/weekly limits + H12 teacher bans
    for t in data.teachers:
        slot_terms = busy.get(t.id, {})
        t_banned = banned_slots_teacher.get(t.id, set())
        for si in range(n_slots):
            at_slot = slot_terms.get(si, [])
            if not at_slot:
                continue
            if si in t_banned:
                m.Add(sum(at_slot) == 0)\
                    .OnlyEnforceIf(groups["availability bans (teacher/subject/class)"])
            else:
                m.Add(sum(at_slot) <= 1)\
                    .OnlyEnforceIf(groups["teacher availability (clash-free teaching)"])
        for d in days:
            in_day = [v for si in slots_of_day[d] for v in slot_terms.get(si, [])]
            if in_day:
                m.Add(sum(in_day) <= t.max_hours_per_day)\
                    .OnlyEnforceIf(groups["teacher daily hour limits"])
        if t.max_hours_per_week is not None:
            week = [v for terms in slot_terms.values() for v in terms]
            if week:
                m.Add(sum(week) <= t.max_hours_per_week)\
                    .OnlyEnforceIf(groups["teacher daily hour limits"])

    # H10: cap consecutive teaching periods per teacher. In every window of k+1
    # time-adjacent slots, the teacher teaches at most k of them. The cap is the
    # teacher's own override, else the tightest cap any of their classes imposes.
    if any_run_cap:
        runs = _consecutive_runs(slots)
        # which sections each teacher can end up in — used to derive their cap
        sections_of_teacher: dict[int, set[int]] = {}
        for (sec_id, sid, t_id) in y:
            sections_of_teacher.setdefault(t_id, set()).add(sec_id)
        for t in data.teachers:
            caps = [c for c in
                    [t.max_consecutive] +
                    [rules[s].max_consecutive_teaching
                     for s in sections_of_teacher.get(t.id, set())]
                    if c is not None]
            if not caps:
                continue
            k = min(caps)
            slot_terms = busy.get(t.id, {})
            for run in runs:
                for start in range(len(run) - k):
                    window = run[start:start + k + 1]
                    terms = [v for si in window for v in slot_terms.get(si, [])]
                    if terms:
                        m.Add(sum(terms) <= k)\
                            .OnlyEnforceIf(groups["teacher consecutive-teaching cap"])

    # H6: dedicated home classroom per section (capacity-checked, distinct)
    c: dict[tuple[int, int], cp_model.IntVar] = {}
    for sec in data.sections:
        choices = []
        for r in classrooms:
            if r.capacity >= sec.strength:
                c[(sec.id, r.id)] = m.NewBoolVar(f"c_{sec.id}_{r.id}")
                choices.append(c[(sec.id, r.id)])
        if not choices:
            return SolveResult(status="infeasible", reasons=[
                f"No classroom has capacity >= {sec.strength} for section {sec.name} "
                f"(rooms reserved for elective baskets are excluded)."])
        m.AddExactlyOne(choices).OnlyEnforceIf(groups["home classroom allocation"])
    for r in classrooms:
        owners = [c[k] for k in c if k[1] == r.id]
        if owners:
            m.Add(sum(owners) <= 1).OnlyEnforceIf(groups["home classroom allocation"])

    # H5b: lab-room choice per lab subject occurrence + lab-room clash-free
    lr: dict[tuple[int, int, int], cp_model.IntVar] = {}
    lab_keys = [(sec, sid) for sec in data.sections for sid in sec.subject_ids
                if data.subjects[sid].needs_lab]
    for sec, sid in lab_keys:
        choices = []
        for r in labs:
            lr[(sec.id, sid, r.id)] = m.NewBoolVar(f"lr_{sec.id}_{sid}_{r.id}")
            choices.append(lr[(sec.id, sid, r.id)])
        m.AddExactlyOne(choices)
    for r in labs:
        # elective baskets sitting in this lab occupy it for the whole band
        oe_here = [g.id for g in electives
                   if any(o.room_id == r.id for o in g.offerings)]
        for si in range(n_slots):
            using = []
            for sec, sid in lab_keys:
                u = m.NewBoolVar(f"u_{sec.id}_{sid}_{r.id}_{si}")
                m.AddBoolOr([x[(sec.id, sid, si)].Not(),
                             lr[(sec.id, sid, r.id)].Not(), u])
                m.AddImplication(u, x[(sec.id, sid, si)])
                m.AddImplication(u, lr[(sec.id, sid, r.id)])
                using.append(u)
            using += [gv[(gid, si)] for gid in oe_here]
            if using:
                m.Add(sum(using) <= 1)\
                    .OnlyEnforceIf(groups["lab consecutive-block scheduling"])

    # Two bands must not overlap when they share a room or a teacher.
    for i, g1 in enumerate(electives):
        for g2 in electives[i + 1:]:
            shares = ({o.room_id for o in g1.offerings} & {o.room_id for o in g2.offerings}) or \
                     ({o.teacher_id for o in g1.offerings} & {o.teacher_id for o in g2.offerings})
            if shares:
                for si in range(n_slots):
                    m.Add(gv[(g1.id, si)] + gv[(g2.id, si)] <= 1)\
                        .OnlyEnforceIf(groups["open-elective bands"])

    # ---------- objective: fairness + soft preferences ----------
    obj_terms = []

    loads = []
    for t in data.teachers:
        terms = [v for tv in busy.get(t.id, {}).values() for v in tv]
        lv = m.NewIntVar(0, n_slots, f"load_{t.id}")
        m.Add(lv == sum(terms) if terms else lv == 0)
        loads.append(lv)
    max_l = m.NewIntVar(0, n_slots, "max_load")
    min_l = m.NewIntVar(0, n_slots, "min_load")
    m.AddMaxEquality(max_l, loads)
    m.AddMinEquality(min_l, loads)
    load_gap = m.NewIntVar(0, n_slots, "load_gap")
    m.Add(load_gap == max_l - min_l)
    obj_terms.append(load_gap)

    # soft: subject placed outside its preferred periods/days
    for pref in opts.preferred:
        off = []
        for sec in data.sections:
            if pref.subject_id not in sec.subject_ids:
                continue
            for si, s in enumerate(slots):
                ok = ((not pref.periods or s.period_no in pref.periods)
                      and (not pref.days or s.day in pref.days))
                if not ok:
                    off.append(x[(sec.id, pref.subject_id, si)])
        if off:
            obj_terms.append(max(1, pref.weight) * sum(off))

    # Soft: idle periods *inside* a section's teaching day — a free period that
    # has some class earlier and some class later that day. Counting only the
    # immediate neighbours would miss a two-period hole, so this uses running
    # prefix/suffix "is busy" flags, which is exact for a gap of any length.
    if opts.avoid_gaps_weight > 0:
        gap_vars = []
        for sec in data.sections:
            for d in days:
                idx = sorted(slots_of_day[d], key=lambda i: slots[i].period_no)
                idx = [i for i in idx if i in allowed[sec.id]]
                if len(idx) < 3:
                    continue
                occ = {}
                for si in idx:
                    ov = m.NewBoolVar(f"occ_{sec.id}_{si}")
                    terms = [x[(sec.id, sid, si)] for sid in sec.subject_ids]
                    terms += [gv[(gid, si)] for gid in band_of_section[sec.id]]
                    # the section clash constraint already caps this sum at 1
                    m.Add(ov == sum(terms)) if terms else m.Add(ov == 0)
                    occ[si] = ov

                # before[k] = a class happens at or before k; after[k] = at or after k
                before: dict[int, cp_model.IntVar] = {}
                prev = None
                for si in idx:
                    bv = m.NewBoolVar(f"bef_{sec.id}_{si}")
                    m.AddMaxEquality(bv, [occ[si]] if prev is None else [prev, occ[si]])
                    before[si] = bv
                    prev = bv
                after: dict[int, cp_model.IntVar] = {}
                nxt = None
                for si in reversed(idx):
                    av = m.NewBoolVar(f"aft_{sec.id}_{si}")
                    m.AddMaxEquality(av, [occ[si]] if nxt is None else [nxt, occ[si]])
                    after[si] = av
                    nxt = av

                for si in idx[1:-1]:
                    gp = m.NewBoolVar(f"gap_{sec.id}_{si}")
                    # idle, yet the day is already running and not yet over
                    m.Add(gp >= before[si] + after[si] - occ[si] - 1)
                    gap_vars.append(gp)
        if gap_vars:
            obj_terms.append(opts.avoid_gaps_weight * sum(gap_vars))

    m.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 8
    status = solver.Solve(m)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        lessons: list[Lesson] = []
        for sec in data.sections:
            home = next((r.id for r in classrooms
                         if (sec.id, r.id) in c and solver.Value(c[(sec.id, r.id)])), None)
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
        placements = [ElectivePlacement(g.id, slots[si].id)
                      for g in electives for si in range(n_slots)
                      if solver.Value(gv[(g.id, si)])]
        return SolveResult(
            status="optimal" if status == cp_model.OPTIMAL else "feasible",
            lessons=lessons,
            electives=placements,
            stats={
                "wall_time_s": round(solver.WallTime(), 3),
                "load_gap": int(solver.Value(load_gap)),
                "objective": int(solver.ObjectiveValue()),
                "lessons": len(lessons),
                "elective_periods": len(placements),
            },
        )

    if status == cp_model.INFEASIBLE:
        bad = solver.SufficientAssumptionsForInfeasibility()
        named = [lit_name[i] for i in bad if i in lit_name]
        reasons = ([f"Conflicting constraint groups: {', '.join(named)}."] if named
                   else ["Constraints conflict in combination (no single group is to blame)."])
        reasons.append("Typical fixes: relax or disable a constraint on the Constraints page, "
                       "add teachers/rooms, raise max_hours_per_day, or reduce periods_per_week.")
        return SolveResult(status="infeasible", reasons=reasons,
                           stats={"wall_time_s": round(solver.WallTime(), 3)})

    return SolveResult(status="error",
                       reasons=[f"Solver stopped: {solver.StatusName(status)}"])
