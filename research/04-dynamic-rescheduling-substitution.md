# 04 — Dynamic Rescheduling & Teacher Substitution

## What the concept is

Once a timetable exists, real life disrupts it — a teacher takes leave. **Dynamic rescheduling**
repairs the plan on the fly while keeping changes minimal (**schedule stability / minimal
perturbation**). Our **Substitution Agent** does this autonomously: on a leave event it finds a
qualified free substitute per affected period, or reschedules with least disruption, then routes
the plan to a human for one-click approval. This is our **flagship differentiator**.

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| School Timetabling Problem Under Disturbances | [Computers & Industrial Engineering (Elsevier), 2016](https://www.sciencedirect.com/science/article/abs/pii/S0360835216300389) | Reschedules school timetables when teacher/room/learner availability changes; update plan promptly to reflect new state | Not autonomous; no agent; no human-approval loop | Formal basis for "repair the timetable on disruption" — we automate + add approval |
| Minimum Penalty Perturbation Heuristics for Curriculum-Based Timetables Subject to Multiple Disruptions | [Computers & OR (Elsevier), 2021](https://www.sciencedirect.com/science/article/abs/pii/S0305054821000964) | Heuristics that **minimize perturbation** when repairing timetables under multiple disruptions | Heuristic, offline, transport/curriculum framing | The **minimal-perturbation objective** we adopt for substitution plans |
| Dynamic and Robust Timetable Rescheduling for Uncertain Railway Disruptions | [Transportation Research (Elsevier), 2019](https://www.sciencedirect.com/science/article/pii/S2210970619300794) | Rolling-horizon two-stage stochastic rescheduling under uncertain disruption duration | Railway domain; heavy optimization, not campus | Concept of robust, staged re-optimization under uncertainty |
| Dynamic Railway Timetable Rescheduling for Multiple Connected Disruptions | [Transportation Research Part C (Elsevier), 2021](https://www.sciencedirect.com/science/article/pii/S0968090X21001029) | MILP model reschedules under multiple overlapping disruptions | Railway; MILP is heavy; no NL interface | Reinforces multi-disruption handling; we keep it lightweight + agentic |
| Automated Faculty Substitution Using Classification Algorithms | [IJARCCE, 2025](https://ijarcce.com/wp-content/uploads/2025/05/IJARCCE.2025.14540.pdf) | Classifies suitable replacement teachers by subject compatibility in emergencies | Classification only; no full rescheduling, no approval workflow, no agent | Closest prior work to our substitution agent — we go further (ranking + plan + HITL + notify) |

## How it maps to our project

The **Substitution Agent** (Phase 2) combines two ideas from this literature: (1) the
**minimal-perturbation** repair objective (Elsevier 2021) and (2) **substitute selection by
subject compatibility** (IJARCCE 2025). We rank candidate substitutes as *teaches-same-subject >
same-department > any-free*, weighted by current workload (fairness), and produce a timetable
diff.

**What makes ours novel** (see [09-DIFFERENTIATION.md](09-DIFFERENTIATION.md)):

1. **Autonomous & event-triggered** — the agent runs itself the moment leave is approved (no one
   presses "reschedule"). The disruption literature above is offline/manual.
2. **Human-in-the-loop** — the plan is proposed, not silently applied; a HOD approves in one click
   ([07-human-in-the-loop.md](07-human-in-the-loop.md)).
3. **Applied to campus staff, not railways** — most rescheduling research is transport; we bring
   it to teacher substitution, where prior work stops at classification (IJARCCE).
