# 09 — Differentiation: What Makes Our Project Stand Out

This is **Set B** — the papers and arguments that show the **gap in existing work** and how our
project is novel. Use this for the "Novelty / Contribution" slide and the "Gap Analysis" section
of the report.

## The one-line thesis

> Existing campus systems are **reactive** (IoT dashboards), and existing agentic-AI research is
> **generic or applied to other domains** (cloud, parking, railways). **No prior system combines
> autonomous multi-agent orchestration + proactive event-driven action + human-in-the-loop
> approval, applied to integrated campus operations.** That combination is our contribution.

## Gap analysis table (existing → limitation → our improvement)

| Area | What existing work does | Its limitation | **Our differentiation** |
|------|------------------------|----------------|-------------------------|
| Smart campus | IoT sensing, dashboards, digital twins ([05](05-smart-campus-systems.md)) | Reactive; hardware-centric; **no autonomous decisions** | An **agentic decision layer** that acts, not just displays |
| Timetabling | Genetic algorithms dominate ([03](03-timetable-scheduling.md)) | Slow, stochastic, **no infeasibility explanation** | **CP-SAT** (~175× faster) **+ LLM explains why a timetable is impossible** and suggests fixes |
| Rescheduling | Studied for railways/transport, offline ([04](04-dynamic-rescheduling-substitution.md)); faculty substitution = classification only | Manual trigger; **not autonomous**; no approval | **Event-triggered autonomous** substitution with **human approval** |
| Multi-agent AI | Surveys + domain apps: cloud, parking ([01](01-agentic-multi-agent-systems.md)) | **Not applied to campus operations** | First to apply the agentic pattern to **integrated campus ops** |
| Reservation | Form-based CRUD booking ([08](08-facility-booking.md)) | No NL; no timetable-aware conflict check | **NL booking** + conflict check against **live timetable** + alternatives |
| Knowledge/FAQ | Generic or domain RAG ([06](06-rag-knowledge-assistant.md)) | Not campus-grounded | RAG over **college's own documents with citations** |
| Autonomy safety | HITL described conceptually ([07](07-human-in-the-loop.md)) | Often theoretical | Concrete **interrupt→approve→resume** loop in a working product |

## The four pillars of our novelty (memorize these for the viva)

1. **Proactive, not reactive.** Agents act on events (leave approved → reschedule) and schedules
   (nightly checks), with no human prompt. Smart-campus literature ([05](05-smart-campus-systems.md))
   is explicitly reactive by its own framing.
2. **Right tool for each job.** Constraint solver for timetables, RAG for knowledge, structured-
   output LLM for routing — the LLM **orchestrates**, it doesn't guess. Timetabling papers
   ([03](03-timetable-scheduling.md)) show LLM-free CP-SAT is the correct engineering choice.
3. **Safe autonomy via human-in-the-loop.** The system proposes; humans approve high-impact
   actions in one click ([07](07-human-in-the-loop.md)).
4. **Integrated, single platform.** One agentic system spans scheduling, substitution, booking,
   and knowledge — prior work solves these in isolation.

## Set B papers — Agentic AI specifically for education/administration

These prove the *trend* is real and that reducing administrative burden with agents is an
active, credible research direction — while none target our exact integrated-operations product.

| Paper | Source / Year | Core Idea | Why It Supports Our Differentiation |
|-------|---------------|-----------|-------------------------------------|
| Agent4EDU: Advancing AI for Education with Agentic Workflows | [ACM ICAIE, 2024](https://dl.acm.org/doi/10.1145/3722237.3722268) | Agentic workflows applied to education | Confirms agentic AI in education is a recognized, publishable direction |
| Instructional Agents: Reducing Teaching Faculty Workload through Multi-Agent Instructional Design | [arXiv:2508.19611, 2025](https://arxiv.org/pdf/2508.19611) | Multi-agent system reduces faculty workload | Same *motivation* as ours (cut staff workload) but targets instructional design, not operations |
| Agentic Workflow for Education: Concepts and Applications | [arXiv:2509.01517, 2025](https://arxiv.org/pdf/2509.01517) | Concepts + applications of agentic workflows in education | Positions our operations focus as an unexplored application area |
| LLM Agents for Education: Advances and Applications | [arXiv:2503.11733, 2025](https://arxiv.org/pdf/2503.11733) | Survey of LLM agents in education | Survey to cite for the field; shows operations/admin is under-addressed |
| Large-Language-Model-Based Agents for Education (survey) | *IEEE Transactions on Learning Technologies, 2025* | Comprehensive survey of LLM agents for education | Strong IEEE citation establishing the research area |
| The Impact of LLMs on Higher Education: AI and Education 4.0 | [Frontiers in Education, 2024](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2024.1392091/full) | LLMs and the Education 4.0 vision | Macro-context: why now, why campuses |

## How to phrase it in the report (paste-ready)

> "While agentic AI has been surveyed extensively and applied to domains such as cloud support and
> smart parking, and while smart-campus research is mature in IoT sensing, the two have not been
> combined. Existing campus systems remain reactive and siloed, timetabling research relies largely
> on slower stochastic genetic algorithms without infeasibility reasoning, and teacher-substitution
> work stops at classification. Our system unifies these into a single agentic platform that acts
> proactively on events, uses a constraint solver with LLM-generated explanations for timetabling,
> and keeps humans in control through explicit approval checkpoints — a combination not present in
> the reviewed literature."
