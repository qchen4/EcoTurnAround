"""T8 — Hermes reflection memory tests.

Verify deterministic construction of reflection entries (signature, failure
modes, lesson), robust JSONL append/load behavior (empty file, blank lines,
malformed JSON), and deterministic tag-based retrieval — all without mutating
inputs.
"""

from __future__ import annotations

import pytest

from ecoturn.analysis import generate_bottleneck_report
from ecoturn.baseline import simulate_baseline
from ecoturn.memory import (
    append_reflection_entry,
    build_reflection_entry,
    load_reflection_entries,
    retrieve_relevant_lessons,
)
from ecoturn.metrics import compute_metrics
from ecoturn.optimizer import simulate_optimized
from ecoturn.refinement import propose_refinements
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.schemas import Metrics, ReflectionEntry
from ecoturn.verifier import verify_schedule

EXPECTED_SIGNATURE_KEYS = {
    "hub",
    "scenario_name",
    "synthetic",
    "vehicle_count",
    "task_count",
    "ev_share",
    "autonomous_ev_present",
    "perishable_tasks_present",
    "chargers_present",
    "wireless_future_present",
}


def _full_run(scenario_name: str = "atl_sandbox_default"):
    scenario = generate_scenario(default_scenario_spec(scenario_name), seed=42)
    baseline = simulate_baseline(scenario)
    optimized = simulate_optimized(scenario, baseline)
    base_metrics = compute_metrics(baseline, scenario)
    opt_metrics = compute_metrics(optimized, scenario, baseline_schedule=baseline)
    report = verify_schedule(optimized, scenario)
    bottleneck = generate_bottleneck_report(optimized, scenario, opt_metrics, report)
    proposals = propose_refinements(opt_metrics, report, bottleneck, scenario)
    return scenario, base_metrics, opt_metrics, report, bottleneck, proposals


def _entry(scenario_name: str = "atl_sandbox_default") -> ReflectionEntry:
    scenario, base_metrics, opt_metrics, report, bottleneck, proposals = _full_run(
        scenario_name
    )
    return build_reflection_entry(
        scenario, base_metrics, opt_metrics, report, bottleneck, proposals
    )


def test_build_returns_valid_entry() -> None:
    entry = _entry()
    assert isinstance(entry, ReflectionEntry)
    ReflectionEntry.model_validate(entry.model_dump())
    assert entry.optimizer == "rolling_horizon_greedy"
    assert entry.attempt_id


def test_signature_keys_present() -> None:
    entry = _entry()
    assert EXPECTED_SIGNATURE_KEYS.issubset(entry.scenario_signature.keys())


def test_failure_modes_include_waste_regression() -> None:
    scenario, _, opt_metrics, report, bottleneck, proposals = _full_run()
    bumped = opt_metrics.model_copy(update={"waste_index": 130.0})
    entry = build_reflection_entry(
        scenario, None, bumped, report, bottleneck, proposals
    )
    assert "metric_regression:waste_index>100" in entry.failure_modes


def test_failure_modes_include_violation_types() -> None:
    from collections import Counter

    from ecoturn.schemas import VerificationReport, Violation

    scenario, _, opt_metrics, _, bottleneck, proposals = _full_run()
    violations = [Violation(constraint="vehicle_overlap", severity="high")]
    bad_report = VerificationReport(
        passed=False,
        violations=violations,
        counterexamples=[],
        hard_constraint_summary=dict(Counter(v.constraint for v in violations)),
    )
    entry = build_reflection_entry(
        scenario, None, opt_metrics, bad_report, bottleneck, proposals
    )
    assert "violation:vehicle_overlap" in entry.failure_modes


def test_lesson_includes_proposal_changes() -> None:
    scenario, base_metrics, opt_metrics, report, bottleneck, proposals = _full_run()
    entry = build_reflection_entry(
        scenario, base_metrics, opt_metrics, report, bottleneck, proposals
    )
    assert proposals  # default run yields at least one proposal
    for proposal in proposals:
        assert proposal.change in entry.lesson


def test_append_creates_jsonl_file(tmp_path) -> None:
    path = tmp_path / "logs" / "reflection_log.jsonl"
    entry = _entry()
    append_reflection_entry(entry, path)
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()


def test_load_appended_entries(tmp_path) -> None:
    path = tmp_path / "reflection_log.jsonl"
    entry = _entry()
    append_reflection_entry(entry, path)
    append_reflection_entry(entry, path)
    loaded = load_reflection_entries(path)
    assert len(loaded) == 2
    assert loaded[0].model_dump() == entry.model_dump()


def test_load_tolerates_empty_file(tmp_path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert load_reflection_entries(path) == []


def test_load_skips_blank_lines(tmp_path) -> None:
    path = tmp_path / "blanks.jsonl"
    entry = _entry()
    append_reflection_entry(entry, path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n   \n")
    loaded = load_reflection_entries(path)
    assert len(loaded) == 1


def test_load_raises_on_malformed_json(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_reflection_entries(path)


def test_retrieve_is_deterministic(tmp_path) -> None:
    path = tmp_path / "reflection_log.jsonl"
    append_reflection_entry(_entry("atl_sandbox_default"), path)
    append_reflection_entry(_entry("future_fleet_2040"), path)
    scenario = generate_scenario(default_scenario_spec(), seed=42)
    a = retrieve_relevant_lessons(scenario, path, limit=5)
    b = retrieve_relevant_lessons(scenario, path, limit=5)
    assert [e.attempt_id for e in a] == [e.attempt_id for e in b]


def test_retrieve_prefers_matching_scenario(tmp_path) -> None:
    path = tmp_path / "reflection_log.jsonl"
    append_reflection_entry(_entry("future_fleet_2040"), path)
    append_reflection_entry(_entry("atl_sandbox_default"), path)

    scenario = generate_scenario(default_scenario_spec("atl_sandbox_default"), seed=42)
    results = retrieve_relevant_lessons(scenario, path, limit=2)
    assert results
    assert results[0].scenario_signature["scenario_name"] == "atl_sandbox_default"


def test_retrieve_missing_file_returns_empty(tmp_path) -> None:
    scenario = generate_scenario(default_scenario_spec(), seed=42)
    assert retrieve_relevant_lessons(scenario, tmp_path / "nope.jsonl") == []


def test_build_does_not_mutate_inputs() -> None:
    scenario, base_metrics, opt_metrics, report, bottleneck, proposals = _full_run()
    before = (
        scenario.model_dump(),
        opt_metrics.model_dump(),
        report.model_dump(),
        bottleneck.model_dump(),
        [p.model_dump() for p in proposals],
    )
    build_reflection_entry(
        scenario, base_metrics, opt_metrics, report, bottleneck, proposals
    )
    after = (
        scenario.model_dump(),
        opt_metrics.model_dump(),
        report.model_dump(),
        bottleneck.model_dump(),
        [p.model_dump() for p in proposals],
    )
    assert before == after


def test_build_is_deterministic() -> None:
    a = _entry()
    b = _entry()
    assert a.model_dump() == b.model_dump()
    assert a.attempt_id == b.attempt_id
