"""Hard constraint checks only.

A deterministic, rule-based verifier for baseline and optimized schedules.
It reports operational and safety-boundary violations but never tries to fix
or improve the schedule, and it must not mutate its inputs.

No Z3 / SMT is used — simple rules keep the MVP stable. All checks are
synthetic-scenario checks, not real operational guarantees.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ecoturn.scenario_generator import RESTRICTED_ZONE
from ecoturn.schemas import (
    GeneratedScenario,
    Schedule,
    Severity,
    VerificationReport,
    Violation,
)
from ecoturn.simulator import EV_POWERTRAINS, is_compatible

# Stable violation-type identifiers and their severities.
_SEVERITY: dict[str, Severity] = {
    "unknown_vehicle": "medium",
    "unknown_task": "medium",
    "incompatible_vehicle_task": "high",
    "vehicle_overlap": "high",
    "negative_timing": "medium",
    "missing_task": "high",
    "duplicate_task": "high",
    "restricted_zone_violation": "critical",
    "autonomy_corridor_violation": "critical",
    "critical_task_late": "critical",
    "negative_energy": "low",
    "negative_co2e": "low",
}


def _events_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return a_start < b_end and b_start < a_end


def verify_schedule(
    schedule: Schedule, scenario: GeneratedScenario
) -> VerificationReport:
    """Check ``schedule`` against hard operational/safety constraints.

    Returns a :class:`~ecoturn.schemas.VerificationReport` whose ``passed``
    flag is ``True`` only when no violations are found. Inputs are not
    mutated.
    """

    vehicles_by_id = {v.vehicle_id: v for v in scenario.vehicles}
    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    restricted_zones = {RESTRICTED_ZONE} | set(
        scenario.spec.safety_policy.restricted_zones
    )

    violations: list[Violation] = []
    counterexamples: list[dict[str, Any]] = []

    def add(
        constraint: str,
        message: str,
        counterexample: dict[str, Any],
        vehicle_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        violations.append(
            Violation(
                constraint=constraint,
                severity=_SEVERITY[constraint],
                message=message,
                vehicle_id=vehicle_id,
                task_id=task_id,
            )
        )
        counterexamples.append({"constraint": constraint, **counterexample})

    # --- Per-event checks --------------------------------------------------
    for e in schedule.events:
        vehicle = vehicles_by_id.get(e.vehicle_id)
        task = tasks_by_id.get(e.task_id)

        if vehicle is None:
            add(
                "unknown_vehicle",
                f"vehicle '{e.vehicle_id}' not in scenario",
                {"vehicle_id": e.vehicle_id, "task_id": e.task_id},
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )
        if task is None:
            add(
                "unknown_task",
                f"task '{e.task_id}' not in scenario",
                {"vehicle_id": e.vehicle_id, "task_id": e.task_id},
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )

        if vehicle is not None and task is not None and not is_compatible(vehicle, task):
            add(
                "incompatible_vehicle_task",
                f"vehicle '{e.vehicle_id}' incompatible with task '{e.task_id}'",
                {"vehicle_id": e.vehicle_id, "task_id": e.task_id},
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )

        if (
            e.start_time_min < 0.0
            or e.end_time_min < e.start_time_min
            or e.late_by_min < 0.0
        ):
            add(
                "negative_timing",
                "invalid event timing",
                {
                    "task_id": e.task_id,
                    "start_time_min": e.start_time_min,
                    "end_time_min": e.end_time_min,
                    "late_by_min": e.late_by_min,
                },
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )

        if vehicle is not None and vehicle.powertrain in EV_POWERTRAINS and e.energy_used < 0.0:
            add(
                "negative_energy",
                f"negative energy_used for '{e.vehicle_id}'",
                {"vehicle_id": e.vehicle_id, "task_id": e.task_id, "energy_used": e.energy_used},
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )

        if e.co2e_proxy < 0.0:
            add(
                "negative_co2e",
                f"negative co2e_proxy for task '{e.task_id}'",
                {"vehicle_id": e.vehicle_id, "task_id": e.task_id, "co2e_proxy": e.co2e_proxy},
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )

        # Restricted-zone boundary.
        hit_zones = restricted_zones & {e.origin_zone, e.destination_zone}
        if hit_zones:
            allowed = set(vehicle.allowed_zones) if vehicle is not None else set()
            if not hit_zones.issubset(allowed):
                add(
                    "restricted_zone_violation",
                    f"task '{e.task_id}' touches restricted zone(s) {sorted(hit_zones)}",
                    {
                        "vehicle_id": e.vehicle_id,
                        "task_id": e.task_id,
                        "zones": sorted(hit_zones),
                    },
                    vehicle_id=e.vehicle_id,
                    task_id=e.task_id,
                )

        # Autonomous corridor boundary.
        if vehicle is not None and vehicle.powertrain == "autonomous_ev":
            allowed = set(vehicle.allowed_zones)
            outside = {e.origin_zone, e.destination_zone} - allowed
            if outside:
                add(
                    "autonomy_corridor_violation",
                    f"autonomous vehicle '{e.vehicle_id}' outside allowed zones {sorted(outside)}",
                    {
                        "vehicle_id": e.vehicle_id,
                        "task_id": e.task_id,
                        "zones": sorted(outside),
                    },
                    vehicle_id=e.vehicle_id,
                    task_id=e.task_id,
                )

        # Critical-task lateness.
        if task is not None and task.is_critical and e.late_by_min > 0.0:
            add(
                "critical_task_late",
                f"critical task '{e.task_id}' late by {e.late_by_min} min",
                {"task_id": e.task_id, "late_by_min": e.late_by_min},
                vehicle_id=e.vehicle_id,
                task_id=e.task_id,
            )

    # --- Vehicle overlap (per vehicle, sweep by start time) ----------------
    events_by_vehicle: dict[str, list] = {}
    for e in schedule.events:
        events_by_vehicle.setdefault(e.vehicle_id, []).append(e)

    for vehicle_id in sorted(events_by_vehicle):
        ordered = sorted(
            events_by_vehicle[vehicle_id],
            key=lambda ev: (ev.start_time_min, ev.end_time_min, ev.task_id),
        )
        for i in range(1, len(ordered)):
            prev = ordered[i - 1]
            curr = ordered[i]
            if _events_overlap(
                prev.start_time_min, prev.end_time_min,
                curr.start_time_min, curr.end_time_min,
            ):
                add(
                    "vehicle_overlap",
                    f"vehicle '{vehicle_id}' has overlapping tasks "
                    f"'{prev.task_id}' and '{curr.task_id}'",
                    {
                        "vehicle_id": vehicle_id,
                        "task_ids": [prev.task_id, curr.task_id],
                    },
                    vehicle_id=vehicle_id,
                )

    # --- Task coverage -----------------------------------------------------
    seen = Counter(e.task_id for e in schedule.events)
    for t in scenario.tasks:
        if seen[t.task_id] == 0:
            add(
                "missing_task",
                f"task '{t.task_id}' missing from schedule",
                {"task_id": t.task_id},
                task_id=t.task_id,
            )
    for task_id in sorted(seen):
        if seen[task_id] > 1 and task_id in tasks_by_id:
            add(
                "duplicate_task",
                f"task '{task_id}' assigned {seen[task_id]} times",
                {"task_id": task_id, "count": seen[task_id]},
                task_id=task_id,
            )

    summary = dict(Counter(v.constraint for v in violations))

    return VerificationReport(
        passed=len(violations) == 0,
        violations=violations,
        counterexamples=counterexamples,
        hard_constraint_summary=summary,
    )
