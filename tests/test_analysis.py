"""T6.5 — bottleneck / critical-path analysis report tests.

Verify the diagnostic report contains all required finding types, that each
"worst" finding matches the actual extreme event, that constraint risk
reflects the verifier, and that the function is deterministic and
non-mutating with confidences in [0, 1].
"""

from __future__ import annotations

from ecoturn.analysis import generate_bottleneck_report
from ecoturn.baseline import simulate_baseline
from ecoturn.metrics import compute_metrics
from ecoturn.optimizer import simulate_optimized
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.schemas import BottleneckReport, DispatchEvent, Schedule
from ecoturn.verifier import verify_schedule

REQUIRED_TYPES = {
    "worst_late_task",
    "worst_energy_event",
    "worst_co2e_event",
    "worst_freshness_waste_event",
    "worst_constraint_risk",
}


def _setup(optimized: bool = False):
    scenario = generate_scenario(default_scenario_spec(), seed=42)
    baseline = simulate_baseline(scenario)
    if optimized:
        schedule = simulate_optimized(scenario, baseline)
        metrics = compute_metrics(schedule, scenario, baseline_schedule=baseline)
    else:
        schedule = baseline
        metrics = compute_metrics(schedule, scenario)
    report = verify_schedule(schedule, scenario)
    return scenario, schedule, metrics, report


def _finding(report: BottleneckReport, finding_type: str):
    return next(f for f in report.findings if f.finding_type == finding_type)


def test_returns_valid_report() -> None:
    scenario, schedule, metrics, report = _setup()
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    assert isinstance(result, BottleneckReport)
    BottleneckReport.model_validate(result.model_dump())
    assert result.summary["synthetic"] is True


def test_contains_all_required_finding_types() -> None:
    scenario, schedule, metrics, report = _setup()
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    assert {f.finding_type for f in result.findings} == REQUIRED_TYPES


def test_worst_late_task_matches_max_late() -> None:
    scenario, schedule, metrics, report = _setup()
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    expected = max(schedule.events, key=lambda e: e.late_by_min)
    finding = _finding(result, "worst_late_task")
    assert finding.evidence["late_by_min"] == expected.late_by_min


def test_worst_energy_matches_max_energy() -> None:
    scenario, schedule, metrics, report = _setup()
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    expected = max(schedule.events, key=lambda e: e.energy_used)
    finding = _finding(result, "worst_energy_event")
    assert finding.evidence["energy_used"] == expected.energy_used


def test_worst_co2e_matches_max_co2e() -> None:
    scenario, schedule, metrics, report = _setup()
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    expected = max(schedule.events, key=lambda e: e.co2e_proxy)
    finding = _finding(result, "worst_co2e_event")
    assert finding.evidence["co2e_proxy"] == expected.co2e_proxy


def test_worst_freshness_is_perishable_task() -> None:
    scenario, schedule, metrics, report = _setup()
    tasks_by_id = {t.task_id: t for t in scenario.tasks}
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    finding = _finding(result, "worst_freshness_waste_event")
    task_id = finding.evidence.get("task_id")
    assert task_id is not None
    assert tasks_by_id[task_id].freshness_decay_rate > 0.0


def test_constraint_risk_reports_pass_when_clean() -> None:
    scenario, schedule, metrics, report = _setup()
    assert report.passed is True
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    finding = _finding(result, "worst_constraint_risk")
    assert finding.evidence["passed"] is True
    assert finding.severity == "low"


def test_constraint_risk_reports_violation_details() -> None:
    scenario, schedule, metrics, clean_report = _setup()
    # Build a schedule with an obvious violation (missing task coverage).
    bad_schedule = Schedule(policy_name="bad", events=list(schedule.events)[:-1])
    bad_report = verify_schedule(bad_schedule, scenario)
    assert bad_report.passed is False

    result = generate_bottleneck_report(bad_schedule, scenario, metrics, bad_report)
    finding = _finding(result, "worst_constraint_risk")
    assert finding.evidence["passed"] is False
    assert "violation_type" in finding.evidence
    assert finding.evidence["n_violations"] >= 1


def test_constraint_risk_when_verifier_missing() -> None:
    scenario, schedule, metrics, _ = _setup()
    result = generate_bottleneck_report(schedule, scenario, metrics, None)
    finding = _finding(result, "worst_constraint_risk")
    assert finding.evidence["verifier_run"] is False


def test_all_confidences_in_unit_interval() -> None:
    scenario, schedule, metrics, report = _setup(optimized=True)
    result = generate_bottleneck_report(schedule, scenario, metrics, report)
    for f in result.findings:
        assert 0.0 <= f.confidence <= 1.0


def test_deterministic() -> None:
    scenario, schedule, metrics, report = _setup()
    a = generate_bottleneck_report(schedule, scenario, metrics, report)
    b = generate_bottleneck_report(schedule, scenario, metrics, report)
    assert a.model_dump() == b.model_dump()


def test_does_not_mutate_inputs() -> None:
    scenario, schedule, metrics, report = _setup()
    before_schedule = schedule.model_dump()
    before_scenario = scenario.model_dump()
    generate_bottleneck_report(schedule, scenario, metrics, report)
    assert schedule.model_dump() == before_schedule
    assert scenario.model_dump() == before_scenario


def test_handles_empty_schedule() -> None:
    scenario, _, metrics, _ = _setup()
    empty = Schedule(policy_name="empty", events=[])
    result = generate_bottleneck_report(empty, scenario, metrics, None)
    assert {f.finding_type for f in result.findings} == REQUIRED_TYPES
    for f in result.findings:
        assert 0.0 <= f.confidence <= 1.0
