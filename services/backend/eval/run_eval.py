"""Agent evaluation harness — produces every number in docs/12-AGENT-EVALUATION-RESULTS.md.

Runs against a *throwaway copy* of campus.db (and a throwaway checkpoint DB), so
the real data is never touched. Results land in docs/evaluation/results/;
docs/evaluation/make_figures.py turns them into figures and tables.

    cd services/backend
    venv/Scripts/python eval/run_eval.py              # deterministic experiments
    venv/Scripts/python eval/run_eval.py --llm        # + live-LLM routing / assistant
    venv/Scripts/python eval/run_eval.py --only solver,scale

Experiments
  E1 routing      Supervisor: keyword router (and LLM router with --llm) on 100 labelled queries
  E2 solver       Timetable Agent: cold vs warm solves, independent H1–H12 verification, churn
  E3 scale        Timetable Agent: synthetic scaling (sections x1..x5)
  E4 infeasible   Timetable Agent: infeasibility diagnosis on 10 broken instances
  E5 exchange     Substitution Agent: every teacher x every weekday + multi-day leaves,
                  vs the legacy stand-in substitution planner
  E6 hitl         Substitution Agent: interrupt -> simulated restart -> resume; notifications
  E7 sweep        Safety-sweep sentinel: detection, idempotency
  E8 registry     Constraint registry validator (30 cases) + compile time
  E9 assistant    Timetable Assistant op compiler (20 plans), bulk-form payload size,
                  and NL -> plan with the LLM (--llm)
  E10 facility    Facility Agent venue resolution (20 queries); Scheduler / General latency
  E11 degrade     Graceful degradation: LLM forced to fail -> every query still answered
"""
import argparse
import json
import os
import platform
import shutil
import statistics as st
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
OUT = REPO / "docs" / "evaluation" / "results"

# ---- isolate: every experiment runs on a copy of the database ---------------
_TMP = Path(tempfile.mkdtemp(prefix="campus_eval_"))
shutil.copy(BACKEND / "campus.db", _TMP / "campus.db")
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'campus.db').as_posix()}"
os.environ["CHECKPOINT_DB"] = str(_TMP / "checkpoints.db")
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.db import models as M  # noqa: E402

init_db()

import datasets as D  # noqa: E402

RESULTS: dict = {}


def ms(seconds: float) -> float:
    return round(seconds * 1000, 3)


def summarise(xs: list[float]) -> dict:
    xs = sorted(xs)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]  # noqa: E731
    return {"n": len(xs), "mean": round(st.mean(xs), 3), "median": round(st.median(xs), 3),
            "p25": round(q(0.25), 3), "p75": round(q(0.75), 3), "p95": round(q(0.95), 3),
            "min": round(xs[0], 3), "max": round(xs[-1], 3),
            "stdev": round(st.stdev(xs), 3) if len(xs) > 1 else 0.0}


def prf(gold: list[str], pred: list[str], labels: list[str]) -> dict:
    """Accuracy, per-class precision/recall/F1, macro-F1, confusion matrix."""
    per = {}
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
        per[lab] = {"precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4),
                    "support": sum(1 for g in gold if g == lab)}
    conf = [[sum(1 for g, p in zip(gold, pred) if g == a and p == b) for b in labels] for a in labels]
    return {"accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 4),
            "macro_f1": round(st.mean(v["f1"] for v in per.values()), 4),
            "per_class": per, "labels": labels, "confusion": conf}


ROUTES = ["timetable", "substitution", "scheduler", "facility", "general"]


# =============================================================================
# E1 — Supervisor routing
# =============================================================================

def e1_routing(use_llm: bool) -> None:
    from app.agents import supervisor as sup

    gold = [lab for _, lab in D.ROUTING]
    queries = [q for q, _ in D.ROUTING]

    # keyword router (the degradation path) — deterministic, timed per query
    preds, lat = [], []
    for q in queries:
        t0 = time.perf_counter()
        route, _ = sup._keyword_fallback(q)
        lat.append(ms(time.perf_counter() - t0))
        preds.append(route)
    out = {"keyword": {**prf(gold, preds, ROUTES), "latency_ms": summarise(lat),
                       "predictions": preds}}

    # system-trigger short-circuit: supervisor_node with source=system
    lat = []
    for i in range(200):
        state = {"messages": [{"role": "user", "content": f"Plan substitutions for approved leave #{i}"}],
                 "source": "system", "task_spec": {"leave_id": i}}
        t0 = time.perf_counter()
        r = sup.supervisor_node(state)
        lat.append(ms(time.perf_counter() - t0))
        assert r["current_action"] == "substitution"
    out["system_bypass"] = {"latency_ms": summarise(lat), "correct": 200, "n": 200}

    if use_llm:
        from app.core.config import settings
        from app.core.llm import is_llm_configured
        if not is_llm_configured():
            out["llm"] = {"skipped": "no LLM key configured"}
        else:
            preds, lat, fell_back, errors = [], [], 0, []
            for q in queries:
                for attempt in range(4):
                    t0 = time.perf_counter()
                    r = sup.supervisor_node({"messages": [{"role": "user", "content": q}]})
                    dt = time.perf_counter() - t0
                    step = r["steps"][-1]
                    if "LLM unavailable" in step and attempt < 3:
                        time.sleep(8 * (attempt + 1))      # rate limit — back off and retry
                        continue
                    break
                if "LLM unavailable" in step:
                    fell_back += 1
                    errors.append(step)
                else:
                    lat.append(ms(dt))
                preds.append(r["current_action"])
                time.sleep(0.5)
            out["llm"] = {**prf(gold, preds, ROUTES), "latency_ms": summarise(lat),
                          "predictions": preds, "fell_back_to_keyword": fell_back,
                          "errors": errors[:5],
                          "model": f"{settings.LLM_PROVIDER}/{settings.LLM_MODEL}"}
    out["queries"] = queries
    out["gold"] = gold
    RESULTS["routing"] = out
    print(f"[E1] keyword acc={out['keyword']['accuracy']}  macroF1={out['keyword']['macro_f1']}"
          + (f" | llm acc={out['llm'].get('accuracy')}" if use_llm and 'llm' in out else ""))


# =============================================================================
# Independent verifier for solver output (does NOT reuse solver code paths
# except the scope resolver, which defines what the rules *mean*)
# =============================================================================

def verify(data, opts, res) -> dict:
    from app.solver.timetable_model import _resolve, _consecutive_pairs, _consecutive_runs, _ban_slots

    slots = data.slots
    sidx = {s.id: i for i, s in enumerate(slots)}
    subj = data.subjects
    teachers = {t.id: t for t in data.teachers}
    rooms = {r.id: r for r in data.rooms}
    secs = {s.id: s for s in data.sections}
    rules = {s.id: _resolve(opts, s) for s in data.sections}
    pairs = set(_consecutive_pairs(slots))
    groups = {g.id: g for g in data.electives}
    viol: dict[str, int] = defaultdict(int)

    L = res.lessons
    band_slots = defaultdict(set)                      # group -> slot idx
    for p in res.electives:
        band_slots[p.group_id].add(sidx[p.timeslot_id])
    sem_band_slots = defaultdict(set)
    for gid, ss in band_slots.items():
        sem_band_slots[groups[gid].semester] |= ss

    # H1 exact weekly demand
    cnt = Counter((l.section_id, l.subject_id) for l in L)
    for s in data.sections:
        for sid in s.subject_ids:
            if cnt[(s.id, sid)] != subj[sid].periods_per_week:
                viol["H1 weekly demand"] += 1
    # H2 section clash (incl. bands)
    sec_slot = Counter((l.section_id, sidx[l.timeslot_id]) for l in L)
    for (sec_id, si), n in sec_slot.items():
        if n + (1 if si in sem_band_slots.get(secs[sec_id].semester, set()) else 0) > 1:
            viol["H2 section clash"] += 1
    # H3 teacher clash (incl. elective duty)
    t_slot = Counter((l.teacher_id, sidx[l.timeslot_id]) for l in L)
    for gid, ss in band_slots.items():
        for o in groups[gid].offerings:
            for si in ss:
                t_slot[(o.teacher_id, si)] += 1
    viol["H3 teacher clash"] += sum(1 for n in t_slot.values() if n > 1)
    # H4 one qualified teacher per (section, subject); pins honoured
    tchoice = defaultdict(set)
    for l in L:
        tchoice[(l.section_id, l.subject_id)].add(l.teacher_id)
    for k, ts in tchoice.items():
        if len(ts) != 1:
            viol["H4 single teacher"] += 1
        t = next(iter(ts))
        if k[1] not in teachers[t].subject_ids:
            viol["H4 qualification"] += 1
        if k in data.assignments and data.assignments[k] != t:
            viol["H4 pinned teacher"] += 1
    # H5 labs: lab room, one consecutive same-day pair
    by_ss = defaultdict(list)
    for l in L:
        by_ss[(l.section_id, l.subject_id)].append(l)
    for (sec_id, sid), ls in by_ss.items():
        if not subj[sid].needs_lab:
            continue
        if any(rooms[l.room_id].type != "lab" for l in ls):
            viol["H5 lab room"] += 1
        idx = sorted(sidx[l.timeslot_id] for l in ls)
        if not any((a, b) in pairs for a in idx for b in idx):
            viol["H5 lab block"] += 1
    # room clash (labs + home rooms) and elective rooms reserved during bands
    r_slot = Counter((l.room_id, sidx[l.timeslot_id]) for l in L)
    viol["H5/H6 room clash"] += sum(1 for n in r_slot.values() if n > 1)
    for gid, ss in band_slots.items():
        for o in groups[gid].offerings:
            for si in ss:
                if r_slot.get((o.room_id, si)):
                    viol["H11 elective room taken"] += 1
    # H6 dedicated home classroom with capacity
    home = {}
    for sec_id in secs:
        th = {l.room_id for l in L if l.section_id == sec_id and not subj[l.subject_id].needs_lab}
        if len(th) > 1:
            viol["H6 one home room"] += 1
        if th:
            r = rooms[next(iter(th))]
            home[sec_id] = r.id
            if r.type != "classroom" or r.capacity < secs[sec_id].strength:
                viol["H6 room capacity/type"] += 1
    if len(set(home.values())) != len(home):
        viol["H6 shared home room"] += 1
    # H7 daily + weekly teacher load (elective duty counts)
    t_day = Counter()
    for (t, si), n in t_slot.items():
        t_day[(t, slots[si].day)] += n
    for (t, d), n in t_day.items():
        if n > teachers[t].max_hours_per_day:
            viol["H7 daily load"] += 1
    t_week = Counter()
    for (t, si), n in t_slot.items():
        t_week[t] += n
    for t, n in t_week.items():
        if teachers[t].max_hours_per_week is not None and n > teachers[t].max_hours_per_week:
            viol["H7 weekly load"] += 1
    # H8 subject daily spread, H9 no back-to-back theory, half-days, per-day caps
    for (sec_id, sid), ls in by_ss.items():
        r = rules[sec_id]
        cap = max(r.subject_daily_max or 2, 2 if subj[sid].needs_lab else 1)
        per_day = Counter(slots[sidx[l.timeslot_id]].day for l in ls)
        viol["H8 daily spread"] += sum(1 for n in per_day.values() if n > cap)
        if not subj[sid].needs_lab and r.no_same_subject_consecutive:
            idx = {sidx[l.timeslot_id] for l in ls}
            viol["H9 back-to-back"] += sum(1 for a, b in pairs if a in idx and b in idx)
    for l in L:
        s = slots[sidx[l.timeslot_id]]
        hd = rules[l.section_id].half_days
        if s.day in hd and s.period_no > hd[s.day]:
            viol["half-day respected"] += 1
    for sec_id, sec in secs.items():
        cap = rules[sec_id].max_periods_per_day
        if cap is None:
            continue
        per_day = Counter(slots[sidx[l.timeslot_id]].day for l in L if l.section_id == sec_id)
        for si in sem_band_slots.get(sec.semester, set()):
            per_day[slots[si].day] += 1
        viol["per-day period cap"] += sum(1 for n in per_day.values() if n > cap)
    # H10 consecutive-teaching cap
    runs = _consecutive_runs(slots)
    elig_secs = defaultdict(set)
    for s in data.sections:
        for sid in s.subject_ids:
            for t in data.teachers:
                if sid in t.subject_ids:
                    elig_secs[t.id].add(s.id)
    for t in data.teachers:
        caps = [c for c in [t.max_consecutive] + [rules[s].max_consecutive_teaching for s in elig_secs[t.id]]
                if c is not None]
        if not caps:
            continue
        k = min(caps)
        for run in runs:
            streak = 0
            for si in run:
                streak = streak + 1 if t_slot.get((t.id, si)) else 0
                if streak > k:
                    viol["H10 consecutive cap"] += 1
    # H11 bands: right count, every semester section idle, pins honoured
    for gid, g in groups.items():
        if not any(s.semester == g.semester for s in data.sections):
            continue
        if len(band_slots[gid]) != g.periods_per_week:
            viol["H11 band periods"] += 1
    for pin in opts.elective_pins:
        for si, s in enumerate(slots):
            if (s.day, s.period_no) in pin.slots and si not in band_slots.get(pin.group_id, set()):
                viol["H11 pinned slot"] += 1
    # H12 bans
    for ban in opts.bans:
        banned = _ban_slots(data, ban)
        for l in L:
            si = sidx[l.timeslot_id]
            if si in banned and ((ban.target == "teacher" and l.teacher_id == ban.ref_id)
                                 or (ban.target == "subject" and l.subject_id == ban.ref_id)
                                 or (ban.target == "section" and l.section_id == ban.ref_id)):
                viol["H12 availability ban"] += 1

    checks = ["H1 weekly demand", "H2 section clash", "H3 teacher clash", "H4 single teacher",
              "H4 qualification", "H4 pinned teacher", "H5 lab room", "H5 lab block", "H5/H6 room clash",
              "H6 one home room", "H6 room capacity/type", "H6 shared home room", "H7 daily load",
              "H7 weekly load", "H8 daily spread", "H9 back-to-back", "half-day respected",
              "per-day period cap", "H10 consecutive cap", "H11 band periods", "H11 pinned slot",
              "H11 elective room taken", "H12 availability ban"]
    return {"checks": len(checks), "passed": sum(1 for c in checks if viol.get(c, 0) == 0),
            "violations": {c: viol.get(c, 0) for c in checks}}


def _load():
    from app.tools.timetable import current_options, load_timetable_input, load_previous_solution
    db = SessionLocal()
    try:
        opts = current_options(db)
        data = load_timetable_input(db, opts)
        prev = load_previous_solution(db)
    finally:
        db.close()
    return data, opts, prev


def _moved(prev, res) -> int:
    now = {(l.section_id, l.subject_id, l.timeslot_id) for l in res.lessons}
    return len(prev.lessons - now)


def _solve(data, opts, prev, limit):
    from app.solver.timetable_model import solve
    o = deepcopy(opts)
    o.previous = prev
    t0 = time.perf_counter()
    r = solve(data, opts=o, time_limit_s=limit)
    return r, time.perf_counter() - t0


# =============================================================================
# E2 — Timetable solver on the real campus instance
# =============================================================================

def e2_solver(runs: int) -> None:
    from app.solver.timetable_model import SubjectIn, SlotBan
    data, opts, prev = _load()
    out = {"instance": {
        "sections": len(data.sections), "teachers": len(data.teachers), "rooms": len(data.rooms),
        "slots": len(data.slots), "subjects": len(data.subjects),
        "lessons_demanded": sum(data.subjects[s].periods_per_week for sec in data.sections for s in sec.subject_ids),
        "elective_bands": len(data.electives), "pins": len(data.assignments),
        "rules_enabled": None}}
    db = SessionLocal()
    out["instance"]["rules_enabled"] = db.query(M.Constraint).filter(M.Constraint.enabled.is_(True)).count()
    db.close()

    modes = {}
    # production setting: 8 s limit (generate_timetable default); cold vs warm-preserve
    for mode, p in [("cold", None), ("warm", prev)]:
        rows = []
        for i in range(runs):
            r, wall = _solve(data, opts, p, 8.0)
            v = verify(data, opts, r) if r.status in ("optimal", "feasible") else None
            rows.append({"run": i, "status": r.status, "wall_s": round(wall, 3),
                         "solver_s": r.stats.get("wall_time_s"), "objective": r.stats.get("objective"),
                         "load_gap": r.stats.get("load_gap"), "lessons": r.stats.get("lessons"),
                         "moved_vs_published": _moved(prev, r) if prev and r.lessons else None,
                         "verify": v})
            print(f"[E2] {mode} run {i}: {r.status} {wall:.2f}s obj={r.stats.get('objective')}")
        modes[mode] = rows
    # how long does the cold model need to *prove* optimality?
    r, wall = _solve(data, opts, None, 120.0)
    modes["cold_120s"] = [{"status": r.status, "wall_s": round(wall, 3),
                           "objective": r.stats.get("objective"), "load_gap": r.stats.get("load_gap")}]
    print(f"[E2] cold 120s: {r.status} {wall:.2f}s")
    out["modes"] = modes

    # incremental-change scenarios: preserve (warm) vs fresh (cold), same 8 s budget
    target = min(data.sections, key=lambda s: sum(data.subjects[x].periods_per_week for x in s.subject_ids))
    teacher = next(t for t in data.teachers if any(x in t.subject_ids for x in target.subject_ids))
    scen = {}

    def add_subject(d, o):
        d = deepcopy(d)
        new_id = max(d.subjects) + 1000
        d.subjects[new_id] = SubjectIn(new_id, "EVAL01", 2, False)
        for s in d.sections:
            if s.id == target.id:
                s.subject_ids = s.subject_ids + [new_id]
        for t in d.teachers:
            if t.id == teacher.id:
                t.subject_ids = set(t.subject_ids) | {new_id}
        return d, o

    def ban_teacher_day(d, o):
        o = deepcopy(o)
        busiest = Counter(prev.teachers.values()).most_common(1)[0][0]
        o.bans = o.bans + [SlotBan("teacher", busiest, ["WED"], [], "eval: teacher off Wednesday")]
        return d, o

    def raise_periods(d, o):
        d = deepcopy(d)
        sid = next(x for x in target.subject_ids if not d.subjects[x].needs_lab)
        d.subjects[sid] = replace(d.subjects[sid], periods_per_week=d.subjects[sid].periods_per_week + 1)
        return d, o

    for name, fn in [("add a 2-period subject to one class", add_subject),
                     ("teacher unavailable all Wednesday", ban_teacher_day),
                     ("one subject +1 period/week", raise_periods)]:
        d2, o2 = fn(data, opts)
        res = {}
        for mode, p in [("preserve", prev), ("fresh", None)]:
            times, moved, stat = [], [], []
            for _ in range(max(1, runs // 2)):
                r, wall = _solve(d2, o2, p, 8.0)
                times.append(round(wall, 3))
                stat.append(r.status)
                moved.append(_moved(prev, r) if r.lessons else None)
            v = verify(d2, o2, r) if r.lessons else None
            res[mode] = {"wall_s": times, "moved": moved, "status": stat,
                         "published_lessons": len(prev.lessons), "verify_passed": v and v["passed"],
                         "verify_checks": v and v["checks"]}
            print(f"[E2] scenario '{name}' {mode}: {stat[-1]} {st.mean(times):.2f}s moved={moved}")
        scen[name] = res
    out["scenarios"] = scen
    RESULTS["solver"] = out


# =============================================================================
# E3 — scalability on synthetic replicas of the campus instance
# =============================================================================

def replicate(data, opts, k: int):
    """k copies of every section, with teachers, classrooms and labs scaled alike."""
    from app.solver.timetable_model import RoomIn, SectionIn, TeacherIn, SlotBan, ScopeRules
    d = deepcopy(data)
    o = deepcopy(opts)
    base_secs, base_teachers = list(d.sections), list(d.teachers)
    base_rooms = [r for r in d.rooms if r.type in ("classroom", "lab")]
    elective_rooms = {off.room_id for g in d.electives for off in g.offerings}
    for c in range(1, k):
        off = 10000 * c
        for s in base_secs:
            d.sections.append(SectionIn(s.id + off, f"{s.name}#{c}", s.strength, list(s.subject_ids), s.semester))
            if s.id in o.section_rules:
                o.section_rules[s.id + off] = deepcopy(o.section_rules[s.id])
        for t in base_teachers:
            d.teachers.append(TeacherIn(t.id + off, f"{t.name}#{c}", t.max_hours_per_day, set(t.subject_ids),
                                        t.max_consecutive, t.max_hours_per_week))
        for r in base_rooms:
            if r.id in elective_rooms:
                continue
            d.rooms.append(RoomIn(r.id + off, f"{r.name}#{c}", r.type, r.capacity))
        o.bans = o.bans + [SlotBan(b.target, b.ref_id + off, b.days, b.periods, b.label)
                           for b in opts.bans if b.target in ("section", "teacher")]
    return d, o


def e3_scale(factors: list[int], limit: float) -> None:
    from app.solver.timetable_model import PreviousSolution, SubjectIn
    data, opts, _ = _load()
    rows = []
    for k in factors:
        d, o = replicate(data, opts, k)
        demand = sum(d.subjects[s].periods_per_week for sec in d.sections for s in sec.subject_ids)
        r, wall = _solve(d, o, None, limit)
        v = verify(d, o, r) if r.lessons else None
        row = {"factor": k, "sections": len(d.sections), "teachers": len(d.teachers),
               "lessons": demand, "cold_status": r.status, "cold_s": round(wall, 3),
               "cold_objective": r.stats.get("objective"), "cold_verify": v and f"{v['passed']}/{v['checks']}"}
        if r.lessons:
            prev = PreviousSolution()
            prev.lessons = {(l.section_id, l.subject_id, l.timeslot_id) for l in r.lessons}
            prev.teachers = {(l.section_id, l.subject_id): l.teacher_id for l in r.lessons}
            prev.electives = {(p.group_id, p.timeslot_id) for p in r.electives}
            hr = defaultdict(Counter)
            for l in r.lessons:
                if not d.subjects[l.subject_id].needs_lab:
                    hr[l.section_id][l.room_id] += 1
            prev.rooms = {s: c.most_common(1)[0][0] for s, c in hr.items()}
            # perturbation: one new 2-period subject in the first section
            d2 = deepcopy(d)
            nid = max(d2.subjects) + 1
            d2.subjects[nid] = SubjectIn(nid, "SCALE01", 2, False)
            # the class with the most spare slots, so the change is feasible
            tgt = min(d2.sections, key=lambda s: sum(d2.subjects[x].periods_per_week for x in s.subject_ids))
            tgt.subject_ids.append(nid)
            for t in d2.teachers:
                if set(tgt.subject_ids) & t.subject_ids:
                    t.subject_ids.add(nid)
                    break
            r2, w2 = _solve(d2, o, prev, limit)
            r3, w3 = _solve(d2, o, None, limit)
            row.update({"warm_status": r2.status, "warm_s": round(w2, 3),
                        "warm_moved": _moved(prev, r2) if r2.lessons else None,
                        "fresh_status": r3.status, "fresh_s": round(w3, 3),
                        "fresh_moved": _moved(prev, r3) if r3.lessons else None})
        rows.append(row)
        print(f"[E3] x{k}: {row}")
    RESULTS["scale"] = {"time_limit_s": limit, "rows": rows}


# =============================================================================
# E4 — infeasibility diagnosis
# =============================================================================

def e4_infeasible() -> None:
    from app.solver.timetable_model import ScopeRules, SlotBan, solve
    data, opts, _ = _load()
    lab_sec = next(s for s in data.sections if any(data.subjects[x].needs_lab for x in s.subject_ids))
    pinned = next(iter(data.assignments.items()))

    def mk(name, fn):
        d, o = deepcopy(data), deepcopy(opts)
        fn(d, o)
        return name, d, o

    def cap1(d, o):
        for t in d.teachers:
            t.max_hours_per_day = 1

    def no_qualified(d, o):
        sid = d.sections[0].subject_ids[0]
        for t in d.teachers:
            t.subject_ids.discard(sid)

    def short_week(d, o):
        o.section_rules.setdefault(d.sections[0].id, ScopeRules()).half_days = \
            {day: 2 for day in ["MON", "TUE", "WED", "THU", "FRI"]}

    def no_labs(d, o):
        d.rooms = [r for r in d.rooms if r.type != "lab"]

    def huge_class(d, o):
        d.sections[0].strength = 500

    def ban_pinned(d, o):
        (sec, sub), t = pinned
        o.bans = o.bans + [SlotBan("teacher", t, [], [], "eval: pinned teacher unavailable all week")]

    def day_cap(d, o):
        o.section_rules.setdefault(lab_sec.id, ScopeRules()).max_periods_per_day = 3

    def spread(d, o):
        # the class with the most spare slots, so only the spread rule can bite
        sec = min(d.sections, key=lambda s: sum(d.subjects[x].periods_per_week for x in s.subject_ids))
        sid = next(x for x in sec.subject_ids if not d.subjects[x].needs_lab)
        d.subjects[sid] = replace(d.subjects[sid], periods_per_week=6)
        o.subject_daily_max = 1
        o.section_rules.setdefault(sec.id, ScopeRules()).subject_daily_max = 1

    def weekly_cap(d, o):
        for t in d.teachers:
            t.max_hours_per_week = 4

    def run_cap(d, o):
        o.max_consecutive_teaching = 1
        for t in d.teachers:
            t.max_hours_per_day = 2

    cases = [mk(*c) for c in [
        ("every teacher capped at 1 period/day", cap1),
        ("no teacher qualified for a subject", no_qualified),
        ("class reduced to 2 periods/day", short_week),
        ("all lab rooms removed", no_labs),
        ("class strength 500 (no room fits)", huge_class),
        ("pinned teacher banned all week", ban_pinned),
        ("class capped at 3 periods/day", day_cap),
        ("6 periods/week with max 1/day", spread),
        ("every teacher capped at 4 periods/week", weekly_cap),
        ("max 1 in a row + 2 periods/day", run_cap),
    ]]
    rows = []
    for name, d, o in cases:
        t0 = time.perf_counter()
        r = solve(d, opts=o, time_limit_s=30.0)
        wall = time.perf_counter() - t0
        reason = " ".join(r.reasons)
        source = ("precheck" if r.reasons and not r.stats else
                  "assumption core" if "Conflicting constraint groups" in reason else
                  "generic" if r.reasons else "none")
        # the CP-SAT core is not minimised, so count how many groups it blames
        named = (reason.split("Conflicting constraint groups:")[1].split(".")[0].split(",")
                 if source == "assumption core" else [])
        rows.append({"case": name, "status": r.status, "wall_s": round(wall, 3), "source": source,
                     "groups_named": len(named),
                     "specific": source == "precheck" or 0 < len(named) <= 2,
                     "reason": reason[:300]})
        print(f"[E4] {name}: {r.status} via {source} ({wall:.2f}s)")
    RESULTS["infeasible"] = {"rows": rows,
                             "detected": sum(r["status"] == "infeasible" for r in rows),
                             "specific": sum(r["specific"] for r in rows), "n": len(rows)}


# =============================================================================
# E5 — Substitution (period-exchange) agent vs legacy stand-in planner
# =============================================================================

EVAL_MONDAY = date(2026, 11, 16)    # a week with no real leaves in the data


def _wipe_leave(db, lv):
    db.query(M.PeriodExchange).filter(M.PeriodExchange.leave_id == lv.id).delete()
    db.query(M.Substitution).filter(M.Substitution.plan_id == f"leave-{lv.id}").delete()
    db.query(M.Approval).filter(M.Approval.ref_id == lv.id,
                                M.Approval.kind == "substitution_plan").delete()
    db.delete(lv)
    db.commit()


def _check_exchanges(db, rows, leave) -> dict:
    """Independent invariant check of one plan against the base timetable."""
    from app.tools.substitution import _latest_version
    ver = _latest_version(db)
    base = db.query(M.TimetableEntry).filter(M.TimetableEntry.version == ver,
                                             M.TimetableEntry.status == "active").all()
    busy = {(e.teacher_id, e.timeslot.day, e.timeslot.period_no) for e in base}
    for e in base:
        if e.elective_group_id:
            g = db.get(M.ElectiveGroup, e.elective_group_id)
            for o in g.offerings:
                busy.add((o.teacher_id, e.timeslot.day, e.timeslot.period_no))
    bad = Counter()
    occupied = Counter()
    for x in rows:
        if not x.partner_entry_id:
            continue
        a, b = db.get(M.TimetableEntry, x.absent_entry_id), db.get(M.TimetableEntry, x.partner_entry_id)
        if a.section_id != b.section_id:
            bad["partner not in same section"] += 1
        if b.teacher_id == leave.teacher_id:
            bad["partner is the absent teacher"] += 1
        if (b.teacher_id, a.timeslot.day, a.timeslot.period_no) in busy:
            bad["partner busy on leave date"] += 1
        if (leave.teacher_id, b.timeslot.day, b.timeslot.period_no) in busy:
            bad["absent teacher busy at recovery"] += 1
        if not (x.recovery_date > leave.to_date):
            bad["recovery not after leave"] += 1
        if x.recovery_date.weekday() != ["MON", "TUE", "WED", "THU", "FRI"].index(b.timeslot.day):
            bad["recovery on wrong weekday"] += 1
        occupied[(b.teacher_id, x.leave_date, a.timeslot.period_no)] += 1
        occupied[(leave.teacher_id, x.recovery_date, b.timeslot.period_no)] += 1
    bad["double-booked by plan"] = sum(1 for n in occupied.values() if n > 1)
    return dict(bad)


def e5_exchange() -> None:
    from app.tools import exchange as ex
    from app.tools import substitution as legacy
    db = SessionLocal()
    ver = legacy._latest_version(db)
    n_master = db.query(M.TimetableEntry).count()
    teacher_ids = sorted({e.teacher_id for e in db.query(M.TimetableEntry)
                          .filter(M.TimetableEntry.version == ver, M.TimetableEntry.status == "active",
                                  M.TimetableEntry.elective_group_id.is_(None))})
    leaves = [(t, EVAL_MONDAY + timedelta(days=d), EVAL_MONDAY + timedelta(days=d), "1-day")
              for t in teacher_ids for d in range(5)]
    leaves += [(t, EVAL_MONDAY, EVAL_MONDAY + timedelta(days=n - 1), f"{n}-day")
               for t in teacher_ids for n in (2, 3, 5)]
    rows = []
    for t, fr, to, kind in leaves:
        lv = M.Leave(teacher_id=t, from_date=fr, to_date=to, reason="eval", status="approved")
        db.add(lv)
        db.commit()
        t0 = time.perf_counter()
        plan = ex.build_plan(db, lv)
        dt_ex = time.perf_counter() - t0
        t0 = time.perf_counter()
        again = ex.build_plan(db, lv)                    # idempotency (resume re-runs the node)
        dt_again = time.perf_counter() - t0
        affected = len(plan)
        exchanged = [x for x in plan if x.partner_entry_id]
        lab = sum(1 for x in plan if not x.partner_entry_id and "lab" in (x.rationale or "").lower())
        nopartner = affected - len(exchanged) - lab
        warned = sum(1 for x in exchanged if (x.rationale or "").startswith("⚠"))
        gaps = [(x.recovery_date - x.leave_date).days for x in exchanged]
        bad = _check_exchanges(db, plan, lv)

        t0 = time.perf_counter()
        subs = legacy.build_plan(db, lv)
        dt_legacy = time.perf_counter() - t0
        # the legacy planner also treats open-elective band rows (repeated per
        # section) as lessons; compare on the same lessons the exchange planner sees
        same = {x.absent_entry_id for x in plan}
        subs = [s for s in subs if s.timetable_entry_id in same]
        covered = [s for s in subs if s.substitute_teacher_id]
        same_subj = 0
        for s in covered:
            e = db.get(M.TimetableEntry, s.timetable_entry_id)
            sub_t = db.get(M.Teacher, s.substitute_teacher_id)
            same_subj += e.subject_id in {x.id for x in sub_t.subjects}
        rows.append({"teacher_id": t, "from": fr.isoformat(), "to": to.isoformat(), "kind": kind,
                     "affected": affected, "exchanged": len(exchanged), "lab_manual": lab,
                     "no_partner": nopartner, "warned": warned, "gaps_days": gaps,
                     "latency_ms": ms(dt_ex), "rebuild_ms": ms(dt_again),
                     "idempotent": len(again) == affected,
                     "violations": bad,
                     "legacy_latency_ms": ms(dt_legacy), "legacy_covered": len(covered),
                     "legacy_same_subject": same_subj, "legacy_affected": len(subs)})
        _wipe_leave(db, lv)
    n_master_after = db.query(M.TimetableEntry).count()
    db.close()

    agg = lambda k: sum(r[k] for r in rows)  # noqa: E731
    out = {"leaves": len(rows), "teachers": len(teacher_ids),
           "affected": agg("affected"), "exchanged": agg("exchanged"), "lab_manual": agg("lab_manual"),
           "no_partner": agg("no_partner"), "warned": agg("warned"),
           "theory_affected": agg("affected") - agg("lab_manual"),
           "invariant_violations": sum(sum(r["violations"].values()) for r in rows),
           "idempotent_all": all(r["idempotent"] for r in rows),
           "master_rows_before": n_master, "master_rows_after": n_master_after,
           "latency_ms": summarise([r["latency_ms"] for r in rows if r["affected"]]),
           "legacy_latency_ms": summarise([r["legacy_latency_ms"] for r in rows if r["affected"]]),
           "gap_days": summarise([g for r in rows for g in r["gaps_days"]]),
           "legacy_covered": agg("legacy_covered"), "legacy_same_subject": agg("legacy_same_subject"),
           "by_kind": {}, "rows": rows}
    for kind in ["1-day", "2-day", "3-day", "5-day"]:
        rs = [r for r in rows if r["kind"] == kind]
        out["by_kind"][kind] = {k: sum(r[k] for r in rs) for k in
                                ["affected", "exchanged", "lab_manual", "no_partner", "warned",
                                 "legacy_covered", "legacy_same_subject"]}
        out["by_kind"][kind]["latency_ms"] = summarise([r["latency_ms"] for r in rs if r["affected"]])
        out["by_kind"][kind]["legacy_latency_ms"] = summarise([r["legacy_latency_ms"] for r in rs if r["affected"]])
    RESULTS["exchange"] = out
    print(f"[E5] {out['leaves']} leaves, {out['affected']} lessons affected, {out['exchanged']} exchanged, "
          f"{out['lab_manual']} lab, {out['no_partner']} no partner, violations={out['invariant_violations']}")


# =============================================================================
# E6 — HITL: interrupt, simulated restart, resume
# =============================================================================

def e6_hitl(n: int) -> None:
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.types import Command
    from app.agents import graph as G

    db = SessionLocal()
    ver = db.query(M.TimetableEntry.version).order_by(M.TimetableEntry.version.desc()).first()[0]
    teacher_ids = sorted({e.teacher_id for e in db.query(M.TimetableEntry)
                          .filter(M.TimetableEntry.version == ver, M.TimetableEntry.elective_group_id.is_(None))})
    rows = []
    for i in range(n):
        t = teacher_ids[i % len(teacher_ids)]
        d = EVAL_MONDAY + timedelta(days=i % 5)
        lv = M.Leave(teacher_id=t, from_date=d, to_date=d, reason="eval-hitl", status="approved")
        db.add(lv)
        db.commit()
        thread = f"eval-{lv.id}-{uuid.uuid4().hex[:8]}"   # ids get reused after wipe
        state = {"messages": [{"role": "user", "content": f"Plan substitutions for approved leave #{lv.id}"}],
                 "steps": [], "params": {}, "final_response": "", "current_action": "general",
                 "source": "system", "task_spec": {"leave_id": lv.id}}
        t0 = time.perf_counter()
        r1 = G.compiled_graph.invoke(state, config={"configurable": {"thread_id": thread}})
        t_pause = time.perf_counter() - t0
        paused = bool(r1.get("__interrupt__"))
        llm_skipped = any("deterministic, no LLM" in s for s in r1.get("steps", []))
        n_rows = db.query(M.PeriodExchange).filter(M.PeriodExchange.leave_id == lv.id).count()
        notif_before = db.query(M.Notification).count()

        # simulated restart: brand-new connection + checkpointer + compiled graph
        conn = sqlite3.connect(os.environ["CHECKPOINT_DB"], check_same_thread=False)
        fresh = G.workflow.compile(checkpointer=SqliteSaver(conn))
        action = "approve" if i % 4 != 3 else "reject"
        t0 = time.perf_counter()
        r2 = fresh.invoke(Command(resume={"action": action}), config={"configurable": {"thread_id": thread}})
        t_resume = time.perf_counter() - t0
        conn.close()

        db.expire_all()
        xs = db.query(M.PeriodExchange).filter(M.PeriodExchange.leave_id == lv.id).all()
        want = {"approve": "confirmed", "reject": "rejected"}[action]
        rows.append({"leave_id": lv.id, "has_lessons": n_rows > 0, "paused": paused, "llm_skipped": llm_skipped,
                     "pause_ms": ms(t_pause), "resume_ms": ms(t_resume), "action": action,
                     "rows_before": n_rows, "rows_after": len(xs), "no_duplicates": n_rows == len(xs),
                     "state_applied": bool(xs) and all(x.status == want for x in xs if x.partner_entry_id)
                     or not any(x.partner_entry_id for x in xs),
                     "notifications": db.query(M.Notification).count() - notif_before,
                     "final_response": bool(r2.get("final_response"))})
        print(f"[E6] leave {lv.id}: paused={paused} resume({action}) ok={rows[-1]['state_applied']}")
        _wipe_leave(db, lv)
    db.close()
    rows = [r for r in rows if r["has_lessons"]]      # a leave with no classes never pauses (by design)
    RESULTS["hitl"] = {
        "n": len(rows), "paused": sum(r["paused"] for r in rows),
        "llm_skipped": sum(r["llm_skipped"] for r in rows),
        "resumed_ok": sum(r["state_applied"] and r["final_response"] for r in rows),
        "no_duplicates": sum(r["no_duplicates"] for r in rows),
        "pause_ms": summarise([r["pause_ms"] for r in rows]),
        "resume_ms": summarise([r["resume_ms"] for r in rows]),
        "notifications_per_approved_plan": summarise([r["notifications"] for r in rows if r["action"] == "approve"]),
        "rows": rows}


# =============================================================================
# E7 — safety sweep sentinel
# =============================================================================

def e7_sweep() -> None:
    import io
    import contextlib
    import main as app_main

    db = SessionLocal()
    ver = db.query(M.TimetableEntry.version).order_by(M.TimetableEntry.version.desc()).first()[0]
    t = db.query(M.TimetableEntry.teacher_id).filter(M.TimetableEntry.version == ver,
                                                     M.TimetableEntry.elective_group_id.is_(None)).first()[0]
    # leaves the normal path "missed": 3 with classes, 1 on a weekend (no classes)
    missed = [M.Leave(teacher_id=t, from_date=EVAL_MONDAY + timedelta(days=k),
                      to_date=EVAL_MONDAY + timedelta(days=k), reason="eval-sweep", status="approved")
              for k in (0, 1, 2)]
    weekend = M.Leave(teacher_id=t, from_date=EVAL_MONDAY + timedelta(days=5),
                      to_date=EVAL_MONDAY + timedelta(days=6), reason="eval-sweep-weekend", status="approved")
    db.add_all(missed + [weekend])
    db.commit()
    ids = [lv.id for lv in missed]
    already = db.query(M.Leave).filter(M.Leave.status == "approved").count() - 4

    triggers = []
    for tick in range(3):
        buf = io.StringIO()
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(buf):
            app_main._substitution_sweep()
        dt = time.perf_counter() - t0
        fired = [ln for ln in buf.getvalue().splitlines() if "[sweep]" in ln]
        triggers.append({"tick": tick, "fired": len(fired), "ms": ms(dt),
                         "fired_for_weekend_leave": any(f"#{weekend.id}" in ln for ln in fired)})
    db.expire_all()
    planned = sum(1 for i in ids if db.query(M.PeriodExchange).filter(M.PeriodExchange.leave_id == i).count())
    dupes = sum(db.query(M.PeriodExchange).filter(M.PeriodExchange.leave_id == i).count() for i in ids)
    # rows from a single build, for comparison
    from app.tools import exchange as ex
    single = 0
    for i in ids:
        single += len({x.absent_entry_id for x in db.query(M.PeriodExchange)
                       .filter(M.PeriodExchange.leave_id == i)})
    for lv in missed + [weekend]:
        _wipe_leave(db, db.get(M.Leave, lv.id))
    db.close()
    RESULTS["sweep"] = {"missed_leaves": len(ids), "recovered": planned, "ticks": triggers,
                        "rows_total": dupes, "rows_unique_lessons": single,
                        "pre_existing_approved_leaves": already}
    print(f"[E7] recovered {planned}/{len(ids)}; ticks={triggers}")


# =============================================================================
# E8 — constraint registry
# =============================================================================

def e8_registry() -> None:
    from app.tools import constraints as reg
    db = SessionLocal()
    ctx = reg.build_ctx(db)
    rows = []
    for kind, scope, val, params, ok in D.CONSTRAINTS:
        t0 = time.perf_counter()
        try:
            reg.validate(db, kind, scope, val, params, ctx=ctx)
            got, msg = True, ""
        except reg.ConstraintError as exc:
            got, msg = False, str(exc)
        except Exception as exc:  # an unhandled error is a failure of the validator
            got, msg = None, f"{type(exc).__name__}: {exc}"
        rows.append({"kind": kind, "scope": scope, "expected": ok, "accepted": got,
                     "correct": got == ok, "message": msg[:160], "ms": ms(time.perf_counter() - t0)})
    t = []
    for _ in range(50):
        t0 = time.perf_counter()
        reg.compile_options(db)
        t.append(ms(time.perf_counter() - t0))
    db.close()
    tp = sum(1 for r in rows if r["expected"] and r["accepted"])
    tn = sum(1 for r in rows if not r["expected"] and r["accepted"] is False)
    RESULTS["registry"] = {"n": len(rows), "correct": sum(r["correct"] for r in rows),
                           "valid_accepted": tp, "valid_total": sum(r["expected"] for r in rows),
                           "invalid_rejected": tn, "invalid_total": sum(not r["expected"] for r in rows),
                           "crashes": sum(r["accepted"] is None for r in rows),
                           "kinds_covered": len({r["kind"] for r in rows} & set(reg.CATALOG)),
                           "catalog_size": len(reg.CATALOG),
                           "validate_ms": summarise([r["ms"] for r in rows]),
                           "compile_ms": summarise(t), "rows": rows}
    print(f"[E8] registry {RESULTS['registry']['correct']}/{len(rows)} correct")


# =============================================================================
# E9 — Timetable Assistant
# =============================================================================

def e9_assistant(use_llm: bool) -> None:
    from app.tools import ops as opsmod
    db = SessionLocal()
    rows = []
    for name, ops, ok in D.ASSISTANT_PLANS:
        t0 = time.perf_counter()
        steps = opsmod.plan(db, ops)
        dt = time.perf_counter() - t0
        got = bool(steps) and all(s.get("ok") for s in steps)
        rows.append({"case": name, "expected": ok, "accepted": got, "correct": got == ok,
                     "steps": len(steps), "ms": ms(dt),
                     "errors": [s.get("error") for s in steps if not s.get("ok")][:2]})

    # atomic-apply check: a plan whose 2nd op fails — what does run() commit?
    before = db.query(M.Room).count()
    done, failed, _ = opsmod.run(db, [
        {"op": "add_room", "params": {"name": "Eval-Room-1", "type": "classroom", "capacity": 40}},
        {"op": "add_room", "params": {"name": "Eval-Bad", "type": "swimming", "capacity": 40}}])
    partial_committed = db.query(M.Room).count() - before

    # bulk vs longhand payload size (what the model has to *write*)
    def payload(n):
        items_s = [{"code": f"CS8{i:02d}", "name": f"Subject {i}"} for i in range(n)]
        items_t = [{"name": f"Dr. Teacher {i}", "subjects": [f"CS8{i:02d}"], "assign_to": "CSE-7A"}
                   for i in range(n)]
        bulk = [{"op": "add_subjects", "params": {"defaults": {"semester": 7, "periods_per_week": 3},
                                                  "items": items_s}},
                {"op": "add_teachers", "params": {"items": items_t}}]
        long = opsmod.expand(deepcopy(bulk))
        for o in long:
            if o["op"] == "add_subject":
                o["params"] = {**o["params"]}
        return len(json.dumps(bulk, separators=(",", ":"))), len(json.dumps(long, separators=(",", ":"))), len(long)
    sizes = []
    for n in (1, 3, 5, 10, 20):
        b, l, nops = payload(n)
        sizes.append({"entities_each": n, "bulk_chars": b, "longhand_chars": l, "ops_after_expand": nops,
                      "reduction": round(l / b, 2)})
    out = {"n": len(rows), "correct": sum(r["correct"] for r in rows),
           "valid_accepted": sum(1 for r in rows if r["expected"] and r["accepted"]),
           "valid_total": sum(r["expected"] for r in rows),
           "invalid_rejected": sum(1 for r in rows if not r["expected"] and not r["accepted"]),
           "invalid_total": sum(not r["expected"] for r in rows),
           "plan_ms": summarise([r["ms"] for r in rows]), "rows": rows,
           "partial_apply": {"ops": 2, "applied": len(done), "failed": len(failed),
                             "rows_committed": partial_committed},
           "payload": sizes}
    db.rollback()

    if use_llm:
        from app.api import assistant as A
        from app.core.llm import is_llm_configured
        if not is_llm_configured():
            out["llm"] = {"skipped": "no LLM key"}
        else:
            lrows = []
            for prompt, expect in D.ASSISTANT_PROMPTS:
                err, raw_ops, dt, text = None, [], None, ""
                for attempt in range(3):
                    t0 = time.perf_counter()
                    try:
                        text = A._ask_llm(db, prompt)
                        dt = time.perf_counter() - t0
                        raw_ops = A._extract_json(text).get("ops") or []
                        err = None
                        break
                    except Exception as exc:
                        err = f"{type(exc).__name__}: {str(exc)[:120]}"
                        time.sleep(10 * (attempt + 1))
                steps = opsmod.plan(db, raw_ops) if raw_ops else []
                kinds = {s["op"] for s in steps}
                lrows.append({"prompt": prompt, "error": err, "latency_s": dt and round(dt, 2),
                              "output_chars": len(text), "ops": len(steps),
                              "all_valid": bool(steps) and all(s.get("ok") for s in steps),
                              "expected_ops_present": expect <= kinds,
                              "kinds": sorted(kinds),
                              "errors": [s.get("error") for s in steps if not s.get("ok")][:2]})
                print(f"[E9] LLM '{prompt[:40]}': valid={lrows[-1]['all_valid']} "
                      f"expected={lrows[-1]['expected_ops_present']} {dt and round(dt,1)}s")
                time.sleep(1)
            ok = [r for r in lrows if not r["error"]]
            out["llm"] = {"n": len(lrows), "answered": len(ok),
                          "all_valid": sum(r["all_valid"] for r in ok),
                          "expected_ops": sum(r["expected_ops_present"] for r in ok),
                          "end_to_end": sum(r["all_valid"] and r["expected_ops_present"] for r in ok),
                          "latency_s": summarise([r["latency_s"] for r in ok]),
                          "output_chars": summarise([r["output_chars"] for r in ok]),
                          "rows": lrows}
    db.close()
    RESULTS["assistant"] = out
    print(f"[E9] op compiler {out['correct']}/{out['n']} correct; partial apply={out['partial_apply']}")


# =============================================================================
# E10 — Facility / Scheduler / General specialists
# =============================================================================

def e10_specialists(use_llm: bool) -> None:
    from app.agents.specialists.booking import facility_node
    from app.agents.specialists.scheduling import scheduler_node
    from app.agents.specialists import general as gen
    db = SessionLocal()
    rooms = {r.name: r.type for r in db.query(M.Room).all()}
    db.close()
    rows = []
    for q, want in D.FACILITY:
        t0 = time.perf_counter()
        r = facility_node({"messages": [{"role": "user", "content": q}], "task_spec": {}, "params": {}})
        dt = time.perf_counter() - t0
        got = r["params"].get("facility_name")
        if want is None:
            ok = got is None
        elif want.startswith("type:"):
            ok = got is not None and rooms.get(got) == want[5:]
        else:
            ok = got == want
        rows.append({"query": q, "expected": want, "got": got, "correct": ok, "ms": ms(dt)})
    sched = []
    for q in ["check schedule conflicts", "schedule status"] * 25:
        t0 = time.perf_counter()
        scheduler_node({"messages": [{"role": "user", "content": q}]})
        sched.append(ms(time.perf_counter() - t0))
    out = {"facility": {"n": len(rows), "correct": sum(r["correct"] for r in rows),
                        "ms": summarise([r["ms"] for r in rows]), "rows": rows},
           "scheduler": {"ms": summarise(sched)}}
    # general fallback, deterministic path (no LLM)
    real = gen.is_llm_configured
    gen.is_llm_configured = lambda: False
    g = []
    for _ in range(50):
        t0 = time.perf_counter()
        gen.general_fallback_node({"messages": [{"role": "user", "content": "hi"}]})
        g.append(ms(time.perf_counter() - t0))
    gen.is_llm_configured = real
    out["general_canned"] = {"ms": summarise(g)}
    if use_llm and real():
        g = []
        for q in ["What can you do?", "When does the semester end?", "Where is the canteen?",
                  "How do I reset my password?", "Explain the grading system"]:
            t0 = time.perf_counter()
            r = gen.general_fallback_node({"messages": [{"role": "user", "content": q}]})
            if "LLM unavailable" not in r["steps"][-1]:
                g.append(ms(time.perf_counter() - t0))
            time.sleep(1)
        out["general_llm"] = {"ms": summarise(g)}
    RESULTS["specialists"] = out
    print(f"[E10] facility {out['facility']['correct']}/{out['facility']['n']}")


# =============================================================================
# E11 — graceful degradation (LLM forced to fail)
# =============================================================================

def e11_degrade() -> None:
    from app.agents import supervisor as sup
    from app.agents.specialists import general as gen

    class Boom:
        def __getattr__(self, _):
            raise ConnectionError("simulated provider outage")

    real = (sup.is_llm_configured, sup.get_llm, gen.is_llm_configured, gen.get_llm)
    sup.is_llm_configured = gen.is_llm_configured = lambda: True
    sup.get_llm = gen.get_llm = lambda *a, **k: Boom()
    try:
        answered, exc, routes, lat = 0, 0, [], []
        from app.agents.specialists.booking import facility_node
        from app.agents.specialists.scheduling import scheduler_node
        nodes = {"facility": facility_node, "scheduler": scheduler_node,
                 "general_fallback": gen.general_fallback_node}
        for q, gold in D.ROUTING:
            t0 = time.perf_counter()
            try:
                st_ = {"messages": [{"role": "user", "content": q}], "task_spec": {}, "params": {}}
                r = sup.supervisor_node(st_)
                routes.append(r["current_action"])
                tgt = sup.route_to(r)
                if tgt in nodes:   # timetable/substitution nodes are exercised in E2/E5/E6
                    rr = nodes[tgt]({**st_, **r})
                    answered += bool(rr.get("final_response"))
                else:
                    answered += 1
            except Exception:
                exc += 1
            lat.append(ms(time.perf_counter() - t0))
    finally:
        sup.is_llm_configured, sup.get_llm, gen.is_llm_configured, gen.get_llm = real
    gold = [g for _, g in D.ROUTING]
    RESULTS["degrade"] = {"n": len(D.ROUTING), "answered": answered, "exceptions": exc,
                          "routing_accuracy": prf(gold, routes, ROUTES)["accuracy"],
                          "latency_ms": summarise(lat)}
    print(f"[E11] degrade answered {answered}/{len(D.ROUTING)} exceptions={exc}")


# =============================================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run live-LLM experiments")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--scale", default="1,2,3,4,5")
    ap.add_argument("--scale-limit", type=float, default=60.0)
    ap.add_argument("--only", default="")
    ap.add_argument("--hitl-n", type=int, default=12)
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    want = lambda k: not only or k in only  # noqa: E731

    import ortools
    RESULTS["meta"] = {"date": date.today().isoformat(), "python": platform.python_version(),
                       "ortools": ortools.__version__, "platform": platform.platform(),
                       "processor": platform.processor(), "cpu_count": os.cpu_count(),
                       "runs": a.runs, "llm": a.llm}
    OUT.mkdir(parents=True, exist_ok=True)
    plan = [("routing", lambda: e1_routing(a.llm)), ("registry", e8_registry),
            ("assistant", lambda: e9_assistant(a.llm)), ("specialists", lambda: e10_specialists(a.llm)),
            ("degrade", e11_degrade), ("exchange", e5_exchange), ("hitl", lambda: e6_hitl(a.hitl_n)),
            ("sweep", e7_sweep), ("infeasible", e4_infeasible), ("solver", lambda: e2_solver(a.runs)),
            ("scale", lambda: e3_scale([int(x) for x in a.scale.split(",")], a.scale_limit))]
    for key, fn in plan:
        if want(key):
            t0 = time.perf_counter()
            fn()
            print(f"--- {key} done in {time.perf_counter() - t0:.1f}s")
            # write after every experiment so a long run is never lost
            path = OUT / (f"eval_{key}.json" if only else "eval_results.json")
            if only:
                path.write_text(json.dumps({"meta": RESULTS["meta"], key: RESULTS[key]}, indent=1, default=str))
            else:
                path.write_text(json.dumps(RESULTS, indent=1, default=str))
    print("results ->", OUT)


if __name__ == "__main__":
    main()
