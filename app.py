"""Streamlit UI orchestration only.

EcoTurnaround OS — Decision Intelligence Cockpit.

A natural-language decision-support cockpit for sustainable airport ground
operations. It answers "what should I do and why?" first, then exposes the
supporting evidence, bottlenecks, reusable knowledge, and raw technicals.

Pipeline behind the scenes (unchanged backend):

    natural-language goal
    -> ATL-sandbox scenario
    -> baseline dispatch
    -> optimized dispatch
    -> metrics / verifier / bottleneck report
    -> adaptive refinement proposals
    -> Hermes reflection memory

Everything shown is SYNTHETIC ATL-sandbox prototype data. It does NOT use real
Delta or ATL operational data and makes no claim of global optimality.

This module is UI orchestration only — all logic lives in ``ecoturn``.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

import ecoturn
from ecoturn.analysis import generate_bottleneck_report
from ecoturn.baseline import simulate_baseline
from ecoturn.memory import (
    DEFAULT_LOG_PATH,
    append_reflection_entry,
    build_reflection_entry,
    retrieve_relevant_lessons,
)
from ecoturn.metrics import compute_metrics
from ecoturn.optimizer import simulate_optimized
from ecoturn.refinement import propose_refinements
from ecoturn.scenario_generator import default_scenario_spec, generate_scenario
from ecoturn.verifier import verify_schedule

DEFAULT_PROMPT = (
    "Reduce ATL-sandbox ground-operation emissions without sacrificing "
    "turnaround reliability. Preserve hard safety boundaries for restricted "
    "runway crossings, autonomous corridors, minimum SOC, and critical "
    "turnaround tasks."
)

DISCLAIMER = (
    "Synthetic ATL-sandbox prototype. Does NOT use real Delta or ATL "
    "operational data. No claim of global optimality."
)

TRACK_ALIGNMENT = (
    "Aligned with Moving Things & People: Port & Airport Sustainability, "
    "Supply Chain Visibility & Efficiency, and EV Charging Experience."
)

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_SEVERITY_COLOR = {
    "low": "#2e7d32",
    "medium": "#f9a825",
    "high": "#ef6c00",
    "critical": "#c62828",
}

TABS = [
    "Decision Brief",
    "What-if Workspace",
    "Evidence & Confidence",
    "Critical Bottlenecks",
    "Knowledge Memory",
    "Technical Appendix",
]

_STATE_KEYS = [
    "scenario",
    "baseline_schedule",
    "optimized_schedule",
    "baseline_metrics",
    "optimized_metrics",
    "verification_report",
    "bottleneck_report",
    "refinement_proposals",
    "reflection_entry",
    "prompt",
]

_BUSINESS_MEANING = {
    "worst_late_task": "On-time turnaround reliability",
    "worst_energy_event": "Energy cost & charging demand",
    "worst_co2e_event": "Carbon footprint of dispatch",
    "worst_freshness_waste_event": "Catering spoilage / waste",
    "worst_constraint_risk": "Safety & operational compliance",
}


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def _init_state() -> None:
    for key in _STATE_KEYS:
        if key not in st.session_state:
            st.session_state[key] = None


def _run_pipeline(prompt: str, scenario_name: str, seed: int) -> None:
    """Run the full deterministic backend pipeline and store results in state.

    The natural-language goal is recorded for context. Parsing is a
    deterministic fallback (no LLM): we build the default ATL-sandbox spec, so
    the app runs without any API access.
    """

    spec = default_scenario_spec(scenario_name or "atl_sandbox_default")
    scenario = generate_scenario(spec, seed=seed)
    baseline_schedule = simulate_baseline(scenario)
    optimized_schedule = simulate_optimized(scenario, baseline_schedule)
    baseline_metrics = compute_metrics(baseline_schedule, scenario)
    optimized_metrics = compute_metrics(
        optimized_schedule, scenario, baseline_schedule=baseline_schedule
    )
    verification_report = verify_schedule(optimized_schedule, scenario)
    bottleneck_report = generate_bottleneck_report(
        optimized_schedule, scenario, optimized_metrics, verification_report
    )
    refinement_proposals = propose_refinements(
        optimized_metrics, verification_report, bottleneck_report, scenario
    )
    reflection_entry = build_reflection_entry(
        scenario,
        baseline_metrics,
        optimized_metrics,
        verification_report,
        bottleneck_report,
        refinement_proposals,
    )

    st.session_state.update(
        prompt=prompt,
        scenario=scenario,
        baseline_schedule=baseline_schedule,
        optimized_schedule=optimized_schedule,
        baseline_metrics=baseline_metrics,
        optimized_metrics=optimized_metrics,
        verification_report=verification_report,
        bottleneck_report=bottleneck_report,
        refinement_proposals=refinement_proposals,
        reflection_entry=reflection_entry,
    )


def _has_run() -> bool:
    return st.session_state.get("scenario") is not None


def _events_df(schedule) -> pd.DataFrame:
    if schedule is None or not schedule.events:
        return pd.DataFrame()
    return pd.DataFrame([e.model_dump() for e in schedule.events])


# --------------------------------------------------------------------------- #
# Derived insight helpers (read-only; no backend changes)
# --------------------------------------------------------------------------- #
def _finding(bottleneck_report, finding_type: str):
    return next(
        (f for f in bottleneck_report.findings if f.finding_type == finding_type),
        None,
    )


def _finding_confidence(bottleneck_report, finding_type: str, default: float = 0.6) -> float:
    f = _finding(bottleneck_report, finding_type)
    return f.confidence if f is not None else default


def _top_recommendation(proposals, base, opt, bottleneck_report):
    """Pick the proposal aligned with the most visible KPI regression."""

    if not proposals:
        return None
    by_change = {p.change: p for p in proposals}

    if opt.waste_index > 100.0:
        for change in (
            "solver:freshness_priority",
            "staging:reserve_catering_vehicle_near_catering_facility",
        ):
            if change in by_change:
                return by_change[change]

    worst_late = _finding(bottleneck_report, "worst_late_task")
    late_worse = opt.late_task_rate > base.late_task_rate
    late_dominant = worst_late is not None and _SEVERITY_RANK.get(
        worst_late.severity, 0
    ) >= max(
        (_SEVERITY_RANK.get(f.severity, 0) for f in bottleneck_report.findings),
        default=0,
    ) and _SEVERITY_RANK.get(worst_late.severity, 0) >= _SEVERITY_RANK["high"]
    if (late_worse or late_dominant) and "solver:lateness_penalty" in by_change:
        return by_change["solver:lateness_penalty"]

    return proposals[0]


def _decision_confidence(bottleneck_report, verification_report) -> float:
    confs = [f.confidence for f in bottleneck_report.findings]
    base = sum(confs) / len(confs) if confs else 0.6
    if verification_report.passed:
        base += 0.05
    return max(0.0, min(1.0, round(base, 3)))


def _tradeoff_summary(base, opt) -> str:
    improvements = []
    if opt.co2e_index < 100.0:
        improvements.append("emissions")
    if opt.cost_index < 100.0:
        improvements.append("cost")
    if opt.idle_time_index < 100.0:
        improvements.append("idle time")
    improved = ", ".join(improvements) if improvements else "no index metrics"

    late_clause = (
        "preserving lateness"
        if opt.late_task_rate <= base.late_task_rate
        else "with some added lateness"
    )
    waste_clause = (
        "but increases perishable waste risk"
        if opt.waste_index > 100.0
        else "and reduces perishable waste risk"
    )
    return (
        f"The optimized dispatch reduces {improved} while {late_clause}, "
        f"{waste_clause}."
    )


def _evidence_summary(finding) -> str:
    """A short, human-readable one-liner describing a bottleneck finding."""

    ev = finding.evidence or {}
    ftype = finding.finding_type
    if ftype == "worst_late_task":
        if not ev or ev.get("late_by_min", 0) in (0, 0.0):
            return "No late tasks in the optimized schedule."
        return (
            f"Task {ev.get('task_id')} on vehicle {ev.get('vehicle_id')} finished "
            f"{ev.get('late_by_min')} min past its deadline "
            f"({ev.get('origin_zone')} → {ev.get('destination_zone')})."
        )
    if ftype == "worst_energy_event":
        if not ev:
            return "No events to assess for energy draw."
        return (
            f"Task {ev.get('task_id')} drew the most energy "
            f"({ev.get('energy_used')} kWh-proxy) on vehicle {ev.get('vehicle_id')}."
        )
    if ftype == "worst_co2e_event":
        if not ev:
            return "No events to assess for emissions."
        return (
            f"Task {ev.get('task_id')} produced the highest CO2e proxy "
            f"({ev.get('co2e_proxy')}) using a {ev.get('powertrain')} vehicle."
        )
    if ftype == "worst_freshness_waste_event":
        if not ev or ev.get("perishable_task_count") == 0:
            return "No perishable/catering tasks in this scenario."
        return (
            f"Catering task {ev.get('task_id')} has the highest freshness/waste "
            f"risk ({ev.get('freshness_risk')}) after {ev.get('elapsed_time_min')} "
            "min elapsed."
        )
    if ftype == "worst_constraint_risk":
        if ev.get("verifier_run") is False:
            return "The verifier was not run for this schedule."
        if ev.get("passed"):
            return "All hard operational and safety constraints passed."
        return (
            f"Highest-severity violation: {ev.get('violation_type')} "
            f"({finding.severity}); {ev.get('n_violations')} total."
        )
    return finding.title


def _decision_implication(finding) -> str:
    ev = finding.evidence or {}
    ftype = finding.finding_type
    if ftype == "worst_late_task":
        if ev.get("late_by_min", 0) in (0, 0.0):
            return "Reliability is healthy — no action needed."
        return "Raise lateness priority or pre-position a compatible vehicle nearer the origin."
    if ftype == "worst_energy_event":
        return "Rebalance vehicle staging to cut cross-concourse travel and energy."
    if ftype == "worst_co2e_event":
        if ev.get("powertrain") == "diesel":
            return "Shift this assignment to an electric vehicle where margins allow."
        return "Emissions for this event are already low; focus elsewhere."
    if ftype == "worst_freshness_waste_event":
        if ev.get("perishable_task_count") == 0:
            return "No perishable tasks — no waste action needed."
        return "Raise freshness priority or pre-stage a catering vehicle near the facility."
    if ftype == "worst_constraint_risk":
        if ev.get("passed"):
            return "No compliance action — hard safety boundaries are intact."
        return "Resolve the violation; safety-critical changes require human approval."
    return "Review the evidence and consider a what-if."


def _co2e_breakdown(schedule, scenario, key: str) -> pd.DataFrame:
    """Synthetic CO2e proxy aggregated by 'powertrain' or 'task_type'."""

    vmap = {v.vehicle_id: v for v in scenario.vehicles}
    tmap = {t.task_id: t for t in scenario.tasks}
    agg: dict[str, float] = {}
    for e in schedule.events:
        if key == "powertrain":
            vehicle = vmap.get(e.vehicle_id)
            label = vehicle.powertrain if vehicle is not None else "unknown"
        else:
            task = tmap.get(e.task_id)
            label = task.task_type if task is not None else "unknown"
        agg[label] = round(agg.get(label, 0.0) + e.co2e_proxy, 3)
    rows = sorted(agg.items(), key=lambda kv: -kv[1])
    return pd.DataFrame(rows, columns=[key, "co2e_proxy"])


def _total_co2e(schedule) -> float:
    return round(sum(e.co2e_proxy for e in schedule.events), 3)


def _whatif_catalog(opt, bottleneck_report, proposals):
    """Deterministic what-if interpretations (no LLM, no optimizer rerun)."""

    fresh = _finding(bottleneck_report, "worst_freshness_waste_event")
    co2 = _finding(bottleneck_report, "worst_co2e_event")
    energy = _finding(bottleneck_report, "worst_energy_event")
    fresh_conf = fresh.confidence if fresh else 0.6
    co2_conf = co2.confidence if co2 else 0.6

    return [
        {
            "prompt": "What if we increase freshness priority?",
            "keywords": ["freshness", "fresh", "priority"],
            "change": "solver:freshness_priority",
            "effect": "Serve catering/perishable tasks sooner, lowering waste risk.",
            "confidence": fresh_conf,
            "human_gate": False,
            "evidence": (
                f"Waste index is {opt.waste_index:.1f} (>100). "
                + (_evidence_summary(fresh) if fresh else "")
            ),
        },
        {
            "prompt": "What if we reserve a catering vehicle near the catering facility?",
            "keywords": ["reserve", "stage", "staging", "catering vehicle", "catering truck"],
            "change": "staging:reserve_catering_vehicle_near_catering_facility",
            "effect": "Cut catering pickup delay and perishable spoilage.",
            "confidence": max(0.5, fresh_conf - 0.05),
            "human_gate": False,
            "evidence": (
                "Catering waste is driven by elapsed time from catering_facility. "
                + (_evidence_summary(fresh) if fresh else "")
            ),
        },
        {
            "prompt": "What if we prefer EVs when SOC and lateness margins allow?",
            "keywords": ["ev", "electric", "prefer"],
            "change": "policy:prefer_electric_when_margins_allow",
            "effect": "Shift load to electric vehicles, lowering the CO2e proxy further.",
            "confidence": co2_conf,
            "human_gate": False,
            "evidence": (
                f"Optimized CO2e index is {opt.co2e_index:.1f}. "
                + (_evidence_summary(co2) if co2 else "")
            ),
        },
        {
            "prompt": "What if we add opportunity charging near the midfield hub?",
            "keywords": ["opportunity", "charging", "charger", "midfield"],
            "change": "infrastructure:add_opportunity_charger_midfield",
            "effect": "Reduce charging detours and SOC risk for EVs working the midfield.",
            "confidence": 0.5,
            "human_gate": False,
            "evidence": (
                "Diagnostic what-if (would need a rerun to quantify). "
                + (_evidence_summary(energy) if energy else "")
            ),
        },
        {
            "prompt": "What if we relax restricted runway crossing?",
            "keywords": ["relax", "restricted", "runway", "crossing"],
            "change": "safety:allow_restricted_runway_crossing",
            "effect": (
                "Could shorten a few routes, but crosses a HARD SAFETY boundary."
            ),
            "confidence": 0.4,
            "human_gate": True,
            "evidence": (
                "Restricted runway crossing is a hard safety boundary. The verifier "
                "enforces it and the system never auto-relaxes it."
            ),
        },
    ]


def _match_whatif(text: str, catalog):
    text_l = (text or "").lower().strip()
    if not text_l:
        return None
    best = None
    best_hits = 0
    for item in catalog:
        hits = sum(1 for kw in item["keywords"] if kw in text_l)
        if hits > best_hits:
            best_hits = hits
            best = item
    return best if best_hits > 0 else None


def _empty_state() -> None:
    st.info("Set your goal in the sidebar and click **Generate decision** to begin.")


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def _tab_brief() -> None:
    st.title("EcoTurnaround OS — Decision Brief")
    st.caption("Natural-language modeling for confidence-weighted ground-ops decisions.")
    st.warning(DISCLAIMER, icon="⚠️")
    st.caption(f"🎯 {TRACK_ALIGNMENT}")

    if not _has_run():
        _empty_state()
        return

    base = st.session_state["baseline_metrics"]
    opt = st.session_state["optimized_metrics"]
    report = st.session_state["verification_report"]
    bottleneck = st.session_state["bottleneck_report"]
    proposals = st.session_state["refinement_proposals"]
    entry = st.session_state["reflection_entry"]

    st.subheader("Business question")
    st.markdown(f"> {st.session_state.get('prompt') or DEFAULT_PROMPT}")

    top = _top_recommendation(proposals, base, opt, bottleneck)
    confidence = _decision_confidence(bottleneck, report)

    st.subheader("Recommended decision")
    if top is None:
        st.success("Adopt the optimized dispatch — no further adjustment needed.")
    else:
        st.success(
            f"**Adopt the optimized dispatch and apply: {top.change}** — "
            f"{top.expected_effect}"
        )

    st.subheader("Confidence")
    st.progress(confidence, text=f"Decision confidence: {confidence:.0%} (synthetic, single-scenario)")

    st.subheader("Expected impact")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("Carbon (CO2e index)", f"{opt.co2e_index:.0f}", delta=f"{opt.co2e_index - 100:.0f}", delta_color="inverse")
    i2.metric("Cost index", f"{opt.cost_index:.0f}", delta=f"{opt.cost_index - 100:.0f}", delta_color="inverse")
    i3.metric("Late task rate", f"{opt.late_task_rate:.0%}", delta=f"{(opt.late_task_rate - base.late_task_rate):.0%}", delta_color="inverse")
    i4.metric("Waste index", f"{opt.waste_index:.0f}", delta=f"{opt.waste_index - 100:.0f}", delta_color="inverse")
    st.caption("Indices are relative to baseline = 100. Lower is better. Synthetic proxies.")

    st.subheader("Key tradeoff")
    st.markdown(_tradeoff_summary(base, opt))

    st.subheader("Human-gated risks")
    gated = [p for p in proposals if p.mode == "human_gate"]
    if not gated:
        st.success(
            "No safety boundaries were breached. Absolute SOC, restricted zones, "
            "autonomous corridors, and critical deadlines remain enforced and are "
            "never auto-relaxed."
        )
    else:
        for p in gated:
            st.warning(f"🔒 {p.change} — requires human approval. {p.expected_effect}")

    st.subheader("Knowledge created by this run")
    st.markdown(
        f"- Reusable lesson recorded as attempt `{entry.attempt_id}`.\n"
        f"- Failure modes captured: "
        + (", ".join(f"`{m}`" for m in entry.failure_modes) or "none")
        + f"\n- Save it in **Knowledge Memory** to help future runs of "
        f"`{entry.scenario_signature.get('scenario_name')}`."
    )


def _tab_whatif() -> None:
    st.header("What-if Workspace")
    st.caption("Explore decisions in plain language — decision support, not uncontrolled automation.")
    if not _has_run():
        _empty_state()
        return

    opt = st.session_state["optimized_metrics"]
    bottleneck = st.session_state["bottleneck_report"]
    proposals = st.session_state["refinement_proposals"]
    catalog = _whatif_catalog(opt, bottleneck, proposals)

    st.markdown("Pick an example or type your own what-if. No optimizer rerun — "
                "each what-if is interpreted into a model change with evidence.")

    example = st.selectbox("Example what-ifs", [c["prompt"] for c in catalog])
    typed = st.text_input("Or type a what-if", value="")

    chosen = _match_whatif(typed, catalog) if typed.strip() else None
    if chosen is None:
        chosen = next(c for c in catalog if c["prompt"] == example)
        if typed.strip():
            st.info("Couldn't map that phrasing — showing the closest selected example.")

    with st.container(border=True):
        badge = "🔒 HUMAN GATE REQUIRED" if chosen["human_gate"] else "⚙️ AUTO-APPLICABLE"
        st.markdown(f"### {chosen['prompt']}")
        st.markdown(f"**{badge}**")
        st.markdown(f"**Interpreted model change:** `{chosen['change']}`")
        st.markdown(f"**Expected effect:** {chosen['effect']}")
        st.progress(
            max(0.0, min(1.0, chosen["confidence"])),
            text=f"Confidence: {chosen['confidence']:.0%}",
        )
        st.markdown(f"**Supporting evidence:** {chosen['evidence']}")
        if chosen["human_gate"]:
            st.error(
                "This touches a hard safety boundary. The system will not "
                "auto-apply it; a human must approve any change."
            )


def _tab_evidence() -> None:
    st.header("Evidence & Confidence")
    if not _has_run():
        _empty_state()
        return

    base = st.session_state["baseline_metrics"]
    opt = st.session_state["optimized_metrics"]
    report = st.session_state["verification_report"]
    bottleneck = st.session_state["bottleneck_report"]
    scenario = st.session_state["scenario"]
    baseline_schedule = st.session_state["baseline_schedule"]
    optimized_schedule = st.session_state["optimized_schedule"]

    reliability = (
        "Reliability preserved"
        if opt.late_task_rate <= base.late_task_rate
        else "Reliability changed"
    )
    waste_claim = (
        "Waste / freshness risk increased"
        if opt.waste_index > 100.0
        else "Waste / freshness risk reduced"
    )
    rows = [
        {
            "Claim": "Carbon improved",
            "Evidence": f"CO2e index {opt.co2e_index:.1f} vs baseline 100",
            "Confidence": f"{_finding_confidence(bottleneck, 'worst_co2e_event'):.0%}",
            "Caveat": "Synthetic CO2e proxy, not measured emissions.",
        },
        {
            "Claim": "Cost improved",
            "Evidence": f"Cost index {opt.cost_index:.1f} vs baseline 100",
            "Confidence": "70%",
            "Caveat": "Composite synthetic cost proxy.",
        },
        {
            "Claim": reliability,
            "Evidence": f"Late rate {opt.late_task_rate:.0%} vs baseline {base.late_task_rate:.0%}",
            "Confidence": f"{_finding_confidence(bottleneck, 'worst_late_task'):.0%}",
            "Caveat": "Single synthetic scenario.",
        },
        {
            "Claim": waste_claim,
            "Evidence": f"Waste index {opt.waste_index:.1f} vs baseline 100",
            "Confidence": f"{_finding_confidence(bottleneck, 'worst_freshness_waste_event'):.0%}",
            "Caveat": "Proxy freshness model, not a spoilage measurement.",
        },
        {
            "Claim": "Hard constraints passed" if report.passed else "Hard constraints FAILED",
            "Evidence": f"{len(report.violations)} violation(s) from the verifier",
            "Confidence": f"{_finding_confidence(bottleneck, 'worst_constraint_risk', 0.8):.0%}",
            "Caveat": "Rule-based verifier over synthetic schedule.",
        },
    ]
    st.subheader("Evidence board")
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.subheader("Synthetic CO2e proxy breakdown")
    st.caption("Synthetic CO2e proxy — NOT real emissions. From DispatchEvent.co2e_proxy.")
    t1, t2 = st.columns(2)
    t1.metric("Baseline total CO2e proxy", f"{_total_co2e(baseline_schedule):.1f}")
    t2.metric(
        "Optimized total CO2e proxy",
        f"{_total_co2e(optimized_schedule):.1f}",
        delta=f"{_total_co2e(optimized_schedule) - _total_co2e(baseline_schedule):.1f}",
        delta_color="inverse",
    )

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**Optimized CO2e proxy by powertrain**")
        st.dataframe(_co2e_breakdown(optimized_schedule, scenario, "powertrain"), width="stretch", hide_index=True)
    with b2:
        st.markdown("**Optimized CO2e proxy by task type**")
        st.dataframe(_co2e_breakdown(optimized_schedule, scenario, "task_type"), width="stretch", hide_index=True)


def _tab_bottlenecks() -> None:
    st.header("Critical Bottlenecks")
    st.caption("Decision-insight cards from an engineering-style critical-path analysis.")
    if not _has_run():
        _empty_state()
        return

    report = st.session_state["bottleneck_report"]
    for finding in report.findings:
        color = _SEVERITY_COLOR.get(finding.severity, "#555")
        with st.container(border=True):
            st.markdown(
                f"**{_BUSINESS_MEANING.get(finding.finding_type, finding.finding_type)}** "
                f"<span style='color:{color};font-weight:600'>· {finding.severity.upper()}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Bottleneck:** {finding.title}")
            st.markdown(f"**Evidence:** {_evidence_summary(finding)}")
            st.markdown(f"**Decision implication:** {_decision_implication(finding)}")
            st.markdown(f"**Suggested what-if:** {finding.suggested_what_if or '—'}")
            st.progress(
                max(0.0, min(1.0, finding.confidence)),
                text=f"Confidence: {finding.confidence:.0%}",
            )
            with st.expander("Raw evidence JSON"):
                st.json(finding.evidence)


def _tab_memory() -> None:
    st.header("Knowledge Memory")
    st.caption("Reusable operational knowledge — Hermes-style reflection.")
    if not _has_run():
        _empty_state()
        return

    entry = st.session_state["reflection_entry"]
    proposals = st.session_state["refinement_proposals"]
    scenario = st.session_state["scenario"]
    sig = entry.scenario_signature

    auto_changes = [p.change for p in proposals if p.mode == "auto"]
    gate_changes = [p.change for p in proposals if p.mode == "human_gate"]

    st.subheader("What the system learned")
    st.markdown(entry.lesson)

    st.subheader("When this lesson applies")
    applies = [f"hub = {sig.get('hub')}", f"scenario = {sig.get('scenario_name')}"]
    if sig.get("perishable_tasks_present"):
        applies.append("perishable/catering tasks present")
    if sig.get("autonomous_ev_present"):
        applies.append("autonomous EVs present")
    if sig.get("wireless_future_present"):
        applies.append("future wireless charging present")
    st.markdown("\n".join(f"- {a}" for a in applies))

    st.subheader("What to try next")
    st.markdown(", ".join(f"`{c}`" for c in auto_changes) or "No auto adjustments suggested.")

    st.subheader("What NOT to auto-relax")
    st.markdown(
        ", ".join(f"`{c}`" for c in gate_changes)
        or "No human-gated changes this run — safety boundaries intact."
    )

    if st.button("Save lesson to memory (JSONL)"):
        append_reflection_entry(entry, DEFAULT_LOG_PATH)
        st.success(f"Saved to {DEFAULT_LOG_PATH}.")

    st.subheader("Relevant past lessons")
    lessons = retrieve_relevant_lessons(scenario, DEFAULT_LOG_PATH, limit=3)
    if not lessons:
        st.info("No prior lessons yet. Save this run's lesson to start building memory.")
    else:
        for lesson in lessons:
            with st.container(border=True):
                st.markdown(
                    f"**{lesson.attempt_id}** · scenario "
                    f"`{lesson.scenario_signature.get('scenario_name')}`"
                )
                st.caption(lesson.lesson)

    with st.expander("Full reflection entry JSON"):
        st.json(entry.model_dump())


def _tab_appendix() -> None:
    st.header("Technical Appendix")
    st.caption("Raw model artifacts for engineers and auditors.")
    if not _has_run():
        _empty_state()
        return

    scenario = st.session_state["scenario"]
    baseline_schedule = st.session_state["baseline_schedule"]
    optimized_schedule = st.session_state["optimized_schedule"]
    base_metrics = st.session_state["baseline_metrics"]
    opt_metrics = st.session_state["optimized_metrics"]
    bottleneck = st.session_state["bottleneck_report"]
    proposals = st.session_state["refinement_proposals"]
    entry = st.session_state["reflection_entry"]

    with st.expander("Baseline schedule table"):
        st.dataframe(_events_df(baseline_schedule), width="stretch", hide_index=True)
    with st.expander("Optimized schedule table"):
        st.dataframe(_events_df(optimized_schedule), width="stretch", hide_index=True)
    with st.expander("ScenarioSpec JSON"):
        st.json(scenario.spec.model_dump())
    with st.expander("Full generated scenario JSON"):
        st.json(scenario.model_dump())
    with st.expander("Baseline metrics JSON"):
        st.json(base_metrics.model_dump())
    with st.expander("Optimized metrics JSON"):
        st.json(opt_metrics.model_dump())
    with st.expander("Bottleneck report JSON"):
        st.json(bottleneck.model_dump())
    with st.expander("Refinement proposals JSON"):
        st.json([p.model_dump() for p in proposals])

    proposals_json = "[\n" + ",\n".join(p.model_dump_json(indent=2) for p in proposals) + "\n]"
    st.subheader("Artifact downloads")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Scenario JSON", scenario.model_dump_json(indent=2), "scenario.json", "application/json")
        st.download_button("Baseline schedule CSV", _events_df(baseline_schedule).to_csv(index=False), "baseline_schedule.csv", "text/csv")
        st.download_button("Optimized schedule CSV", _events_df(optimized_schedule).to_csv(index=False), "optimized_schedule.csv", "text/csv")
        st.download_button("Baseline metrics JSON", base_metrics.model_dump_json(indent=2), "baseline_metrics.json", "application/json")
    with c2:
        st.download_button("Optimized metrics JSON", opt_metrics.model_dump_json(indent=2), "optimized_metrics.json", "application/json")
        st.download_button("Bottleneck report JSON", bottleneck.model_dump_json(indent=2), "bottleneck_report.json", "application/json")
        st.download_button("Refinement proposals JSON", proposals_json, "refinement_proposals.json", "application/json")
        st.download_button("Reflection entry JSON", entry.model_dump_json(indent=2), "reflection_entry.json", "application/json")


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def _sidebar() -> None:
    st.sidebar.title("EcoTurnaround OS")
    st.sidebar.caption(f"Decision intelligence cockpit · v{ecoturn.__version__}")
    st.sidebar.info(DISCLAIMER)
    st.sidebar.caption(TRACK_ALIGNMENT)
    st.sidebar.divider()

    st.sidebar.subheader("Your business goal")
    prompt = st.sidebar.text_area(
        "Goal",
        value=st.session_state.get("prompt") or DEFAULT_PROMPT,
        height=140,
        label_visibility="collapsed",
    )
    scenario_name = st.sidebar.text_input("Scenario", value="atl_sandbox_default")
    seed = st.sidebar.number_input("Random seed", min_value=0, value=42, step=1)
    if st.sidebar.button("Generate decision", type="primary", width="stretch"):
        with st.spinner("Modeling the ATL-sandbox decision..."):
            _run_pipeline(prompt, scenario_name, int(seed))
        st.sidebar.success("Decision ready.")


def main() -> None:
    st.set_page_config(page_title="EcoTurnaround OS — Decision Cockpit", layout="wide")
    _init_state()
    _sidebar()

    tab_objs = st.tabs(TABS)
    renderers = [
        _tab_brief,
        _tab_whatif,
        _tab_evidence,
        _tab_bottlenecks,
        _tab_memory,
        _tab_appendix,
    ]
    for tab, render in zip(tab_objs, renderers):
        with tab:
            render()


if __name__ == "__main__":
    main()
