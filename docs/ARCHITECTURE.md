# File 3: `docs/ARCHITECTURE.md`

```md
# EcoTurnaround OS — Architecture

## System Pipeline

User Prompt
→ Intent Parser
→ ScenarioSpec JSON
→ Scenario Generator
→ Baseline Simulator
→ Optimized Simulator
→ Metrics Calculator
→ Verifier
→ Adaptive Refinement Engine
→ Hermes Reflection Memory
→ Streamlit Dashboard

## Components

### 1. Intent Parser

File: `ecoturn/parser.py`

Input:

- natural-language prompt

Output:

- `ScenarioSpec`

Responsibilities:

- parse objectives
- parse fleet assumptions
- parse charger assumptions
- parse safety policy
- fall back to preset scenario when LLM is unavailable

### 2. Scenario Generator

File: `ecoturn/scenario_generator.py`

Input:

- `ScenarioSpec`

Output:

- zones
- travel-time matrix
- vehicles
- tasks
- chargers

Responsibilities:

- generate deterministic synthetic data
- use fixed random seed
- support scenario presets

### 3. Baseline Simulator

Files:

- `ecoturn/baseline.py`
- `ecoturn/simulator.py`

Policy:

- FCFS tasks
- nearest compatible vehicle
- simple charge-when-idle EV policy

Purpose:

- provide a weak but realistic comparison baseline

### 4. Optimizer

File: `ecoturn/optimizer.py`

Policy:

- rolling-horizon greedy assignment
- deadline-aware scoring
- SOC-aware scoring
- charger-aware scoring
- freshness-aware scoring
- optional local swaps

Do not implement full global MILP.

### 5. Metrics

File: `ecoturn/metrics.py`

Compute:

- CO2e index
- waste index
- idle time index
- late task rate
- charger queue peak
- runtime
- cost index

### 6. Verifier

File: `ecoturn/verifier.py`

Checks:

- no vehicle overlap
- compatible vehicle-task assignment
- EV SOC not below absolute minimum
- charger capacity not exceeded
- restricted zone respected
- autonomous vehicles stay inside allowed corridors
- critical tasks not late unless explicitly soft

### 7. Adaptive Refinement

File: `ecoturn/refinement.py`

Input:

- metrics
- verification report
- scenario

Output:

- refinement proposals

Rules:

- late tasks high → increase lateness penalty
- charger queue high → increase charger queue penalty
- waste high → increase freshness priority
- SOC violation → increase dispatch SOC threshold
- safety boundary changes → human gate

### 8. Hermes Memory

File: `ecoturn/memory.py`

Storage:

- `data/reflection_log.jsonl`

Responsibilities:

- append reflection entries
- retrieve relevant lessons by tags
- explain why second run changed behavior

### 9. Streamlit App

File: `app.py`

Tabs:

1. Prompt & Model
2. Baseline vs Optimized
3. Verifier & Boundary Refinement
4. Hermes Reflection
5. Artifacts

The app must run even without LLM API access.
```