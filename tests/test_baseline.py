"""T4 — baseline simulator + metrics tests.

Verify the deterministic baseline produces a valid, schema-conformant
schedule (one event per task), with consistent timing, valid assignments,
and baseline metrics that normalize index KPIs to 100.0.
"""

from __future__ import annotations

from ecoturn.baseline import simulate_baseline
from ecoturn.metrics import compute_metrics
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.simulator import is_compatible
from ecoturn.schemas import DispatchEvent, Metrics, Schedule


def _scenario():
    return generate_scenario(default_scenario_spec(), seed=42)


def test_baseline_returns_valid_schedule() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    assert isinstance(schedule, Schedule)
    Schedule.model_validate(schedule.model_dump())
    assert schedule.policy_name == "baseline"
    assert schedule.scenario_name == scenario.spec.scenario_name


def test_one_event_per_task() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    assert len(schedule.events) == len(scenario.tasks)
    assert {e.task_id for e in schedule.events} == {t.task_id for t in scenario.tasks}


def test_events_are_dispatch_events_with_nonnegative_times() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    for e in schedule.events:
        assert isinstance(e, DispatchEvent)
        assert e.start_time_min >= 0.0
        assert e.end_time_min >= 0.0


def test_end_after_or_equal_start() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    for e in schedule.events:
        assert e.end_time_min >= e.start_time_min


def test_assigned_vehicles_and_tasks_exist() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    vehicle_ids = {v.vehicle_id for v in scenario.vehicles}
    task_ids = {t.task_id for t in scenario.tasks}
    for e in schedule.events:
        assert e.vehicle_id in vehicle_ids
        assert e.task_id in task_ids


def test_assignments_are_compatible() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    vehicles_by_id = {v.vehicle_id: v for v in scenario.vehicles}
    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    for e in schedule.events:
        vehicle = vehicles_by_id[e.vehicle_id]
        task = tasks_by_id[e.task_id]
        assert is_compatible(vehicle, task)


def test_baseline_is_deterministic() -> None:
    scenario = _scenario()
    a = simulate_baseline(scenario)
    b = simulate_baseline(scenario)
    assert a.model_dump() == b.model_dump()


def test_baseline_metrics_validate() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    metrics = compute_metrics(schedule, scenario)
    assert isinstance(metrics, Metrics)
    Metrics.model_validate(metrics.model_dump())


def test_baseline_index_metrics_are_100() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    metrics = compute_metrics(schedule, scenario)
    assert metrics.co2e_index == 100.0
    assert metrics.waste_index == 100.0
    assert metrics.idle_time_index == 100.0
    assert metrics.cost_index == 100.0


def test_late_task_rate_in_unit_interval() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    metrics = compute_metrics(schedule, scenario)
    assert 0.0 <= metrics.late_task_rate <= 1.0


def test_ev_energy_usage_nonnegative() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    for e in schedule.events:
        assert e.energy_used >= 0.0


def test_no_negative_lateness() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    for e in schedule.events:
        assert e.late_by_min >= 0.0


def test_runtime_sec_nonnegative_and_queue_peak_placeholder() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    metrics = compute_metrics(schedule, scenario)
    assert metrics.runtime_sec >= 0.0
    assert metrics.charger_queue_peak == 0.0


def test_diesel_events_carry_co2e_and_no_energy() -> None:
    scenario = _scenario()
    schedule = simulate_baseline(scenario)
    vehicles_by_id = {v.vehicle_id: v for v in scenario.vehicles}
    diesel_events = [
        e for e in schedule.events if vehicles_by_id[e.vehicle_id].powertrain == "diesel"
    ]
    assert diesel_events
    for e in diesel_events:
        assert e.energy_used == 0.0
        assert e.co2e_proxy >= 0.0
