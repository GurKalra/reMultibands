"""
network_effects.py

Visualizes the additive log-odds decomposition with animated belief bars,
a knowledge-flow diagram, and a dramatic before/after comparison showing
cross-bank transfer of learned network effects.
"""

import random
import json

import streamlit as st
import streamlit.components.v1 as components

from shared.simulation_runner import BANKS, ERROR_CODES, PAYMENT_NETWORKS
from shared.theme import apply_custom_css, prettify
from engine.bandit import SegmentedThompsonBandit
from widgets.belief_animation import render_belief_bars

apply_custom_css()

st.title("Network Effects")
st.caption(
    "How much of a decision comes from THIS bank's own history, "
    "vs the payment network it's on - and how banks share knowledge."
)

# ── Explainer banner ─────────────────────────────────────────────────────
st.markdown(
    """
    reMultiBands learns **two things separately** and combines them additively:

    - **Bank belief** - how this specific bank behaves for this failure type, learned from that bank's own outcomes.
    - **Network belief** - how a payment network shifts outcomes in general, pooled across *every* bank on that rail.

    This means Bank B can benefit from Bank A's experience on the same network, **without ever sharing
    bank-specific data**. Run the demo below to see this live.
    """
)

# ── Knowledge Flow Diagram ────────────────────────────────────────────────
flow_html = """
<div id="flow-root" style="font-family:'Segoe UI',Roboto,sans-serif; padding:4px 0 10px;">
<style>
  #flow-root svg text { font-family: 'Segoe UI', Roboto, sans-serif; }
  @keyframes flowDash {
    from { stroke-dashoffset: 24; }
    to   { stroke-dashoffset: 0;  }
  }
  @keyframes nodePulse {
    0%,100% { opacity:1; }
    50%      { opacity:0.7; }
  }
</style>
<svg width="100%" height="170" viewBox="0 0 740 170" preserveAspectRatio="xMidYMid meet">
  <!-- Bank A node -->
  <rect x="10" y="30" width="180" height="90" rx="16"
        fill="#131826" stroke="#60a5fa" stroke-width="2.5"/>
  <text x="100" y="60" text-anchor="middle" fill="#60a5fa" font-size="15" font-weight="800">Bank A</text>
  <text x="100" y="80" text-anchor="middle" fill="#9ca3af" font-size="11">Direct observations</text>
  <text x="100" y="97" text-anchor="middle" fill="#9ca3af" font-size="11">on this rail</text>

  <!-- Network rail node (centre) -->
  <rect x="265" y="18" width="210" height="110" rx="18"
        fill="#0f1e18" stroke="#10b981" stroke-width="3"/>
  <text x="370" y="52" text-anchor="middle" fill="#10b981" font-size="16" font-weight="800">Network Rail</text>
  <text x="370" y="75" text-anchor="middle" fill="#d1d5db" font-size="12">Pooled belief across</text>
  <text x="370" y="94" text-anchor="middle" fill="#d1d5db" font-size="12">all banks on this rail</text>

  <!-- Bank B node -->
  <rect x="550" y="30" width="180" height="90" rx="16"
        fill="#131826" stroke="#a78bfa" stroke-width="2.5"/>
  <text x="640" y="60" text-anchor="middle" fill="#a78bfa" font-size="15" font-weight="800">Bank B</text>
  <text x="640" y="80" text-anchor="middle" fill="#9ca3af" font-size="11">Zero direct data -</text>
  <text x="640" y="97" text-anchor="middle" fill="#9ca3af" font-size="11">yet belief shifts!</text>

  <!-- Arrows A -> Rail -->
  <line x1="192" y1="75" x2="263" y2="75"
        stroke="#10b981" stroke-width="2.5" stroke-dasharray="6,3"
        style="animation:flowDash 1s linear infinite;"/>
  <polygon points="263,70 273,75 263,80" fill="#10b981"/>

  <!-- Arrows Rail -> B -->
  <line x1="477" y1="75" x2="548" y2="75"
        stroke="#a78bfa" stroke-width="2.5" stroke-dasharray="6,3"
        style="animation:flowDash 1s linear infinite;"/>
  <polygon points="548,70 558,75 548,80" fill="#a78bfa"/>

  <!-- Labels -->
  <text x="228" y="65" text-anchor="middle" fill="#10b981" font-size="11" font-weight="600">updates</text>
  <text x="512" y="65" text-anchor="middle" fill="#a78bfa" font-size="11" font-weight="600">transfers to</text>
</svg>
</div>
"""
components.html(flow_html, height=185, scrolling=False)

st.divider()

# ── Selectors ────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
bank       = col1.selectbox("Bank",            BANKS,            key="ne_bank")
error_code = col2.selectbox("Error code",      ERROR_CODES,      key="ne_error")
network    = col3.selectbox("Payment network", PAYMENT_NETWORKS, key="ne_network",
                            format_func=prettify)

if st.button("Run cross-bank transfer demo", type="primary"):
    bandit = SegmentedThompsonBandit()

    # Snapshot before
    before       = bandit.snapshot(bank, error_code, network)
    before_vals  = {arm: s["combined_probability"] for arm, s in before.items()}

    # Feed 60 successful whatsapp_escalate observations to bank
    for _ in range(60):
        bandit.update(bank, error_code, network, "whatsapp_escalate",
                      success=True, revenue_weight=1.0)

    other_banks = [b for b in BANKS if b != bank]
    other_bank  = other_banks[0] if other_banks else bank

    # Snapshots after
    after_a = bandit.snapshot(bank,       error_code, network)
    after_b = bandit.snapshot(other_bank, error_code, network)
    shift   = after_b["whatsapp_escalate"]["network_effect_shift"]

    # ── Before banner ───────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:#0c1520; border:1px solid rgba(255,255,255,0.08); "
        f"border-radius:12px; padding:14px 18px; margin-bottom:14px;'>"
        f"<span style='color:#9ca3af; font-size:12px;'>BEFORE any observations</span><br>"
        f"<span style='color:#f3f4f6; font-weight:700;'>Segment: "
        f"{bank} · {error_code} · {prettify(network)}</span></div>",
        unsafe_allow_html=True,
    )
    render_belief_bars(before_vals, title="Initial belief per arm (prior only)", height=200)

    st.divider()

    # ── Training banner ─────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:#0f1e18; border:1px solid rgba(16,185,129,0.3); "
        f"border-radius:12px; padding:14px 18px; margin-bottom:14px; text-align:center;'>"
        f"<span style='color:#10b981; font-size:13px; font-weight:700;'>"
        f"Fed 60 successful <em>WhatsApp Escalate</em> observations to "
        f"<strong>{bank}</strong> on <strong>{prettify(network)}</strong></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── After: side-by-side ─────────────────────────────────────────────
    st.markdown("**After training - direct data vs zero data:**")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"<div style='background:#131826; border:1px solid #10b981; border-radius:10px; "
            f"padding:10px 14px; margin-bottom:10px;'>"
            f"<span style='color:#10b981; font-size:11px; font-weight:700;'>DIRECT DATA</span><br>"
            f"<span style='color:#f3f4f6; font-size:13px; font-weight:700;'>"
            f"{bank} · {error_code} · {prettify(network)}</span></div>",
            unsafe_allow_html=True,
        )
        render_belief_bars(
            {arm: s["combined_probability"] for arm, s in after_a.items()},
            height=220,
        )
    with c2:
        st.markdown(
            f"<div style='background:#131826; border:1px solid #a78bfa; border-radius:10px; "
            f"padding:10px 14px; margin-bottom:10px;'>"
            f"<span style='color:#a78bfa; font-size:11px; font-weight:700;'>ZERO DIRECT DATA</span><br>"
            f"<span style='color:#f3f4f6; font-size:13px; font-weight:700;'>"
            f"{other_bank} · {error_code} · {prettify(network)}</span></div>",
            unsafe_allow_html=True,
        )
        render_belief_bars(
            {arm: s["combined_probability"] for arm, s in after_b.items()},
            highlight_arm="whatsapp_escalate",
            height=220,
        )

    # ── Insight callout ─────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:#0c1520; border:1.5px solid rgba(16,185,129,0.4); "
        f"border-radius:14px; padding:16px 20px; margin-top:10px;'>"
        f"<span style='color:#10b981; font-size:22px; font-weight:800;'>{shift:+.1%}</span> "
        f"<span style='color:#d1d5db; font-size:14px;'> shift in <em>WhatsApp Escalate</em> belief "
        f"for <strong>{other_bank}</strong> - despite receiving <strong>zero</strong> direct observations. "
        f"The network rail transferred knowledge automatically.</span></div>",
        unsafe_allow_html=True,
    )

else:
    st.info("Choose a bank, error code, and payment network above, then run the demo.")