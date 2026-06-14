"""Hermes reflection JSONL only.

A simple, deterministic, file-based reflection memory. Each run can record a
scenario signature, result KPIs, derived failure modes, and a reusable lesson
as one JSON line in ``data/reflection_log.jsonl``. Later runs can retrieve
relevant past lessons by deterministic tag matching (no vector DB, no external
APIs, no agent runtime).

This supports the narrative that EcoTurnaround OS does not just optimize once:
it remembers what failed, which bottlenecks appeared, what refinements were
suggested, and what to try next.

All recorded data is synthetic ATL-sandbox prototype data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from ecoturn.schemas import (
    BottleneckReport,
    GeneratedScenario,
    Metrics,
    RefinementProposal,
    ReflectionEntry,
    VerificationReport,
)

DEFAULT_LOG_PATH = "data/reflection_log.jsonl"

_SYNTHETIC_NOTE = "Synthetic ATL-sandbox prototype lesson; not real Delta data."

_HIGH_LATE_RATE = 0.10
_SEVERITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _scenario_signature(scenario: GeneratedScenario) -> dict[str, object]:
    """Deterministic, comparable tag bundle describing a scenario."""

    vehicles = scenario.vehicles
    n_vehicles = len(vehicles)
    ev_count = sum(
        1 for v in vehicles if v.powertrain in ("ev", "autonomous_ev")
    )
    autonomous_present = any(v.powertrain == "autonomous_ev" for v in vehicles)
    perishable_present = any(t.freshness_decay_rate > 0.0 for t in scenario.tasks)
    wireless_present = any(
        c.charger_type == "wireless_future" for c in scenario.chargers
    )

    return {
        "hub": scenario.spec.hub,
        "scenario_name": scenario.spec.scenario_name,
        "synthetic": bool(scenario.synthetic),
        "vehicle_count": n_vehicles,
        "task_count": len(scenario.tasks),
        "ev_share": round(ev_count / n_vehicles, 3) if n_vehicles else 0.0,
        "autonomous_ev_present": autonomous_present,
        "perishable_tasks_present": perishable_present,
        "chargers_present": len(scenario.chargers) > 0,
        "wireless_future_present": wireless_present,
    }


def _build_result(
    optimized_metrics: Metrics,
    baseline_metrics: Metrics | None,
    verification_report: VerificationReport,
    refinement_proposals: list[RefinementProposal],
) -> dict[str, object]:
    result: dict[str, object] = {
        "late_task_rate": optimized_metrics.late_task_rate,
        "co2e_index": optimized_metrics.co2e_index,
        "waste_index": optimized_metrics.waste_index,
        "idle_time_index": optimized_metrics.idle_time_index,
        "cost_index": optimized_metrics.cost_index,
        "verifier_passed": verification_report.passed,
        "num_violations": len(verification_report.violations),
        "num_refinement_proposals": len(refinement_proposals),
    }
    if baseline_metrics is not None:
        result["baseline_late_task_rate"] = baseline_metrics.late_task_rate
        result["baseline_co2e_index"] = baseline_metrics.co2e_index
    return result


def _build_failure_modes(
    optimized_metrics: Metrics,
    verification_report: VerificationReport,
    bottleneck_report: BottleneckReport,
) -> list[str]:
    modes: list[str] = []

    for violation_type in sorted({v.constraint for v in verification_report.violations}):
        modes.append(f"violation:{violation_type}")

    for finding in bottleneck_report.findings:
        if _SEVERITY_RANK.get(finding.severity, 0) >= _SEVERITY_RANK["high"]:
            modes.append(f"bottleneck:{finding.finding_type}:{finding.severity}")

    if optimized_metrics.waste_index > 100.0:
        modes.append("metric_regression:waste_index>100")
    if optimized_metrics.co2e_index > 100.0:
        modes.append("metric_regression:co2e_index>100")
    if optimized_metrics.late_task_rate > _HIGH_LATE_RATE:
        modes.append("metric_regression:high_late_task_rate")

    return modes


def _build_lesson(refinement_proposals: list[RefinementProposal]) -> str:
    all_changes = [p.change for p in refinement_proposals]
    auto_changes = [p.change for p in refinement_proposals if p.mode == "auto"]
    human_changes = [p.change for p in refinement_proposals if p.mode == "human_gate"]

    parts = [
        f"Proposed changes: {', '.join(all_changes) if all_changes else 'none'}.",
        f"Auto-applicable next run: {', '.join(auto_changes) if auto_changes else 'none'}.",
    ]
    if human_changes:
        parts.append(
            "Do NOT auto-relax (human approval required): "
            f"{', '.join(human_changes)}."
        )
    parts.append(
        "Next run: apply auto adjustments, keep safety boundaries human-gated, "
        "and re-check bottlenecks."
    )
    parts.append(_SYNTHETIC_NOTE)
    return " ".join(parts)


def _attempt_id(
    signature: dict[str, object], optimizer: str, result: dict[str, object]
) -> str:
    payload = json.dumps(
        {"signature": signature, "optimizer": optimizer, "result": result},
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"atl-{digest[:12]}"


def build_reflection_entry(
    scenario: GeneratedScenario,
    baseline_metrics: Metrics | None,
    optimized_metrics: Metrics,
    verification_report: VerificationReport,
    bottleneck_report: BottleneckReport,
    refinement_proposals: list[RefinementProposal],
    optimizer_name: str = "rolling_horizon_greedy",
) -> ReflectionEntry:
    """Assemble a deterministic :class:`ReflectionEntry` from a run's artifacts.

    Does not mutate any input.
    """

    signature = _scenario_signature(scenario)
    result = _build_result(
        optimized_metrics, baseline_metrics, verification_report, refinement_proposals
    )
    failure_modes = _build_failure_modes(
        optimized_metrics, verification_report, bottleneck_report
    )
    lesson = _build_lesson(refinement_proposals)

    tags = [
        f"hub:{signature['hub']}",
        f"scenario:{signature['scenario_name']}",
    ]
    if signature["perishable_tasks_present"]:
        tags.append("perishable")
    if signature["autonomous_ev_present"]:
        tags.append("autonomous_ev")
    if signature["wireless_future_present"]:
        tags.append("wireless_future")

    return ReflectionEntry(
        attempt_id=_attempt_id(signature, optimizer_name, result),
        scenario_signature=signature,
        optimizer=optimizer_name,
        result=result,
        failure_modes=failure_modes,
        lesson=lesson,
        tags=tags,
    )


def append_reflection_entry(
    entry: ReflectionEntry,
    path: str | Path = DEFAULT_LOG_PATH,
) -> None:
    """Append one reflection entry as a JSON line, creating parents as needed."""

    file_path = Path(path)
    if file_path.parent and not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")


def load_reflection_entries(
    path: str | Path = DEFAULT_LOG_PATH,
) -> list[ReflectionEntry]:
    """Load all reflection entries from a JSONL file.

    Tolerates a missing or empty file and skips blank lines. Raises a clear
    ``ValueError`` on malformed JSON or schema-invalid lines (never silently
    ignores them).
    """

    file_path = Path(path)
    if not file_path.exists():
        return []

    entries: list[ReflectionEntry] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                entries.append(ReflectionEntry.model_validate(obj))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValueError(
                    f"Malformed reflection entry at {file_path}:{line_no}: {exc}"
                ) from exc
    return entries


def _relevance_score(
    entry: ReflectionEntry, query: dict[str, object]
) -> int:
    sig = entry.scenario_signature
    score = 0
    if sig.get("hub") == query.get("hub"):
        score += 3
    if sig.get("scenario_name") == query.get("scenario_name"):
        score += 3
    if sig.get("perishable_tasks_present") == query.get("perishable_tasks_present"):
        score += 1
    if sig.get("autonomous_ev_present") == query.get("autonomous_ev_present"):
        score += 1
    if sig.get("wireless_future_present") == query.get("wireless_future_present"):
        score += 1
    return score


def retrieve_relevant_lessons(
    scenario: GeneratedScenario,
    path: str | Path = DEFAULT_LOG_PATH,
    limit: int = 3,
) -> list[ReflectionEntry]:
    """Return up to ``limit`` past entries most relevant to ``scenario``.

    Relevance is deterministic tag matching (hub, scenario_name, perishable,
    autonomous, wireless). Results are sorted by descending score then
    ``attempt_id``. Does not mutate inputs.
    """

    query = _scenario_signature(scenario)
    entries = load_reflection_entries(path)
    ranked = sorted(
        entries,
        key=lambda e: (-_relevance_score(e, query), e.attempt_id),
    )
    if limit < 0:
        limit = 0
    return ranked[:limit]
