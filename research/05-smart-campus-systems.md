# 05 — Smart Campus Management Systems

## What the concept is

A **smart campus** uses technology (traditionally IoT sensors, networks, dashboards) to manage
campus activities — scheduling, energy, facilities, safety, communication — more efficiently.
This is our project's **domain**. Our contribution is to move the smart campus from *sensing and
dashboards* (reactive) to an *agentic decision layer* (proactive).

## Papers

| Paper | Source / Year | Core Idea | Limitation / Gap | What We Take |
|-------|---------------|-----------|------------------|--------------|
| Internet of Things Based Model for Smart Campus: Challenges and Limitations | [IEEE, 2020](https://ieeexplore.ieee.org/document/9036629/) | 3-layer smart-campus model: perception → network → application | **Hardware/sensing-centric; reactive; no autonomous decision-making** | The layered model; our agents sit in an enhanced "application/decision" layer |
| Roadmap to Smart Campus Based on IoT | [IEEE, 2020](https://ieeexplore.ieee.org/abstract/document/9197926/) | Vision for smart schooling, classrooms, parking via IoT | Roadmap/vision; no intelligent automation | Frames the campus subsystems (scheduling, facilities) we automate |
| IoT, AI and Digital Twin for Smart Campus | [IEEE, 2022](https://ieeexplore.ieee.org/document/9910286/) | Digital twin + IoT for campus energy management | Focus on energy + digital twin infra; not operations agents | Precedent for our (stretch) Energy Watchdog agent; shows AI+campus fit |
| Survey Toward a Smart Campus Using the Internet of Things | [IEEE, 2016](https://ieeexplore.ieee.org/document/7575869/) | Survey of smart-campus drivers: service quality, cost, sustainability | Survey; IoT lens only | Motivation/justification (cost, efficiency) for our problem statement |
| Internet of Things Based Smart Campus — A Review | [IET/IEEE, 2022](https://ieeexplore.ieee.org/document/9770699) | Reviews smart-campus types by IoT layers and applications | Review; no decision intelligence | Establishes state-of-the-art baseline we extend with agents |
| Smart Campus as a Learning Platform for Industry 4.0 and IoT | [IEEE, 2019](https://ieeexplore.ieee.org/document/9277679/) | Uses smart campus as an education/Industry-4.0 platform | Pedagogical framing | Broadens relevance; supports the education context |

## How it maps to our project

Every smart-campus paper here is **IoT- and sensing-centric** and, by their own framing,
**reactive** — they collect data and display it, matching our problem statement's critique of
"rigid, reactive, manually-supervised" systems. Our system adopts their **layered view** (the
perception/network/application model from IEEE 9036629) but adds a new top layer: an **agentic
decision layer** that acts on the data autonomously. That is the precise gap we fill — detailed in
[09-DIFFERENTIATION.md](09-DIFFERENTIATION.md).
