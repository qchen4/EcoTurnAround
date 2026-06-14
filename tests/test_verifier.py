"""T6 — verifier tests.

Verify that the rule-based hard-constraint verifier passes on the default
baseline/optimized schedules and detects each intentionally-injected
violation type, with a populated summary and correct ``passed`` flag.
"""

from __future__ import annotations

from ecoturn.baseline import simulate_baseline
from ecoturn.optimizer import simulate_optimized
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.schemas import (
    DispatchEvent,
    GeneratedScenario,
    ScenarioSpec,
    Schedule,
    Task,
    Vehicle,
    VerificationReport,
)
from ecoturn.verifier import verify_schedule

RESTRICTED = "restricted_runway_crossing"


def _scenario_with(vehicles: list[Vehicle], tasks: list[Task]) -> GeneratedScenario:
    return GeneratedScenario(
        spec=ScenarioSpec(scenario_name="verify_test"),
        zones=["depot", "concourse_A", "concourse_B", "cargo_north", RESTRICTED],
        vehicles=vehicles,
        tasks=tasks,
    )


def _baggage_vehicle(vehicle_id: str, powertrain: str = "diesel", **kw) -> Vehicle:
    data = dict(
        vehicle_id=vehicle_id,
        vehicle_type="baggage_tractor",
        powertrain=powertrain,
        current_zone="depot",
        compatible_tasks=["baggage"],
        allowed_zones=["depot", "concourse_A", "concourse_B"],
    )
    data.update(kw)
    return Vehicle(**data)


def _baggage_task(task_id: str, **kw) -> Task:
    data = dict(
        task_id=task_id,
        task_type="baggage",
        deadline_min=100.0,
        duration_min=10.0,
        origin_zone="depot",
        destination_zone="concourse_A",
        compatible_vehicle_types=["baggage_tractor"],
    )
    data.update(kw)
    return Task(**data)


def _event(vehicle_id: str, task_id: str, **kw) -> DispatchEvent:
    data = dict(
        vehicle_id=vehicle_id,
        task_id=task_id,
        start_time_min=0.0,
        end_time_min=10.0,
        origin_zone="depot",
        destination_zone="concourse_A",
    )
    data.update(kw)
    return DispatchEvent(**data)


def _constraints(report: VerificationReport) -> set[str]:
    return {v.constraint for v in report.violations}


# --- Default schedules pass -------------------------------------------------

def test_passes_on_default_baseline() -> None:
    scenario = generate_scenario(default_scenario_spec(), seed=42)
    report = verify_schedule(simulate_baseline(scenario), scenario)
    assert report.passed is True
    assert report.violations == []


def test_passes_on_default_optimized() -> None:
    scenario = generate_scenario(default_scenario_spec(), seed=42)
    report = verify_schedule(simulate_optimized(scenario), scenario)
    assert report.passed is True
    assert report.violations == []


# --- Injected violations ----------------------------------------------------

def test_detects_vehicle_overlap() -> None:
    scenario = _scenario_with(
        [_baggage_vehicle("V1")],
        [_baggage_task("T1"), _baggage_task("T2")],
    )
    schedule = Schedule(
        events=[
            _event("V1", "T1", start_time_min=0.0, end_time_min=20.0),
            _event("V1", "T2", start_time_min=10.0, end_time_min=30.0),
        ]
    )
    report = verify_schedule(schedule, scenario)
    assert "vehicle_overlap" in _constraints(report)
    assert report.passed is False


def test_detects_incompatible_assignment() -> None:
    cargo_task = Task(
        task_id="T1",
        task_type="cargo",
        deadline_min=100.0,
        duration_min=10.0,
        origin_zone="cargo_north",
        destination_zone="concourse_A",
        compatible_vehicle_types=["cargo_tug"],
    )
    scenario = _scenario_with([_baggage_vehicle("V1")], [cargo_task])
    schedule = Schedule(
        events=[_event("V1", "T1", origin_zone="cargo_north")]
    )
    report = verify_schedule(schedule, scenario)
    assert "incompatible_vehicle_task" in _constraints(report)


def test_detects_missing_task() -> None:
    scenario = _scenario_with(
        [_baggage_vehicle("V1")],
        [_baggage_task("T1"), _baggage_task("T2")],
    )
    schedule = Schedule(events=[_event("V1", "T1")])
    report = verify_schedule(schedule, scenario)
    assert "missing_task" in _constraints(report)


def test_detects_duplicate_task() -> None:
    scenario = _scenario_with(
        [_baggage_vehicle("V1"), _baggage_vehicle("V2")],
        [_baggage_task("T1")],
    )
    schedule = Schedule(
        events=[
            _event("V1", "T1", start_time_min=0.0, end_time_min=10.0),
            _event("V2", "T1", start_time_min=20.0, end_time_min=30.0),
        ]
    )
    report = verify_schedule(schedule, scenario)
    assert "duplicate_task" in _constraints(report)


def test_detects_restricted_zone_violation() -> None:
    # Diesel vehicle whose allowed_zones excludes the restricted crossing.
    vehicle = _baggage_vehicle("V1", allowed_zones=["depot", "concourse_A"])
    task = _baggage_task("T1", destination_zone=RESTRICTED)
    scenario = _scenario_with([vehicle], [task])
    schedule = Schedule(
        events=[_event("V1", "T1", destination_zone=RESTRICTED)]
    )
    report = verify_schedule(schedule, scenario)
    assert "restricted_zone_violation" in _constraints(report)


def test_detects_autonomy_corridor_violation() -> None:
    vehicle = Vehicle(
        vehicle_id="V1",
        vehicle_type="tow_tractor",
        powertrain="autonomous_ev",
        soc=0.8,
        current_zone="concourse_A",
        compatible_tasks=["tow"],
        allowed_zones=["concourse_A", "concourse_B"],
    )
    task = Task(
        task_id="T1",
        task_type="tow",
        deadline_min=100.0,
        duration_min=10.0,
        origin_zone="concourse_A",
        destination_zone="cargo_north",
        compatible_vehicle_types=["tow_tractor"],
    )
    scenario = _scenario_with([vehicle], [task])
    schedule = Schedule(
        events=[
            _event("V1", "T1", origin_zone="concourse_A", destination_zone="cargo_north")
        ]
    )
    report = verify_schedule(schedule, scenario)
    assert "autonomy_corridor_violation" in _constraints(report)


def test_detects_critical_task_late() -> None:
    task = _baggage_task("T1", deadline_min=50.0, is_critical=True)
    scenario = _scenario_with([_baggage_vehicle("V1")], [task])
    schedule = Schedule(
        events=[_event("V1", "T1", start_time_min=40.0, end_time_min=55.0, late_by_min=5.0)]
    )
    report = verify_schedule(schedule, scenario)
    assert "critical_task_late" in _constraints(report)


def test_detects_negative_timing() -> None:
    scenario = _scenario_with([_baggage_vehicle("V1")], [_baggage_task("T1")])
    bad = DispatchEvent.model_construct(
        vehicle_id="V1",
        task_id="T1",
        start_time_min=-5.0,
        end_time_min=10.0,
        origin_zone="depot",
        destination_zone="concourse_A",
        energy_used=0.0,
        co2e_proxy=0.0,
        late_by_min=0.0,
    )
    report = verify_schedule(Schedule(events=[bad]), scenario)
    assert "negative_timing" in _constraints(report)


def test_detects_negative_energy_or_co2e() -> None:
    scenario = _scenario_with(
        [_baggage_vehicle("V1", powertrain="ev", soc=0.8)],
        [_baggage_task("T1")],
    )
    bad = DispatchEvent.model_construct(
        vehicle_id="V1",
        task_id="T1",
        start_time_min=0.0,
        end_time_min=10.0,
        origin_zone="depot",
        destination_zone="concourse_A",
        energy_used=-1.0,
        co2e_proxy=-1.0,
        late_by_min=0.0,
    )
    report = verify_schedule(Schedule(events=[bad]), scenario)
    constraints = _constraints(report)
    assert "negative_energy" in constraints or "negative_co2e" in constraints


# --- Report shape -----------------------------------------------------------

def test_summary_contains_violation_counts() -> None:
    scenario = _scenario_with(
        [_baggage_vehicle("V1")],
        [_baggage_task("T1"), _baggage_task("T2")],
    )
    schedule = Schedule(
        events=[
            _event("V1", "T1", start_time_min=0.0, end_time_min=20.0),
            _event("V1", "T2", start_time_min=10.0, end_time_min=30.0),
        ]
    )
    report = verify_schedule(schedule, scenario)
    assert report.hard_constraint_summary
    assert report.hard_constraint_summary.get("vehicle_overlap", 0) >= 1
    assert sum(report.hard_constraint_summary.values()) == len(report.violations)


def test_passed_false_when_violations_exist() -> None:
    scenario = _scenario_with([_baggage_vehicle("V1")], [_baggage_task("T1")])
    schedule = Schedule(events=[])  # missing T1
    report = verify_schedule(schedule, scenario)
    assert report.passed is False
    assert report.violations


def test_passed_true_when_no_violations() -> None:
    scenario = _scenario_with([_baggage_vehicle("V1")], [_baggage_task("T1")])
    schedule = Schedule(events=[_event("V1", "T1")])
    report = verify_schedule(schedule, scenario)
    assert report.passed is True
    assert report.violations == []
    assert report.counterexamples == []


def test_does_not_mutate_inputs() -> None:
    scenario = generate_scenario(default_scenario_spec(), seed=42)
    schedule = simulate_baseline(scenario)
    before_schedule = schedule.model_dump()
    before_scenario = scenario.model_dump()
    verify_schedule(schedule, scenario)
    assert schedule.model_dump() == before_schedule
    assert scenario.model_dump() == before_scenario
