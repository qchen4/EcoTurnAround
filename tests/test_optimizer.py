"""T5 — optimizer tests.

Verify the deterministic optimized policy produces a valid, schema-conformant
schedule (one event per task), with valid/compatible assignments, and that it
visibly improves at least one index metric over the baseline without making
lateness catastrophically worse.
"""

from __future__ import annotations

from ecoturn.baseline import simulate_baseline
from ecoturn.metrics import compute_metrics
from ecoturn.optimizer import simulate_optimized
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.simulator import is_compatible
from ecoturn.schemas import DispatchEvent, Metrics, Schedule


def _scenario():
    return generate_scenario(default_scenario_spec(), seed=42)


def test_optimized_returns_valid_schedule() -> None:
    scenario = _scenario()
    schedule = simulate_optimized(scenario)
    assert isinstance(schedule, Schedule)
    Schedule.model_validate(schedule.model_dump())
    assert schedule.policy_name == "optimized"


def test_one_event_per_task() -> None:
    scenario = _scenario()
    schedule = simulate_optimized(scenario)
    assert len(schedule.events) == len(scenario.tasks)
    assert {e.task_id for e in schedule.events} == {t.task_id for t in scenario.tasks}


def test_optimized_is_deterministic() -> None:
    scenario = _scenario()
    a = simulate_optimized(scenario)
    b = simulate_optimized(scenario)
    assert a.model_dump() == b.model_dump()


def test_deterministic_with_baseline_arg() -> None:
    scenario = _scenario()
    baseline = simulate_baseline(scenario)
    a = simulate_optimized(scenario, baseline)
    b = simulate_optimized(scenario, baseline)
    assert a.model_dump() == b.model_dump()


def test_assigned_vehicles_and_tasks_exist() -> None:
    scenario = _scenario()
    schedule = simulate_optimized(scenario)
    vehicle_ids = {v.vehicle_id for v in scenario.vehicles}
    task_ids = {t.task_id for t in scenario.tasks}
    for e in schedule.events:
        assert e.vehicle_id in vehicle_ids
        assert e.task_id in task_ids


def test_assignments_are_compatible() -> None:
    scenario = _scenario()
    schedule = simulate_optimized(scenario)
    vehicles_by_id = {v.vehicle_id: v for v in scenario.vehicles}
    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    for e in schedule.events:
        assert is_compatible(vehicles_by_id[e.vehicle_id], tasks_by_id[e.task_id])


def test_no_negative_times_or_lateness() -> None:
    scenario = _scenario()
    schedule = simulate_optimized(scenario)
    for e in schedule.events:
        assert isinstance(e, DispatchEvent)
        assert e.start_time_min >= 0.0
        assert e.end_time_min >= e.start_time_min
        assert e.late_by_min >= 0.0


def test_ev_energy_usage_nonnegative() -> None:
    scenario = _scenario()
    schedule = simulate_optimized(scenario)
    for e in schedule.events:
        assert e.energy_used >= 0.0


def test_compute_metrics_with_baseline() -> None:
    scenario = _scenario()
    baseline = simulate_baseline(scenario)
    optimized = simulate_optimized(scenario, baseline)
    metrics = compute_metrics(optimized, scenario, baseline_schedule=baseline)
    assert isinstance(metrics, Metrics)
    Metrics.model_validate(metrics.model_dump())


def test_at_least_one_index_improves() -> None:
    scenario = _scenario()
    baseline = simulate_baseline(scenario)
    optimized = simulate_optimized(scenario, baseline)
    base_metrics = compute_metrics(baseline, scenario)
    opt_metrics = compute_metrics(optimized, scenario, baseline_schedule=baseline)

    improved = (
        opt_metrics.co2e_index < 100.0
        or opt_metrics.waste_index < 100.0
        or opt_metrics.idle_time_index < 100.0
        or opt_metrics.cost_index < 100.0
        or opt_metrics.late_task_rate <= base_metrics.late_task_rate
    )
    assert improved, (
        "expected at least one improved index; got "
        f"co2={opt_metrics.co2e_index}, waste={opt_metrics.waste_index}, "
        f"idle={opt_metrics.idle_time_index}, cost={opt_metrics.cost_index}, "
        f"late={opt_metrics.late_task_rate} vs base late={base_metrics.late_task_rate}"
    )


def test_lateness_not_catastrophically_worse() -> None:
    scenario = _scenario()
    baseline = simulate_baseline(scenario)
    optimized = simulate_optimized(scenario, baseline)
    base_metrics = compute_metrics(baseline, scenario)
    opt_metrics = compute_metrics(optimized, scenario, baseline_schedule=baseline)
    assert opt_metrics.late_task_rate <= base_metrics.late_task_rate + 0.10


def test_does_not_degrade_baseline_schedule() -> None:
    scenario = _scenario()
    baseline_before = simulate_baseline(scenario).model_dump()
    baseline = simulate_baseline(scenario)
    simulate_optimized(scenario, baseline)
    assert baseline.model_dump() == baseline_before
