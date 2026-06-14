"""Bottleneck / critical-path analysis only.

Produces an engineering-style diagnostic report (in the spirit of a Vivado
timing report) that highlights the worst operational bottlenecks in a
schedule and backs each finding with concrete evidence. This is purely
diagnostic — it never mutates or improves the schedule — but its findings are
designed to feed the T7 adaptive-refinement engine later.

All analysis is over synthetic ATL-sandbox prototype data; it is not real
Delta operational data.
"""

from __future__ import annotations

from ecoturn.schemas import (
    BottleneckFinding,
    BottleneckReport,
    DispatchEvent,
    GeneratedScenario,
    Metrics,
    Schedule,
    Severity,
    VerificationReport,
)

_SYNTHETIC_NOTE = (
    "Synthetic ATL-sandbox prototype analysis. Not real Delta operational data."
)

_SEVERITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Late-task severity thresholds (synthetic minutes).
_LATE_HIGH_MIN = 30.0
_LATE_MEDIUM_MIN = 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _argmax(events: list[DispatchEvent], value_fn) -> DispatchEvent:
    """Deterministic argmax: highest value, ties broken by task_id."""

    return min(events, key=lambda e: (-value_fn(e), e.task_id))


def _late_task_finding(
    events: list[DispatchEvent], scenario: GeneratedScenario
) -> BottleneckFinding:
    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    if not events:
        return BottleneckFinding(
            finding_type="worst_late_task",
            title="No dispatch events to analyze for lateness",
            severity="low",
            evidence={},
            likely_cause="Empty schedule.",
            suggested_what_if="Generate a schedule before running analysis.",
            confidence=0.5,
        )

    worst = _argmax(events, lambda e: e.late_by_min)
    task = tasks_by_id.get(worst.task_id)
    is_critical = bool(task.is_critical) if task is not None else False

    if worst.late_by_min <= 0.0:
        severity: Severity = "low"
        title = "No late tasks in schedule"
    elif is_critical:
        severity = "critical"
        title = f"Critical task {worst.task_id} is late"
    elif worst.late_by_min >= _LATE_HIGH_MIN:
        severity = "high"
        title = f"Task {worst.task_id} significantly late"
    else:
        severity = "medium"
        title = f"Task {worst.task_id} late"

    return BottleneckFinding(
        finding_type="worst_late_task",
        title=title,
        severity=severity,
        evidence={
            "task_id": worst.task_id,
            "vehicle_id": worst.vehicle_id,
            "origin_zone": worst.origin_zone,
            "destination_zone": worst.destination_zone,
            "start_time_min": worst.start_time_min,
            "end_time_min": worst.end_time_min,
            "late_by_min": worst.late_by_min,
            "is_critical": is_critical,
        },
        likely_cause=(
            "Tight deadline relative to travel + service time, or vehicle "
            "availability/charging delay upstream."
        ),
        suggested_what_if=(
            "Increase lateness penalty weight or pre-position a compatible "
            "vehicle closer to the origin zone."
        ),
        confidence=_clamp01(0.75 if worst.late_by_min > 0.0 else 0.65),
    )


def _energy_finding(events: list[DispatchEvent]) -> BottleneckFinding:
    if not events:
        return BottleneckFinding(
            finding_type="worst_energy_event",
            title="No dispatch events to analyze for energy",
            severity="low",
            evidence={},
            likely_cause="Empty schedule.",
            suggested_what_if="Generate a schedule before running analysis.",
            confidence=0.5,
        )

    worst = _argmax(events, lambda e: e.energy_used)
    severity: Severity = "medium" if worst.energy_used > 0.0 else "low"
    return BottleneckFinding(
        finding_type="worst_energy_event",
        title=f"Highest energy draw on task {worst.task_id}",
        severity=severity,
        evidence={
            "task_id": worst.task_id,
            "vehicle_id": worst.vehicle_id,
            "energy_used": worst.energy_used,
            "origin_zone": worst.origin_zone,
            "destination_zone": worst.destination_zone,
        },
        likely_cause=(
            "Long combined travel + service time on an electric vehicle."
        ),
        suggested_what_if=(
            "Shorten routing for this assignment or balance load across more "
            "electric vehicles."
        ),
        confidence=0.7,
    )


def _co2e_finding(
    events: list[DispatchEvent], scenario: GeneratedScenario
) -> BottleneckFinding:
    vehicles_by_id = {v.vehicle_id: v for v in scenario.vehicles}
    if not events:
        return BottleneckFinding(
            finding_type="worst_co2e_event",
            title="No dispatch events to analyze for CO2e",
            severity="low",
            evidence={},
            likely_cause="Empty schedule.",
            suggested_what_if="Generate a schedule before running analysis.",
            confidence=0.5,
        )

    worst = _argmax(events, lambda e: e.co2e_proxy)
    vehicle = vehicles_by_id.get(worst.vehicle_id)
    powertrain = vehicle.powertrain if vehicle is not None else None
    if worst.co2e_proxy <= 0.0:
        severity: Severity = "low"
    elif powertrain == "diesel":
        severity = "high"
    else:
        severity = "medium"

    return BottleneckFinding(
        finding_type="worst_co2e_event",
        title=f"Highest CO2e proxy on task {worst.task_id}",
        severity=severity,
        evidence={
            "task_id": worst.task_id,
            "vehicle_id": worst.vehicle_id,
            "co2e_proxy": worst.co2e_proxy,
            "powertrain": powertrain,
        },
        likely_cause=(
            "A diesel (or high-emission) vehicle serving a long-duration task."
            if powertrain == "diesel"
            else "Long operating time dominates the emissions proxy."
        ),
        suggested_what_if=(
            "Prefer an electric vehicle for this assignment if SOC and "
            "lateness allow."
        ),
        confidence=0.7,
    )


def _freshness_finding(
    events: list[DispatchEvent], scenario: GeneratedScenario
) -> BottleneckFinding:
    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    perishable = [
        e
        for e in events
        if (t := tasks_by_id.get(e.task_id)) is not None
        and t.freshness_decay_rate > 0.0
    ]

    if not perishable:
        return BottleneckFinding(
            finding_type="worst_freshness_waste_event",
            title="No perishable tasks in schedule",
            severity="low",
            evidence={"perishable_task_count": 0},
            likely_cause="Scenario has no tasks with positive freshness decay.",
            suggested_what_if="Add catering/perishable tasks to stress waste.",
            confidence=0.5,
        )

    def freshness_risk(e: DispatchEvent) -> float:
        task = tasks_by_id[e.task_id]
        elapsed = max(1.0, e.end_time_min - task.release_time_min)
        return task.freshness_decay_rate * elapsed

    worst = _argmax(perishable, freshness_risk)
    task = tasks_by_id[worst.task_id]
    elapsed = max(1.0, worst.end_time_min - task.release_time_min)
    risk = task.freshness_decay_rate * elapsed

    return BottleneckFinding(
        finding_type="worst_freshness_waste_event",
        title=f"Highest freshness/waste risk on task {worst.task_id}",
        severity="medium",
        evidence={
            "task_id": worst.task_id,
            "vehicle_id": worst.vehicle_id,
            "freshness_decay_rate": task.freshness_decay_rate,
            "elapsed_time_min": round(elapsed, 3),
            "freshness_risk": round(risk, 3),
        },
        likely_cause=(
            "Long elapsed time between release and completion for a "
            "perishable (catering) task."
        ),
        suggested_what_if=(
            "Increase freshness priority weight so perishable tasks are "
            "served sooner."
        ),
        # Proxy-based heuristic (not a measured spoilage model): lower confidence.
        confidence=0.55,
    )


def _constraint_risk_finding(
    verification_report: VerificationReport | None,
) -> BottleneckFinding:
    if verification_report is None:
        return BottleneckFinding(
            finding_type="worst_constraint_risk",
            title="Hard constraints not evaluated",
            severity="low",
            evidence={"verifier_run": False},
            likely_cause="No verification report supplied to the analyzer.",
            suggested_what_if="Run the verifier and re-analyze.",
            confidence=0.5,
        )

    if not verification_report.violations:
        return BottleneckFinding(
            finding_type="worst_constraint_risk",
            title="All hard constraints passed",
            severity="low",
            evidence={"verifier_run": True, "passed": True, "n_violations": 0},
            likely_cause="No operational or safety-boundary violations detected.",
            suggested_what_if=(
                "Stress the scenario (tighter deadlines, lower SOC) to probe "
                "constraint margins."
            ),
            confidence=0.8,
        )

    worst = min(
        verification_report.violations,
        key=lambda v: (-_SEVERITY_RANK[v.severity], v.constraint),
    )
    counterexample = next(
        (
            ce
            for ce in verification_report.counterexamples
            if ce.get("constraint") == worst.constraint
        ),
        None,
    )

    return BottleneckFinding(
        finding_type="worst_constraint_risk",
        title=f"Highest-severity violation: {worst.constraint}",
        severity=worst.severity,
        evidence={
            "verifier_run": True,
            "passed": False,
            "violation_type": worst.constraint,
            "message": worst.message,
            "vehicle_id": worst.vehicle_id,
            "task_id": worst.task_id,
            "counterexample": counterexample,
            "n_violations": len(verification_report.violations),
        },
        likely_cause=(
            "A hard operational/safety constraint was breached by the schedule."
        ),
        suggested_what_if=(
            "Route refinement around the violating assignment; safety-critical "
            "boundary changes require human approval."
        ),
        confidence=0.8,
    )


def generate_bottleneck_report(
    schedule: Schedule,
    scenario: GeneratedScenario,
    metrics: Metrics,
    verification_report: VerificationReport | None = None,
) -> BottleneckReport:
    """Produce a diagnostic bottleneck report for a schedule.

    Does not mutate ``schedule`` or ``scenario``. The ``metrics`` bundle is
    summarized for context. Findings are deterministic and evidence-backed.
    """

    events = list(schedule.events)

    findings = [
        _late_task_finding(events, scenario),
        _energy_finding(events),
        _co2e_finding(events, scenario),
        _freshness_finding(events, scenario),
        _constraint_risk_finding(verification_report),
    ]

    severity_counts: dict[str, int] = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    summary = {
        "note": _SYNTHETIC_NOTE,
        "synthetic": True,
        "scenario_name": scenario.spec.scenario_name,
        "policy_name": schedule.policy_name,
        "n_events": len(events),
        "n_findings": len(findings),
        "severity_counts": severity_counts,
        "metrics": {
            "co2e_index": metrics.co2e_index,
            "waste_index": metrics.waste_index,
            "idle_time_index": metrics.idle_time_index,
            "late_task_rate": metrics.late_task_rate,
            "cost_index": metrics.cost_index,
        },
        "verifier_passed": (
            verification_report.passed if verification_report is not None else None
        ),
    }

    return BottleneckReport(findings=findings, summary=summary)
