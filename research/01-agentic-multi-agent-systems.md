# 01 — Agentic AI & Multi-Agent Systems

## What the concept is

**Agentic AI** refers to autonomous systems that pursue complex goals with minimal human
intervention: they perceive their environment, reason, plan, and act — often as **multiple
specialized agents** that coordinate with one another. This is the core paradigm of our
project: instead of one monolithic program, campus operations are split among cooperating
agents (supervisor, scheduler, facility, knowledge, notification), each owning one domain.

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| Agentic AI in Action: A Review of Architectures, Communication, and Coordination in Intelligent Multi-Agent Systems | [IEEE, 2025](https://ieeexplore.ieee.org/abstract/document/11345772/) | Reviews 10+ agentic frameworks (2023–2025); proposes a 3-dimensional taxonomy of architecture, communication, coordination | Survey-level; identifies open challenges in scalability, benchmarking, security — no concrete application | Our architecture (supervisor + specialists) instantiates the coordination patterns this survey formalizes |
| Agentic AI: Autonomous Intelligence for Complex Goals — A Comprehensive Survey | [IEEE Access, vol. 13, 2025](https://ieeexplore.ieee.org/) (Acharya, Kuppan, Divya) | Defines agentic AI, its components (planning, memory, tools), and application areas | Broad survey; no domain implementation | Grounds our definition of "agentic" and justifies the autonomous-agent design in the report |
| Agentic AI Systems: Architecture and Evaluation Using a Frictionless Parking Scenario | [IEEE, 2025](https://ieeexplore.ieee.org/document/11083588/) | Shows how multiple specialized agents coordinate to achieve a goal with minimal supervision; details agent design + interaction + cooperation | Single narrow scenario (parking) | Blueprint for coordinating specialized agents toward one operational goal — we mirror this for campus ops |
| Agentic AI for Cloud Troubleshooting: A Review of Multi-Agent System for Automated Cloud Support | [IEEE, 2025](https://ieeexplore.ieee.org/document/11005005/) | Multi-agent system that autonomously diagnoses and resolves cloud issues | Domain-specific to cloud infra | Evidence that the multi-agent "detect → plan → act" loop works for real operational automation |
| AI Agents vs. Agentic AI: A Conceptual Taxonomy, Applications and Challenges | [arXiv:2505.10468, 2025](https://arxiv.org/abs/2505.10468) | Distinguishes single "AI agents" from collaborative "agentic AI"; taxonomy + challenges | Conceptual, not applied | Justifies *why* we use a multi-agent (agentic) design rather than a single chatbot |
| Distinguishing Autonomous AI Agents from Collaborative Agentic Systems | [arXiv:2506.01438, 2025](https://arxiv.org/abs/2506.01438) | Framework for understanding modern intelligent architectures and where collaboration adds value | Theoretical framework | Supports our claim that collaboration between specialist agents beats one general model |

## How it maps to our project

Our system is a **collaborative agentic system** (per the taxonomy in the papers above): a
supervisor agent classifies each request and delegates to a specialist agent that owns one
domain. This directly realizes the architecture/communication/coordination dimensions that the
IEEE survey (11345772) formalizes and the frictionless-parking paper (11083588) demonstrates.
Our contribution over these works is **domain application** — none target integrated campus
operations, which is exactly the gap file [09-DIFFERENTIATION.md](09-DIFFERENTIATION.md) claims.
