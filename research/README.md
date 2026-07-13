# Research — Literature Base for the Smart Campus Agent System

This folder is the **academic backbone** of the project. It collects real, citable research
papers (IEEE Xplore, ACM, Springer, Elsevier/ScienceDirect, IEEE Access, and peer-reviewed
journals indexed on Google Scholar) for every concept we use, and documents **how each concept
maps into our implementation** and **what we do differently** to stand out.

## How this folder is organized

| File | What it contains |
|------|------------------|
| [00-CONCEPT-MAPPING.md](00-CONCEPT-MAPPING.md) | **Master table** — every concept → where it lives in our code → supporting papers → why. Start here. |
| [01-agentic-multi-agent-systems.md](01-agentic-multi-agent-systems.md) | Agentic AI & multi-agent systems (the core paradigm) |
| [02-llm-orchestration-tool-calling.md](02-llm-orchestration-tool-calling.md) | LLM orchestration, supervisor-router pattern, tool/function calling |
| [03-timetable-scheduling.md](03-timetable-scheduling.md) | Automated timetabling (CP-SAT / OR-Tools vs genetic algorithms) |
| [04-dynamic-rescheduling-substitution.md](04-dynamic-rescheduling-substitution.md) | Dynamic rescheduling & teacher substitution under disruption (our flagship) |
| [05-smart-campus-systems.md](05-smart-campus-systems.md) | Smart campus management systems (the domain) |
| [06-rag-knowledge-assistant.md](06-rag-knowledge-assistant.md) | Retrieval-Augmented Generation for the knowledge assistant |
| [07-human-in-the-loop.md](07-human-in-the-loop.md) | Human-in-the-loop AI & approval workflows |
| [08-facility-booking.md](08-facility-booking.md) | Facility / room reservation & resource allocation |
| [09-DIFFERENTIATION.md](09-DIFFERENTIATION.md) | **What makes us stand out** — the gap in existing work + education-specific agentic papers |

## How to use each topic file

Every topic file has the same clean structure so it drops straight into your report and slides:

1. **What the concept is** — one plain-language paragraph.
2. **Paper table** with columns:
   - **Paper** — title
   - **Source / Year** — venue (IEEE, ACM, arXiv, etc.) + link
   - **Core Idea** — what the paper contributes
   - **Limitation / Gap** — where it falls short (this is what your "Limitations" column needs)
   - **What We Take** — exactly what our project borrows or improves on
3. **How it maps to our project** — the paragraph you paste into your methodology section.

## ⚠️ Verification note (read before final submission)

Paper titles, venues, and links here were captured from IEEE Xplore / publisher search results
and are real. **However, before you paste citations into your final report, open each link and
confirm the exact author list, page numbers, and year** — publishers occasionally update metadata,
and your viva panel may check. Use the linked page as the source of truth for the formal citation.
A ready-to-fill reference list is at the bottom of [00-CONCEPT-MAPPING.md](00-CONCEPT-MAPPING.md).

## Two "sets" of papers (as requested)

- **Set A — Foundation papers** (files 01–08): prove the concepts we *use* are established and sound.
- **Set B — Differentiation papers** (file 09): show the *gap* in existing systems and how our
  agentic, proactive, human-in-the-loop approach is novel for campus operations.
