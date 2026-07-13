# 03 — Automated Timetable Scheduling (CP-SAT / OR-Tools)

## What the concept is

University timetabling is a classic **NP-hard constraint satisfaction / optimization problem**:
assign (section, subject, teacher, room, timeslot) so that hard constraints hold (no teacher or
room double-booked, required periods per subject, labs consecutive) while optimizing soft
constraints (teacher load balance, preferences). We solve it with **Google OR-Tools CP-SAT**, a
constraint-programming solver — *not* an LLM (LLMs are unreliable at combinatorial search).

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| ⭐ A Comparative Analysis of Constraint Programming and Genetic Algorithms for Automated University Timetable Generation | [IEEE, 2024](https://ieeexplore.ieee.org/document/11379218/) | Compares Google **CP-SAT** vs a Genetic Algorithm; CP is **~175× faster** and functionally superior on a realistic medium-complexity problem | GA shown weaker; study is a benchmark, not a product | **Direct justification** for choosing OR-Tools CP-SAT over GA — cite this as our design rationale |
| Genetic Algorithm for Solving University Course Timetabling Using Dynamic Chromosomes | [IEEE, 2021](https://ieeexplore.ieee.org/document/9406539/) | GA with dynamic-length chromosomes for course timetabling | Stochastic; convergence + tuning issues; no optimality guarantee | Baseline we compare against; motivates a deterministic solver |
| Time Table Scheduling Using Genetic Algorithms Employing Guided Mutation | [IEEE, 2011](https://ieeexplore.ieee.org/document/5705788/) | Guided-mutation GA avoids faculty/classroom clashes, improves convergence | GA quality depends on operators; slow on large instances | Shows constraint types (faculty/room clash) we encode as hard constraints |
| Solving Timetabling Problems Using Genetic Algorithms | [IEEE, 2004](https://ieeexplore.ieee.org/document/1490384/) | Foundational GA formulation of timetabling | Older; small-scale; no infeasibility explanation | Establishes timetabling as an evolutionary-search problem in the literature |
| Solving University Timetabling as a Constraint Satisfaction Problem with Genetic Algorithm | [Academia/Scholar](https://www.academia.edu/2876050/) | Models timetabling explicitly as a **CSP** solved via GA | Hybrid; still stochastic | Confirms the **CSP formulation** we adopt for our CP-SAT model |
| Automating University Course Scheduling Using Genetic Algorithm | [Springer, 2025](https://link.springer.com/10.1007/978-981-95-0375-9_12) | Recent GA-based course scheduling with practical framework | GA limitations persist (runtime, no explanation) | Recent evidence the field still leans on GA — our CP-SAT + LLM-explanation is a step beyond |

## How it maps to our project

Our **`app/solver/`** module (Phase 1) builds an OR-Tools **CP-SAT** model: boolean assignment
variables per (section, subject, teacher, room, timeslot), hard constraints for clash-freeness
and period counts, and soft objectives for load balance. The flagship comparison paper
(IEEE 11379218) is our headline citation — it empirically shows CP-SAT is ~175× faster than a GA,
which is precisely why we reject the GA-heavy mainstream (papers 2–6) in favour of constraint
programming.

**Our added value over all of these:** when the problem is *infeasible*, a raw solver just fails.
We wrap the solver so the **LLM explains which constraints conflict and suggests relaxations**
in plain language — a usability capability none of these papers provide. See
[09-DIFFERENTIATION.md](09-DIFFERENTIATION.md).
