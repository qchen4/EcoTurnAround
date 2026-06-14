# EcoTurnaround OS

**EcoTurnaround OS is an ATL-sandbox decision cockpit for sustainable airport
ground operations.** It turns a natural-language operational goal into a
structured scenario, simulates baseline and optimized ground-ops dispatch,
verifies hard safety constraints, produces an engineering-style bottleneck
report, proposes adaptive boundary refinements, and records Hermes-style
reflection memory so future runs learn from past ones.

> **Claim boundary:** This is a **synthetic ATL-sandbox prototype**. It uses
> **no real Delta or ATL operational data** (no real fleet counts, flight
> schedules, GSE locations, or charging infrastructure) and makes **no claim of
> global optimality**. All tasks, vehicles, chargers, travel times, emissions
> proxies, and metrics are synthetic prototype assumptions.

## Track alignment

Built for **Moving Things & People**, addressing:

- **Port & Airport Sustainability** — reduce a CO2e proxy for ground-service
  equipment during the diesel → electric → autonomous transition.
- **Supply Chain Visibility & Efficiency** — verifiable dispatch with a
  bottleneck/critical-path report and before/after KPIs.
- **EV Charging Experience** — SOC-aware dispatch, charge-when-needed behavior,
  and charging-hub modeling.

## Pipeline

```
Natural-language prompt
  → ATL-sandbox scenario (deterministic synthetic generator)
  → baseline dispatch (FCFS, nearest compatible vehicle)
  → optimized dispatch (priority-based rolling-horizon greedy)
  → metrics (baseline = 100 index; lower is better)
  → verifier (hard operational + safety constraints)
  → bottleneck report (worst late / energy / CO2e / waste / constraint risk)
  → adaptive refinement (auto vs human-gated proposals)
  → Hermes reflection memory (JSONL lessons, deterministic retrieval)
```

## Project layout

```
app.py                  Streamlit Decision Cockpit (UI orchestration only)
requirements.txt        Python dependencies
ecoturn/                Core package
  schemas.py            Pydantic data contracts (single source of truth)
  parser.py             Natural language → ScenarioSpec (stub / fallback)
  scenario_generator.py Deterministic synthetic ATL-sandbox generation
  simulator.py          Shared simulation primitives + energy/CO2e proxy model
  baseline.py           Baseline dispatch policy
  optimizer.py          Optimized dispatch policy (greedy, scored)
  metrics.py            Metric calculation (indices + raw totals)
  verifier.py           Hard constraint checks
  analysis.py           Bottleneck / critical-path diagnostic report
  refinement.py         Adaptive boundary refinement proposals
  memory.py             Hermes reflection JSONL memory
data/
  presets/              Scenario presets
  reflection_log.jsonl  Hermes reflection log
tests/                  Pytest suite (135 tests)
docs/                   Spec, architecture, schema, demo & submission materials
```

## Requirements

- Python 3.11+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

The app runs fully offline — **no LLM or external API is required**. The
natural-language prompt is recorded for context; scenario building uses a
deterministic ATL-sandbox fallback.

## Run the tests

```bash
pytest
```

## Demo path

1. Open the **Decision Cockpit**, keep the default goal, click **Run Full
   Pipeline**.
2. Read the KPI cards: **CO2e** and **Cost** indices drop below 100, **late
   task rate** is preserved, **Verifier = PASS**.
3. Note the tradeoff line and top recommendation (freshness priority, because
   waste regressed).
4. **Schedule Comparison** — baseline vs optimized index cards.
5. **Bottleneck Report** — the worst-waste finding explains *why* waste rose.
6. **Refinement & Memory** — auto vs human-gated proposals; save a reflection
   and see retrieved lessons.
7. **Artifacts** — download scenario/schedules/metrics/report JSON & CSV.

## What is innovative?

- **Natural-language goal → verifiable model**, not just a chatbot answer.
- **Engineering-grade diagnostics**: a Vivado-timing-report-style bottleneck /
  critical-path analysis with evidence and confidence.
- **Adaptive refinement with a safety gate**: emissions/cost/lateness weights
  can auto-adjust, but absolute SOC, restricted zones, autonomous corridors,
  and critical deadlines are **never auto-relaxed** — they require human
  approval.
- **Hermes reflection memory**: the system remembers failure modes and lessons
  so the next run starts smarter.

## Limitations

- Synthetic ATL-sandbox data only; not calibrated to real operations.
- Greedy optimizer, not a global MILP/VRP — no optimality guarantee.
- `charger_queue_peak` is a documented placeholder (0.0) pending explicit
  charging-contention modeling.
- The LLM parser is a deterministic fallback; prompts are not yet parsed into
  custom specs.

## Future work

- Real LLM intent parsing into `ScenarioSpec`.
- Explicit charger-contention simulation and queue metrics.
- Local-search / rolling-horizon improvements over the greedy core.
- Optional Z3-backed verification.
- Calibration against (appropriately licensed) real ground-ops data.

## Status

Built task-by-task per [`TASKS.md`](TASKS.md). **T1–T9.5 complete** (schemas,
generator, baseline, optimizer, verifier, bottleneck analysis, refinement,
Hermes memory, Streamlit cockpit, demo polish); **T10** prepares demo and
submission materials (see [`docs/`](docs/)).
