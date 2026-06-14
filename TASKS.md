# TASKS.md — EcoTurnaround OS

## Current Rule

Only work on one task at a time.  
Do not modify unrelated files.  
After each task, run tests.  
Update this file when the task is complete.

---

## T1 — Repository Skeleton

Status: DONE

Create:

- `app.py`
- `requirements.txt`
- `README.md`
- `AGENTS.md`
- `docs/PROJECT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/SCHEMA.md`
- `data/presets/`
- `data/reflection_log.jsonl`
- `ecoturn/`
- `tests/`

Done when:

- project imports cleanly
- `pytest` can run
- `streamlit run app.py` starts a placeholder page

---

## T2 — Schemas

Status: DONE

Implement `ecoturn/schemas.py`.

Required models:

- `ScenarioSpec`
- `ObjectiveSpec`
- `FleetSpec`
- `SafetyPolicy`
- `SolverPolicy`
- `Vehicle`
- `Task`
- `Charger`
- `DispatchEvent`
- `Schedule`
- `Metrics`
- `Violation`
- `VerificationReport`
- `RefinementProposal`
- `ReflectionEntry`

Done when:

- models validate sample data
- `tests/test_schemas.py` passes

---

## T3 — Scenario Generator

Status: DONE

Implement `ecoturn/scenario_generator.py`.

It should generate:

- zones
- travel-time matrix
- vehicles
- tasks
- chargers

Done when:

- same seed generates same scenario
- generated vehicles/tasks/chargers validate against schemas
- `tests/test_scenario_generator.py` passes

---

## T3.1 — ATL-Sandbox Default Scenario

Status: DONE

Refinement of T3: replaced the generic airport graph with an ATL-inspired
synthetic `ATL-sandbox` graph (domestic/international terminals, concourses
T/A/B/C/D/E/F ordered west-to-east, cargo north/midfield/south, catering,
maintenance, three charging hubs, restricted runway crossing, future
autonomy corridor). Storytelling/demo model only — not real ATL or Delta
data. Determinism, `synthetic=True`, and full travel-time coverage
preserved. See `docs/PROJECT_SPEC.md` → "ATL-Sandbox Modeling Assumption".

---

## T4 — Baseline Simulator

Status: DONE

Implement:

- `ecoturn/baseline.py`
- basic simulator logic

Policy:

- FCFS
- nearest compatible vehicle
- simple EV charge-when-idle

Done when:

- baseline produces a schedule
- metrics are computed
- no invalid schema objects
- `tests/test_baseline.py` passes

---

## T5 — Optimizer

Status: DONE

Implement `ecoturn/optimizer.py`.

Policy:

- rolling-horizon greedy
- score by lateness risk, distance, CO2e, SOC risk, charger queue, freshness risk

Done when:

- optimizer produces schedule
- optimizer improves at least one metric in default scenario
- `tests/test_optimizer.py` passes

---

## T6 — Verifier

Status: TODO

Implement `ecoturn/verifier.py`.

Check:

- vehicle overlap
- incompatible assignment
- SOC below absolute minimum
- charger over-capacity
- restricted zone violation
- autonomy corridor violation
- critical task late

Done when:

- verifier detects intentionally bad schedules
- verifier passes default optimized schedule
- `tests/test_verifier.py` passes

---

## T7 — Adaptive Refinement

Status: TODO

Implement `ecoturn/refinement.py`.

Rules:

- late task rate high → increase lateness penalty
- charger queue high → increase charger queue penalty
- waste high → increase freshness weight
- SOC violation → increase dispatch SOC threshold
- safety-critical change → human gate

Done when:

- produces deterministic proposals
- distinguishes auto vs human_gate
- `tests/test_refinement.py` passes

---

## T8 — Hermes Memory

Status: TODO

Implement `ecoturn/memory.py`.

Features:

- append JSONL reflection entry
- retrieve lessons by scenario tags
- support replay with memory

Done when:

- entries can be written and retrieved
- `tests/test_memory.py` passes

---

## T9 — Streamlit App

Status: TODO

Implement `app.py`.

Tabs:

1. Prompt & Model
2. Baseline vs Optimized
3. Verifier & Boundary Refinement
4. Hermes Reflection
5. Artifacts

Done when:

- app runs locally
- default prompt works
- baseline and optimized results show
- verifier report shows
- refinement proposals show
- memory replay shows

---

## T10 — Demo Polish

Status: TODO

Add:

- README
- demo script
- default scenario
- fallback screenshots if needed
- final Devpost language

Done when:

- 3-minute demo is possible without live debugging