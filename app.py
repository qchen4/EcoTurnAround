"""Streamlit UI orchestration only.

EcoTurnaround OS — ATL-sandbox Decision Cockpit.

A one-click Streamlit demo that runs the full backend pipeline:

    natural-language prompt
    -> ATL-sandbox scenario
    -> baseline dispatch
    -> optimized dispatch
    -> metrics comparison
    -> verifier status
    -> bottleneck report
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

TABS = [
    "Decision Cockpit",
    "Scenario & Model",
    "Schedule Comparison",
    "Bottleneck Report",
    "Refinement & Memory",
    "Artifacts",
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
    "pipeline_status",
]

_SEVERITY_COLOR = {
    "low": "#2e7d32",
    "medium": "#f9a825",
    "high": "#ef6c00",
    "critical": "#c62828",
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

    The natural-language prompt is recorded for context. Parsing is a
    deterministic fallback (T9): we build the default ATL-sandbox spec rather
    than calling an LLM, so the app runs without any API access.
    """

    status: list[str] = []

    spec = default_scenario_spec(scenario_name or "atl_sandbox_default")
    scenario = generate_scenario(spec, seed=seed)
    status.append("Scenario generated (deterministic ATL-sandbox fallback)")

    baseline_schedule = simulate_baseline(scenario)
    status.append("Baseline simulated")

    optimized_schedule = simulate_optimized(scenario, baseline_schedule)
    status.append("Optimized simulated")

    baseline_metrics = compute_metrics(baseline_schedule, scenario)
    optimized_metrics = compute_metrics(
        optimized_schedule, scenario, baseline_schedule=baseline_schedule
    )
    status.append("Metrics computed")

    verification_report = verify_schedule(optimized_schedule, scenario)
    status.append("Verifier completed")

    bottleneck_report = generate_bottleneck_report(
        optimized_schedule, scenario, optimized_metrics, verification_report
    )
    status.append("Bottleneck report generated")

    refinement_proposals = propose_refinements(
        optimized_metrics, verification_report, bottleneck_report, scenario
    )
    status.append("Refinements proposed")

    reflection_entry = build_reflection_entry(
        scenario,
        baseline_metrics,
        optimized_metrics,
        verification_report,
        bottleneck_report,
        refinement_proposals,
    )
    status.append("Reflection memory entry built (not yet saved)")

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
        pipeline_status=status,
    )


def _has_run() -> bool:
    return st.session_state.get("scenario") is not None


def _events_df(schedule) -> pd.DataFrame:
    if schedule is None or not schedule.events:
        return pd.DataFrame()
    return pd.DataFrame([e.model_dump() for e in schedule.events])


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
def _tab_cockpit() -> None:
    st.title("EcoTurnaround OS")
    st.caption(
        "ATL-sandbox decision cockpit for sustainable airport ground operations."
    )
    st.warning(DISCLAIMER, icon="⚠️")

    st.subheader("Operational goal (natural language)")
    prompt = st.text_area(
        "Prompt",
        value=st.session_state.get("prompt") or DEFAULT_PROMPT,
        height=120,
        label_visibility="collapsed",
    )

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            scenario_name = st.text_input(
                "Scenario name / preset", value="atl_sandbox_default"
            )
        with col2:
            seed = st.number_input("Random seed", min_value=0, value=42, step=1)
        with col3:
            st.write("")
            st.write("")
            run = st.button("Run Full Pipeline", type="primary", width="stretch")

    if run:
        with st.spinner("Running deterministic ATL-sandbox pipeline..."):
            _run_pipeline(prompt, scenario_name, int(seed))
        st.success("Pipeline complete.")

    if not _has_run():
        st.info("Set your goal and click **Run Full Pipeline** to begin.")
        return

    st.divider()
    st.subheader("Pipeline status")
    for step in st.session_state["pipeline_status"]:
        st.write(f"✅ {step}")

    st.divider()
    st.subheader("Key performance indicators")
    opt = st.session_state["optimized_metrics"]
    report = st.session_state["verification_report"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("CO2e Index", f"{opt.co2e_index:.1f}", delta=f"{opt.co2e_index - 100:.1f}", delta_color="inverse")
    c2.metric("Cost Index", f"{opt.cost_index:.1f}", delta=f"{opt.cost_index - 100:.1f}", delta_color="inverse")
    c3.metric("Waste Index", f"{opt.waste_index:.1f}", delta=f"{opt.waste_index - 100:.1f}", delta_color="inverse")
    c4.metric("Late Task Rate", f"{opt.late_task_rate:.2%}")
    c5.metric("Verifier", "PASS" if report.passed else "FAIL")

    st.caption("Index metrics are relative to the baseline (=100). Lower is better.")

    st.divider()
    st.subheader("Recommendation summary")
    proposals = st.session_state["refinement_proposals"]
    if not proposals:
        st.success("No refinements suggested — the optimized schedule looks healthy.")
    else:
        top = proposals[0]
        gated = [p for p in proposals if p.mode == "human_gate"]
        st.markdown(
            f"**Top action:** `{top.change}` ({top.mode}) — {top.expected_effect}"
        )
        st.markdown(f"{len(proposals)} proposal(s) total; {len(gated)} require human approval.")
        if gated:
            st.warning(
                "Some changes touch hard safety boundaries and must be "
                "human-approved (never auto-relaxed)."
            )


def _tab_scenario() -> None:
    st.header("Scenario & Model")
    if not _has_run():
        st.info("Run the pipeline first.")
        return

    scenario = st.session_state["scenario"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zones", len(scenario.zones))
    c2.metric("Vehicles", len(scenario.vehicles))
    c3.metric("Tasks", len(scenario.tasks))
    c4.metric("Chargers", len(scenario.chargers))

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Fleet by powertrain")
        fleet = Counter(v.powertrain for v in scenario.vehicles)
        st.dataframe(
            pd.DataFrame(sorted(fleet.items()), columns=["powertrain", "count"]),
            width="stretch",
            hide_index=True,
        )
        st.subheader("Chargers by type")
        chargers = Counter(c.charger_type for c in scenario.chargers)
        st.dataframe(
            pd.DataFrame(sorted(chargers.items()), columns=["charger_type", "count"]),
            width="stretch",
            hide_index=True,
        )
    with col_right:
        st.subheader("Tasks by type")
        tasks = Counter(t.task_type for t in scenario.tasks)
        st.dataframe(
            pd.DataFrame(sorted(tasks.items()), columns=["task_type", "count"]),
            width="stretch",
            hide_index=True,
        )
        st.subheader("ATL-sandbox zones")
        st.dataframe(
            pd.DataFrame({"zone": scenario.zones}),
            width="stretch",
            hide_index=True,
        )

    with st.expander("ScenarioSpec JSON"):
        st.json(scenario.spec.model_dump())
    with st.expander("Full generated scenario JSON (vehicles / tasks / chargers)"):
        st.json(scenario.model_dump())


def _tab_comparison() -> None:
    st.header("Schedule Comparison")
    if not _has_run():
        st.info("Run the pipeline first.")
        return

    base = st.session_state["baseline_metrics"]
    opt = st.session_state["optimized_metrics"]

    metrics_table = pd.DataFrame(
        {
            "baseline": [
                base.co2e_index, base.waste_index, base.idle_time_index,
                base.cost_index, base.late_task_rate, base.charger_queue_peak,
            ],
            "optimized": [
                opt.co2e_index, opt.waste_index, opt.idle_time_index,
                opt.cost_index, opt.late_task_rate, opt.charger_queue_peak,
            ],
        },
        index=[
            "co2e_index", "waste_index", "idle_time_index",
            "cost_index", "late_task_rate", "charger_queue_peak",
        ],
    )
    st.subheader("Metrics: baseline vs optimized")
    st.dataframe(metrics_table, width="stretch")

    st.subheader("Index metrics (baseline = 100, lower is better)")
    index_chart = pd.DataFrame(
        {
            "baseline": [base.co2e_index, base.waste_index, base.idle_time_index, base.cost_index],
            "optimized": [opt.co2e_index, opt.waste_index, opt.idle_time_index, opt.cost_index],
        },
        index=["co2e_index", "waste_index", "idle_time_index", "cost_index"],
    )
    st.bar_chart(index_chart)

    st.subheader("Late task rate")
    lc1, lc2 = st.columns(2)
    lc1.metric("Baseline late rate", f"{base.late_task_rate:.2%}")
    lc2.metric(
        "Optimized late rate",
        f"{opt.late_task_rate:.2%}",
        delta=f"{(opt.late_task_rate - base.late_task_rate):.2%}",
        delta_color="inverse",
    )

    with st.expander("Baseline schedule"):
        st.dataframe(_events_df(st.session_state["baseline_schedule"]), width="stretch", hide_index=True)
    with st.expander("Optimized schedule"):
        st.dataframe(_events_df(st.session_state["optimized_schedule"]), width="stretch", hide_index=True)


def _tab_bottleneck() -> None:
    st.header("Bottleneck / Critical-Path Report")
    st.caption("Engineering-style diagnostic over synthetic ATL-sandbox data.")
    if not _has_run():
        st.info("Run the pipeline first.")
        return

    report = st.session_state["bottleneck_report"]
    for finding in report.findings:
        color = _SEVERITY_COLOR.get(finding.severity, "#555")
        with st.expander(f"{finding.title}  ·  [{finding.severity.upper()}]", expanded=False):
            st.markdown(
                f"<span style='color:{color};font-weight:600'>"
                f"{finding.finding_type} — severity: {finding.severity}</span>",
                unsafe_allow_html=True,
            )
            st.progress(
                min(1.0, max(0.0, finding.confidence)),
                text=f"Confidence: {finding.confidence:.0%}",
            )
            st.markdown(f"**Likely cause:** {finding.likely_cause or '—'}")
            st.markdown(f"**Suggested what-if:** {finding.suggested_what_if or '—'}")
            st.markdown("**Evidence:**")
            st.json(finding.evidence)


def _tab_refinement() -> None:
    st.header("Adaptive Refinement & Hermes Memory")
    if not _has_run():
        st.info("Run the pipeline first.")
        return

    proposals = st.session_state["refinement_proposals"]
    st.subheader("Refinement proposals")
    if not proposals:
        st.success("No refinements proposed for this run.")
    for p in proposals:
        is_gate = p.mode == "human_gate"
        with st.container(border=True):
            badge = "🔒 HUMAN GATE" if is_gate else "⚙️ AUTO"
            st.markdown(f"**{badge}** — `{p.change}`")
            st.markdown(
                f"- from: `{p.from_value}` → to: `{p.to_value}`\n"
                f"- expected effect: {p.expected_effect}"
            )
            st.caption(p.reason)

    st.divider()
    st.subheader("Hermes reflection memory")
    entry = st.session_state["reflection_entry"]
    with st.expander("Reflection entry to be saved"):
        st.json(entry.model_dump())

    if st.button("Save Reflection to JSONL"):
        append_reflection_entry(entry, DEFAULT_LOG_PATH)
        st.success(f"Saved reflection entry to {DEFAULT_LOG_PATH}.")

    st.markdown("**Relevant past lessons**")
    lessons = retrieve_relevant_lessons(st.session_state["scenario"], DEFAULT_LOG_PATH, limit=3)
    if not lessons:
        st.info("No prior lessons yet. Save a reflection to start building memory.")
    else:
        for lesson in lessons:
            with st.container(border=True):
                st.markdown(f"**{lesson.attempt_id}** · `{lesson.scenario_signature.get('scenario_name')}`")
                st.caption(lesson.lesson)
                if lesson.failure_modes:
                    st.markdown("Failure modes: " + ", ".join(f"`{m}`" for m in lesson.failure_modes))


def _tab_artifacts() -> None:
    st.header("Artifacts")
    if not _has_run():
        st.info("Run the pipeline first.")
        return

    scenario = st.session_state["scenario"]
    baseline_schedule = st.session_state["baseline_schedule"]
    optimized_schedule = st.session_state["optimized_schedule"]
    base_metrics = st.session_state["baseline_metrics"]
    opt_metrics = st.session_state["optimized_metrics"]
    bottleneck = st.session_state["bottleneck_report"]
    proposals = st.session_state["refinement_proposals"]
    entry = st.session_state["reflection_entry"]

    proposals_json = "[\n" + ",\n".join(p.model_dump_json(indent=2) for p in proposals) + "\n]"

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


def main() -> None:
    st.set_page_config(page_title="EcoTurnaround OS — Decision Cockpit", layout="wide")
    _init_state()
    st.sidebar.title("EcoTurnaround OS")
    st.sidebar.caption(f"ATL-sandbox prototype · v{ecoturn.__version__}")
    st.sidebar.info(DISCLAIMER)

    tab_objs = st.tabs(TABS)
    renderers = [
        _tab_cockpit,
        _tab_scenario,
        _tab_comparison,
        _tab_bottleneck,
        _tab_refinement,
        _tab_artifacts,
    ]
    for tab, render in zip(tab_objs, renderers):
        with tab:
            render()


if __name__ == "__main__":
    main()
