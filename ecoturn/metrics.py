"""Metric calculation only.

Turns a :class:`~ecoturn.schemas.Schedule` into the public
:class:`~ecoturn.schemas.Metrics` KPI bundle.

Index metrics (``co2e_index``, ``waste_index``, ``idle_time_index``,
``cost_index``) follow the schema rule: the baseline normalizes to 100.0.
When a ``baseline_schedule`` is supplied (e.g. for the T5 optimizer), each
index is expressed relative to the baseline raw total, so values below 100
mean an improvement.

Raw totals are exposed via :func:`compute_raw_totals` so future policies can
be compared from their schedules. All values are synthetic prototype proxies.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from ecoturn.schemas import GeneratedScenario, Metrics, Schedule

# Synthetic cost proxy weights.
_ENERGY_COST_WEIGHT = 1.0
_LATE_COST_WEIGHT = 10.0
_IDLE_COST_WEIGHT = 0.1
# Extra waste attributed to lateness of perishable tasks.
_WASTE_LATE_FACTOR = 2.0


@dataclass
class RawTotals:
    """Un-normalized totals derived purely from a schedule + scenario."""

    n_tasks: int
    late_count: int
    late_task_rate: float
    co2e_total: float
    energy_total: float
    idle_total: float
    waste_total: float
    cost_total: float


def compute_raw_totals(
    schedule: Schedule, scenario: GeneratedScenario
) -> RawTotals:
    """Recompute raw (un-indexed) totals from a schedule."""

    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    events = schedule.events
    n_tasks = len(events)

    late_count = sum(1 for e in events if e.late_by_min > 0.0)
    late_task_rate = (late_count / n_tasks) if n_tasks else 0.0

    co2e_total = sum(e.co2e_proxy for e in events)
    energy_total = sum(e.energy_used for e in events)

    busy_total = sum(e.end_time_min - e.start_time_min for e in events)
    makespan = max((e.end_time_min for e in events), default=0.0)
    n_vehicles = max(1, len(scenario.vehicles))
    idle_total = max(0.0, makespan * n_vehicles - busy_total)

    waste_total = 0.0
    for e in events:
        task = tasks_by_id.get(e.task_id)
        if task is None or task.freshness_decay_rate <= 0.0:
            continue
        elapsed = max(0.0, e.end_time_min - task.release_time_min)
        waste_total += task.freshness_decay_rate * (
            elapsed + _WASTE_LATE_FACTOR * e.late_by_min
        )

    cost_total = (
        co2e_total
        + _ENERGY_COST_WEIGHT * energy_total
        + _LATE_COST_WEIGHT * late_count
        + _IDLE_COST_WEIGHT * idle_total
    )

    return RawTotals(
        n_tasks=n_tasks,
        late_count=late_count,
        late_task_rate=late_task_rate,
        co2e_total=co2e_total,
        energy_total=energy_total,
        idle_total=idle_total,
        waste_total=waste_total,
        cost_total=cost_total,
    )


def _index(value: float, baseline: float) -> float:
    """Express ``value`` as an index where ``baseline`` maps to 100.0."""

    if baseline <= 0.0:
        return 100.0
    return round(100.0 * value / baseline, 3)


def compute_metrics(
    schedule: Schedule,
    scenario: GeneratedScenario,
    baseline_schedule: Schedule | None = None,
    runtime_sec: float | None = None,
) -> Metrics:
    """Compute the public :class:`Metrics` bundle for a schedule.

    When ``baseline_schedule`` is ``None`` the schedule is treated as the
    baseline and all index metrics are 100.0. Otherwise indices are relative
    to the baseline's raw totals.

    ``runtime_sec`` may be supplied by the caller (e.g. measured around the
    simulation). If omitted, the metric-computation wall time is used as a
    lightweight proxy. ``charger_queue_peak`` is a documented placeholder
    (0.0) until charging is modeled explicitly in T6/T7.
    """

    start = perf_counter()
    totals = compute_raw_totals(schedule, scenario)

    if baseline_schedule is None:
        co2e_index = 100.0
        waste_index = 100.0
        idle_time_index = 100.0
        cost_index = 100.0
    else:
        base = compute_raw_totals(baseline_schedule, scenario)
        co2e_index = _index(totals.co2e_total, base.co2e_total)
        waste_index = _index(totals.waste_total, base.waste_total)
        idle_time_index = _index(totals.idle_total, base.idle_total)
        cost_index = _index(totals.cost_total, base.cost_total)

    measured_runtime = runtime_sec if runtime_sec is not None else (perf_counter() - start)

    return Metrics(
        co2e_index=co2e_index,
        waste_index=waste_index,
        idle_time_index=idle_time_index,
        late_task_rate=min(1.0, max(0.0, totals.late_task_rate)),
        # Placeholder: baseline does not model charger contention yet.
        charger_queue_peak=0.0,
        runtime_sec=max(0.0, measured_runtime),
        cost_index=cost_index,
    )
