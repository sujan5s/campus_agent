# Phase 2.3 Plan — Per-Class Constraints, Anti-Consecutive by Default, Fast Plan Creation

**Status:** PLANNED (2026-07-15). Written for direct implementation — every change lists file, location, and acceptance check. Prereqs: read `docs/07-PHASE2.2-PLAN.md` (what shipped in 2.2) first.

Three fixes, ordered by user impact. Fix 3 (performance) is independent; Fixes 1+2 both touch the solver and should be done together.

---

## Fix 1 — Constraints must be configurable PER CLASS (section), not only globally

### Problem

`SolveOptions` (Phase 2.2) applies half-days and the anti-consecutive rule to **every** section. Real college: CSE-7A may have WED half-day while CSE-7B doesn't. Teacher run cap stays global (it's a teacher property, not a class property).

### Design: global defaults + per-section overrides

**B1. Solver — `services/backend/app/solver/timetable_model.py`**

```python
@dataclass
class SectionRules:
    half_days: dict[str, int] = field(default_factory=dict)      # {"WED": 4}
    no_same_subject_consecutive: bool | None = None              # None = inherit global

@dataclass
class SolveOptions:
    half_days: dict[str, int] = field(default_factory=dict)      # global default
    no_same_subject_consecutive: bool = True                     # ← now DEFAULT ON (Fix 2)
    max_consecutive_teaching: int | None = None                  # global only
    section_rules: dict[int, SectionRules] = field(default_factory=dict)  # by section_id
```

- **Replace the global slot-filtering half-day implementation** with per-section allowed-slot sets. Global filtering is wrong once one section keeps the full day (rooms/teachers may still be needed there). New approach:
  - Keep `data.slots` intact. Compute `allowed: dict[int, set[int]]` = slot indices allowed per section (global `half_days` merged with `section_rules[sec.id].half_days`, section override wins per day).
  - For every disallowed `(sec, sid, si)`: `m.Add(x[(sec.id, sid, si)] == 0)` right where x vars are created (cheap; no assumption group needed — it's an input restriction, not a constraint conflict).
- **Precheck must be per-section aware.** `precheck(data, opts)` — change the capacity check to `need > len(allowed[sec.id])` with message "Section X needs N periods/week but its half-day rules leave only M slots". Also: for each **lab** subject of a section, verify at least one consecutive pair lies fully inside `allowed[sec.id]`, else precise message ("Section X's half-days leave no consecutive block for LAB101").
- **H9 per section**: effective flag = `section_rules[sec.id].no_same_subject_consecutive` if not None else `opts.no_same_subject_consecutive`. Apply the pairwise `x[a]+x[b] <= 1` only for sections whose effective flag is True. Keep the single assumption group ("no same-subject back-to-back") shared across sections.
- H10 (teacher cap) unchanged, global.
- **Serialization note:** `asdict()` on nested dataclasses works, but `section_rules` keys are ints → JSON turns them into strings. `get_version_config` consumers must not assume int keys; simplest: store keys as section **names** in config_json for readability (map id→name when persisting in `app/tools/timetable.py`).

**B2. API — `services/backend/app/api/timetable.py`**

```python
class SectionRulesIn(BaseModel):
    section: str                                # section name, e.g. "CSE-7A"
    half_days: list[HalfDayIn] = []
    no_same_subject_consecutive: bool | None = None

class GenerateIn(BaseModel):
    half_days: list[HalfDayIn] = []
    no_same_subject_consecutive: bool = True    # ← default on (Fix 2)
    max_consecutive_teaching: int | None = Field(default=None, ge=1)
    sections: list[SectionRulesIn] = []
```

`_build_options`: validate each `sections[].section` against the Section table (404-style 422 if unknown); validate its half_days with the same grid check as global; build `section_rules` keyed by section_id. Duplicate section entries → 422.

**B3. Frontend — `apps/web/src/app/timetable/page.tsx`**

Constraints panel gains a **scope selector**: a dropdown `[All classes ▾ | CSE-7A | CSE-7B | …]` (reuse the already-loaded `sections` state). The half-day day-chips and anti-consecutive toggle edit the currently selected scope; "All classes" edits the global default. State: `rulesByScope: Record<string, {halfDays, halfDayLast, noConsecutive}>` with `"*"` for global. Scopes with overrides show a small dot/chip next to their name in the dropdown. `generate()` assembles `GenerateIn` from all scopes (skip scopes with no overrides). Config summary line lists per-section parts: `CSE-7A: WED≤P4 · global: no back-to-back`.

Teacher run cap input stays outside the scope selector (global).

### Acceptance (Fix 1)

1. Body `{"sections":[{"section":"CSE-7A","half_days":[{"day":"WED","last_period":4}]}]}` → CSE-7A has zero WED P5–P7 entries; CSE-7B still has WED P5–P7 lessons.
2. Global `half_days` + section override on the same day → override wins for that section only.
3. Lab-block feasibility: give a lab section half-days that leave no consecutive pair → 422 with the precise lab message.
4. Unknown section name → 422. UI round-trips scopes correctly; config_json shows section names.

---

## Fix 2 — Timetables must not get back-to-back same-subject periods by default

### Root cause (verified in code)

H9 exists but is **opt-in and defaults off**, and two generation paths never send options at all:
- `timetable_node` (`app/agents/specialists/timetable.py:21`) calls `generate_timetable()` bare — chat "generate a timetable" ignores every constraint.
- UI checkbox defaults unchecked.

So the college's actual rule ("continuous same periods are hectic — avoid them") only held when the admin remembered to tick a box, and never via chat.

### Changes

1. **Default ON everywhere**: `SolveOptions.no_same_subject_consecutive = True` (B1 above), `GenerateIn.no_same_subject_consecutive = True` (B2), UI checkbox initial state `true` (`useState(true)` in `timetable/page.tsx`). Explicit opt-out remains possible per request and per section (`SectionRulesIn.no_same_subject_consecutive: false`).
2. **Agent path honors saved config**: `timetable_node` should load the latest version's persisted config (`get_version_config` in `app/tools/timetable.py`) and reuse it: deserialize config_json → `SolveOptions` (helper `options_from_config(db) -> SolveOptions` in `app/tools/timetable.py`; falls back to defaults when no version/config). Pass it to `generate_timetable(options=...)`. Chat regeneration then keeps the admin's per-class rules instead of silently dropping them.
3. **Lab hardening** (closes the remaining 3-in-a-row hole): a lab subject with `periods_per_week > 2` currently gets one consecutive pair (H5) but its extra periods can land adjacent to the block → 3 continuous periods of one subject. Fix: apply the H8 "≤2 per day" constraint to **lab subjects too** (currently only in the `else:` theory branch, `timetable_model.py` ~L226). With the pair mandatory and daily ≤2, no 3-run of a lab subject is possible. (Seed labs are ppw=2, so seeded output is unchanged — this is future-proofing for real data.)

### Acceptance (Fix 2)

1. `POST /generate` with **empty body** → no theory subject occupies two time-adjacent periods for any section (script-check over the version, as done in 2.2 verification).
2. Chat "Generate a fresh timetable" → same guarantee (agent path now applies options).
3. Explicit `{"no_same_subject_consecutive": false}` → back-to-back allowed again (opt-out works).
4. Synthetic lab subject with ppw=3 → solver never places 3 adjacent periods of it in one day.

---

## Fix 3 — Plan creation after leave approval is far too slow

### Root causes (both verified in code — fix BOTH)

**(a) Pointless LLM round-trip on system triggers.** `decide_leave` (`app/api/leaves.py:89`) invokes the graph with `source="system"` and `task_spec={"leave_id": ...}` already set — the route is fully determined. Yet `supervisor_node` (`app/agents/supervisor.py:55`) still makes a Gemini structured-output call (2–15s on the free tier, more with retries/quota errors). The APScheduler safety sweep pays the same cost every 2 minutes.

**Fix**: at the top of `supervisor_node`, before `is_llm_configured()`:
```python
if state.get("source") == "system" and (state.get("task_spec") or {}).get("leave_id"):
    return {"steps": [... "system trigger → substitution (deterministic, no LLM)"],
            "current_action": "substitution",
            "task_spec": state.get("task_spec") or {}}
```
General rule: **system-sourced invocations never call the LLM** — the trigger already knows the intent. (Check the sweep in `main.py`/scheduler code passes `source="system"` too; make it so if not.) Chat-sourced requests keep full LLM routing.

**(b) N+1 query storm in the Phase 2.2 adjacency guard.** In `app/tools/exchange.py`, for **every candidate of every affected lesson**, `_adjacency_warnings` triggers: 2× `_effective_subject_map` (each scans ALL confirmed `PeriodExchange` rows and does 2 `db.get(TimetableEntry)` per row + a full section entry scan), 2× `_teacher_day_periods` (full teacher entry scan), plus `_adjacent_period_nos`/`_day_runs`/`_max_consecutive` each re-querying `TimeSlot`. With L lessons × C candidates this is thousands of SQLite round-trips → seconds to tens of seconds, growing with confirmed-exchange history.

**Fix: a `PlanContext` built once per `build_plan`, all checks become pure in-memory lookups.**

New dataclass/plain class in `exchange.py`:

```python
class PlanContext:
    slots_by_day: dict[str, list[TimeSlot-lite]]        # one TimeSlot query
    adjacent: dict[tuple[str, int], set[int]]           # (day, period) -> adjacent periods
    runs: dict[str, list[list[int]]]                    # day -> consecutive-period chains
    entries_by_id: dict[int, TimetableEntry]            # one eager-loaded entry query
    section_day: dict[tuple[int, str], dict[int, int]]  # (section, day) -> {period: subject}
    teacher_day: dict[tuple[int, str], set[int]]        # (teacher, day) -> periods taught
    candidates_by_section: dict[int, list[TimetableEntry]]
    busy: set[tuple[int, str, int]]                     # (teacher, day, period) from base
    loads: dict[int, int]                               # weekly load per teacher
    overlay: dict[tuple[int, str], dict[int, int]]      # (section, date_iso) -> {period: subject}
                                                        #   from CONFIRMED exchanges, one query
    leaves: list[(teacher_id, from, to)]                # approved leaves, one query (replaces
                                                        #   per-candidate _on_leave queries)
```

Build it at the top of `build_plan` with exactly **5 queries**: TimeSlot, TimetableEntry (latest version, `joinedload(timeslot, subject, teacher.user, section)`), confirmed PeriodExchange, approved Leave, plus the existing plan-idempotency check. Then:
- `_teacher_busy_at` → `(tid, day, p) in ctx.busy` set lookup.
- `_on_leave` → date-range check against `ctx.leaves` (keep the imported function for the legacy module; exchange.py stops calling it per-candidate).
- `_effective_subject_map` → `dict(ctx.section_day[(sec, day)])`, apply `ctx.overlay.get((sec, date))`, apply plan-local `placed` — zero queries.
- `_adjacent_period_nos` / `_max_consecutive` → `ctx.adjacent` / `ctx.runs` lookups.
- `_pick_partner` iterates `ctx.candidates_by_section[section_id]` instead of re-querying; `loads` comes from ctx (delete the loads loop currently at `build_plan` top — it's the same single pass).
- `plan_summary` and `apply_plan` can keep their current shape (small row counts) but replace per-row `db.get(TimetableEntry)` with `joinedload`-ed queries if trivially easy — optional.

Keep behavior byte-identical: same scoring, same warnings, same rationale strings — this is a pure performance refactor of 2.2's logic. The 2.2 verification scripts (clean flow, forced adjacency, idempotency) must produce identical output before/after.

**(c) Minor, same theme (do if time permits):**
- `list_approvals` calls `plan_summary` per pending card on every 15s poll — fine at demo scale; skip.
- `exchanges_board` / `effective_grid` (`app/api/timetable.py`) scan ALL confirmed exchanges then filter in Python — push the date-range/status filter into SQL with `filter(PeriodExchange.leave_date.between(...) | PeriodExchange.recovery_date.between(...))`.

### Acceptance (Fix 3)

1. **Measure first, then re-measure**: wrap `compiled_graph.invoke` in `decide_leave` with `time.perf_counter()` prints (or temporary logging) — record before/after numbers in the roadmap entry.
2. Leave-approval endpoint completes in **< 1s** on seeded data with no LLM call in the trace (steps must show "system trigger → substitution (deterministic, no LLM)").
3. `build_plan` runs ≤ ~10 SQL statements regardless of candidate count (verify with `echo=True` on a scratch engine or a query counter event listener in the test script).
4. Output identical to 2.2: re-run the temp-leave script (4 lessons affected, 2 exchanged, lab rows manual) and the forced-adjacency script — same partners, same rationale text, same warnings.
5. HOD approve/reject resume path unchanged and still idempotent (node re-runs from top: build_plan early-returns on existing plan).

---

## Implementation order & chores

1. **Fix 3a** (supervisor bypass — 10 lines, biggest win) → measure.
2. **Fix 3b** (PlanContext refactor) → re-run 2.2 verification scripts, compare output, measure.
3. **Fix 1 + Fix 2 together** (solver per-section rework + defaults + agent-path options + lab hardening) → run all Fix 1/Fix 2 acceptance checks.
4. Frontend scope selector last (backend is testable via Swagger without it).
5. `cd apps/web && npx tsc --noEmit` must stay clean.
6. Update `docs/04-ROADMAP.md` (Phase 2.3 section with measured before/after latency), CLAUDE.md status line, `docs/05-DEMO-SCRIPT.md` Act 2 step 4 (mention per-class scoping) and Act 3 (mention instant plan).
7. `python -m graphify update .` after code changes.

**Testing note:** still no pytest suite; acceptance via seeded dev DB + throwaway scratch scripts (NOT committed) + Swagger + UI walkthrough. The 2.2 verification one-liners in this repo's history (roadmap entry) are the regression baseline for Fix 3b.
