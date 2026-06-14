# EcoTurnaround OS

A natural-language-driven adaptive modeling copilot for **airport ground
operations**. It converts an operational sustainability goal into a structured
scenario, simulates baseline and optimized ground-ops dispatch, verifies hard
constraints, proposes boundary refinements, and records Hermes-style reflection
memory.

> **Prototype notice:** All scenario data is **synthetic**. This project does
> **not** use real Delta data and does **not** represent real Delta performance.

## Demo loop

```
Natural-language prompt
  → structured Scenario JSON
  → synthetic airport ground-ops scenario
  → baseline dispatch
  → optimized dispatch
  → verifier checks hard constraints
  → adaptive boundary refinement
  → Hermes reflection memory
  → replay with memory improves results
```

## Project layout

```
app.py                  Streamlit UI entry point
requirements.txt        Python dependencies
ecoturn/                Core package
  schemas.py            Pydantic data contracts
  parser.py             Natural language → ScenarioSpec
  scenario_generator.py Synthetic scenario generation
  simulator.py          Shared simulation primitives
  baseline.py           Baseline dispatch policy
  optimizer.py          Optimized dispatch policy
  metrics.py            Metric calculation
  verifier.py           Hard constraint checks
  refinement.py         Boundary refinement proposals
  memory.py             Hermes reflection memory
data/
  presets/              Scenario presets
  reflection_log.jsonl  Hermes reflection log
tests/                  Pytest suite
docs/                   Spec, architecture, schema contract
```

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

The app runs even without LLM API access.

## Test

```bash
pytest
```

## Status

Built task-by-task per [`TASKS.md`](TASKS.md). Currently: **T1 — Repository
Skeleton** complete.
