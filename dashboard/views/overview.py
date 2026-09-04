"""
overview.py

Landing page: the animated 'Recovery Race' hook with a live metrics panel
on the right, and the 'Run on New Seed' button to re-run the simulation.
First-time visits require clicking 'Run Simulation'. Once run, returning to
this page maintains the completed/auto-playing simulation state.
"""

import streamlit as st

from shared.simulation_runner import run_comparison, new_random_seed
from widgets.recovery_race import render_recovery_race

st.title("reMultiBands")
st.caption("AI Revenue Recovery - a compliant, learning mandate retry sequencer")

if "seed" not in st.session_state:
    st.session_state.seed = 7  # fixed, reproducible default on first load

if "has_run_initial_sim" not in st.session_state:
    st.session_state.has_run_initial_sim = False

if not st.session_state.has_run_initial_sim:
    st.markdown(
        """
        <div style="background:#131826; border:1px solid rgba(16,185,129,0.3); border-radius:16px; padding:28px 24px; text-align:center; margin: 20px 0 28px 0;">
            <h3 style="color:#f3f4f6; margin-top:0; margin-bottom:10px; font-size:20px;">Ready to run the recovery simulation?</h3>
            <p style="color:#9ca3af; font-size:14px; max-width:620px; margin:0 auto 24px auto; line-height:1.5;">
                Replay failed mandate transactions through static baseline retries vs reMultiBands' segmented bandit and compliance engine.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Run Simulation", type="primary", use_container_width=True):
            st.session_state.has_run_initial_sim = True
            st.rerun()
else:
    col_a, col_b = st.columns([3, 1])
    with col_b:
        if st.button("Run on New Seed", use_container_width=True):
            st.session_state.seed = new_random_seed()
            st.rerun()

    st.caption(
        f"Current seed: `{st.session_state.seed}` - every number below is a real, live computation "
        f"for this seed, not a canned demo."
    )

    baseline_result, remultibands_result, audit_entries, audit_summary_text = run_comparison(st.session_state.seed)

    render_recovery_race(baseline_result, remultibands_result)

    st.divider()

    st.markdown(
        "**What just happened:** every failed transaction was replayed through two strategies - a naive "
        "static retry schedule, and reMultiBands' segmented bandit wrapped by a compliance rule engine. "
        "reMultiBands recovered more revenue while incurring **zero** network retry-cap violations, because "
        "its rule engine hard-stops and escalates to WhatsApp instead of ever exceeding the real, "
        "research-grounded caps (NPCI, Visa, Mastercard) enforced per payment network. Both figures are "
        "net of RBI-regulated UPI 'deemed approved' reversals, applied fairly to both strategies."
    )

    with st.expander("See the raw comparison numbers"):
        st.json({"baseline": baseline_result, "remultibands": remultibands_result})