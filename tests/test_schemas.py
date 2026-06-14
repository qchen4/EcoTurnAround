"""T2 — schema contract tests.

Validate that each core model accepts a valid object, that constrained
fields reject invalid values, and that nested/serializable models behave
as required by ``docs/SCHEMA.md``.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ecoturn.schemas import (
    Charger,
    DispatchEvent,
    FleetSpec,
    Metrics,
    ObjectiveSpec,
    RefinementProposal,
    ReflectionEntry,
    SafetyPolicy,
    ScenarioSpec,
    Schedule,
    SolverPolicy,
    Task,
    Vehicle,
    VerificationReport,
    Violation,
)


def make_vehicle(**overrides) -> Vehicle:
    data = dict(
        vehicle_id="V1",
        vehicle_type="belt_loader",
        powertrain="ev",
        current_zone="Z1",
    )
    data.update(overrides)
    return Vehicle(**data)


def make_task(**overrides) -> Task:
    data = dict(
        task_id="T1",
        task_type="bag_transfer",
        deadline_min=60.0,
        duration_min=10.0,
        origin_zone="Z1",
        destination_zone="Z2",
    )
    data.update(overrides)
    return Task(**data)


def make_charger(**overrides) -> Charger:
    data = dict(charger_id="C1", charger_type="dc_fast", zone="Z1", power_kw=150.0)
    data.update(overrides)
    return Charger(**data)


def make_dispatch_event(**overrides) -> DispatchEvent:
    data = dict(
        vehicle_id="V1",
        task_id="T1",
        start_time_min=0.0,
        end_time_min=10.0,
        origin_zone="Z1",
        destination_zone="Z2",
    )
    data.update(overrides)
    return DispatchEvent(**data)


def test_valid_objective_spec() -> None:
    obj = ObjectiveSpec(name="co2e", weight=2.0, direction="minimize")
    assert obj.weight == 2.0
    assert ObjectiveSpec(name="reliability").direction == "minimize"


def test_valid_fleet_spec() -> None:
    fleet = FleetSpec(diesel_count=2, ev_count=3, vehicles=[make_vehicle()])
    assert fleet.ev_count == 3
    assert fleet.vehicles[0].vehicle_id == "V1"


def test_valid_safety_policy_defaults() -> None:
    policy = SafetyPolicy()
    assert policy.allow_auto_relax_safety is False
    assert 0.0 <= policy.min_soc <= 1.0


def test_valid_solver_policy() -> None:
    policy = SolverPolicy(rolling_horizon_min=20.0)
    assert policy.rolling_horizon_min == 20.0
    assert policy.solver_fallback == "greedy"


def test_valid_vehicle() -> None:
    v = make_vehicle(powertrain="autonomous_ev", soc=0.5)
    assert v.powertrain == "autonomous_ev"
    assert v.soc == 0.5


def test_valid_task() -> None:
    task = make_task(is_critical=True, priority=5)
    assert task.is_critical is True
    assert task.priority == 5


def test_valid_charger() -> None:
    charger = make_charger(charger_type="wireless_future", capacity=2)
    assert charger.charger_type == "wireless_future"
    assert charger.capacity == 2


def test_valid_scenario_spec_nested() -> None:
    spec = ScenarioSpec(
        scenario_name="atl_demo",
        objectives=[ObjectiveSpec(name="co2e")],
        fleet=FleetSpec(ev_count=1, vehicles=[make_vehicle()]),
        chargers=[make_charger()],
        tasks=[make_task()],
    )
    assert spec.hub == "ATL"
    assert spec.tasks[0].task_id == "T1"
    assert spec.chargers[0].charger_id == "C1"


def test_valid_metrics_defaults() -> None:
    metrics = Metrics()
    assert metrics.co2e_index == 100.0


def test_invalid_powertrain_fails() -> None:
    with pytest.raises(ValidationError):
        make_vehicle(powertrain="hydrogen")


def test_invalid_charger_type_fails() -> None:
    with pytest.raises(ValidationError):
        make_charger(charger_type="supercharger")


def test_invalid_refinement_mode_fails() -> None:
    with pytest.raises(ValidationError):
        RefinementProposal(change="lateness_penalty", mode="automatic")


def test_invalid_violation_severity_fails() -> None:
    with pytest.raises(ValidationError):
        Violation(constraint="soc_min", severity="fatal")


def test_schedule_holds_multiple_events() -> None:
    schedule = Schedule(
        policy_name="optimized",
        scenario_name="atl_demo",
        events=[
            make_dispatch_event(task_id="T1"),
            make_dispatch_event(task_id="T2", start_time_min=10.0, end_time_min=25.0),
        ],
    )
    assert len(schedule.events) == 2
    assert {e.task_id for e in schedule.events} == {"T1", "T2"}


def test_verification_report_with_violations() -> None:
    report = VerificationReport(
        passed=False,
        violations=[
            Violation(constraint="soc_min", severity="critical", vehicle_id="V1"),
            Violation(constraint="overlap", severity="high", vehicle_id="V1"),
        ],
        counterexamples=[{"vehicle_id": "V1", "detail": "double-booked at t=10"}],
        hard_constraint_summary={"soc_min": 1, "overlap": 1},
    )
    assert report.passed is False
    assert len(report.violations) == 2
    assert report.hard_constraint_summary["soc_min"] == 1
    assert report.counterexamples[0]["vehicle_id"] == "V1"


def test_refinement_proposal_modes() -> None:
    auto = RefinementProposal(change="charger_queue_penalty", mode="auto")
    gated = RefinementProposal(change="min_soc", mode="human_gate")
    assert auto.mode == "auto"
    assert gated.mode == "human_gate"


def test_reflection_entry_json_serializable() -> None:
    entry = ReflectionEntry(
        attempt_id="a1",
        scenario_signature={"scenario_name": "atl_demo", "hub": "ATL"},
        optimizer="rolling_horizon_greedy",
        result={"co2e_index": 86.0, "late_task_rate": 0.0},
        failure_modes=["charger_congestion"],
        lesson="Raise charger queue penalty when DC fast chargers saturate.",
        tags=["atl", "charging"],
    )
    payload = entry.model_dump_json()
    restored = json.loads(payload)
    assert restored["attempt_id"] == "a1"
    assert restored["result"]["co2e_index"] == 86.0
    assert ReflectionEntry.model_validate_json(payload) == entry
