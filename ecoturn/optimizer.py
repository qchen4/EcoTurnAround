"""Optimized dispatch policy only.

A deterministic, priority-based rolling-horizon *greedy* optimizer for the
ATL-sandbox scenario. It is intentionally NOT a global MILP and NOT a full
VRP solver — it simply makes smarter, score-driven choices than the FCFS
baseline so that at least one KPI visibly improves.

Key differences from the baseline:

- tasks are ordered by deadline → priority → freshness risk → release time;
- each task is assigned to the vehicle with the best multi-criteria score
  (lateness, travel, CO2e proxy, SOC risk, freshness risk, priority), which
  biases toward cleaner electric vehicles and shorter trips while keeping
  lateness in check.

All numbers are synthetic prototype proxies. No claim of global optimality.
"""

from __future__ import annotations

from dataclasses import dataclass

from ecoturn.schemas import DispatchEvent, GeneratedScenario, Schedule, Task
from ecoturn.simulator import (
    BATTERY_CAPACITY_KWH,
    EV_GRID_CO2_FACTOR,
    FULL_CHARGE_MINUTES,
    VehicleState,
    init_vehicle_states,
    is_compatible,
    operating_minutes,
    travel_time,
)

_ROUND = 3

# Scoring weights (lower score is better). Tuned so the CO2e term steers work
# toward electric vehicles, while the lateness/SOC terms prevent that from
# creating tardy assignments or draining batteries.
W_LATE = 6.0
W_TRAVEL = 1.0
W_CO2 = 1.0
W_SOC = 20.0
W_FRESH = 3.0
W_PRIORITY = 5.0


@dataclass
class _Plan:
    """A scored tentative assignment of one task to one vehicle."""

    state: VehicleState
    service_start: float
    arrival_dest: float
    predicted_lateness: float
    travel_total: float
    energy_used: float
    co2e_proxy: float
    soc_risk: float
    freshness_risk: float
    charge_delay: float
    soc_after: float | None
    score: float


def _ordered_tasks(scenario: GeneratedScenario) -> list[Task]:
    """Deadline-first ordering with priority/freshness/release tie-breakers."""

    return sorted(
        scenario.tasks,
        key=lambda t: (
            t.deadline_min,
            -t.priority,
            -t.freshness_decay_rate,
            t.release_time_min,
            t.task_id,
        ),
    )


def _plan_assignment(
    state: VehicleState,
    task: Task,
    scenario: GeneratedScenario,
    min_soc: float,
    dispatch_threshold: float,
) -> _Plan:
    """Compute timing, costs, and a multi-criteria score for an assignment."""

    travel_to = travel_time(scenario, state.current_zone, task.origin_zone)
    travel_od = travel_time(scenario, task.origin_zone, task.destination_zone)
    travel_total = travel_to + travel_od
    op_min = operating_minutes(travel_to, travel_od, task.duration_min)

    charge_delay = 0.0
    energy_used = 0.0
    soc_after = state.soc
    soc_risk = 0.0

    if state.is_electric and state.soc is not None:
        energy_used = state.vehicle.energy_rate * op_min
        soc_drop = energy_used / BATTERY_CAPACITY_KWH
        projected_soc = state.soc - soc_drop
        soc_risk = max(0.0, dispatch_threshold - projected_soc)
        if state.soc < dispatch_threshold or projected_soc < min_soc:
            charge_delay = (1.0 - state.soc) * FULL_CHARGE_MINUTES
            soc_after = max(0.0, 1.0 - soc_drop)
        else:
            soc_after = max(0.0, projected_soc)
        co2e_proxy = EV_GRID_CO2_FACTOR * energy_used
    else:
        co2e_proxy = state.vehicle.emission_rate * op_min

    effective_available = state.available_time + charge_delay
    arrival_origin = effective_available + travel_to
    service_start = max(arrival_origin, task.release_time_min)
    service_end = service_start + task.duration_min
    arrival_dest = service_end + travel_od
    predicted_lateness = max(0.0, arrival_dest - task.deadline_min)

    if task.freshness_decay_rate > 0.0:
        elapsed = max(0.0, arrival_dest - task.release_time_min)
        freshness_risk = task.freshness_decay_rate * (elapsed + predicted_lateness)
    else:
        freshness_risk = 0.0

    score = (
        W_LATE * predicted_lateness
        + W_TRAVEL * travel_total
        + W_CO2 * co2e_proxy
        + W_SOC * soc_risk
        + W_FRESH * freshness_risk
        - W_PRIORITY * task.priority
    )

    return _Plan(
        state=state,
        service_start=round(service_start, _ROUND),
        arrival_dest=round(arrival_dest, _ROUND),
        predicted_lateness=round(predicted_lateness, _ROUND),
        travel_total=round(travel_total, _ROUND),
        energy_used=round(energy_used, _ROUND),
        co2e_proxy=round(co2e_proxy, _ROUND),
        soc_risk=round(soc_risk, _ROUND),
        freshness_risk=round(freshness_risk, _ROUND),
        charge_delay=round(charge_delay, _ROUND),
        soc_after=None if soc_after is None else round(soc_after, _ROUND),
        score=round(score, _ROUND),
    )


def simulate_optimized(
    scenario: GeneratedScenario,
    baseline_schedule: Schedule | None = None,
) -> Schedule:
    """Run the deterministic optimized dispatch policy.

    ``baseline_schedule`` is accepted for API symmetry with metrics/UI flows;
    the greedy optimizer does not require it. Returns a
    :class:`~ecoturn.schemas.Schedule` with one
    :class:`~ecoturn.schemas.DispatchEvent` per assignable task.
    """

    _ = baseline_schedule  # not needed by the greedy policy

    min_soc = scenario.spec.safety_policy.min_soc
    dispatch_threshold = scenario.spec.solver_policy.dispatch_soc_threshold

    states = init_vehicle_states(scenario)
    events: list[DispatchEvent] = []

    for task in _ordered_tasks(scenario):
        candidates = [s for s in states if is_compatible(s.vehicle, task)]
        if not candidates:
            continue

        plans = [
            _plan_assignment(s, task, scenario, min_soc, dispatch_threshold)
            for s in candidates
        ]
        best = min(
            plans,
            key=lambda p: (p.score, p.arrival_dest, p.state.vehicle.vehicle_id),
        )

        events.append(
            DispatchEvent(
                vehicle_id=best.state.vehicle.vehicle_id,
                task_id=task.task_id,
                start_time_min=best.service_start,
                end_time_min=best.arrival_dest,
                origin_zone=task.origin_zone,
                destination_zone=task.destination_zone,
                energy_used=best.energy_used,
                co2e_proxy=best.co2e_proxy,
                late_by_min=best.predicted_lateness,
            )
        )

        best.state.available_time = best.arrival_dest
        best.state.current_zone = task.destination_zone
        best.state.soc = best.soc_after

    return Schedule(
        policy_name="optimized",
        scenario_name=scenario.spec.scenario_name,
        events=events,
    )
