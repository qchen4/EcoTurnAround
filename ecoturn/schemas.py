"""Data contracts only.

Pydantic models defining every object exchanged between EcoTurnaround OS
modules. This is the single source of truth for the schema contract
described in ``docs/SCHEMA.md`` — other modules must not invent ad-hoc
dictionaries or alternative formats.

All scenario data built on these models is synthetic.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Powertrain = Literal["diesel", "ev", "autonomous_ev"]
ChargerType = Literal["ac", "dc_fast", "opportunity", "wireless_future"]
RefinementMode = Literal["auto", "human_gate"]
Severity = Literal["low", "medium", "high", "critical"]
ObjectiveDirection = Literal["minimize", "maximize"]


class ObjectiveSpec(BaseModel):
    """A single weighted optimization objective."""

    name: str
    weight: float = 1.0
    direction: ObjectiveDirection = "minimize"


class FleetSpec(BaseModel):
    """Fleet composition assumptions for a scenario.

    Counts describe how many vehicles of each powertrain to generate.
    ``vehicles`` may hold an explicit roster when one is supplied.
    """

    diesel_count: int = Field(default=0, ge=0)
    ev_count: int = Field(default=0, ge=0)
    autonomous_ev_count: int = Field(default=0, ge=0)
    vehicles: list["Vehicle"] = Field(default_factory=list)


class SafetyPolicy(BaseModel):
    """Hard safety boundaries.

    These may only be changed through a human gate; the system must never
    automatically relax safety-critical constraints.
    """

    min_soc: float = Field(default=0.2, ge=0.0, le=1.0)
    restricted_zones: list[str] = Field(default_factory=list)
    autonomous_allowed_zones: list[str] = Field(default_factory=list)
    critical_deadline_buffer_min: float = Field(default=0.0, ge=0.0)
    allow_auto_relax_safety: bool = False


class SolverPolicy(BaseModel):
    """Tunable (auto-adjustable) solver parameters."""

    rolling_horizon_min: float = Field(default=30.0, gt=0.0)
    charger_queue_penalty: float = Field(default=1.0, ge=0.0)
    freshness_priority: float = Field(default=1.0, ge=0.0)
    lateness_penalty: float = Field(default=1.0, ge=0.0)
    dispatch_soc_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    solver_fallback: str = "greedy"


class Vehicle(BaseModel):
    """One ground-service vehicle."""

    vehicle_id: str
    vehicle_type: str
    powertrain: Powertrain
    soc: float | None = Field(default=1.0, ge=0.0, le=1.0)
    current_zone: str
    compatible_tasks: list[str] = Field(default_factory=list)
    allowed_zones: list[str] = Field(default_factory=list)
    speed_mph: float = Field(default=15.0, gt=0.0)
    emission_rate: float = Field(default=0.0, ge=0.0)
    energy_rate: float = Field(default=0.0, ge=0.0)


class Task(BaseModel):
    """One ground-operation task."""

    task_id: str
    task_type: str
    release_time_min: float = Field(default=0.0, ge=0.0)
    deadline_min: float = Field(ge=0.0)
    duration_min: float = Field(gt=0.0)
    origin_zone: str
    destination_zone: str
    compatible_vehicle_types: list[str] = Field(default_factory=list)
    priority: int = Field(default=1, ge=0)
    freshness_decay_rate: float = Field(default=0.0, ge=0.0)
    is_critical: bool = False


class Charger(BaseModel):
    """One charging resource."""

    charger_id: str
    charger_type: ChargerType
    zone: str
    power_kw: float = Field(gt=0.0)
    capacity: int = Field(default=1, ge=1)


class ScenarioSpec(BaseModel):
    """A user's natural-language request after parsing."""

    scenario_name: str
    hub: str = "ATL"
    planning_horizon_min: float = Field(default=120.0, gt=0.0)
    time_granularity_min: float = Field(default=5.0, gt=0.0)
    objectives: list[ObjectiveSpec] = Field(default_factory=list)
    fleet: FleetSpec = Field(default_factory=FleetSpec)
    chargers: list[Charger] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)
    solver_policy: SolverPolicy = Field(default_factory=SolverPolicy)


class DispatchEvent(BaseModel):
    """One scheduled task execution."""

    vehicle_id: str
    task_id: str
    start_time_min: float = Field(ge=0.0)
    end_time_min: float = Field(ge=0.0)
    origin_zone: str
    destination_zone: str
    energy_used: float = Field(default=0.0, ge=0.0)
    co2e_proxy: float = Field(default=0.0, ge=0.0)
    late_by_min: float = Field(default=0.0, ge=0.0)


class Schedule(BaseModel):
    """An ordered set of dispatch events produced by a policy."""

    policy_name: str = "baseline"
    scenario_name: str | None = None
    events: list[DispatchEvent] = Field(default_factory=list)


class Metrics(BaseModel):
    """KPI bundle. Baseline index metrics normalize to 100."""

    co2e_index: float = 100.0
    waste_index: float = 100.0
    idle_time_index: float = 100.0
    late_task_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    charger_queue_peak: float = Field(default=0.0, ge=0.0)
    runtime_sec: float = Field(default=0.0, ge=0.0)
    cost_index: float = 100.0


class Violation(BaseModel):
    """A single detected hard-constraint violation."""

    constraint: str
    severity: Severity
    message: str = ""
    vehicle_id: str | None = None
    task_id: str | None = None


class VerificationReport(BaseModel):
    """Result of running the hard-constraint verifier."""

    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    counterexamples: list[dict[str, Any]] = Field(default_factory=list)
    hard_constraint_summary: dict[str, int] = Field(default_factory=dict)


class RefinementProposal(BaseModel):
    """A proposed boundary/parameter refinement.

    ``mode`` distinguishes auto-applicable tweaks from safety-critical
    changes that require a human gate.
    """

    change: str
    from_value: Any = None
    to_value: Any = None
    reason: str = ""
    mode: RefinementMode = "auto"
    expected_effect: str = ""


class ReflectionEntry(BaseModel):
    """A Hermes-style reflection memory entry."""

    attempt_id: str
    scenario_signature: str
    optimizer: str
    result: dict[str, Any] = Field(default_factory=dict)
    failure_modes: list[str] = Field(default_factory=list)
    lesson: str = ""
    tags: list[str] = Field(default_factory=list)


class GeneratedScenario(BaseModel):
    """A fully materialized synthetic scenario produced by the generator.

    Bundles the originating spec with the generated zone graph, travel-time
    matrix, fleet, tasks, and chargers. All contents are synthetic.
    """

    spec: ScenarioSpec
    zones: list[str] = Field(default_factory=list)
    travel_times: dict[str, dict[str, float]] = Field(default_factory=dict)
    vehicles: list[Vehicle] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    chargers: list[Charger] = Field(default_factory=list)
    synthetic: bool = True


FleetSpec.model_rebuild()
