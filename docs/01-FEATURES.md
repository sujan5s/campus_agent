# 01 — Features

The system is a set of **autonomous agents** coordinated by a supervisor. Each agent owns one
campus domain, has its own tools, and can act in two modes:

- **Reactive** — a user asks for something in the chat ("Book the auditorium Friday 3pm").
- **Proactive** — a scheduled trigger or database event wakes the agent up with no human
  prompt (a teacher's leave gets approved → the substitution agent re-plans the timetable
  on its own). **This proactive mode is what makes the project "agentic" rather than a chatbot.**

Features are split into **Core** (must build — this is the graded demo) and **Stretch**
(build if time permits — each one is an independent add-on).

---

## CORE FEATURES

### F1. Timetable Generation Agent 🗓️

**What it does:** Generates a complete, clash-free weekly timetable for all class sections
from basic inputs: subjects, teachers (and which subjects they can teach), rooms/labs,
periods per week per subject, and constraints (teacher max hours/day, lab needs 2 consecutive
periods, no teacher in two rooms at once, etc.).

**How it works:**
1. Admin enters/uploads the basic data (subjects, teachers, sections, rooms) via the dashboard
   or a CSV upload.
2. The agent **does not ask the LLM to solve the puzzle** — LLMs are bad at constraint
   satisfaction. Instead, the LLM parses the request and constraints into a structured spec,
   then calls a **CP-SAT constraint solver tool (Google OR-Tools)** that computes a provably
   clash-free timetable in seconds.
3. If constraints are infeasible (e.g., not enough rooms), the solver reports *which*
   constraints conflict, and the LLM explains it in plain language and suggests relaxations
   ("Add one more lab slot or reduce Section B's electives to make this solvable").
4. Generated timetable is stored in the DB and rendered as an interactive grid in the dashboard.

**Why it impresses:** deterministic solver + LLM explanation is the correct engineering
pattern, and "explain why it's impossible" is a genuinely useful capability no manual system has.

---

### F2. Leave & Substitution Agent (the flagship) 🔁

**What it does:** When a teacher applies for leave, the system *autonomously* repairs the
timetable: finds a qualified, free substitute for each affected period, or reschedules /
merges / marks a free period when no substitute exists, then notifies everyone affected.

**How it works (fully proactive):**
1. Teacher submits leave via the dashboard (date range + reason).
2. HOD/admin approves it (one click — human-in-the-loop checkpoint).
3. Approval event triggers the **Substitution Agent** automatically:
   - Queries the timetable for all periods the teacher had in that range.
   - For each period, ranks candidate substitutes: teaches the same subject > same
     department > any free teacher, weighted by current workload (fairness).
   - Applies changes as a *proposed diff* to the timetable.
4. The proposed substitution plan goes back to the HOD as a single approval card
   ("3 periods reassigned, 1 period moved to Thursday slot 6 — Approve / Edit / Reject").
5. On approval, the timetable updates and the **Notification Agent** informs the substitute
   teachers and the affected class sections.

**Why it impresses:** this is the clearest "agent does a real employee's job" demo — the
system observes an event, plans, and acts with only an approval click from a human.

---

### F3. Event & Venue Booking Agent 🎪

**What it does:** Natural-language booking of auditoriums, seminar halls, labs, and grounds —
with automatic conflict detection, capacity matching, and an approval workflow.

**How it works:**
1. Student club / faculty types: "Need the auditorium on 21 Aug, 2–5pm, for the coding club
   hackathon, ~120 people."
2. Agent extracts structured fields (venue, date, time, purpose, headcount), checks conflicts
   against existing bookings **and the academic timetable** (a hall used for a class is not free),
   and checks capacity fit.
3. If the requested venue is taken, it proposes alternatives ("Auditorium is booked; Seminar
   Hall B seats 150 and is free 2–6pm").
4. Booking enters an approval chain (faculty advisor → admin) — the agent tracks the state
   and nags pending approvers after 24h.
5. On approval: booking confirmed, notifications sent, event appears on the campus calendar.

---

### F4. Campus Knowledge Assistant (RAG) 📚

**What it does:** Answers any campus question — rules, circulars, syllabus, exam policies,
fee deadlines, department info — from the college's own documents, **with citations**.

**How it works:**
1. Admin uploads documents (PDFs of circulars, handbook, academic calendar) to a knowledge base.
2. Documents are chunked, embedded, and stored in a vector database (Chroma).
3. When the supervisor routes a "general" query here, the agent retrieves the most relevant
   chunks and answers grounded in them, citing the source document and page.
4. If nothing relevant is found it says so — it never invents policy.

**Why it matters:** this replaces the current keyword-matched "general fallback" node with a
real capability, and covers the "communication" pillar of the synopsis.

---

### F5. Notification Agent 📣 (cross-cutting)

**What it does:** The single outbound channel for the whole system. Other agents never send
messages directly — they hand the Notification Agent a structured event, and it decides who
to tell, on which channel (in-app, email; Telegram bot as stretch), and composes the message.

**Examples:** substitution alerts to teachers, "class moved to Room 204" to a section,
booking confirmations, attendance warnings, daily digest to admins.

---

## STRETCH FEATURES (independent add-ons, in recommended order)

### F6. Attendance Sentinel Agent 📉
Runs weekly (proactive). Scans attendance records, **projects** each student's end-of-semester
percentage at their current rate, and warns students *before* they fall below 75% — plus a
summary to proctors. Demo-friendly: seed with mock attendance data.

### F7. Complaint & Maintenance Triage Agent 🔧
Students/staff report issues in natural language ("fan not working in room 204", optionally a
photo). Agent classifies (electrical/plumbing/IT/civil), sets priority, routes to the right
department queue, tracks SLA, and auto-escalates stale complaints. Covers the synopsis's
"infrastructure maintenance" pillar.

### F8. Exam Scheduling Agent 📝
Reuses the F1 solver core with different constraints: no student writes two exams in one day,
room seating capacity split across sections, and automatic invigilation duty allocation
balanced by workload.

### F9. Analytics Agent (talk to your data) 📊
Admin asks questions in English — "Which rooms are least used on Fridays?", "Which teacher
has the highest substitution load this month?" — the agent generates **safe, read-only SQL**,
runs it, and answers with a chart. High wow-factor, small implementation surface.

### F10. Energy Watchdog Agent ⚡ (ties to the synopsis)
A simulated IoT feed (script emitting room-level power/occupancy readings) + an agent that
cross-references the timetable: lights/AC drawing power in a room with no scheduled class →
flag it, log estimated waste, notify maintenance. Simulation is acceptable and expected for a
student project — the agent logic is the contribution.

---

## What makes this one of the best projects

1. **Proactive multi-agent behaviour** — agents act on events and schedules, not just chat.
2. **Human-in-the-loop approvals** — the system proposes, humans approve with one click.
   (Safe autonomy is a current industry research theme.)
3. **Right tool for each job** — constraint solver for timetables, RAG for knowledge,
   text-to-SQL for analytics; the LLM orchestrates rather than guesses.
4. **Model-agnostic core** — swap Gemini/Claude/GPT with one env variable (see 03-TECH-STACK).
5. **Full-stack, demo-ready** — live dashboard with real-time agent trace visualization
   already exists and every feature plugs into it.
