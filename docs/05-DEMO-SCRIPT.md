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
3. Switch section in the dropdown — different grid, same guarantees.
4. **Infeasibility explanation** (the wow): in Data Setup, edit a teacher and remove
   ALL subjects covering e.g. CS701 (note who taught it first!). Back in Timetable →
   Generate → the banner explains in plain language: *"No teacher can teach CS701 —
   map at least one teacher to it in Data Setup."*
   *Say: "GA-based systems just fail. Ours tells you exactly what to fix."*
   → Restore the teacher mapping, regenerate. ✅

## Act 3 — THE FLAGSHIP: autonomous substitution with human-in-the-loop (3 min)

1. **Sign out → login as faculty** `anita.rao@campus.edu` / `faculty123`.
2. Open **Leaves** → apply for leave (pick a MON/TUE next week, reason "Medical").
   *Say: "A teacher applies for leave. Watch what happens with zero further prompting."*
3. **Sign out → login as admin** → **Leaves** → click **Approve** on Anita's row.
   *Say — this is the key sentence: "The approval event itself triggered the
   Substitution Agent. It queried her affected lessons, ranked every candidate —
   teaches-the-same-subject beats same-department beats merely-free, weighted by
   workload for fairness — built a minimal-perturbation plan, and now it has PAUSED.
   LangGraph checkpointed the workflow mid-execution; it resumes only when a human decides."*
4. Banner appears → open **Approvals** → walk through the plan card:
   date, period, class, original → substitute, and the **rationale column**.
5. Click **Approve plan**.
   *Say: "The paused workflow just resumed from the exact interrupt point."*
6. **Sign out → login as** `suresh.shetty@campus.edu` / `faculty123` → **Inbox**:
   "Substitution assigned: you cover CS704 for CSE-7B…" — proactive notification.
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
- **"What if no substitute is free?"** — The plan marks the lesson "NO COVER
  AVAILABLE"; the HOD sees it before approving. Human stays in control.
- **"What if the server restarts mid-approval?"** — The workflow is checkpointed in
  SQLite; the approval row stores the thread id; resume works after restart. Plus an
  APScheduler sweep re-triggers planning for any approved leave that lost its plan.
- **"Is it one prompt to ChatGPT?"** — No: supervisor-router multi-agent architecture,
  typed tools, constraint solver, versioned DB, HITL interrupts — the LLM is
  swappable via one .env line (show `app/core/llm.py`).
