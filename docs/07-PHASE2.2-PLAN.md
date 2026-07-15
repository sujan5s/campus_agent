# Phase 2.2 Plan — Exchange Adjacency Guard + Configurable Generation Constraints

**Status:** PLANNED (2026-07-15). Written for direct implementation — every change lists file, location, and acceptance check. Read `docs/06-EXCHANGE-PLAN.md` first for exchange semantics.

Two independent features. Implement A first (smaller, pure backend), then B.

---

## Feature A — Exchange planner must not create back-to-back same-subject periods

### Problem (verified in code)

`_pick_partner()` in `services/backend/app/tools/exchange.py:158` validates only **teacher availability** (on-leave, busy-at-slot, plan reservations) on the leave date D and recovery date R. It never inspects the **section's day composition** on either date. Consequences:

1. **Leave date D:** partner B's subject moves into A's period. If that section already has B's subject in a time-adjacent period that day, students get the same subject back-to-back (and B teaches that section consecutively).
2. **Recovery date R:** A recovers their subject in B's slot. If the section's base timetable already has A's subject adjacent to B's period on that weekday, same problem.
3. Either side can also push a subject past the "≤2 per day" spirit of solver constraint H8, since exchanges bypass the solver entirely.

Spreading exchanges across more days is fine (the planner already prefers near recovery via the `-2.0 * gap` score term); adjacency is the thing to avoid.

### Design: overlay-aware adjacency checks inside `_pick_partner`, penalty-based (not hard reject)

Hard-rejecting risks flipping viable exchanges into "NO EXCHANGE AVAILABLE". Instead: candidates that create adjacency get a **large score penalty** and a **warning embedded in the rationale**, so a clean candidate always wins when one exists, and the HOD sees a visible ⚠ on the approval card when it doesn't.

### Changes — all in `services/backend/app/tools/exchange.py`

**A1. New helpers** (place near `_teacher_busy_at`):

```python
def _adjacent_period_nos(db, day: str, period_no: int) -> set[int]:
    """Period numbers time-adjacent to (day, period_no): same day, and the two
    slots share a boundary (prev.end == this.start or this.end == next.start).
    A break between periods breaks adjacency — mirror the logic of
    _consecutive_pairs() in app/solver/timetable_model.py:153."""

def _section_day_map(db, ver: int, section_id: int, day: str) -> dict[int, int]:
    """Base timetable for one section on one weekday: {period_no: subject_id}.
    Latest version, status='active'."""

def _effective_subject_map(db, ver, section_id, day, on_date, plan_overlay) -> dict[int, int]:
    """Section's *effective* {period_no: subject_id} for a real date:
    start from _section_day_map, then apply
      (a) already-CONFIRMED PeriodExchange rows from other plans touching
          this section+date (both leave_date and recovery_date sides), and
      (b) this plan's in-progress placements (plan_overlay dict, see A2).
    """
```

**A2. Track this plan's subject placements in `build_plan()` (exchange.py:66).** Alongside the existing `reserved` set, add:

```python
# (section_id, date_iso, period_no) -> subject_id placed there by this plan
placed: dict[tuple[int, str, int], int] = {}
```

After each accepted exchange, record both sides:
- `placed[(entry_a.section_id, on_date.isoformat(), entry_a.timeslot.period_no)] = entry_b.subject_id`  (D: B's subject now sits in A's period)
- `placed[(entry_b.section_id, recovery_date.isoformat(), entry_b.timeslot.period_no)] = entry_a.subject_id`  (R: A's subject sits in B's period)

Pass `placed` into `_pick_partner`.

**A3. Candidate evaluation in `_pick_partner()` (exchange.py:158).** After the existing availability checks pass for a candidate, compute violations:

- **D-side student adjacency:** `eff_d = _effective_subject_map(..., day, on_date, placed)`; violation if `entry_b.subject_id` appears at any period in `_adjacent_period_nos(db, day, a_period)` within `eff_d`.
- **R-side student adjacency:** `eff_r = _effective_subject_map(..., entry_b.timeslot.day, recovery_date, placed)`; violation if `entry_a.subject_id` appears adjacent to `b_period` in `eff_r`. NOTE: exclude `a_period`'s own base row on D and `b_period`'s own base row on R from the map before checking — that slot's subject is being replaced.
- **Daily-count guard (H8 parity):** count occurrences of the incoming subject in the effective map (after replacement); violation if it would exceed 2 that day. Applies to both D and R sides.
- **Teacher run-length guard:** helper `_teacher_day_periods(db, ver, teacher_id, day) -> set[int]` plus this plan's `reserved` entries for that date; placing the new period must not give the teacher **3+ time-adjacent consecutive teaching periods**. Check partner B on date D and absent teacher A on date R.

Scoring: keep the existing terms, add `score -= 100.0 * violations` and when `violations > 0` prefix the rationale with `"⚠ back-to-back {SUBJ} for students"` / `"⚠ 3 consecutive teaching periods for {name}"` (join multiple with "; "). The 100 penalty dwarfs the gap/fairness terms (max ~30), so any clean candidate beats any dirty one, while a dirty candidate still beats "no exchange".

**A4. Surface warnings on the approval card.** In `plan_summary()` (exchange.py:232), add per item: `"warning": item rationale startswith "⚠"` (boolean) — no schema change; warnings live in the rationale text. Frontend `apps/web/src/app/approvals/page.tsx` already renders rationale; additionally tint the card row amber when `warning` is true (small conditional class).

### Acceptance checks (A)

1. Craft seed data where section S has subject X at TUE P3 and partner B's only lesson is X at some slot such that the naive planner would move X into TUE P4 → planner must pick a different partner/lesson when one exists.
2. When the adjacency-creating candidate is the *only* option, exchange is still proposed and rationale starts with ⚠; approval card shows the warning.
3. Existing happy path unchanged: re-run the `docs/05-DEMO-SCRIPT.md` leave flow — plan builds, approve works, notifications fire, `/api/timetable/effective/{section}?date=` overlay still correct.
4. Idempotency preserved: calling `build_plan` twice still returns the existing plan.

---

## Feature B — Configurable constraints at timetable generation (half-days, anti-consecutive, teacher run cap)

### What the admin gets

The Generate button becomes a small options panel. All options default **off** → output identical to today.

| Option | Example | Type |
|---|---|---|
| Half days | WED and FRI end after P4 | per-day toggle + last-period select |
| No same-subject back-to-back | on/off | toggle (theory subjects only; labs exempt — H5 *requires* the block) |
| Max consecutive teaching periods per teacher | 3 | int, blank = off |

### B1. Solver — `services/backend/app/solver/timetable_model.py`

Add options dataclass + new `solve()` parameter:

```python
@dataclass
class SolveOptions:
    half_days: dict[str, int] = field(default_factory=dict)  # {"WED": 4} = WED ends after P4
    no_same_subject_consecutive: bool = False
    max_consecutive_teaching: int | None = None

def solve(data: TimetableInput, opts: SolveOptions | None = None, time_limit_s: float = 20.0) -> SolveResult:
```

- **Half days — slot filtering, not a constraint.** At the top of `solve()`, before `precheck()`: `data.slots = [s for s in data.slots if not (s.day in opts.half_days and s.period_no > opts.half_days[s.day])]`. `precheck()` then automatically produces the precise "Section X needs N periods/week but only M timeslots exist" message when half-days make demand infeasible — no new explanation code needed. (Copy the input or filter into a local var; don't mutate the caller's list.)
- **H9 — no same-subject consecutive (only when toggled).** New assumption group `"no same-subject back-to-back"`. For each section, each **theory** subject, each adjacent pair `(a, b)` from `_consecutive_pairs(slots)`: `m.Add(x[(sec.id, sid, a)] + x[(sec.id, sid, b)] <= 1).OnlyEnforceIf(group)`. Add it in the existing `else:` branch beside H8 (line ~226).
- **H10 — teacher consecutive-run cap (only when set).** New assumption group `"teacher consecutive-teaching cap"`. Build per-day *chains* of consecutive slots (extend `_consecutive_pairs` into `_consecutive_runs(slots) -> list[list[int]]`, splitting at breaks). For each teacher, each run, each sliding window of length `k+1` where `k = opts.max_consecutive_teaching`: `m.Add(sum(w-vars of that teacher over window slots) <= k).OnlyEnforceIf(group)`. Reuse the existing per-teacher `keys` list at line ~250.
- Register both new groups in the `groups` dict (line ~184) **only when active**, so infeasibility explanations name them ("Conflicting constraint groups: teacher consecutive-teaching cap, …").

### B2. Persist the config per version — `services/backend/app/db/models.py`

New table (created automatically by the existing `Base.metadata.create_all` startup path; SQLite dev DB, no migration tooling in this repo):

```python
class TimetableConfig(Base):
    __tablename__ = "timetable_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    config_json: Mapped[str] = mapped_column(Text)          # the SolveOptions as JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

Why: `/status` and the grid header can show *what rules produced version N* — demo-friendly and needed to regenerate comparably. (16th table; update the "15 tables" mentions in CLAUDE.md/docs.)

### B3. Tools — `services/backend/app/tools/timetable.py`

- `generate_timetable(time_limit_s=8.0, options: SolveOptions | None = None)` → pass to `solve()`; on success also `db.add(TimetableConfig(version=version, config_json=json.dumps(asdict(options or SolveOptions()))))`.
- `latest_version` untouched. Optionally add `get_version_config(db, ver)` returning the parsed JSON for the API.

### B4. API — `services/backend/app/api/timetable.py`

Pydantic request model on `POST /generate` (line 34), optional body so the old no-body call still works:

```python
class HalfDayIn(BaseModel):
    day: str                      # MON..FRI — validate against existing TimeSlot days
    last_period: int = Field(ge=1)

class GenerateIn(BaseModel):
    half_days: list[HalfDayIn] = []
    no_same_subject_consecutive: bool = False
    max_consecutive_teaching: int | None = Field(None, ge=1)
```

Validate: each `day` exists in the timeslot grid; `last_period` < max period of that day (else 422 "half day would remove all/no periods"). Map to `SolveOptions`, call `generate_timetable(options=...)`. Extend `GET /status` response with the latest version's config summary.

### B5. Frontend — `apps/web/src/app/timetable/page.tsx`

- Around the Generate button (line ~165): collapsible "Constraints" panel (glassmorphic, consistent with existing `glass-*` classes): five day checkboxes each with a last-period `<select>` (enabled when checked), the anti-consecutive toggle, the max-consecutive-teaching number input.
- `generate()` (line 105) posts the `GenerateIn` body; on success show the config summary alongside the existing "Generated v{n}…" line (e.g., "half days: WED≤P4, FRI≤P4 · no back-to-back subjects").
- Grid rendering: on half days the cut periods simply have no entries — render those cells as an em-dash with muted styling so the grid doesn't look broken (grid periods come from all TimeSlots, which are not filtered).

### Interplay with Feature A / exchanges

None structural — exchanges read `TimetableEntry` rows, and half-days just mean fewer entries exist on those days. The adjacency helpers in Feature A use real slot times, so they stay correct under any config.

### Acceptance checks (B)

1. `POST /api/timetable/generate` with empty body → result identical in shape to today; new version + config row (`{}` config).
2. Body `{"half_days":[{"day":"WED","last_period":4}]}` → new version has **zero** entries at WED P5–P7 for every section; if demand no longer fits, response is 422 with the precheck slots message.
3. `{"no_same_subject_consecutive": true}` → for every section/day, no theory subject occupies two time-adjacent periods (script-check over the version's entries); labs still form their block.
4. `{"max_consecutive_teaching": 3}` → no teacher has 4 time-adjacent teaching periods in the version.
5. Infeasible combo (tight demand + aggressive half-days + cap) → 422 names the conflicting groups.
6. UI: options round-trip, defaults produce old behavior, config summary shown.

---

## Implementation order & chores

1. Feature A (exchange.py + plan_summary + approvals page tint) → run acceptance A1–A4.
2. Feature B backend (solver → models → tools → API) → curl checks B1–B5 via `/docs` Swagger.
3. Feature B frontend panel → check B6.
4. Update `docs/04-ROADMAP.md` (Phase 2.2 done), `docs/05-DEMO-SCRIPT.md` (add "generate with half-days" beat), CLAUDE.md status line + table count (15 → 16).
5. `python -m graphify update .` after code changes.

**Testing note:** repo has no pytest suite; acceptance is via seeded dev DB + curl/Swagger + UI walkthrough per `docs/05-DEMO-SCRIPT.md`. Write throwaway verification scripts in scratch, not the repo.
