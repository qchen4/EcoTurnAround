"""T7 — adaptive boundary refinement tests.

Verify the refinement engine turns metrics/verifier/bottleneck evidence into
valid, deterministic, non-mutating refinement proposals with correct modes
(auto vs human_gate) and no duplicate `change` keys.
"""

from __future__ import annotations

from ecoturn.refinement import propose_refinements
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.schemas import (
    BottleneckFinding,
    BottleneckReport,
    Metrics,
    RefinementProposal,
    VerificationReport,
    Violation,
)


def _scenario():
    return generate_scenario(default_scenario_spec(), seed=42)


def _finding(finding_type: str, severity: str = "low", evidence=None) -> BottleneckFinding:
    return BottleneckFinding(
        finding_type=finding_type,
        title=f"{finding_type} ({severity})",
        severity=severity,
        evidence=evidence or {},
        likely_cause="",
        suggested_what_if="",
        confidence=0.65,
    )


def _report(
    late="low",
    energy="low",
    co2e="low",
    fresh="low",
    co2e_powertrain="ev",
) -> BottleneckReport:
    return BottleneckReport(
        findings=[
            _finding("worst_late_task", late),
            _finding("worst_energy_event", energy),
            _finding("worst_co2e_event", co2e, {"powertrain": co2e_powertrain}),
            _finding("worst_freshness_waste_event", fresh),
            _finding("worst_constraint_risk", "low"),
        ],
        summary={},
    )


def _metrics(**kw) -> Metrics:
    return Metrics(**kw)


def _clean_report() -> VerificationReport:
    return VerificationReport(passed=True, violations=[], counterexamples=[], hard_constraint_summary={})


def _violation_report(violations: list[Violation]) -> VerificationReport:
    from collections import Counter

    return VerificationReport(
        passed=False,
        violations=violations,
        counterexamples=[{"constraint": v.constraint} for v in violations],
        hard_constraint_summary=dict(Counter(v.constraint for v in violations)),
    )


def test_returns_valid_proposals() -> None:
    proposals = propose_refinements(
        _metrics(), _clean_report(), _report(), _scenario()
    )
    assert isinstance(proposals, list)
    for p in proposals:
        assert isinstance(p, RefinementProposal)
        RefinementProposal.model_validate(p.model_dump())


def test_high_late_rate_produces_lateness_refinement() -> None:
    proposals = propose_refinements(
        _metrics(late_task_rate=0.5), _clean_report(), _report(), _scenario()
    )
    changes = {p.change for p in proposals}
    assert "solver:lateness_penalty" in changes


def test_waste_regression_produces_freshness_refinement() -> None:
    proposals = propose_refinements(
        _metrics(waste_index=130.0), _clean_report(), _report(), _scenario()
    )
    changes = {p.change for p in proposals}
    assert "solver:freshness_priority" in changes


def test_diesel_co2e_produces_co2e_refinement() -> None:
    report = _report(co2e="high", co2e_powertrain="diesel")
    proposals = propose_refinements(_metrics(), _clean_report(), report, _scenario())
    changes = {p.change for p in proposals}
    assert "solver:co2e_weight" in changes


def test_high_energy_produces_staging_refinement() -> None:
    report = _report(energy="high")
    proposals = propose_refinements(_metrics(), _clean_report(), report, _scenario())
    changes = {p.change for p in proposals}
    assert "staging:rebalance_vehicle_staging" in changes


def test_restricted_zone_violation_is_human_gated() -> None:
    vr = _violation_report(
        [Violation(constraint="restricted_zone_violation", severity="critical")]
    )
    proposals = propose_refinements(_metrics(), vr, _report(), _scenario())
    gated = [p for p in proposals if p.change == "safety:allow_restricted_runway_crossing"]
    assert gated
    assert gated[0].mode == "human_gate"


def test_critical_task_lateness_produces_human_gate() -> None:
    vr = _violation_report(
        [Violation(constraint="critical_task_late", severity="critical")]
    )
    proposals = propose_refinements(_metrics(), vr, _report(), _scenario())
    gated = [p for p in proposals if p.mode == "human_gate"]
    assert any(p.change == "safety:critical_deadline_buffer_min" for p in gated)


def test_clean_verifier_with_waste_still_auto_freshness() -> None:
    proposals = propose_refinements(
        _metrics(waste_index=120.0), _clean_report(), _report(), _scenario()
    )
    fresh = [p for p in proposals if p.change == "solver:freshness_priority"]
    assert fresh
    assert fresh[0].mode == "auto"


def test_all_modes_valid() -> None:
    vr = _violation_report(
        [
            Violation(constraint="restricted_zone_violation", severity="critical"),
            Violation(constraint="vehicle_overlap", severity="high"),
        ]
    )
    report = _report(late="high", energy="high", co2e="high", fresh="high", co2e_powertrain="diesel")
    proposals = propose_refinements(_metrics(waste_index=130.0), vr, report, _scenario())
    for p in proposals:
        assert p.mode in ("auto", "human_gate")
    # And both modes should appear given this rich input.
    modes = {p.mode for p in proposals}
    assert modes == {"auto", "human_gate"}


def test_deterministic() -> None:
    vr = _violation_report(
        [Violation(constraint="autonomy_corridor_violation", severity="critical")]
    )
    report = _report(late="high", co2e="high", co2e_powertrain="diesel")
    metrics = _metrics(late_task_rate=0.4, waste_index=140.0, co2e_index=110.0)
    scenario = _scenario()
    a = propose_refinements(metrics, vr, report, scenario)
    b = propose_refinements(metrics, vr, report, scenario)
    assert [p.model_dump() for p in a] == [p.model_dump() for p in b]


def test_does_not_mutate_inputs() -> None:
    vr = _violation_report(
        [Violation(constraint="restricted_zone_violation", severity="critical")]
    )
    report = _report(late="high", co2e="high", co2e_powertrain="diesel")
    metrics = _metrics(waste_index=130.0, co2e_index=120.0, late_task_rate=0.4)
    scenario = _scenario()

    before = (
        metrics.model_dump(),
        vr.model_dump(),
        report.model_dump(),
        scenario.model_dump(),
    )
    propose_refinements(metrics, vr, report, scenario)
    after = (
        metrics.model_dump(),
        vr.model_dump(),
        report.model_dump(),
        scenario.model_dump(),
    )
    assert before == after


def test_no_duplicate_change_values() -> None:
    vr = _violation_report(
        [
            Violation(constraint="critical_task_late", severity="critical"),
            Violation(constraint="vehicle_overlap", severity="high"),
        ]
    )
    report = _report(late="critical", energy="high", co2e="high", fresh="high", co2e_powertrain="diesel")
    metrics = _metrics(late_task_rate=0.6, waste_index=150.0, co2e_index=130.0)
    proposals = propose_refinements(metrics, vr, report, _scenario())
    changes = [p.change for p in proposals]
    assert len(changes) == len(set(changes))
