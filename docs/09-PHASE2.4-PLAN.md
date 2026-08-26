# 09 — Phase 2.4: Constraint Registry, Multi-Semester, Teacher Assignments & Open Electives

> Status: **implemented 2026-08-25**. Supersedes the ad-hoc `SolveOptions` request body
> introduced in Phase 2.2/2.3 — those rules are migrated into the registry automatically.

## 1. Why

Phase 2.2/2.3 let an admin tick a few constraints in a panel on `/timetable`. Those rules
lived in one request body and survived only as a JSON snapshot attached to the generated
version. They could not be listed, edited, disabled, or reasoned about after the fact, and
the set of possible rules was whatever had been hard-coded into the panel.

Four things were missing for a real college:

1. **Different semesters need differently-shaped weeks.** A sem-3 cohort and a sem-7 cohort
   do not run the same day length or the same rules.
2. **Admins decide who teaches what.** The solver picking any qualified teacher is fine for
   a demo, not for a department where a specific faculty member owns a specific subject for
   a specific class — and where one teacher legitimately teaches across several semesters.
3. **Open electives (sem 6/7).** All classes of the semester sit in the same band of
   periods, and inside it several baskets run *in parallel* with students split across them.
4. **New rules without a code change.** An admin should be able to state a rule in English,
   see it, edit it later, and have the LLM amend a rule that already exists.

## 2. The central idea: a constraint registry

A `constraints` table is the single source of truth for generation. The solver no longer
receives hand-assembled options; `POST /api/timetable/generate` takes **no body** and
compiles the registry instead.

```
Constraint(id, kind, scope_type, scope_value, params_json, priority,
           weight, enabled, source, origin_prompt, description, created_at, updated_at)

scope_type ∈ global | semester | section     resolution: section > semester > global
priority   ∈ hard | soft                     soft rules become weighted objective terms
source     ∈ seed | ui | llm                 origin_prompt keeps the sentence that made it
description                                  the rendered English form shown everywhere
```

`app/tools/constraints.py` holds three things:

* **`CATALOG`** — the whitelist of kinds. Each `Kind` knows its allowed scopes, its UI form
  fields, a validator that normalises params **against real DB entities**, and a renderer
  that produces the English `description`. This is what makes the LLM path safe: a rule kind
  that is not in the catalog, a teacher who does not exist, a period outside the grid — all
  are rejected by the same validator the UI form uses, and never reach the solver.
* **CRUD helpers** (`create` / `update` / `delete` / `list_constraints`), used by both the
  API and the LLM apply path. Kinds marked `unique_per_scope` rewrite the existing row for
  that scope instead of stacking duplicates.
* **`compile_options(db)`** — registry rows → `SolveOptions`.

`ensure_defaults(db)` seeds the registry on first use, carrying over the rules of the most
recent `TimetableConfig` snapshot, so an existing database keeps generating what it did
before the upgrade.

### Kinds shipped in v1

| kind | scopes | what it does |
|---|---|---|
| `half_day` | global / semester / section | day ends after period N |
| `no_same_subject_consecutive` | global / semester / section | H9, theory only, ON by default |
| `max_consecutive_teaching` | global / semester / section | H10 teacher run cap |
| `subject_daily_max` | global / semester / section | H8 spread limit (was hard-coded at 2) |
| `max_periods_per_day` | global / semester / section | cap on a class's day, electives included |
| `class_slot_ban` | semester / section | this class is free at given days/periods |
| `teacher_unavailable` | global | teacher never scheduled at given days/periods |
| `teacher_max_daily` / `teacher_max_weekly` / `teacher_max_consecutive` | global | per-teacher caps |
| `subject_slot_ban` | global | e.g. "no labs in P1" |
| `subject_preferred_periods` | global | **soft** — penalty for placing it elsewhere |
| `elective_fixed_slots` | semester | pin an elective band to given day×period slots; extra band periods still float |
| `avoid_gaps` | global | **soft** — penalise a free period with classes either side |

## 3. Solver changes (`app/solver/timetable_model.py`)

`SolveOptions` keeps its Phase 2.3 top-level fields (they are now the *global* defaults) and
gains `semester_rules`, `bans`, `preferred`, `avoid_gaps_weight` and `teacher_caps`.
`SectionRules` is kept as an alias of the new `ScopeRules` so existing imports still work.
`_resolve(opts, section)` merges global ← semester ← section for every scoped rule.

New hard constraints:

* **H11 pinned teachers.** `TimetableInput.assignments` maps `(section_id, subject_id) →
  teacher_id`; the corresponding `y` variable is fixed. Unpinned pairs are still chosen by
  the solver, so an admin only fills in what they care about.
* **H11 open-elective bands.** Group variables `g[band, slot]` choose the band's periods.
  Every section of that semester is forced idle in those slots
  (`Σ x[sec,*,slot] + g[band,slot] ≤ 1`), each basket's teacher is marked busy, and rooms
  used by a basket are reserved. Two bands sharing a room or a teacher may not overlap.
* **H12 availability bans.** Teacher / subject / class bans pin the relevant variables off.

Rooms hosting an elective basket **leave the home-classroom pool** — that is what keeps room
allocation sound without modelling per-slot classroom sharing, and the precheck says so in
plain language when it leaves too few classrooms.

Prechecks were extended to cover: elective periods eating into a section's week, per-day
caps that cannot fit the required periods, pinned teachers who are not mapped to the subject,
a teacher whose *total* pinned load across all semesters exceeds their own limits, baskets
sharing a room or a teacher, and bands aimed at a semester with no sections.

Assumption literals gained groups for pinned assignments, elective bands, availability bans
and per-day caps, so an infeasible combination still names the culprit.

## 4. Data model additions

| table | purpose |
|---|---|
| `constraints` | the registry above |
| `teaching_assignments` | `(section, subject) → teacher`, unique per pair |
| `elective_groups` | a band: name, semester, periods/week, needs_block, active |
| `elective_offerings` | one basket: subject + teacher + room + capacity |
| `timetable_entries.elective_group_id` | nullable tag marking a row as part of a band |

`create_all()` cannot add a column to an existing table, and the project has no Alembic yet,
so `app/db/session.py` gained `ensure_schema()` — an idempotent, additive-only
`ALTER TABLE … ADD COLUMN` pass listed in `_ADDED_COLUMNS`, run from `init_db()` and again
at startup. Anything structural still warrants a real migration.

An elective period is stored as **one row per section of the semester**, tagged with the
group, with subject/teacher/room pointing at the first basket. Every existing reader (grids,
the exchange overlay, the PDF) therefore keeps working unchanged, while the UI expands the
tag into the full basket list. `app/tools/exchange.py` treats a tagged row as *occupied but
not exchangeable* (the same treatment labs get) and marks every basket teacher busy once.

## 5. Natural language → typed operations

`POST /api/constraints/interpret` sends the model: the catalog, **the current rules with
their ids**, and the real days/periods/sections/semesters/subjects/teachers. It returns
operations, not prose:

```json
{"ops": [{"op": "create|update|delete|enable|disable", "id": 4,
          "kind": "half_day", "scope_type": "section",
          "scope_value": "CSE-7A", "params": {"last_period": 3}}],
 "notes": "one sentence for the admin"}
```

Because existing rows arrive with ids, "make that Wednesday half-day end at P3 instead"
becomes an `update`, not a duplicate. Every op is then run through `_preview()` — the same
validator as the form — and returned with either a rendered `description` (plus `before` for
an update) or an `error`. **Nothing is written.** The admin confirms, and `POST
/api/constraints/apply` commits only the ops that validated.

Two robustness details worth keeping:

* **Model choice matters more than it looks.** `gemini-flash-latest` — the previous default —
  is listed by `GET /v1beta/models` but *hangs indefinitely* on `generateContent`, with no error
  and no disconnect; `gemini-2.5-flash` now returns a 404 naming `gemini-3.6-flash` as its
  replacement. `.env` is pinned to `gemini-3.6-flash` (≈4–10s per call). If the Ask-AI box
  reports the model could not be reached, check the *model* before the key: `GET
  /v1beta/models` with the key confirms auth independently of any single model.
* The call is bounded by `LLM_TIMEOUT_S` (30s) on a **daemon** thread. LangChain offers no
  cancellation, so on timeout the worker is abandoned — and a `ThreadPoolExecutor` worker,
  being non-daemon, would then block interpreter exit and uvicorn's auto-reload. A stalled
  provider degrades to the deterministic parser instead of hanging the admin's browser.
* `app/core/llm.py` gained `text_of(reply)`. Providers differ: some return `content` as a
  string, newer ones (Gemini, Claude with extended thinking) return a list of content
  blocks. `str()`-ing that yields a Python repr, which is not JSON. Every caller now goes
  through `text_of`.

With no API key (or an unreachable provider) a small deterministic parser handles the common
phrasings, so the demo never depends on the network.

## 6. API surface

| method | path | role | notes |
|---|---|---|---|
| GET | `/api/constraints` | any | rules + catalog + entity context + `llm` flag |
| POST | `/api/constraints` | admin | add one from the form |
| PATCH | `/api/constraints/{id}` | admin | edit params / scope / enabled |
| DELETE | `/api/constraints/{id}` | admin | remove |
| POST | `/api/constraints/interpret` | admin | sentence → previewed ops, commits nothing |
| POST | `/api/constraints/apply` | admin | commit previewed ops |
| GET/PUT | `/api/setup/assignments` | any / admin | the section × subject → teacher matrix |
| GET/POST/PUT/DELETE | `/api/setup/electives[/{id}]` | any / admin | elective bands |
| POST | `/api/timetable/generate` | admin | **no body** — compiles the registry |
| GET | `/api/timetable/status` | any | now also returns `active_rules` |

## 7. UI

New `/constraints` page (nav entry between Timetable and Leaves), three tabs:

* **Rules** — every rule grouped by scope, each with its English description, kind chip,
  hard/soft badge, a "from a prompt" badge showing the original sentence, and On/Off, edit
  and delete controls. Above it: the *Ask AI* box with the confirm-diff flow, and a
  structured Add-constraint form whose inputs are generated from the catalog's field types.
* **Teacher assignments** — the matrix grouped by semester → class → subject, each with
  `Auto — solver picks` or one of the teachers actually mapped to that subject.
* **Open electives** — band editor (name, semester, periods/week, consecutive block, active)
  with its parallel options (subject + teacher + room + capacity).

`/timetable` lost its constraints panel: it now shows a read-only "Rules in force" summary
with a link here, so there is exactly one source of truth. Elective periods render as a
violet cell listing every basket, in the grid and in the PDF export.

## 8. Verification (2026-08-25)

Independent checks against the stored timetable, not the solver's own report
(3 sections across 2 semesters, 72 lessons + a 3-period elective band):

```
[PASS] no class is double-booked
[PASS] no teacher is in two places at once
[PASS] all classes: at most 2 consecutive teaching periods per teacher
[PASS] all classes: no same-subject back-to-back periods
[PASS] all classes: CS703 is never scheduled at P1
[PASS] all classes: Dr. Anita Rao is unavailable on MON at P1, P2
[PASS] all classes: Dr. Meera Nair is unavailable on FRI at P6, P7
[PASS] semester 5: at most 4 periods per day for the class
[PASS] semester 7: at most 7 periods per day for the class
[PASS] CSE-7A: TUE ends after P3
[PASS] CSE-7B: THU ends after P4
[PASS] pin: CSE-7A CS701 -> Prof. Arjun Pai
[PASS] semester 7: OE-1 runs at MON-P3, TUE-P3
[PASS] OE-1: same 3 periods for all 2 sem-7 classes
```

Infeasibility still explains itself. Asking for "semester 7: at most 6 periods per day" when
those classes need 31 periods a week returns:

> Section CSE-7A needs 31 periods/week but its 'at most 6 periods per day' rule allows at
> most 30 — raise the cap or cut periods.

The LLM op pipeline was verified **live** (2026-08-26, `gemini-3.6-flash`) across a
four-prompt conversation:

| prompt | result |
|---|---|
| "no teacher should ever teach more than 3 periods in a row, and semester 5 classes should end by period 5 on friday" | one `update` (2→3) + one `create`, both applied |
| "actually make that friday cutoff period 4 instead for semester 5" | `update` of the rule it had just made — resolved "that friday cutoff" from context |
| "remove the rule about teachers teaching in a row" | `delete`, matched by description |
| "make Dr. Strange unavailable on Mondays" | no op — "Dr. Strange was not found in the teacher registry" |

Re-stating a rule that already exists produces an `update`, not a duplicate, because the
current rows are handed to the model with their ids. It was separately exercised against a
stubbed content-block reply, where a hallucinated class (`CSE-9Z`) and an invented kind
(`teleport_students`) were both rejected by the validator and never stored.

HTTP-level checks: faculty can read constraints (200) but not write (403); out-of-grid
periods and unknown teachers are rejected 422; an unqualified teacher cannot be pinned; two
elective baskets cannot share a room.

## 9. Demo data

`seed_phase24()` in `app/db/seed.py` runs on **every** startup and only adds what is
missing, so a pre-Phase-2.4 database gains the new demo data without being wiped: a sem-5
cohort (`CSE-5A` + `CS501`–`CS505`), a fourth classroom, and the sem-7 open-elective band
`OE-1` with two baskets (Blockchain in Seminar Hall B, IoT in the Main Auditorium).

## 10. Follow-ups (not in this phase)

* A rule kind whose params depend on its scope (currently only `elective_fixed_slots`,
  which resolves its band within the scope semester) reads the semester through the reserved
  `SCOPE_SEMESTER` param key that `validate()` injects and strips again. If a second such kind
  appears, promote this to a proper argument on `Kind.validate`.
* Per-basket student enrolment (who is in which elective) — capacity is recorded but not
  enforced against real headcounts.
* Elective bands are excluded from the leave/exchange flow; a basket teacher's absence still
  needs manual handling.
* `subject_preferred_periods` and `avoid_gaps` are the only soft rules; a general
  soft/weighted form for the other kinds would be a natural extension.
