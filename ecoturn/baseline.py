"""Baseline dispatch policy only.

A deliberately simple, deterministic baseline for the ATL-sandbox scenario:

- tasks processed first-come-first-served, sorted by ``release_time_min``;
- each task assigned to the nearest compatible *available* vehicle
  (earliest feasible arrival, ties broken by shortest travel and id);
- simple "charge-when-needed" EV behavior modeled as an availability delay
  plus SOC restoration;
- no global optimization, no rolling horizon, no local search.

This is intentionally weak so the optimizer (T5) can visibly improve on it.
All numbers are synthetic prototype proxies.
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


@dataclass
class _Plan:
    """A tentative assignment of one task to one vehicle."""

    state: VehicleState
    arrival_origin: float
    travel_to: float
    service_start: float
    service_end: float
    arrival_dest: float
    late_by: float
    energy_used: float
    co2e_proxy: float
    charge_delay: float
    soc_after: float | None


def _plan_assignment(
    state: VehicleState,
    task: Task,
    scenario: GeneratedScenario,
    min_soc: float,
    dispatch_threshold: float,
) -> _Plan:
    """Compute the cost/timing of assigning ``task`` to ``state``'s vehicle."""

    travel_to = travel_time(scenario, state.current_zone, task.origin_zone)
    travel_od = travel_time(scenario, task.origin_zone, task.destination_zone)
    op_min = operating_minutes(travel_to, travel_od, task.duration_min)

    charge_delay = 0.0
    energy_used = 0.0
    soc_after = state.soc

    if state.is_electric and state.soc is not None:
        energy_used = state.vehicle.energy_rate * op_min
        soc_drop = energy_used / BATTERY_CAPACITY_KWH
        # Charge when below the dispatch threshold or when serving the task
        # would breach the absolute minimum SOC.
        if state.soc < dispatch_threshold or (state.soc - soc_drop) < min_soc:
            charge_delay = (1.0 - state.soc) * FULL_CHARGE_MINUTES
            soc_after = max(0.0, 1.0 - soc_drop)
        else:
            soc_after = max(0.0, state.soc - soc_drop)
        co2e_proxy = EV_GRID_CO2_FACTOR * energy_used
    else:
        co2e_proxy = state.vehicle.emission_rate * op_min

    effective_available = state.available_time + charge_delay
    arrival_origin = effective_available + travel_to
    service_start = max(arrival_origin, task.release_time_min)
    service_end = service_start + task.duration_min
    arrival_dest = service_end + travel_od
    late_by = max(0.0, arrival_dest - task.deadline_min)

    return _Plan(
        state=state,
        arrival_origin=round(arrival_origin, _ROUND),
        travel_to=round(travel_to, _ROUND),
        service_start=round(service_start, _ROUND),
        service_end=round(service_end, _ROUND),
        arrival_dest=round(arrival_dest, _ROUND),
        late_by=round(late_by, _ROUND),
        energy_used=round(energy_used, _ROUND),
        co2e_proxy=round(co2e_proxy, _ROUND),
        charge_delay=round(charge_delay, _ROUND),
        soc_after=None if soc_after is None else round(soc_after, _ROUND),
    )


def simulate_baseline(scenario: GeneratedScenario) -> Schedule:
    """Run the deterministic baseline dispatch policy.

    Returns a :class:`~ecoturn.schemas.Schedule` with exactly one
    :class:`~ecoturn.schemas.DispatchEvent` per task that has a compatible
    vehicle (every task in the default ATL-sandbox scenario).
    """

    min_soc = scenario.spec.safety_policy.min_soc
    dispatch_threshold = scenario.spec.solver_policy.dispatch_soc_threshold

    states = init_vehicle_states(scenario)
    tasks = sorted(scenario.tasks, key=lambda t: (t.release_time_min, t.task_id))

    events: list[DispatchEvent] = []
    for task in tasks:
        candidates = [s for s in states if is_compatible(s.vehicle, task)]
        if not candidates:
            # No compatible vehicle: skip rather than fabricate an assignment.
            continue

        plans = [
            _plan_assignment(s, task, scenario, min_soc, dispatch_threshold)
            for s in candidates
        ]
        # Earliest feasible arrival, then shortest travel, then stable id.
        best = min(
            plans,
            key=lambda p: (p.arrival_origin, p.travel_to, p.state.vehicle.vehicle_id),
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
                late_by_min=best.late_by,
            )
        )

        best.state.available_time = best.arrival_dest
        best.state.current_zone = task.destination_zone
        best.state.soc = best.soc_after

    return Schedule(
        policy_name="baseline",
        scenario_name=scenario.spec.scenario_name,
        events=events,
    )
