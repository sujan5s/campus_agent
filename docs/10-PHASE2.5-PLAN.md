# 10 — Phase 2.5 / 2.6: The assistant does the data entry too

> Status: **2.5 implemented 2026-08-28; 2.6 (speed + minimal change) 2026-08-28.**
> Extends Phase 2.4 (`docs/09-PHASE2.4-PLAN.md`).

## 1. What was wrong

Phase 2.4 let an admin write scheduling *rules* in English. Everything else still
went through the Setup forms by hand, because the assistant was built to **refuse**
anything it could not find:

> "Add a teacher John who takes DBMS for CSE-7A"
> → *No teacher matches 'John'. Add them in Data Setup first.*

That refusal was described as a safety property. It is not. It is the system
handing the repetitive work back to the person it was supposed to do it for — and
in a project whose whole premise is automating campus operations, it was the wrong
default in the most visible place.

The distinction Phase 2.4 conflated:

| | 2.4 | 2.5 |
|---|---|---|
| Refusing to act on missing data | "safety" | **removed** — the assistant creates it |
| Typed, validated, previewed writes | safety | **kept** — it is what makes creating safe |

## 2. What the assistant can now do

`app/tools/ops.py` is a registry of **23 operations** covering every piece of
timetable master data, not just rules.

| Area | Operations |
|---|---|
| Subjects | `add_subject` · `edit_subject` · `remove_subject` |
| Teachers | `add_teacher` · `edit_teacher` · `remove_teacher` · `set_teacher_subjects` |
| Rooms | `add_room` · `edit_room` · `remove_room` |
| Classes | `add_class` · `edit_class` · `remove_class` |
| Who teaches what | `assign_teacher` |
| Open electives | `add_elective_band` · `add_elective_option` · `remove_elective_band` |
| Rules | `add_rule` · `edit_rule` · `remove_rule` · `enable_rule` · `disable_rule` |
| Action | `generate_timetable` |

Each is an `OpSpec` carrying `validate` (against live data), `describe` (English for
the preview), `apply` (the write), and a `destructive` flag the UI colours red.

## 3. The two ideas that make a whole sentence work

### Forward references

"Add a teacher John who takes a new subject DBMS for CSE-5A" is three operations,
and the second refers to something the first has not created yet. `plan()` walks
the batch **in order** carrying a `PlanCtx`, and each op registers what it will
create through a `note` callback. Later ops — including rules — see it.

For the rule validator this needed more than a name set. `tools/constraints.py`
resolves teachers and subjects to objects with ids, so a pending entity is inserted
into its `Ctx` as a `_Stub` carrying just the attributes that validator reads, with
a **negative id that is never persisted**. `run()` re-validates every op against the
real database as it applies it, where the entity now exists with its real id.

That is what makes this work:

```
add_class    CSE-2A, semester 2
add_rule     semester 2: at most 5 periods per day     <- semester 2 did not exist a moment ago
add_teacher  Dr. Aditi Sharma
add_rule     Dr. Aditi Sharma is unavailable on FRI    <- nor did she
```

### Implied fixups

Assigning a teacher to a subject they are not qualified for **adds the
qualification** rather than erroring. The admin asked for the outcome; chasing the
prerequisite is precisely the busywork being removed. The preview says so:

```
CSE-5A CS501 → Dr. John Doe (also qualified them for it)
```

Same for an elective option whose teacher is not yet mapped to its subject.

Other detail the assistant fills in rather than asking for: a new teacher's email is
derived from their name (`priya.menon@campus.edu`, uniquified), and subject codes are
invented to match the conventions visible in the existing data.

## 4. What is still enforced

Widening what the assistant may do did not weaken how it does it:

* **The op vocabulary is closed.** An unknown op is rejected listing the 23 real ones.
* **Every op is validated against live data** before the preview and again as it runs.
* **Range and type checks stand** — semester 99, a room type that is not one of the
  five, a negative capacity are all refused with a readable message.
* **The whole plan is previewed in English** and applied on one confirmation.
  Destructive steps are flagged and coloured; the model is told to prefer `edit_*`
  over remove-and-recreate.
* **A batch is one transaction.** `run()` applies in order and commits once; a
  failure is reported per-op.

## 5. Architecture

```
sentence
   ↓  POST /api/assistant/interpret          app/api/assistant.py
   ↓  system prompt + full campus context (classes, subjects, teachers, rooms,
   ↓  elective bands, rule catalog, existing rules with ids)
   ↓  → model returns {"ops": [...], "notes": "..."}
   ↓
   ↓  opsmod.plan(db, ops)                   app/tools/ops.py
   ↓  validate in order, carrying pending creations
   ↓  → preview: description | error, per op
   ↓
   ↓  ——— admin confirms ———
   ↓
   ↓  POST /api/assistant/apply
   ↓  opsmod.run(db, ops) → re-validate, apply, commit once
   ↓  optional generate_timetable → CP-SAT
```

`POST /api/constraints/interpret` and `/apply` remain as thin delegates so older
clients keep working; there is one implementation.

## 6. Verified live (2026-08-28, `gemini-3.6-flash`)

**One sentence, a whole new cohort** — *"we are opening a new second-semester class
CSE-2A with 70 students. It needs subjects Maths-2, Physics-2 and a Programming Lab,
two teachers to cover them, and a new classroom LT-501."*

```
add_room       add classroom LT-501 (capacity 70)
add_subject    add subject CS201 "Maths-2" — semester 2, 4 periods/week
add_subject    add subject CS202 "Physics-2" — semester 2, 4 periods/week
add_subject    add subject CS203 "Programming Lab" — semester 2, 2 periods/week (lab)
add_class      add class CSE-2A — semester 2, 70 students
add_teacher    add teacher Dr. Aditi Sharma (CSE, ≤5h/day) teaching CS201, CS202
add_teacher    add teacher Prof. Rahul Verma (CSE, ≤5h/day) teaching CS203
assign_teacher CSE-2A CS201 is taught by Dr. Aditi Sharma
assign_teacher CSE-2A CS202 is taught by Dr. Aditi Sharma
assign_teacher CSE-2A CS203 is taught by Prof. Rahul Verma
generate_timetable
→ 11 applied, timetable v36 — 87 lessons + 7 elective periods
```

It inferred the lab flag from "Programming Lab", invented codes matching the existing
convention, sized the room to the class, derived both emails, and appended
`generate_timetable` unprompted.

**Rules about things created in the same breath** — all three validated:
`semester 2: at most 5 periods per day` · `Dr. Aditi Sharma is unavailable on FRI at
P5, P6, P7` (from "friday afternoons") · `CSE-2A: WED ends after P4`.

**Validation still bites:**

```
[REJ] add_room         Room 'LT-401' already exists — edit it instead.
[REJ] add_teacher      Ghost would teach unknown subject(s) NOPE99 — add those
                       subjects in the same request.
[REJ] assign_teacher   No class named 'CSE-9Z'.
[REJ] teleport_students  'teleport_students' is not something I can do. Available: …
[REJ] add_class        Semester must be between 1 and 12, got 99.
```

The remove ops were exercised by using them to clean up every entity these tests
created.

## 7. Phase 2.6 — making it fast, and making it leave things alone

Two problems showed up the moment the assistant was used in anger.

### 7.1 A big request timed out

*"create a new class 2a, add 5 subjects …, add 5 new teachers … and one classroom"* hit the
45-second budget. Measured, the cause was unambiguous:

```
context in : 7,091 chars (~1,772 tokens)
reply out  : 3,253 chars, 18 ops, 31.1s
```

The admin was waiting on **output** tokens, and that request is genuinely 18 operations written
longhand. So the fix was to let the model say the same thing in fewer tokens — **bulk forms**:

```json
{"op": "add_subjects", "defaults": {"semester": 2, "periods_per_week": 4},
 "items": [{"code": "ENG201", "name": "English"}, ...]}
{"op": "add_teachers", "defaults": {"assign_to": "2A"},
 "items": [{"name": "Dr. Sunita Sharma", "subjects": ["ENG201"]}, ...]}
```

`expand()` in `app/tools/ops.py` unpacks these into exactly the individual ops as before,
*prior to* validation — so the preview, per-step errors and apply path are untouched. A
teacher's `assign_to` also folds in what would otherwise be a second op per subject.

Result on the same request: **31.1s → 15.4s**, output 3,253 → 1,404 chars, 18 ops → 5.
The timeout was raised to 90s as a backstop, because provider latency for one identical
request was measured between **10.9s and 58.7s** — the variance is on their side.

> **Tried and rejected:** `thinking_level="low"` on the Gemini client, on the theory that
> reasoning tokens dominated. Measured *slower* (58.7s vs 10.9s default) and was not adopted.
> Latency here is provider variance, not reasoning configuration.

### 7.2 A small change rewrote the whole timetable

CP-SAT has no notion of "the answer you gave last time". Re-solving after adding one subject
returned a completely different — equally optimal — week, which is useless once a timetable has
been published.

`PreviousSolution` feeds the current schedule back into the model two ways:

* **as hints** (`AddHint`) on the placement, teacher-choice, home-room and elective variables,
  which is also what makes it fast;
* **as a penalty**, `stability_weight × (number of lessons that moved)`, so keeping the
  schedule is an actual objective rather than a tiebreak.

`generate_timetable(preserve=True)` is the default; `preserve=False` (or `?fresh=true`, or
`generate_timetable {"fresh": true}` from the assistant) re-plans from scratch. The result
reports `lessons_moved`, which the UI shows as *"nothing already scheduled had to move."*

Measured on the seeded campus:

| | time | lessons moved |
|---|---|---|
| regenerate, nothing changed — preserve | **0.7s**, proved optimal | **0** |
| regenerate, nothing changed — fresh | 8.1s, hit the time limit | 64 of 71 |
| add a 2-period subject — preserve | **0.6s**, proved optimal | **0** |
| add a 2-period subject — fresh | 8.1s, hit the time limit | most of the week |

The warm start does not merely bias the search: it lets the solver *prove* optimality inside a
second where a cold solve exhausts its eight-second budget without doing so.

> **Two bugs found while verifying this**, both of which would have made the feature silently
> useless rather than visibly broken:
> * `PreviousSolution` records lessons against timeslot **ids**, but the model's `x` variables
>   are keyed by slot **index**. Every hint silently missed, and the first measurement showed
>   *more* churn with preservation on. Fixed by translating through `slot_index`.
> * A previous solution referencing a since-deleted subject crashed the loader on
>   `e.subject.needs_lab`. Such a lesson is now skipped — there is nothing left to preserve.

## 8. Known gaps

* **Timeslots are not editable by the assistant** — the period grid is still seeded.
  A `set_period_grid` op is the obvious next one.
* **No dry-run against the solver.** A plan can be applied and only then turn out
  infeasible; the precheck explains it, but the assistant cannot yet warn at preview
  time. Running `precheck()` over the simulated post-plan state would fix this.
* **No undo.** A batch commits atomically but there is no reverse operation; a
  destructive plan needs the preview read carefully.
* **The offline parser covers only rules and rooms.** Creating teachers, subjects
  and classes needs the model.
* **Stability is all-or-nothing.** `preserve` protects the whole timetable; there is no way to
  say "keep semester 7 exactly, re-plan semester 5". Per-scope stability weights would do it.
* **Provider latency is unmanaged.** A request can take 10s or 60s for the same input. Streaming
  the plan as it arrives would hide most of that.
