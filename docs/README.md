# Smart Campus Ops — Project Documentation

**Project:** Agentic AI–Driven Smart Campus Operations Management System
**Team:** Manvith Y Shetty, M Vaibhav, Sujan S, Mohith L A — Dept. of CSE, NMAM Institute of Technology
**Type:** Final Year Major Project (2026)

This folder is the **single source of truth** for the project's design. It exists so that
any team member — or any AI assistant, regardless of which model is available — can open
this folder and continue the work without losing context.

## Reading order

| Doc | What it answers |
|-----|-----------------|
| [01-FEATURES.md](01-FEATURES.md) | *What* are we building? Every feature, explained in plain language, with how it works end-to-end. |
| [02-ARCHITECTURE.md](02-ARCHITECTURE.md) | *How* is it built? System architecture, agent workflow design, data model, API surface. |
| [03-TECH-STACK.md](03-TECH-STACK.md) | *With what?* Every technology choice and the reason for it, including the model-agnostic LLM layer. |
| [04-ROADMAP.md](04-ROADMAP.md) | *In what order?* Phased implementation plan with checkboxes — **update this as work completes**. |

## Rules for continuing this project (human or AI)

1. **Read `CLAUDE.md` at the repo root first**, then this folder. `CLAUDE.md` describes the
   code as it exists; these docs describe the design target.
2. **The roadmap is the state file.** Before starting work, check `04-ROADMAP.md` for what is
   done (checked) and what is next. After finishing a task, check it off and note the date.
3. **Never hardcode an LLM provider.** All model calls go through `app/core/llm.py`
   (see 03-TECH-STACK). Switching from Gemini to Claude to OpenAI must only ever require
   changing `.env`, not code.
4. **Every agent is a LangGraph node/subgraph with tools.** No agent talks to the database
   directly from prompt text — it calls typed tools. See 02-ARCHITECTURE.
5. **Keep docs and code in sync.** If a design decision changes, update the relevant doc in
   the same commit.
