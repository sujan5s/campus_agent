# 00 — Master Concept Mapping

The single table that ties **research → concept → our code → why**. This is the backbone of
your methodology chapter and the "System Design" slides.

## Concept → Implementation → Literature

| # | Concept We Use | Where It Lives In Our Code | Supporting Papers (file) | Why We Use It |
|---|----------------|----------------------------|--------------------------|---------------|
| 1 | **Agentic AI / autonomous multi-agent system** | Whole `app/agents/` package; supervisor + specialists | [01](01-agentic-multi-agent-systems.md) | Decompose campus operations into autonomous, cooperating agents instead of one monolithic program |
| 2 | **Supervisor-router orchestration** | `app/agents/supervisor.py` (LLM structured-output routing) | [02](02-llm-orchestration-tool-calling.md) | A routing node classifies intent and delegates to the right specialist — the canonical, proven multi-agent pattern |
| 3 | **Stateful graph workflow + checkpointing** | `app/agents/graph.py` (LangGraph `StateGraph` + `SqliteSaver`) | [02](02-llm-orchestration-tool-calling.md) | Durable, resumable workflows; enables pause/resume for approvals |
| 4 | **Tool / function calling** | `app/tools/` (Phase 1+), specialist nodes call typed tools | [02](02-llm-orchestration-tool-calling.md) | The LLM orchestrates; deterministic tools act — auditable and safe |
| 5 | **Constraint-based timetable generation** | `app/solver/` OR-Tools CP-SAT (Phase 1) | [03](03-timetable-scheduling.md) | Timetabling is NP-hard; a CP solver is provably clash-free and far faster than metaheuristics |
| 6 | **Dynamic rescheduling / substitution** | Substitution Agent (Phase 2) | [04](04-dynamic-rescheduling-substitution.md) | Repair the timetable on disruption (teacher leave) with minimal perturbation — our flagship |
| 7 | **Smart campus operations domain** | Entire system; `docs/01-FEATURES.md` | [05](05-smart-campus-systems.md) | Grounds the project in the established smart-campus research area |
| 8 | **Retrieval-Augmented Generation (RAG)** | `app/rag/` Knowledge Agent (Phase 3) | [06](06-rag-knowledge-assistant.md) | Answer campus questions from real documents with citations, no hallucination |
| 9 | **Human-in-the-loop approval** | LangGraph `interrupt()` + `approvals` table | [07](07-human-in-the-loop.md) | Safe autonomy — the agent proposes, a human approves high-impact actions |
| 10 | **Facility / resource booking** | Booking Agent (Phase 3), `bookings`/`rooms` tables | [08](08-facility-booking.md) | Conflict-aware venue reservation with approval chain |

## The "we took / we changed" summary (for the Limitations & Contribution slide)

| Concept | What existing work does | Its limitation | **What we took / changed** |
|---------|------------------------|----------------|----------------------------|
| Multi-agent AI | Frameworks/surveys, mostly generic or cloud/parking/enterprise domains | Not applied to integrated campus operations | We **apply** the agentic pattern to a concrete campus-operations product |
| Orchestration | Supervisor-router pattern proven in surveys | Demonstrated on generic tasks | We **implement** it in LangGraph for campus intent routing with entity extraction |
| Timetabling | Genetic algorithms dominate the literature | Slow, stochastic, no infeasibility explanation | We use **OR-Tools CP-SAT** (deterministic, ~100×+ faster) + LLM explains infeasibility |
| Rescheduling | Studied mostly for railways/transport | Rarely applied to teacher substitution; not autonomous | We make substitution **event-triggered and autonomous** with a human approval gate |
| Smart campus | IoT sensing + dashboards | Reactive, hardware-centric, no autonomous decisions | We add an **agentic decision layer** on top of the data |
| RAG | Strong for domain QA | Generic corpora | We ground it in **college-specific documents** with citations |
| Human-in-the-loop | Approval patterns described conceptually | Often theoretical | We wire a concrete **interrupt→approve→resume** loop into a real workflow |

## Ready-to-fill reference list (IEEE style skeleton)

> Fill `[Authors]`, exact `pp.`, and confirm year from each linked page before submission.

**Agentic & multi-agent**
1. [Authors], "Agentic AI in Action: A Review of Architectures, Communication, and Coordination in Intelligent Multi-Agent Systems," *IEEE*, 2025. https://ieeexplore.ieee.org/abstract/document/11345772/
2. D. B. Acharya, K. Kuppan, B. Divya, "Agentic AI: Autonomous Intelligence for Complex Goals—A Comprehensive Survey," *IEEE Access*, vol. 13, pp. 18912–18936, 2025.
3. [Authors], "Agentic AI Systems: Architecture and Evaluation Using a Frictionless Parking Scenario," *IEEE*, 2025. https://ieeexplore.ieee.org/document/11083588/

**Orchestration & tool calling**
4. [Authors], "LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns," *Future Internet*, vol. 18, no. 6, 326, 2026. https://doi.org/10.3390/fi18060326
5. [Authors], "Function Calling in Large Language Models: Industrial Practices, Challenges, and Future Directions," 2025. https://openreview.net/pdf/d01d50e27f7636724789f2aad6f4ac378749a0e1.pdf

**Timetabling**
6. [Authors], "A Comparative Analysis of Constraint Programming and Genetic Algorithms for Automated University Timetable Generation," *IEEE*, 2024. https://ieeexplore.ieee.org/document/11379218/
7. [Authors], "Genetic Algorithm For Solving University Course Timetabling Problem Using Dynamic Chromosomes," *IEEE*, 2021. https://ieeexplore.ieee.org/document/9406539/

**Rescheduling**
8. [Authors], "School timetabling problem under disturbances," *Computers & Industrial Engineering* (Elsevier), 2016. https://www.sciencedirect.com/science/article/abs/pii/S0360835216300389

**Smart campus**
9. [Authors], "Internet of Things Based Model for Smart Campus: Challenges and Limitations," *IEEE*, 2020. https://ieeexplore.ieee.org/document/9036629/
10. [Authors], "Roadmap to Smart Campus based on IoT," *IEEE*, 2020. https://ieeexplore.ieee.org/abstract/document/9197926/

**RAG**
11. A. Saha, B. Saha, A. Malik, "QuIM-RAG: Advancing Retrieval-Augmented Generation With Inverted Question Matching for Enhanced QA Performance," *IEEE Access*, vol. 12, pp. 185401–185410, 2024.
12. [Authors], "Domain-Specific Retrieval-Augmented Generation Using Vector Stores, Knowledge Graphs, and Tensor Factorization," *IEEE*, 2025. https://ieeexplore.ieee.org/document/10903241/

**Human-in-the-loop**
13. [Authors], "A Decoupled Human-in-the-Loop System for Controlled Autonomy in Agentic Workflows," arXiv:2604.23049, 2026.

**Facility booking**
14. [Authors], "Design and Development of an Integrated Room Reservation System for Higher Education Institutions," *IEEE*, 2021. https://ieeexplore.ieee.org/document/9436766/

**Differentiation (education agentic)**
15. [Authors], "Agent4EDU: Advancing AI for Education with Agentic Workflows," *ACM ICAIE*, 2024. https://dl.acm.org/doi/10.1145/3722237.3722268
