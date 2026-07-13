# 02 — LLM Orchestration, Supervisor-Router Pattern & Tool Calling

## What the concept is

**Orchestration** is how multiple LLM-driven agents are coordinated. We use the **supervisor
(router) pattern**: a central supervisor node classifies intent and delegates to worker
(specialist) agents. Each specialist uses **tool / function calling** — the LLM decides *which*
typed tool to call (DB query, solver, retriever), and deterministic code executes it. The whole
graph is **stateful and checkpointed** (LangGraph), so workflows are durable and resumable.

## Papers — Orchestration & supervisor-router

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| LLM-Based Multi-Agent Orchestration: A Survey of Frameworks, Communication Protocols, and Emerging Patterns | [Future Internet (MDPI), 18(6):326, 2026](https://doi.org/10.3390/fi18060326) | Surveys orchestration frameworks; explicitly describes the **supervisor pattern where a routing node delegates to workers**, plus hierarchical and swarm patterns | Survey; does not build a product | **Direct blueprint** for our `supervisor.py` → specialists design |
| The Orchestration of Multi-Agent Systems: Architectures, Protocols, and Enterprise Adoption | [arXiv:2601.13671, 2026](https://arxiv.org/html/2601.13671v1) | Bridges conceptual architectures with implementation-ready design principles for enterprise multi-agent systems | Enterprise-generic | Design principles for reliable orchestration we follow (clear roles, typed hand-offs) |
| Multi-Agent Orchestration for High-Throughput Materials Screening | [arXiv:2604.07681, 2026](https://arxiv.org/pdf/2604.07681) | Hierarchical planner–executor architecture **implemented using LangGraph** | Scientific-computing domain | Precedent that **LangGraph** (our exact framework) scales to real multi-agent workflows |
| Difficulty-Aware Agent Orchestration in LLM-Powered Workflows | [arXiv:2509.11079, 2025](https://arxiv.org/html/2509.11079v1) | An **LLM router** assigns operators/models to tasks by difficulty | Focuses on routing optimization only | Validates our LLM-router supervisor; a future extension (route by difficulty/cost) |
| A Survey of Agent Interoperability Protocols (MCP, ACP, A2A, ANP) | [arXiv:2505.02279, 2025](https://arxiv.org/pdf/2505.02279) | LLMs enable zero/few-shot understanding of NL instructions; agents combine reasoning with external tool execution; standard protocols | Protocol-level, forward-looking | Justifies our tool-calling design; roadmap for standard agent protocols later |

## Papers — Tool / function calling & intent classification

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| Function Calling in Large Language Models: Industrial Practices, Challenges, and Future Directions | [OpenReview, 2025](https://openreview.net/pdf/d01d50e27f7636724789f2aad6f4ac378749a0e1.pdf) | Breaks function calling into pre-call (intent recognition), execution (parameter extraction, multi-call), post-call (result mismatch) stages | Reports failure modes but is a survey | We design tools to avoid these failure modes (typed schemas, validated params) |
| Natural Language Tools: A NL Approach to Tool Calling in Large Language Agents | [arXiv:2510.14453, 2025](https://arxiv.org/pdf/2510.14453) | Replacing rigid JSON tool calls with NL improves accuracy by 18.4 pts, cuts variance 70% | New method, not yet standard | Informs prompt design; a candidate optimization if JSON tool calls prove brittle |
| Classification-Based Concurrent API Calls & Optimal Model Combination for Tool-Augmented LLMs | [Scientific Reports (Nature), 2025](https://www.nature.com/articles/s41598-025-06469-w) | Multi-step plan → tool-invocation staging; classify then call APIs concurrently | General agent setting | Supports our "supervisor classifies, specialist invokes tools" two-stage flow |

## How it maps to our project

- **`app/agents/supervisor.py`** is exactly the *supervisor/routing node* the MDPI survey
  (fi18060326) names as a canonical pattern — it uses structured output to return
  `{route, task_spec}`.
- **`app/agents/graph.py`** builds a LangGraph `StateGraph`, the same framework used in the
  materials-screening paper (2604.07681), and adds a `SqliteSaver` checkpointer for durability.
- **`app/tools/`** (Phase 1+) follows the staged function-calling discipline (pre/execution/post)
  that the OpenReview survey recommends, using typed Pydantic schemas so parameter extraction is
  validated — mitigating the failure modes those papers catalogue.
