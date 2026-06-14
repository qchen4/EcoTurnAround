# File 2: `docs/PROJECT_SPEC.md`

```md
# EcoTurnaround OS — Project Spec

## One-Sentence Pitch

EcoTurnaround OS turns natural-language airport ground-operation goals into verifiable dispatch simulations, then uses data-driven boundary refinement and Hermes-style memory to help airlines reduce emissions without sacrificing turnaround reliability.

## Problem

Airport ground operations are transitioning from diesel ground service equipment to mixed electric, semi-autonomous, and eventually autonomous fleets. During this transition, multiple technology generations will coexist:

- diesel human-driven vehicles
- EV ground service equipment
- future autonomous EVs
- fixed plug-in chargers
- opportunity charging points
- future wireless charging pads
- restricted autonomous corridors

The operational challenge is to reduce CO2e, idle time, waste, and charging congestion while preserving aircraft turnaround deadlines and safety boundaries.

## Target User

Primary user:

- airline ground operations manager

Secondary users:

- airport sustainability planner
- fleet electrification planner
- ground service contractor
- infrastructure planning team

## MVP

The MVP must demonstrate:

1. Natural-language prompt input.
2. Prompt parsed into structured Scenario JSON.
3. Synthetic ATL-sandbox airport scenario generation.
4. Baseline dispatch simulation.
5. Optimized dispatch simulation.
6. KPI comparison dashboard.
7. Hard-constraint verifier.
8. Adaptive boundary refinement proposals.
9. Human-gated safety boundary changes.
10. Hermes-style reflection memory.
11. Replay with memory.

## Core Metrics

- CO2e index
- waste index
- idle time index
- late task rate
- charger queue peak
- runtime
- cost index

Baseline index metrics should normalize to 100.

## Demo Claim Boundary

All numbers are prototype simulation results using synthetic data. The project must not claim to use real Delta data or represent real Delta performance.

## Success Criteria

The MVP succeeds if a judge can understand within 3 minutes:

1. the airport ground-ops problem;
2. why mixed-generation fleet transition is hard;
3. how natural language becomes a structured model;
4. how baseline and optimized dispatch differ;
5. what constraints are verified;
6. how failed assumptions trigger boundary refinement;
7. how Hermes memory improves the second run.

## ATL-Sandbox Modeling Assumption

The MVP uses an ATL-inspired synthetic airport graph. The graph reflects public, high-level airport structure such as domestic/international terminals, concourses T/A/B/C/D/E/F, cargo areas, catering, maintenance, and charging hubs. It does not use real ATL operational data, real Delta fleet counts, real flight schedules, real GSE locations, or real charging infrastructure.

All tasks, vehicles, chargers, travel times, emissions proxies, and performance metrics are synthetic prototype assumptions.
```