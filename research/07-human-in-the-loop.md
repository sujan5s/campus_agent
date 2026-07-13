# 07 — Human-in-the-Loop (HITL) & Approval Workflows

## What the concept is

**Human-in-the-loop** integrates human oversight into an autonomous workflow at critical
decision points: the AI proposes an action, then **pauses at a checkpoint** until a human
approves, edits, or rejects before continuing. This gives **safe autonomy** — the system does the
heavy lifting, humans retain control over high-impact actions. We use it for leave approval,
substitution-plan approval, and booking approval.

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| ⭐ A Decoupled Human-in-the-Loop System for Controlled Autonomy in Agentic Workflows | [arXiv:2604.23049, 2026](https://arxiv.org/pdf/2604.23049) | Decouples agent execution from human approval checkpoints for controlled autonomy in agentic workflows | Recent preprint; general framework | **Directly matches** our interrupt→approve→resume design |
| A Comprehensive Framework for Human-AI Collaborative Decision Making | [Expert Systems w/ Applications (Elsevier), 2025](https://www.sciencedirect.com/science/article/pii/S0957417425036292) | Framework for human–AI collaborative decisions (retail) | Retail domain | Tiered oversight model: low-risk auto, high-risk human sign-off |
| Human-in-the-Loop AI in Ongoing Process Verification (Pharma) | [Information (MDPI), 16(12):1082, 2025](https://www.mdpi.com/2078-2489/16/12/1082) | HITL for regulated pharmaceutical process verification | Regulated-industry specific | Evidence HITL is the norm where mistakes are costly — like altering a live timetable |
| Trustworthy Human Computation: A Survey | [arXiv:2210.12324](https://arxiv.org/pdf/2210.12324) | Trust via human participation — humans provide info or confirm/modify AI decisions | Survey | Grounds *why* HITL builds trust in our approvals |
| Automating Document Intelligence in Statutory City Planning | [arXiv:2603.13245, 2026](https://arxiv.org/pdf/2603.13245) | HITL document automation in a government/statutory setting | Document-processing domain | Precedent for HITL in administrative workflows (like ours) |

## Key distinction the literature gives us (great for the report)

The research distinguishes **HITL** (AI acts autonomously, escalates exceptions/low-confidence to
a human) from **AI-in-the-Loop / AI2L** (human is primary actor, AI assists). Our substitution and
booking flows are **HITL**: the agent plans autonomously and escalates the final decision to a
human approver. Stating this distinction explicitly strengthens the methodology section.

## How it maps to our project

We implement HITL with LangGraph's **`interrupt()`** plus a checkpointer: when a specialist reaches
a high-impact action (apply a substitution plan, confirm a booking), the graph **pauses** and
writes an `approvals` row with the `langgraph_thread_id`. The dashboard shows an approval card;
when the HOD clicks Approve/Reject (`POST /api/approvals/{id}/decide`), the graph **resumes from
the exact paused state** — even days later. This realizes the decoupled-HITL pattern of arXiv
2604.23049 in a concrete campus workflow, applying the tiered-oversight idea (Elsevier 2025):
low-risk actions like notifications proceed automatically; high-risk timetable/booking changes
require sign-off.
