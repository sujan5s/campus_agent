# 06 — Phase 2.1 Plan: Period-Exchange Substitution (replaces ranked-cover model)

> **For the implementing model:** This is a complete, self-contained spec. Read it top to
> bottom before writing code. The approval flow (LangGraph `interrupt()` → approval card →
> resume → notifications) is verified working and MUST NOT change. Only the *planning logic*,
> *plan data shape*, and *timetable views* change.

## 1. Why this change

The current Phase 2 model assigns a **substitute who covers the absent teacher's subject**
(ranked: subject match > dept > free). That is not how this college actually operates.

**Real-world practice (what we must implement):** teachers **exchange periods**. When
Teacher A is on leave, another teacher B *of the same section* moves their own lesson into
A's slot on the leave date, and A **recovers** the missed lesson later in B's vacated slot.
No subject is ever taught by the wrong teacher; subject weekly-period counts are preserved —
lessons just swap dates.

### Concrete example

- Teacher **A** (Anita) is on leave **Tue 2026-07-21**. She has CS704 with CSE-7B at **TUE P5**.
- Teacher **B** (Suresh) also teaches CSE-7B — CS701 at **THU P2**.
- **Exchange:**
  - **Tue P5 (leave date):** B teaches **his own CS701** to CSE-7B (Thursday's lesson advanced).
  - **Thu P2 (recovery date, after A returns):** A teaches **her CS704** to CSE-7B (Tuesday's lesson recovered).
- Net effect: both subjects keep their weekly counts; students always have the right
  teacher for the right subject; only two dates swapped.

## 2. What stays exactly the same (do not touch)

- Leave apply/approve flow (`app/api/leaves.py`) and the proactive trigger on approval.
- The Substitution Agent node structure in `app/agents/specialists/substitution.py`:
  `interrupt()` pause, Approval row with `langgraph_thread_id`, resume via
  `POST /api/approvals/{id}/decide` → `Command(resume={"action": ...})`. **Everything before
  `interrupt()` must remain safe to run twice** (node body re-executes on resume) —
  keep the idempotency pattern (check for existing plan rows by `plan_id` before creating).
- Approval `kind="substitution_plan"` (reuse it; avoids touching approvals API filtering).
- The supervisor `task_spec` **merge** behavior (it merges, never overwrites — `leave_id`
  flows through it; this was a deliberate earlier fix).
- Notification mechanics (`notify_user`, `/inbox`, unread badges, polling).
- The **original timetable**: `timetable_entries` rows are NEVER modified by exchanges.
  Exchanges are a dated overlay only.
- APScheduler safety sweep concept in `main.py` (just re-point its "does a plan exist?"
  query at the new table).

## 3. Data model — new table (do NOT alter existing tables)

⚠️ **Gotcha:** we use `Base.metadata.create_all` (no Alembic). SQLite `create_all` creates
**new tables only** — it will NOT add columns to existing tables. Therefore: add a **new
table**, leave `substitutions` untouched (it is legacy history from the old model).

Add to `app/db/models.py`:

```python
class PeriodExchange(Base):
    """One exchanged pair: A's missed lesson on the leave date is taken by partner B
    (teaching B's own subject), and A recovers it in B's slot on recovery_date."""
    __tablename__ = "period_exchanges"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64))              # "exchange-leave-<leave_id>"
    leave_id: Mapped[int] = mapped_column(ForeignKey("leaves.id"))

    # Leave-date side: A's lesson that is missed
    absent_entry_id: Mapped[int] = mapped_column(ForeignKey("timetable_entries.id"))
    leave_date: Mapped[date] = mapped_column(Date)                # D

    # Partner side: B's lesson whose slot hosts the recovery. NULL = no exchange found.
    partner_entry_id: Mapped[int | None] = mapped_column(ForeignKey("timetable_entries.id"), nullable=True)
    recovery_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # R

    absent_teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    partner_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | confirmed | rejected
    rationale: Mapped[str] = mapped_column(Text, default="")
```

## 4. Exchange-planning algorithm

New module **`app/tools/exchange.py`** exposing the SAME four function names the agent node
already imports (`build_plan`, `plan_summary`, `apply_plan`, `reject_plan`) plus
`plan_id_for(leave_id) -> "exchange-leave-<id>"`. Then switch the imports in
`app/agents/specialists/substitution.py` from `app.tools.substitution` to
`app.tools.exchange`. Keep `notify_user` where it is (or move it to a shared module).

### `build_plan(db, leave)` — for each affected lesson of A

Affected lessons = latest-version `timetable_entries` of teacher A whose `timeslot.day`
falls on a date within `[leave.from_date, leave.to_date]` (reuse the existing
`_leave_dates` weekday-mapping logic from `app/tools/substitution.py`).

For each affected lesson `entry_a = (section S, subject X, slot P)` on leave date `D`:

1. **Candidate partners** = latest-version entries `entry_b` where:
   - `entry_b.section_id == S` and `entry_b.teacher_id != A` (same section, different teacher)
   - **B is free at slot P on date D**: B has no timetable entry at `(D.weekday, P.period_no)`,
     B is not on approved leave covering D, and B is not already used at `(D, P)` by another
     exchange in this plan or any confirmed exchange.
   - **Recovery date R exists**: R = the nearest date **strictly after `leave.to_date`**
     whose weekday equals `entry_b.timeslot.day` (same week if that weekday is still ahead,
     else next week). Constraints on R:
     - A is free at `entry_b`'s slot on R (no entry of A at that weekday/period, not on leave,
       no conflicting exchange already using A at `(R, Q)`).
     - B is not on approved leave on R (B must actually be absent-from-that-slot willingly —
       B simply doesn't teach it; no constraint needed on B beyond not double-booking the
       same `(entry_b, R)` occurrence twice within/across plans).
   - **Lab exclusion**: skip `entry_b` if its subject `needs_lab`; and if `entry_a`'s subject
     `needs_lab`, mark the item "manual handling required — lab block" with no partner
     (splitting a consecutive lab block breaks it; HOD handles labs manually).
   - Each `(partner_entry_id, recovery_date)` pair may be used **at most once** per plan
     and must not collide with existing confirmed exchanges.

2. **Score candidates** (higher = better) and pick the best:
   - `- 2.0 × (R − D).days` — prefer the nearest recovery date (syllabus pacing)
   - `- 0.5 × exchanges_already_assigned_to_B_in_this_plan` — spread load
   - `- 0.1 × B's weekly lesson count` — fairness toward lighter-loaded teachers
   - Build a human-readable `rationale`, e.g.
     `"Suresh Shetty teaches CS701 to this section; swap with THU P2, recovery on 2026-07-23 (2 days later)"`.

3. If no valid candidate: create the row with `partner_entry_id=NULL` and
   `rationale="NO EXCHANGE AVAILABLE — needs manual arrangement"`. The HOD sees this
   before approving (same philosophy as the old "no cover").

4. **Idempotency**: first line of `build_plan` checks
   `db.query(PeriodExchange).filter_by(plan_id=plan_id_for(leave.id))` — if rows exist,
   return them unchanged (interrupt re-execution safety).

- **Room rule:** each lesson keeps the room of the slot it lands in (section stays in its
  home room; only teacher+subject swap). No room changes anywhere.
- **No student clash is possible by construction** — both sides of the swap are lessons of
  the *same section*, so the section's occupancy at each slot is unchanged.

### `plan_summary(db, leave_id) -> dict`

Shape consumed by the approval card and the agent's final response:

```json
{
  "teacher": "Anita Rao", "from_date": "...", "to_date": "...", "reason": "...",
  "lessons_affected": 2, "exchanged": 2,
  "items": [{
    "leave_date": "2026-07-21", "leave_day": "TUE", "leave_period": 5, "leave_time": "13:45-14:35",
    "section": "CSE-7B", "room": "LT-301",
    "missed_subject": "CS704", "missed_subject_name": "...",
    "partner": "Suresh Shetty",                     // null if no exchange
    "partner_subject": "CS701", "partner_subject_name": "...",
    "recovery_date": "2026-07-23", "recovery_day": "THU", "recovery_period": 2, "recovery_time": "...",
    "rationale": "..."
  }]
}
```

### `apply_plan(db, leave_id)` (on HOD approve)

- Set all plan rows `status="confirmed"`.
- Notify **each partner B**: title `"Period exchange scheduled"`, body like
  `"On 2026-07-21 (TUE P5, LT-301) you teach CS701 to CSE-7B in place of Anita Rao. Your THU P2 lesson on 2026-07-23 will be taken by her (CS704 recovery)."`
- Notify **A**: `"Your leave is covered by period exchanges"` + per-lesson summary of
  where each missed lesson is recovered.
- Return counts for the agent's final response.

### `reject_plan(db, leave_id)` (on HOD reject)

- Set all plan rows `status="rejected"`. No notifications. (Same as today.)

### Agent node text

Update the pre-interrupt payload and post-resume `final_response` strings in
`app/agents/specialists/substitution.py` to speak in exchange terms
("proposed N period exchanges; recovery dates preserved subject hours") — structure unchanged.

### Safety sweep (`main.py`)

In `_substitution_sweep`, replace the "plan exists?" check: query `PeriodExchange` by
`plan_id_for(leave.id)` instead of `Substitution`. Nothing else changes.

## 5. Dated (effective) timetable — separate view, original untouched

### Backend — add to `app/api/timetable.py`

1. **`GET /api/timetable/effective/{section_name}?date=YYYY-MM-DD`** (any authenticated user)
   - Take the section's normal grid for that weekday (latest version).
   - Overlay **confirmed** exchanges:
     - cell where `leave_date == date` and entry == `absent_entry_id` → show partner B +
       partner's subject, flag `"exchanged": true`, include
       `swap: {with: "Anita Rao", their_subject: "CS704", counterpart_date: "2026-07-23", counterpart_period: 2}`
     - cell where `recovery_date == date` and entry == `partner_entry_id` → show A + missed
       subject, flag `"exchanged": true`, `swap: {...counterpart is the leave date...}`
   - If the date's weekday is SAT/SUN → return empty grid with a note.
   - Response: `{section, date, day, periods: [...], entries: [{period, subject, subject_name, teacher, room, exchanged, swap?}]}`

2. **`GET /api/timetable/exchanges?from=YYYY-MM-DD&to=YYYY-MM-DD`** (any authenticated user;
   default range = today → +14 days) — flat list of confirmed exchanges in range, each item
   carrying both sides (leave-date side and recovery side) with section, periods, teachers,
   subjects, dates. This powers the "who got exchanged, on which date" board.

### Frontend — new page `apps/web/src/app/exchanges/page.tsx` (shown separately, per requirement)

Follow the exact conventions of `apps/web/src/app/approvals/page.tsx` (glass-panel cards,
`api<T>()` client from `../../lib/api`, `getToken()` redirect guard, lucide icons).

Two stacked sections:

1. **Exchange board** (top): table of upcoming confirmed exchanges from
   `/timetable/exchanges` — columns: Date · Slot · Section · Lesson taught (teacher + subject)
   · In place of · Recovery (date + slot). Highlight leave-date rows vs recovery rows with
   two badge colors (e.g. amber "exchanged in", emerald "recovery").
2. **Effective day grid** (below): section dropdown + date input → renders
   `/timetable/effective/...` as a single-day period strip (P1–P7 cards). Exchanged cells get
   an amber border + a `⇄` badge; tooltip/subtext shows the swap counterpart
   ("⇄ with Anita Rao — recovery THU P2, 23 Jul").

Add a sidebar link on the dashboard (`apps/web/src/app/page.tsx`): "Exchanges" with the
`ArrowLeftRight` lucide icon, next to the existing Leaves/Approvals/Inbox links.
(⚠️ Read `page.tsx` before editing — it is large; only touch the sidebar nav block.)

### Approval card update (`apps/web/src/app/approvals/page.tsx`)

Replace the table columns to show the pair per row:
`Leave date/slot · Class · Missed subject · Partner teaches · Recovery date/slot · Why`.
Update the `PlanItem` interface to the new `plan_summary` shape (section 4). Show
`no exchange` in rose where partner is null. Header stat becomes
`{exchanged}/{lessons_affected} lessons exchanged`.

## 6. Task order for implementation

1. `app/db/models.py` — add `PeriodExchange` (new table only). Restart backend once so
   `create_all` creates it; verify with a quick sqlite query.
2. `app/tools/exchange.py` — `plan_id_for`, `build_plan`, `plan_summary`, `apply_plan`,
   `reject_plan` (mirror the structure/helpers of `app/tools/substitution.py`; reuse or
   import its `_leave_dates`, `_on_leave`, `_latest_version` helpers).
3. `app/agents/specialists/substitution.py` — switch imports to `app.tools.exchange`,
   update wording. Interrupt/resume structure untouched.
4. `main.py` — sweep query points at `PeriodExchange`.
5. `app/api/timetable.py` — the two new GET endpoints.
6. Frontend: approvals card rework → new `/exchanges` page → sidebar link.
7. Docs: check off in `docs/04-ROADMAP.md` (add a "Phase 2.1 — period-exchange model"
  entry with date), update the F2 bullet in `CLAUDE.md` (exchange model, `/exchanges` page),
  and adjust `docs/05-DEMO-SCRIPT.md` Act 3 (the key sentence now explains the exchange +
  recovery + "original timetable untouched — dated overlay").
8. `python -m graphify update .` after code changes.

## 7. Verification checklist (run all before declaring done)

⚠️ **Restart discipline:** the backend does NOT reliably hot-reload router/model changes.
After edits: kill the old process (check for zombies holding port 8000 — this bit us twice;
`Get-NetTCPConnection -LocalPort 8000` → `Stop-Process`), then `python main.py` fresh.

1. `GET /openapi.json` lists the two new timetable endpoints.
2. **Approve path:** login as `anita.rao@campus.edu`/`faculty123` → apply leave (future TUE)
   → as admin approve leave → approval card shows exchange pairs **with recovery dates** →
   approve plan → verify:
   - `/api/timetable/effective/CSE-7B?date=<leave TUE>` shows partner teaching their own
     subject in Anita's slot, flagged `exchanged`.
   - `/api/timetable/effective/CSE-7B?date=<recovery date>` shows Anita teaching CS704 in
     the partner's slot.
   - Partner's `/inbox` has the exchange notification; Anita's has the recovery summary.
   - `timetable_entries` rows unchanged (compare count + a checksum/select before vs after).
3. **Reject path:** second leave → reject plan → all `period_exchanges` rows `rejected`,
   effective view shows the normal grid, no notifications.
4. **No-partner case:** if reproducible (e.g., a slot where no same-section teacher is
   free), card shows "NO EXCHANGE AVAILABLE" and approve still works for the rest.
5. **Restart resilience:** restart backend mid-pause (after card appears, before decision)
   → decide → resume still works (checkpointer + sweep don't duplicate plans — idempotency).
6. Frontend: `cd apps/web && npx tsc --noEmit` exits 0; `/exchanges` page renders board +
   day grid; exchanged cells highlighted.
