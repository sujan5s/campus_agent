# 05 — Rehearsed Demo Script (Reviews & Final Viva)

> Total runtime ~8 minutes. Practice the flagship (Act 3) until it's muscle memory —
> it's the differentiator (research/09-DIFFERENTIATION.md).
>
> **Pre-demo checklist:** backend running (`python main.py` in services/backend),
> frontend running (`npm run dev` in apps/web), a timetable generated (any version),
> no pending leaves/approvals left over (reject stale ones), browser logged out.

## Act 1 — The platform (90s)

1. Open `http://localhost:3000/login` → login `admin@campus.edu` / `admin123`.
   *Say: "Role-based JWT auth — admin, faculty, and student see different capabilities."*
2. Open **Data Setup** → flip through Subjects / Teachers / Sections / Rooms tabs.
   *Say: "Master data enters once — forms or CSV import. Agents read it themselves via
   typed tools; nobody ever types data into a chatbot."*
3. Show the **CSV template download + import** on any tab (10 seconds).

## Act 2 — Constraint-solver timetabling (2 min)

1. Open **Timetable** → click **Generate Timetable**.
   *While it solves (~8s), say: "This is Google OR-Tools CP-SAT — 8 hard constraints:
   no teacher/section/room clash, exact weekly period counts, labs as consecutive
   blocks in lab rooms, teacher daily-hour caps — plus a fairness objective that
   minimizes the load gap between teachers. Deterministic and provably clash-free,
   ~175× faster than the genetic algorithms that dominate the literature (IEEE 2024)."*
2. Grid appears → point at a **lab block** (two consecutive periods, flask icon, lab room).
3. Switch section in the dropdown — different grid, same guarantees. Click **PDF** to
   download the current section's timetable as a formatted PDF (works for any role).
4. **Configurable constraints** (Phase 2.2/2.3): click **Constraints**. No-same-subject
   back-to-back is **already on by default**. Use the **"Rules for"** scope selector →
   pick one class → tick **WED** ends after **P4** → Generate. Banner's config summary
   shows the per-class rule (e.g. `CSE-7A: WED≤P4`); only that class loses WED P5–P7,
   the others keep the full day.
   *Say: "Every college has its own rules, and they differ per class — one section has a
   half-day, another doesn't. These plug straight into the solver as optional hard
   constraints, per class, and each version records exactly which rules produced it.
   Avoiding hectic back-to-back periods is the default, not an afterthought."*
5. **Infeasibility explanation** (the wow): in Data Setup, edit a teacher and remove
   ALL subjects covering e.g. CS701 (note who taught it first!). Back in Timetable →
   Generate → the banner explains in plain language: *"No teacher can teach CS701 —
   map at least one teacher to it in Data Setup."* (Over-aggressive half-days trigger the
   same clear explanation.)
   *Say: "GA-based systems just fail. Ours tells you exactly what to fix."*
   → Restore the teacher mapping, regenerate. ✅

## Act 3 — THE FLAGSHIP: autonomous period-exchange with human-in-the-loop (3 min)

1. **Sign out → login as faculty** `anita.rao@campus.edu` / `faculty123`.
2. Open **Leaves** → apply for leave (pick a TUE next week, reason "Medical").
   *Say: "A teacher applies for leave. Watch what happens with zero further prompting."*
3. **Sign out → login as admin** → **Leaves** → click **Approve** on Anita's row.
   The plan appears **instantly** (~0.1 s — the system trigger routes deterministically
   with no LLM round-trip, and the whole plan is built in one DB pass).
   *Say — this is the key sentence: "The approval event itself triggered the
   Substitution Agent. This college doesn't put a stand-in in front of the class to
   teach the wrong subject — teachers **exchange periods**. So the agent found, for each
   of Anita's affected lessons, a partner who already teaches that same section: the
   partner moves their own lesson into Anita's slot on the leave day, and Anita
   **recovers** the missed lesson later in the partner's vacated slot — nearest recovery
   date, workload-balanced. Subject hours are preserved and the original timetable is
   never touched. Then it PAUSED — LangGraph checkpointed the workflow mid-execution; it
   resumes only when a human decides."*
4. Banner appears → open **Approvals** → walk through the plan card: leave date/slot,
   class, missed subject, **partner teaches (their own subject)**, **recovery date/slot**,
   and the rationale column.
5. Click **Approve plan**.
   *Say: "The paused workflow just resumed from the exact interrupt point."*
6. Open **Exchanges** → show the board (both sides of each swap) and the **effective day
   view**: pick CSE-7B on the leave date — the partner teaches their subject in Anita's
   slot (amber ⇄); switch to the recovery date — Anita teaches her own subject back.
   *Say: "This is a dated overlay. The master timetable is unchanged — only these dates
   differ."*
7. **Sign out → login as the partner** (e.g. `meera.nair@campus.edu` / `faculty123`) →
   **Inbox**: "Period exchange scheduled: on <date> you teach <your subject> to CSE-7B in
   place of Anita; your <day/slot> lesson will be taken by her (recovery)." Anita's inbox
   has the recovery schedule.
   *Say: "Nobody asked the system anything after the approval click. Detect → plan →
   human gate → act → notify. That's agentic, and no published campus system does it."*

## Act 4 — Chat + resilience (60s)

1. Dashboard → **Agent Chat**: type "Generate a fresh timetable for all sections" →
   watch the trace sidebar (Supervisor route → Timetable Agent → solver stats).
2. *Mention: "The supervisor is an LLM with structured output — but if the provider is
   down or the key is missing, it degrades to deterministic keyword routing. The demo
   cannot die on stage."* (If Gemini errors live, that IS the demo of resilience.)

## Q&A ammunition

- **"Why not let the LLM make the timetable?"** — NP-hard; LLMs can't guarantee
  clash-freeness. CP-SAT proves it. The LLM parses intent and explains results —
  each tool does what it's provably good at (research/02, /03).
- **"What if no partner is free to exchange?"** — The plan marks the lesson "NO EXCHANGE
  AVAILABLE — needs manual arrangement" (labs are flagged for manual handling too, since a
  consecutive lab block shouldn't be split); the HOD sees it before approving. Human stays
  in control.
- **"Why exchange instead of a substitute teacher?"** — It's how this college actually runs:
  the right teacher always teaches the subject, and weekly subject hours are preserved — the
  lesson just moves to another date. A stand-in teaching an unfamiliar subject helps no one.
- **"What if the server restarts mid-approval?"** — The workflow is checkpointed in
  SQLite; the approval row stores the thread id; resume works after restart. Plus an
  APScheduler sweep re-triggers planning for any approved leave that lost its plan.
- **"Is it one prompt to ChatGPT?"** — No: supervisor-router multi-agent architecture,
  typed tools, constraint solver, versioned DB, HITL interrupts — the LLM is
  swappable via one .env line (show `app/core/llm.py`).
