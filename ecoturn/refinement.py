"""Boundary refinement proposals only.

A deterministic refinement engine that turns metrics, verifier results, and
bottleneck findings into evidence-backed what-if / boundary-refinement
proposals. It does NOT run or apply anything — it only proposes changes — and
it never mutates its inputs.

Safety-critical boundaries (absolute minimum SOC, restricted zones,
autonomous corridors, critical turnaround deadlines, hard safety constraints)
are always routed to a human gate and never auto-relaxed.

All recommendations are based on synthetic ATL-sandbox prototype analysis.
"""

from __future__ import annotations

from ecoturn.schemas import (
    BottleneckReport,
    GeneratedScenario,
    Metrics,
    RefinementProposal,
    VerificationReport,
)

_SYNTHETIC_NOTE = "Based on ATL-sandbox synthetic prototype analysis."

_SEVERITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Verifier violation types that touch hard safety boundaries.
_SAFETY_VIOLATIONS = frozenset(
    {
        "restricted_zone_violation",
        "autonomy_corridor_violation",
        "critical_task_late",
    }
)

# Thresholds (synthetic).
_LATE_RATE_HIGH = 0.10
_WEIGHT_BUMP = 1.5
_HORIZON_BUMP = 1.25


def _finding(report: BottleneckReport, finding_type: str):
    return next(
        (f for f in report.findings if f.finding_type == finding_type), None
    )


def _sev_at_least(finding, level: str) -> bool:
    if finding is None:
        return False
    return _SEVERITY_RANK[finding.severity] >= _SEVERITY_RANK[level]


def propose_refinements(
    metrics: Metrics,
    verification_report: VerificationReport,
    bottleneck_report: BottleneckReport,
    scenario: GeneratedScenario,
) -> list[RefinementProposal]:
    """Propose deterministic, ordered boundary refinements.

    Ordering (most to least important):
      1. human-gated safety / constraint risks
      2. late-task risks
      3. freshness / waste risks
      4. CO2e risks
      5. energy / idle risks

    Proposals are de-duplicated by ``change`` (first occurrence wins).
    """

    solver = scenario.spec.solver_policy
    safety = scenario.spec.safety_policy

    worst_late = _finding(bottleneck_report, "worst_late_task")
    worst_co2e = _finding(bottleneck_report, "worst_co2e_event")
    worst_energy = _finding(bottleneck_report, "worst_energy_event")
    worst_fresh = _finding(bottleneck_report, "worst_freshness_waste_event")

    violations = verification_report.violations
    summary = verification_report.hard_constraint_summary
    safety_hits = {v.constraint for v in violations if v.constraint in _SAFETY_VIOLATIONS}
    non_safety_hits = [
        v for v in violations if v.constraint not in _SAFETY_VIOLATIONS
    ]

    critical_late = (
        "critical_task_late" in safety_hits
        or _sev_at_least(worst_late, "critical")
    )

    constraint_human: list[RefinementProposal] = []
    constraint_auto: list[RefinementProposal] = []
    late: list[RefinementProposal] = []
    freshness: list[RefinementProposal] = []
    co2e: list[RefinementProposal] = []
    energy: list[RefinementProposal] = []

    # --- 1. Constraint risks: human-gated safety changes -------------------
    if "restricted_zone_violation" in safety_hits:
        constraint_human.append(
            RefinementProposal(
                change="safety:allow_restricted_runway_crossing",
                from_value=False,
                to_value="human_review_required",
                reason=(
                    "Verifier flagged a restricted_runway_crossing violation. "
                    "Allowing access to a restricted runway crossing is a hard "
                    "safety boundary and must never be auto-relaxed. "
                    f"{_SYNTHETIC_NOTE}"
                ),
                mode="human_gate",
                expected_effect=(
                    "Only a human approver may authorize restricted-zone access; "
                    "otherwise reroute to avoid the crossing."
                ),
            )
        )
    if "autonomy_corridor_violation" in safety_hits:
        constraint_human.append(
            RefinementProposal(
                change="safety:autonomous_allowed_zones",
                from_value=list(safety.autonomous_allowed_zones),
                to_value="human_review_required",
                reason=(
                    "Verifier flagged an autonomous vehicle operating outside "
                    "its allowed corridors. Changing autonomous allowed corridors "
                    f"requires human approval. {_SYNTHETIC_NOTE}"
                ),
                mode="human_gate",
                expected_effect=(
                    "Keep autonomous EVs inside approved corridors; expand "
                    "corridors only with human sign-off."
                ),
            )
        )
    if critical_late:
        constraint_human.append(
            RefinementProposal(
                change="safety:critical_deadline_buffer_min",
                from_value=safety.critical_deadline_buffer_min,
                to_value="human_review_required",
                reason=(
                    "A critical turnaround task is late. Relaxing a critical "
                    "deadline is a hard safety/operational boundary and requires "
                    f"human approval. {_SYNTHETIC_NOTE}"
                ),
                mode="human_gate",
                expected_effect=(
                    "Protect critical turnarounds; deadline changes only via "
                    "human gate, otherwise raise lateness weight (see below)."
                ),
            )
        )

    # --- 1b. Constraint risks: ordinary (auto) parameter changes ----------
    if non_safety_hits:
        types = sorted({v.constraint for v in non_safety_hits})
        constraint_auto.append(
            RefinementProposal(
                change="solver:rolling_horizon_min",
                from_value=solver.rolling_horizon_min,
                to_value=round(solver.rolling_horizon_min * _HORIZON_BUMP, 3),
                reason=(
                    "Verifier flagged ordinary operational violations "
                    f"({', '.join(types)}). Widening the rolling horizon can "
                    f"reduce infeasible overlaps/assignments. {_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect=(
                    "Improve assignment feasibility and reduce overlap/"
                    "incompatibility violations."
                ),
            )
        )

    # --- 2. Late-task risks (auto) ----------------------------------------
    if metrics.late_task_rate > _LATE_RATE_HIGH or _sev_at_least(worst_late, "high"):
        late.append(
            RefinementProposal(
                change="solver:lateness_penalty",
                from_value=solver.lateness_penalty,
                to_value=round(solver.lateness_penalty * _WEIGHT_BUMP, 3),
                reason=(
                    f"Late-task rate is {round(metrics.late_task_rate, 3)} and the "
                    "worst late-task bottleneck is significant. Increasing the "
                    f"lateness penalty prioritizes on-time turnarounds. {_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect="Reduce late tasks and protect turnaround reliability.",
            )
        )

    # --- 3. Freshness / waste risks (auto) --------------------------------
    if metrics.waste_index > 100.0 or _sev_at_least(worst_fresh, "medium"):
        freshness.append(
            RefinementProposal(
                change="solver:freshness_priority",
                from_value=solver.freshness_priority,
                to_value=round(solver.freshness_priority * _WEIGHT_BUMP, 3),
                reason=(
                    f"Waste index is {round(metrics.waste_index, 3)} (>100) or a "
                    "perishable task shows elevated freshness risk. Raising "
                    f"freshness priority serves catering tasks sooner. {_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect="Reduce perishable/catering waste risk.",
            )
        )
        freshness.append(
            RefinementProposal(
                change="staging:reserve_catering_vehicle_near_catering_facility",
                from_value=None,
                to_value="reserve 1 catering-compatible vehicle near catering_facility",
                reason=(
                    "Catering waste risk is driven by elapsed time from "
                    "catering_facility. Pre-staging a catering-compatible vehicle "
                    f"there cuts pickup delay. {_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect="Reduce catering pickup delay and spoilage risk.",
            )
        )

    # --- 4. CO2e risks (auto) ---------------------------------------------
    diesel_heavy = bool(
        worst_co2e is not None and worst_co2e.evidence.get("powertrain") == "diesel"
    )
    if metrics.co2e_index > 100.0 or diesel_heavy:
        co2e.append(
            RefinementProposal(
                change="solver:co2e_weight",
                from_value=None,
                to_value="increase",
                reason=(
                    f"CO2e index is {round(metrics.co2e_index, 3)} or the worst "
                    "emissions event is diesel-heavy. Increasing the CO2e weight "
                    f"steers work toward cleaner vehicles. {_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect="Reduce the emissions proxy.",
            )
        )
        co2e.append(
            RefinementProposal(
                change="policy:prefer_electric_when_margins_allow",
                from_value=None,
                to_value="prefer ev/autonomous_ev when SOC and lateness margins allow",
                reason=(
                    "Diesel assignments dominate the emissions proxy. Preferring "
                    "electric vehicles where SOC and lateness margins allow lowers "
                    f"CO2e without risking turnarounds. {_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect="Shift load to electric vehicles, reducing emissions.",
            )
        )

    # --- 5. Energy / idle risks (auto) ------------------------------------
    if _sev_at_least(worst_energy, "high"):
        energy.append(
            RefinementProposal(
                change="staging:rebalance_vehicle_staging",
                from_value=None,
                to_value="stage vehicles closer to demand zones to cut cross-concourse travel",
                reason=(
                    "The worst energy event reflects long cross-concourse travel. "
                    "Rebalancing vehicle staging shortens trips and idle travel. "
                    f"{_SYNTHETIC_NOTE}"
                ),
                mode="auto",
                expected_effect="Reduce energy consumption and idle travel.",
            )
        )

    ordered = (
        constraint_human
        + constraint_auto
        + late
        + freshness
        + co2e
        + energy
    )

    # De-duplicate by `change`, preserving first (highest-priority) occurrence.
    seen: set[str] = set()
    deduped: list[RefinementProposal] = []
    for proposal in ordered:
        if proposal.change in seen:
            continue
        seen.add(proposal.change)
        deduped.append(proposal)

    return deduped
