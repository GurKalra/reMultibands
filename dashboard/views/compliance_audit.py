"""
compliance_audit.py

Filterable audit trail table + compliance decision-source breakdown.
Filters are live (no submit button) - selections persist across reruns
via Streamlit's session_state key mechanism. All display labels use
prettify() so no underscores appear in the UI.
"""

import streamlit as st
import pandas as pd

from shared.simulation_runner import run_comparison
from shared.theme import apply_custom_css, prettify

apply_custom_css()

st.title("Compliance & Audit Trail")
st.caption("Every recovery decision, with a plain-language explanation of why it was made.")

if "seed" not in st.session_state:
    st.session_state.seed = 7

baseline_result, remultibands_result, audit_entries, audit_summary_text = run_comparison(st.session_state.seed)
df = pd.DataFrame(audit_entries)

bandit_count   = int((df["decision_source"] == "bandit").sum())
override_count = int((df["decision_source"] == "rule_engine_override").sum())
total          = len(df)

st.markdown(
    f"""
    <div style="display:flex; gap:14px; margin-bottom:18px;">
      <div style="flex:1; background:#131826; border:1px solid rgba(255,255,255,0.08); border-radius:14px; padding:16px;">
        <div style="color:#9ca3af; font-size:12px;">Total decisions logged</div>
        <div style="color:#f3f4f6; font-size:26px; font-weight:800;">{total:,}</div>
      </div>
      <div style="flex:1; background:#131826; border:1px solid rgba(16,185,129,0.3); border-radius:14px; padding:16px;">
        <div style="color:#9ca3af; font-size:12px;">Bandit-chosen</div>
        <div style="color:#10b981; font-size:26px; font-weight:800;">{bandit_count:,} ({bandit_count/total*100:.1f}%)</div>
      </div>
      <div style="flex:1; background:#131826; border:1px solid rgba(245,158,11,0.3); border-radius:14px; padding:16px;">
        <div style="color:#9ca3af; font-size:12px;">Rule-engine overrides</div>
        <div style="color:#f59e0b; font-size:26px; font-weight:800;">{override_count:,} ({override_count/total*100:.1f}%)</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Live filters (no form/submit required) ─────────────────────────────────
col1, col2 = st.columns(2)

network_options = sorted(df["payment_network"].unique())
source_options  = sorted(df["decision_source"].unique())

network_filter = col1.multiselect(
    "Filter by payment network",
    options=network_options,
    format_func=prettify,
    key="audit_network_filter",
)
source_filter = col2.multiselect(
    "Filter by decision source",
    options=source_options,
    format_func=prettify,
    key="audit_source_filter",
)

# Apply filters
filtered = df.copy()
if network_filter:
    filtered = filtered[filtered["payment_network"].isin(network_filter)]
if source_filter:
    filtered = filtered[filtered["decision_source"].isin(source_filter)]

st.markdown(f"**Showing {len(filtered):,} of {len(df):,} logged decisions**")

# Build display DataFrame with prettified labels and reset index to 1-based
display_cols = ["transaction_id", "bank", "error_code", "payment_network",
                "arm_chosen", "decision_source", "outcome_success", "explanation"]
display_df = filtered[display_cols].copy()
display_df["payment_network"] = display_df["payment_network"].map(prettify)
display_df["arm_chosen"]      = display_df["arm_chosen"].map(prettify)
display_df["decision_source"] = display_df["decision_source"].map(prettify)
display_df = display_df.reset_index(drop=True)
display_df.index = display_df.index + 1  # 1-based row numbering

st.dataframe(display_df, use_container_width=True, height=460)

st.divider()
st.markdown("### A few representative decisions")

override_examples  = df[df["decision_source"] == "rule_engine_override"].head(2)
soft_zone_examples = df[df["excluded_arms"].apply(lambda x: len(x) > 0)].head(2)
bandit_examples    = df[df["decision_source"] == "bandit"].head(2)
examples = pd.concat([override_examples, soft_zone_examples, bandit_examples])

cards_html = ""
for _, row in examples.iterrows():
    border_color = "#f59e0b" if row["decision_source"] == "rule_engine_override" else "#10b981"
    cards_html += f"""
    <div style="background:#131826; border-left:3px solid {border_color}; border-radius:8px;
                padding:12px 16px; margin-bottom:10px;">
      <span style="color:#d1d5db; font-size:13.5px;">{row['explanation']}</span>
    </div>
    """
st.markdown(cards_html, unsafe_allow_html=True)