# File 1: `AGENTS.md`

```md
# AGENTS.md — EcoTurnaround OS

## Mission

Build a 3-day hackathon MVP called **EcoTurnaround OS**.

EcoTurnaround OS is a natural-language-driven adaptive modeling copilot for airport ground operations. It converts a user’s operational sustainability goal into a structured scenario, simulates baseline and optimized ground-ops dispatch, verifies hard constraints, proposes boundary refinements, and records Hermes-style reflection memory.

Target context: Delta Air Lines / Moving Things & People track.

## Core Demo Loop

Natural language prompt
→ structured Scenario JSON
→ synthetic airport ground-ops scenario
→ baseline dispatch
→ optimized dispatch
→ verifier checks hard constraints
→ adaptive boundary refinement
→ Hermes reflection memory
→ replay with memory improves results

## Build Priorities

1. Working demo over theoretical completeness.
2. Deterministic synthetic data over real data.
3. Simple greedy / rolling-horizon optimizer over full MILP.
4. Rule-based verifier first, optional Z3 later.
5. Stable Streamlit UI over complex frontend.
6. Clear before/after metrics over hidden complexity.

## Non-Goals

Do not build:

- real Delta data integration
- full airport digital twin
- real autonomous vehicle control
- real wireless charging physics
- reinforcement learning
- production database
- complex multi-agent framework
- React/FastAPI split app
- full global optimizer

## Coding Rules

- Use Python 3.11+.
- Use type hints.
- Use Pydantic models from `ecoturn/schemas.py`.
- Keep modules small.
- Do not invent new data formats outside `schemas.py`.
- Do not silently swallow errors.
- Synthetic data must always be labeled as synthetic.
- Never claim results are real Delta operational numbers.
- Avoid unrelated refactors.
- After each task, run tests.

## Module Boundaries

- `schemas.py`: data contracts only.
- `scenario_generator.py`: synthetic data generation only.
- `baseline.py`: baseline dispatch policy only.
- `optimizer.py`: optimized dispatch policy only.
- `verifier.py`: hard constraint checks only.
- `refinement.py`: boundary refinement proposals only.
- `memory.py`: Hermes reflection JSONL only.
- `metrics.py`: metric calculation only.
- `app.py`: Streamlit UI orchestration only.

## Safety Boundary Rule

The system may automatically adjust:

- objective weights
- rolling horizon size
- charger queue penalty
- freshness priority
- solver fallback policy

The system must require human approval before changing:

- absolute minimum SOC
- restricted zones
- autonomous vehicle allowed corridors
- critical turnaround deadlines
- hard safety constraints

The system must never automatically relax safety-critical constraints.
```







