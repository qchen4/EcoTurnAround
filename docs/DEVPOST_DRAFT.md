# EcoTurnaround OS — Devpost Draft (copy-ready)

## Project title

EcoTurnaround OS

## Tagline

An ATL-sandbox decision cockpit for sustainable airport ground operations —
turn a sentence into a verifiable, safety-bounded dispatch plan.

## Inspiration

Airports are electrifying ground-service equipment, but the transition is
messy: diesel, EV, and future autonomous vehicles coexist, competing for
chargers and avoiding restricted airside zones. Operations teams must cut
emissions and waste while never missing a turnaround or crossing a safety
boundary. We wanted to show how a natural-language goal could become a
**verifiable, explainable** operating plan — not just a chatbot opinion.

## What it does

You state an operational goal in plain English. EcoTurnaround OS then:

- generates a synthetic **ATL-sandbox** airport scenario (zones, fleet, tasks,
  chargers, travel times);
- runs a **baseline** dispatch (first-come-first-served, nearest vehicle);
- runs an **optimized** dispatch (priority-based rolling-horizon greedy);
- computes **before/after KPIs** (CO2e, cost, waste, idle, late-task rate;
  baseline = 100, lower is better);
- runs a **verifier** for hard operational and safety constraints;
- produces a **bottleneck / critical-path report** (like a timing report);
- proposes **adaptive refinements**, split into auto vs human-gated;
- records **Hermes reflection memory** so future runs reuse lessons.

## How we built it

Pure Python: **Pydantic** schemas as the single data contract, deterministic
synthetic generation, a greedy scored optimizer, a rule-based verifier, a
diagnostic analyzer, a refinement engine, and a JSONL memory layer — all
surfaced in a **Streamlit** multi-tab "Decision Cockpit." No external APIs, no
database, no frontend framework. 135 unit tests keep each stage honest.

## Challenges we ran into

- Designing a baseline that is realistically weak so the optimizer can *visibly*
  improve it, without faking the numbers.
- Keeping everything **deterministic** for a stable live demo.
- Drawing a clean line between objectives the AI may auto-tune and **safety
  boundaries it must never auto-relax**.
- Being honest about tradeoffs — the optimized run actually *increases*
  perishable waste risk, and we chose to surface that rather than hide it.

## Accomplishments that we're proud of

- A full **goal → scenario → baseline → optimized → verify → diagnose →
  refine → remember** loop that runs offline in one click.
- An **engineering-style bottleneck report** with evidence and confidence.
- A **human-gated safety model** baked into the refinement engine.
- Reflection **memory** that turns one-shot optimization into iterative learning.

## What we learned

- Verifiability and explainability matter more than raw optimization for
  operational trust.
- Surfacing a tradeoff (waste up) with a diagnosis builds more credibility than
  a single "we improved everything" claim.
- A tiny, well-typed schema contract makes a multi-stage pipeline easy to test.

## What's next

- Real LLM intent parsing into `ScenarioSpec`.
- Explicit charger-contention modeling and a real charger-queue metric.
- Local-search improvements over the greedy core; optional Z3 verification.
- Calibration against appropriately licensed real ground-ops data.

## Track fit

**Moving Things & People:**

- **Port & Airport Sustainability** — reduces a CO2e proxy for ground-service
  equipment during fleet electrification.
- **Supply Chain Visibility & Efficiency** — verifiable dispatch with a
  bottleneck report and transparent before/after KPIs.
- **EV Charging Experience** — SOC-aware dispatch, charge-when-needed behavior,
  and charging-hub modeling.

## Sustainability impact

On the synthetic ATL-sandbox default scenario, the optimized policy cuts the
CO2e index to ~31 and the cost index to ~83 (vs a baseline of 100) while
preserving the late-task rate — by shifting work toward electric vehicles and
shorter routes, within hard safety limits. (Synthetic prototype results.)

## Technical architecture

`schemas.py` (contracts) → `scenario_generator.py` → `baseline.py` /
`optimizer.py` (on `simulator.py`) → `metrics.py` → `verifier.py` →
`analysis.py` → `refinement.py` → `memory.py`, orchestrated by a Streamlit
`app.py`. Deterministic, type-hinted, and unit-tested.

## Limitations / claim boundary

This is a **synthetic ATL-sandbox prototype**. It uses **no real Delta or ATL
operational data** and makes **no claim of global optimality**. All numbers are
prototype simulation results on synthetic data. Safety-critical boundaries are
never auto-relaxed; they require human approval.
