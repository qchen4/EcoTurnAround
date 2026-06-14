# File 5: `docs/SCHEMA.md`

```md
# EcoTurnaround OS — Schema Contract

All modules must use the models in `ecoturn/schemas.py`.

Do not invent alternative dictionaries or ad-hoc formats.

## Core Objects

### ScenarioSpec

Represents the user’s natural-language request after parsing.

Fields:

- `scenario_name`
- `hub`
- `planning_horizon_min`
- `time_granularity_min`
- `objectives`
- `fleet`
- `chargers`
- `tasks`
- `safety_policy`
- `solver_policy`

### Vehicle

Represents one ground-service vehicle.

Fields:

- `vehicle_id`
- `vehicle_type`
- `powertrain`
- `soc`
- `current_zone`
- `compatible_tasks`
- `allowed_zones`
- `speed_mph`
- `emission_rate`
- `energy_rate`

Allowed `powertrain` values:

- `diesel`
- `ev`
- `autonomous_ev`

### Task

Represents one ground-operation task.

Fields:

- `task_id`
- `task_type`
- `release_time_min`
- `deadline_min`
- `duration_min`
- `origin_zone`
- `destination_zone`
- `compatible_vehicle_types`
- `priority`
- `freshness_decay_rate`
- `is_critical`

### Charger

Represents one charging resource.

Fields:

- `charger_id`
- `charger_type`
- `zone`
- `power_kw`
- `capacity`

Allowed `charger_type` values:

- `ac`
- `dc_fast`
- `opportunity`
- `wireless_future`

### DispatchEvent

Represents one scheduled task execution.

Fields:

- `vehicle_id`
- `task_id`
- `start_time_min`
- `end_time_min`
- `origin_zone`
- `destination_zone`
- `energy_used`
- `co2e_proxy`
- `late_by_min`

### Metrics

Fields:

- `co2e_index`
- `waste_index`
- `idle_time_index`
- `late_task_rate`
- `charger_queue_peak`
- `runtime_sec`
- `cost_index`

### VerificationReport

Fields:

- `passed`
- `violations`
- `counterexamples`
- `hard_constraint_summary`

### RefinementProposal

Fields:

- `change`
- `from_value`
- `to_value`
- `reason`
- `mode`
- `expected_effect`

Allowed `mode` values:

- `auto`
- `human_gate`

### ReflectionEntry

Fields:

- `attempt_id`
- `scenario_signature`
- `optimizer`
- `result`
- `failure_modes`
- `lesson`

## Index Metric Rule

Baseline index metrics should normalize to 100.

Example:

- baseline CO2e index = 100
- optimized CO2e index = 86

This means the optimized policy reduced the synthetic CO2e proxy by 14%.

## Synthetic Data Rule

All generated data must be labeled synthetic.  
Never imply the demo uses real Delta operational data.
```
