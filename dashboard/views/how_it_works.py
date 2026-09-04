"""
how_it_works.py

Full methodology explainer rendered as a horizontal grid of click-to-expand
cards. Each card shows a title and teaser; clicking reveals the full content
in a detail panel below the row.
"""

import streamlit as st
from widgets.info_cards import render_info_cards

st.title("How It Works")
st.caption("Click any card to read more about each part of the system.")

cards = [
    {
        "title": "The Problem",
        "teaser": "Why fixed retry schedules waste attempts and risk merchant penalties",
        "body_html": """
        <p>Standard mandate retry systems retry failed payments on a <b>fixed schedule</b> - the same
        delay every time, regardless of <em>why</em> the payment failed or <em>which</em> bank or rail
        was involved.</p>
        <p>This wastes strictly-capped retry attempts (card networks and NPCI both enforce real limits)
        and risks merchant penalties, while doing nothing smarter than "try again in 24 hours."</p>
        <ul>
          <li>Every network enforces hard retry caps - exceed them and the merchant gets penalised.</li>
          <li>Different failure codes call for different strategies - a soft decline ≠ an NSF error.</li>
          <li>Banks behave differently on the same network - one-size-fits-all is leaving money on the table.</li>
        </ul>
        """,
    },
    {
        "title": "The Architecture",
        "teaser": "Three layers - the brain, the guardrail, and the proof",
        "body_html": """
        <p>reMultiBands is three layers, each with exactly one job:</p>
        <ul>
          <li><b>The bandit (the brain)</b> - learns which recovery action converts best, per bank and
          per failure type, using Thompson Sampling. It never sees compliance rules or money directly -
          it just tracks a belief per arm and updates it from real outcomes.</li>
          <li><b>The rule engine (the guardrail)</b> - wraps the bandit and enforces hard compliance
          limits the bandit is never allowed to violate. A network retry cap is a hard constraint,
          not something worth risking on a learned policy's occasional exploration.</li>
          <li><b>The audit log (the proof)</b> - records every single decision with a human-readable
          explanation: which arm was chosen, why, and whether it was the bandit's own choice or a
          forced compliance override.</li>
        </ul>
        <p>Four <b>arms</b> (recovery actions) are available for every failed transaction:
        retry in 2 hours, retry in 24 hours, retry in 72 hours, or escalate immediately to a
        WhatsApp payment link.</p>
        """,
    },
    {
        "title": "Why Segmented",
        "teaser": "One bandit per (bank, failure type) - network effects pooled separately",
        "body_html": """
        <p>reMultiBands isn't <em>one</em> bandit - it's many, one per (bank, failure type)
        combination, because different banks genuinely behave differently for the same failure.</p>
        <p>Payment network (UPI Autopay, RuPay, Visa, Mastercard) is learned as a
        <b>separate, independent</b> effect and combined additively at decision time, rather than
        being folded into an even finer segmentation.</p>
        <p>An earlier, more finely-segmented design was tried and performed <em>worse</em>: splitting
        the data further diluted the strong bank-specific signal every time a thin segment had to fall
        back on a pooled estimate. Learning bank effects and network effects independently, then
        combining them, avoids that dilution.</p>
        <p>This also exactly matches how the project's own synthetic ground truth was constructed -
        a base probability plus a network-specific modifier, with no interaction term.</p>
        """,
    },
    {
        "title": "Where Numbers Came From",
        "teaser": "Every limit, cap, and modifier - sourced, assumed, or heuristic",
        "body_html": """
        <table>
          <tr><th>Value</th><th>Number</th><th>Status</th></tr>
          <tr><td>UPI Autopay retry cap</td><td>3 retries (1 original + 3)</td>
              <td><b>Sourced</b> - NPCI August 2025 Autopay guidelines</td></tr>
          <tr><td>Visa retry cap</td><td>15 reattempts / 30 days (soft declines only)</td>
              <td><b>Sourced</b> - Visa Excessive Reattempts Rule</td></tr>
          <tr><td>Visa hard-decline cap</td><td>0 retries, any network</td>
              <td><b>Sourced</b> - Visa Category 1 "Never Retry" rule</td></tr>
          <tr><td>Mastercard retry cap</td><td>10 retries / 30 days</td>
              <td><b>Sourced</b> - Mastercard signals via Merchant Advice Codes</td></tr>
          <tr><td>RuPay retry cap</td><td>3 retries (mirrors UPI Autopay)</td>
              <td><b>Assumed</b> - no separately published RuPay-specific cap found</td></tr>
          <tr><td>UPI "deemed approved" reversal window</td><td>T+5 calendar days</td>
              <td><b>Sourced</b> - RBI Turn Around Time (TAT) framework</td></tr>
          <tr><td>Rate of provisional/reversed UPI outcomes</td><td>5% provisional, 30% of those reverse</td>
              <td><b>Assumed</b> - RBI publishes the time window, not the frequency</td></tr>
          <tr><td>Network-specific behavior modifiers</td><td>±0.01 to ±0.06 per arm</td>
              <td><b>Assumed</b> - illustrative, directional reasoning</td></tr>
          <tr><td>Bank/error-type informed priors</td><td>Beta distribution starting beliefs</td>
              <td><b>Heuristic</b> - deliberately weak, corrected quickly by real data</td></tr>
        </table>
        """,
    },
    {
        "title": "Academic Grounding",
        "teaser": "Two real production deployments validate this approach",
        "body_html": """
        <p>This general approach - non-stationary bandits for payment recovery, with hard compliance
        constraints layered on top - is validated by two real, published, <b>production</b>
        deployments:</p>
        <ul>
          <li><b>Chaudhary, A., Rai, A., &amp; Gupta, A. (2023).</b> <em>Maximizing Success Rate of
          Payment Routing using Non-stationary Bandits.</em>
          <a href="https://arxiv.org/abs/2308.01028" target="_blank">arXiv:2308.01028</a>.
          Deployed at <b>Dream11</b> (10,000+ transactions/second, PCI-DSS compliant).
          Live result: <b>+0.92% success rate improvement over one month</b> vs rule-based routing.</li>
          <li><b>Agrawal, A., &amp; Patil, H. (2025).</b> <em>A Control-Theoretic Approach to Dynamic
          Payment Routing for Success Rate Optimization.</em>
          <a href="https://arxiv.org/abs/2510.16735" target="_blank">arXiv:2510.16735</a>.
          Live production result: <b>up to +1.15% improvement</b> over rule-based routing.</li>
        </ul>
        <p><b>Honest note:</b> the simulated lift in this dashboard (typically 6–13%) is larger than
        either published production result. That's expected - the synthetic ground truth deliberately
        encodes bigger, more visible differences between arms so the mechanism is legible in a short
        demo. This demonstrates the <em>mechanism</em>, not a production benchmark claim.</p>
        """,
    },
    {
        "title": "What's Simplified",
        "teaser": "Three deliberate simplifications, clearly disclosed",
        "body_html": """
        <ul>
          <li><b>Additive independence of bank and network effects</b> - a real simplification.
          In production, this should be actively monitored: once a specific bank+network combination
          accumulates enough of its own data to show a persistent gap from what the additive model
          predicts, it can "graduate" to its own independently-tracked posterior.</li>
          <li><b>End-of-run reversal correction</b> - this simulator resolves each transaction to
          completion before moving to the next, rather than running a full day-by-day event timeline.
          So provisional UPI outcomes are corrected in a single pass at the end of the run rather than
          exactly 5 days after each individual transaction. The substance that matters - a delayed
          reward correction hitting both revenue and the bandit's learned belief - is fully real;
          only the exact scheduling mechanics are simplified.</li>
          <li><b>Synthetic data, not real bank/network statistics</b> - clearly disclosed throughout.
          Real per-bank, per-network retry-outcome data isn't publicly available; the point of the
          Bayesian bandit design is precisely that it doesn't need the starting numbers to be exactly
          right - it corrects itself against real observed outcomes over time.</li>
        </ul>
        """,
    },
    {
        "title": "Future Scope",
        "teaser": "What's been scoped but intentionally not built yet",
        "body_html": """
        <p>A live WhatsApp + Razorpay payment-link integration (real message sent, real test payment
        link, webhook confirming recovery) was scoped for this project but intentionally <b>not
        built</b> - the ML core, compliance layer, and audit trail were prioritised as the stronger,
        more defensible use of build time.</p>
        <p>This remains a natural, concrete next step: the <code>whatsapp_escalate</code> arm is
        already a first-class decision the system makes; wiring it to a real send is an integration
        task, not a design change.</p>
        <p>Other researched-but-not-built extensions:</p>
        <ul>
          <li>Background card-updater silent recovery (Visa Account Updater / Mastercard Automatic
          Billing Updater)</li>
          <li>Notification/dunning fatigue decay on repeated WhatsApp contacts</li>
          <li>Calendar-aware (payday-cycle) retry timing</li>
        </ul>
        """,
    },
]

render_info_cards(cards, height=950)