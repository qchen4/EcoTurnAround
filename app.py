"""Streamlit UI orchestration only.

Minimal placeholder app for T1. The full multi-tab dashboard is built in
later tasks. This entry point only needs to start a placeholder page so
that ``streamlit run app.py`` works.
"""

from __future__ import annotations

import streamlit as st

import ecoturn

TABS = [
    "Prompt & Model",
    "Baseline vs Optimized",
    "Verifier & Boundary Refinement",
    "Hermes Reflection",
    "Artifacts",
]


def main() -> None:
    st.set_page_config(page_title="EcoTurnaround OS", layout="wide")
    st.title("EcoTurnaround OS")
    st.caption(
        f"Adaptive modeling copilot for airport ground operations "
        f"· v{ecoturn.__version__}"
    )
    st.warning(
        "Prototype — all data is synthetic. Not real Delta operational data.",
        icon="⚠️",
    )

    tabs = st.tabs(TABS)
    for tab, name in zip(tabs, TABS):
        with tab:
            st.subheader(name)
            st.info("Placeholder — implemented in a later task.")


if __name__ == "__main__":
    main()
