# 08 — Facility / Room Booking & Resource Allocation

## What the concept is

Campuses must allocate scarce venues (auditoriums, seminar halls, labs, grounds) without clashes
and with capacity matching. Our **Booking Agent** (Phase 3) handles natural-language booking
requests, detects conflicts against **both existing bookings and the academic timetable**,
matches capacity, proposes alternatives, and runs an approval chain.

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| Design and Development of an Integrated Room Reservation System for Higher Education Institutions | [IEEE, 2021](https://ieeexplore.ieee.org/document/9436766/) | Online system to ease room/facility management with real-time info exchange; cuts reservation effort/time | **Form-based CRUD; no NL interface, no autonomous conflict-resolution, no agent** | Baseline reservation system — we add NL + agentic conflict handling |
| Optimization of Room Allocation Plans (University Duisburg-Essen) with a Regulatory Algorithm | [IEEE, 2016](https://ieeexplore.ieee.org/document/7744407/) | Evolutionary "regulatory algorithm" optimizes room allocation on real university data | Optimization only; batch; not interactive/agentic | Evidence of algorithmic room allocation; we keep it conversational + real-time |
| Online Reservation Inventory Systems in Higher Education | [IJRES, 2025](https://www.ijres.org/papers/Volume-13/Issue-7/13077382.pdf) | Architecture/layers of online room-booking systems for universities | Traditional IS design; no AI | System-design reference for our booking data model + flow |
| DHMS: A Digital Hostel Management System Integrating Campus ChatBot, Predictive Intelligence, and Real-Time Automation | [arXiv:2507.17759, 2025](https://arxiv.org/pdf/2507.17759) | Campus system combining a chatbot + predictive automation for hostel management | Hostel-specific; chatbot not full agent | Nearby example of chatbot + campus automation; we generalize to an agent |

## How it maps to our project

Existing reservation systems (IEEE 9436766, IJRES 2025) are **form-based CRUD** — the user fills a
form and the system stores it. Our Booking Agent instead accepts **natural language** ("Need the
auditorium 21 Aug 2–5pm for ~120 people"), extracts structured fields via the supervisor, and
**checks conflicts against the live timetable as well as other bookings** (a hall used for a class
is not free) — a check those systems don't perform. When a venue is taken, it **proposes
alternatives** by capacity, then routes to the approval chain
([07-human-in-the-loop.md](07-human-in-the-loop.md)). The optimization paper (IEEE 7744407) shows
algorithmic allocation is viable; we keep ours interactive and agentic rather than batch.
