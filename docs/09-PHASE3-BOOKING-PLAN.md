# 09 — Phase 3 (F3): Event & Venue Booking Agent

> Spec for the first half of Phase 3 in `04-ROADMAP.md`. F4 (Knowledge RAG) is a
> separate, later piece of work — this document covers **event booking only**.
> Feature statement: `01-FEATURES.md` §F3. Data model: `02-ARCHITECTURE.md` §3.

## 1. What we are building

A student club or a faculty member asks — in the UI form or in plain language in
chat — for a venue at a time. The Booking Agent:

1. **Extracts** the structured request (venue, date, window, headcount, title).
2. **Checks conflicts** against *two* sources: existing bookings **and the academic
   timetable** (a hall occupied by a scheduled class is not free). Plus a capacity fit.
3. **Proposes alternatives** when the requested venue fails — ranked by tightest
   capacity fit so a 30-person meeting doesn't take the 500-seat auditorium.
4. **Runs an approval chain** — student requests need a faculty advisor *then* an
   admin; faculty/admin requests need only an admin. Each stage is a LangGraph
   `interrupt()` on the same durable thread.
5. **Confirms + notifies** on approval, and the event lands on the campus calendar.
6. **Nags** approvers whose stage has been pending more than 24 h (APScheduler sweep).

## 2. Why the design looks like this

- **Conflict = bookings ∪ timetable.** This is the one thing a naive booking form
  always gets wrong, and we already own the timetable. Overlap is computed on
  wall-clock windows against the `timeslots` of that date's weekday, so a booking
  that straddles two periods is caught.
- **Chain as sequential interrupts, one thread.** Verified in langgraph 1.2.11:
  a node containing two `interrupt()` calls resumes each in order via
  `Command(resume=...)`. The node re-executes from the top on every resume, so —
  exactly as in `tools/exchange.py` — **everything before an interrupt is
  idempotent**: the `Booking` row is keyed by `request_key` (the graph thread id)
  and `Approval` rows are keyed by `(kind, ref_id)`.
- **No new approval machinery.** Reuses `approvals` + `/api/approvals/{id}/decide`
  from Phase 2. Two new kinds: `booking_faculty`, `booking_admin`.
- **The advisor is derived from real data**, not hardcoded: for a student
  organiser it is the teacher with the most lessons for that student's section in
  the active timetable version (fallback: any faculty user).

## 3. Data model

`events` and `bookings` already existed (unused, 0 rows). Extended in place:

```
events   + category (fest|workshop|seminar|sports|meeting|event), created_at
bookings + requested_by (FK users)     -- who asked, even for an ad-hoc booking
         + purpose (text)              -- one-line reason shown on the approval card
         + rationale (text)            -- the agent's reasoning for THIS venue
         + request_key (str, unique)   -- graph thread id -> idempotent re-execution
         + last_nag_at (datetime)      -- 24h nag bookkeeping
approvals  kind now also: booking_faculty | booking_admin   (approver_id set at creation)
```

`create_all` cannot add columns to a table that already exists, so `db/session.py`
gained a small idempotent SQLite `ALTER TABLE ... ADD COLUMN` shim (`_ensure_columns`)
that runs after `create_all`. It only ever adds; it never drops or rewrites.

## 4. Tools — `app/tools/booking.py`

Typed tools only; the agent never writes SQL (rule 4 in `docs/README.md`).

| Function | Purpose |
|---|---|
| `check_availability(db, room, date, start, end, headcount)` | conflicts (bookings + classes) + capacity verdict |
| `find_alternatives(db, date, start, end, headcount, exclude, prefer_type)` | free venues ranked by tightest fit |
| `choose_venue(db, ...)` | requested venue if free, else best alternative, with rationale |
| `create_request(db, ..., request_key)` | idempotent `Event` + pending `Booking` |
| `approval_chain_for(db, user)` | `["booking_faculty","booking_admin"]` for students, `["booking_admin"]` otherwise |
| `booking_summary(db, id)` | approval-card payload (venue, window, conflicts avoided, chain state) |
| `confirm_booking` / `reject_booking` / `cancel_booking` | terminal transitions + notifications |
| `calendar(db, from, to)` | campus calendar feed |
| `pending_nags(db, hours)` | bookings whose current stage is older than N hours |

## 5. API — `app/api/bookings.py`

```
POST /api/bookings                 # structured request -> Booking Agent (any auth user)
GET  /api/bookings                 # list (mine, or all for admin) with ?status=&from=&to=
GET  /api/bookings/availability    # live check for the request form (+ alternatives)
GET  /api/bookings/calendar        # campus calendar feed for a date range
GET  /api/bookings/venues          # venue registry with capacity/type
POST /api/bookings/{id}/cancel     # organiser or admin
```

`POST /api/bookings` is a **deterministic trigger** (the form already carries the
intent) — like leave-approval, it skips the supervisor LLM entirely. Free-text
chat still routes through the supervisor to the same node.

`/api/approvals` is widened: faculty may list and decide `booking_faculty` cards;
admin keeps everything.

## 6. Frontend

- **`/bookings`** — two tabs.
  *Request*: venue/date/time/headcount form with a live availability probe
  (green = free, red = conflicts + alternative chips) before submitting; then the
  agent's decision card. Below it, "My requests" with chain state per row.
  *Calendar*: week grid of the campus — venues × days, approved and pending events.
- **`/approvals`** — booking cards alongside substitution cards, showing the venue,
  window, headcount, conflicts the agent avoided, and which stage the card is.
- Sidebar gets a **Bookings** entry.

## 7. Definition of done — all verified live 2026-08-25

- [x] A booking on a venue that a class occupies is refused and an alternative offered
- [x] Student request → faculty card → admin card → confirmed, both stages on one thread
- [x] Faculty request → single admin card
- [x] Rejection at either stage discards the booking and notifies the organiser
- [x] Re-executing the node (resume) never duplicates the `Booking` or `Approval` rows
- [x] Nag sweep notifies the pending approver once per 24 h window
- [x] Calendar shows confirmed events; cancelled/rejected disappear
