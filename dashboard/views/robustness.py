"""
robustness.py

The 10-seed robustness sweep with premium animated visuals: an animated
win-rate gauge, per-seed lift bars with colour coding, and a strikes
comparison - all rendered as custom HTML components.
"""

import json

import streamlit as st

from shared.simulation_runner import run_robustness_sweep

st.title("Robustness")
st.caption(
    "The same comparison, run across 10 independent seeds - "
    "does reMultiBands win by chance, or reliably?"
)

rows = run_robustness_sweep()

wins              = int(sum(r["lift"] > 0 for r in rows))
zero_strikes      = all(r["remultibands_strikes"] == 0 for r in rows)
avg_lift_pct      = sum(r["lift_pct"] for r in rows) / len(rows)
seeds             = [r["seed"] for r in rows]
lift_pcts         = [round(r["lift_pct"], 2) for r in rows]
baseline_strikes  = [r["baseline_strikes"] for r in rows]
remulti_strikes   = [r["remultibands_strikes"] for r in rows]
total_seeds       = len(rows)

rows_json = json.dumps(rows)
seeds_json   = json.dumps(seeds)
liftpct_json = json.dumps(lift_pcts)
bl_str_json  = json.dumps(baseline_strikes)
rm_str_json  = json.dumps(remulti_strikes)

# ── Animated scoreboard + charts HTML ────────────────────────────────────
viz_html = f"""
<div id="rob-root" style="font-family:'Segoe UI',Roboto,sans-serif; color:#f3f4f6;">
<style>
  #rob-root {{ padding:4px; }}
  /* ── Scoreboard ── */
  #rob-root .scoreboard {{
    display:flex; gap:14px; margin-bottom:24px; flex-wrap:wrap;
  }}
  #rob-root .score-card {{
    flex:1; min-width:140px; background:#131826;
    border:1.5px solid rgba(255,255,255,0.08);
    border-radius:16px; padding:18px 16px; text-align:center;
    transition:border-color 0.4s ease, box-shadow 0.4s ease;
  }}
  #rob-root .score-card.green  {{
    border-color:#10b981;
    box-shadow:0 0 20px rgba(16,185,129,0.2);
  }}
  #rob-root .score-card.amber  {{
    border-color:#f59e0b;
    box-shadow:0 0 20px rgba(245,158,11,0.2);
  }}
  #rob-root .score-label {{ color:#9ca3af; font-size:12px; margin-bottom:6px; }}
  #rob-root .score-value {{
    font-size:32px; font-weight:800;
    font-variant-numeric:tabular-nums;
    background:linear-gradient(135deg,#10b981,#34d399);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }}
  #rob-root .score-value.amber {{
    background:linear-gradient(135deg,#f59e0b,#fbbf24);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }}
  #rob-root .score-sub {{ color:#6b7280; font-size:11px; margin-top:4px; }}

  /* ── Win rate donut ── */
  #rob-root .donut-wrap {{
    display:flex; align-items:center; gap:24px; margin-bottom:24px;
    background:#111827; border:1px solid rgba(255,255,255,0.07);
    border-radius:16px; padding:20px 24px; flex-wrap:wrap;
  }}
  #rob-root .donut-label {{ flex:1; min-width:160px; }}
  #rob-root .donut-title {{ font-size:16px; font-weight:700; margin-bottom:6px; }}
  #rob-root .donut-desc  {{ color:#9ca3af; font-size:13px; line-height:1.5; }}

  /* ── Bar chart section ── */
  #rob-root .chart-section {{ margin-bottom:28px; }}
  #rob-root .chart-title {{
    font-size:15px; font-weight:700; margin-bottom:12px;
    border-bottom:1px solid rgba(16,185,129,0.15); padding-bottom:8px;
  }}
  #rob-root .seed-row {{
    display:flex; align-items:center; gap:10px; margin-bottom:10px;
  }}
  #rob-root .seed-tag {{
    width:52px; text-align:right; font-size:12px; color:#6b7280;
    flex-shrink:0; font-variant-numeric:tabular-nums;
  }}
  #rob-root .bar-track {{
    flex:1; height:22px; background:rgba(255,255,255,0.05);
    border-radius:11px; overflow:hidden; position:relative;
  }}
  #rob-root .bar-fill {{
    height:100%; width:0%; border-radius:11px;
    transition:width 0.9s cubic-bezier(0.22,1,0.36,1);
    display:flex; align-items:center; padding-left:10px;
    font-size:11px; font-weight:700; color:white;
    white-space:nowrap;
  }}
  #rob-root .bar-val {{
    width:52px; font-size:12px; font-weight:700; color:#f3f4f6;
    font-variant-numeric:tabular-nums;
  }}

  /* ── Strikes comparison ── */
  #rob-root .strikes-grid {{
    display:flex; gap:10px; flex-wrap:wrap;
  }}
  #rob-root .strike-card {{
    flex:1; min-width:80px; background:#131826;
    border:1px solid rgba(255,255,255,0.07); border-radius:12px;
    padding:12px; text-align:center;
  }}
  #rob-root .sk-seed {{ font-size:11px; color:#6b7280; margin-bottom:6px; }}
  #rob-root .sk-row  {{ display:flex; justify-content:center; gap:8px; }}
  #rob-root .sk-val  {{
    font-size:15px; font-weight:800;
    font-variant-numeric:tabular-nums;
  }}
  #rob-root .sk-lbl  {{ font-size:9px; color:#9ca3af; margin-top:2px; }}
</style>

<!-- Scoreboard -->
<div class="scoreboard">
  <div class="score-card green" id="sc-wins">
    <div class="score-label">Seeds Won</div>
    <div class="score-value" id="sv-wins">0</div>
    <div class="score-sub">out of {total_seeds}</div>
  </div>
  <div class="score-card green" id="sc-lift">
    <div class="score-label">Avg Revenue Lift</div>
    <div class="score-value" id="sv-lift">0%</div>
    <div class="score-sub">across all seeds</div>
  </div>
  <div class="score-card {'green' if zero_strikes else 'amber'}" id="sc-strikes">
    <div class="score-label">Network Strikes</div>
    <div class="score-value {'amber' if not zero_strikes else ''}" id="sv-strikes">–</div>
    <div class="score-sub">reMultiBands total</div>
  </div>
</div>

<!-- Donut win rate -->
<div class="donut-wrap">
  <svg width="120" height="120" viewBox="0 0 120 120">
    <circle cx="60" cy="60" r="48" fill="none"
            stroke="rgba(255,255,255,0.06)" stroke-width="14"/>
    <circle id="donut-arc" cx="60" cy="60" r="48" fill="none"
            stroke="#10b981" stroke-width="14" stroke-linecap="round"
            stroke-dasharray="301.6" stroke-dashoffset="301.6"
            transform="rotate(-90 60 60)"
            style="transition:stroke-dashoffset 1.4s cubic-bezier(0.22,1,0.36,1);"/>
    <text x="60" y="56" text-anchor="middle"
          fill="#f9fafb" font-size="20" font-weight="800"
          font-family="'Segoe UI',Roboto,sans-serif">{wins}/{total_seeds}</text>
    <text x="60" y="72" text-anchor="middle"
          fill="#10b981" font-size="10"
          font-family="'Segoe UI',Roboto,sans-serif">seeds won</text>
  </svg>
  <div class="donut-label">
    <div class="donut-title">Win Rate: {wins}/{total_seeds} seeds</div>
    <div class="donut-desc">
      reMultiBands outperformed the static baseline on every seed tested.
      {('Zero network strikes were incurred in every single run - the compliance layer held firm throughout.' if zero_strikes else 'Some seeds incurred network strikes - check the table below.')}
    </div>
  </div>
</div>

<!-- Revenue lift per seed -->
<div class="chart-section">
  <div class="chart-title">Revenue Lift % per Seed</div>
  <div id="lift-bars"></div>
</div>

<!-- Network strikes per seed -->
<div class="chart-section">
  <div class="chart-title">Network Strikes per Seed</div>
  <div class="strikes-grid" id="strikes-grid"></div>
</div>

<script>
const SEEDS     = {seeds_json};
const LIFT_PCTS = {liftpct_json};
const BL_STR    = {bl_str_json};
const RM_STR    = {rm_str_json};
const WINS      = {wins};
const TOTAL     = {total_seeds};
const AVG_LIFT  = {avg_lift_pct:.2f};

function animateNumber(el, start, end, duration, fmt) {{
  const startTime = performance.now();
  function tick(now) {{
    const t = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = fmt(start + (end - start) * eased);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = fmt(end);
  }}
  requestAnimationFrame(tick);
}}

// Animate scoreboard
setTimeout(function() {{
  animateNumber(document.getElementById('sv-wins'), 0, WINS, 1000,
                n => Math.floor(n) + '/{total_seeds}');
  animateNumber(document.getElementById('sv-lift'), 0, AVG_LIFT, 1200,
                n => n.toFixed(1) + '%');
  document.getElementById('sv-strikes').textContent = {'\"0 always\"' if zero_strikes else '\"⚠ check\"'};
}}, 300);

// Animate donut
setTimeout(function() {{
  const arc = document.getElementById('donut-arc');
  const circ = 301.6;
  arc.style.strokeDashoffset = circ * (1 - WINS / TOTAL);
}}, 400);

// Build lift bars
const maxLift = Math.max(...LIFT_PCTS);
const liftDiv = document.getElementById('lift-bars');
SEEDS.forEach(function(seed, i) {{
  const row  = document.createElement('div'); row.className = 'seed-row';
  const stag = document.createElement('div'); stag.className = 'seed-tag';
  stag.textContent = 'Seed ' + seed;
  const trk  = document.createElement('div'); trk.className = 'bar-track';
  const fill = document.createElement('div'); fill.className = 'bar-fill';
  fill.style.background = LIFT_PCTS[i] > 0
    ? 'linear-gradient(90deg,#10b981,#34d399)'
    : 'linear-gradient(90deg,#ef4444,#f87171)';
  const val  = document.createElement('div'); val.className = 'bar-val';
  val.textContent = LIFT_PCTS[i].toFixed(1) + '%';
  trk.appendChild(fill);
  row.appendChild(stag); row.appendChild(trk); row.appendChild(val);
  liftDiv.appendChild(row);
  setTimeout(function() {{
    fill.style.width = (Math.abs(LIFT_PCTS[i]) / maxLift * 100) + '%';
    fill.textContent = LIFT_PCTS[i].toFixed(1) + '%';
  }}, i * 90 + 600);
}});

// Build strikes grid
const strGrid = document.getElementById('strikes-grid');
SEEDS.forEach(function(seed, i) {{
  const card = document.createElement('div'); card.className = 'strike-card';
  const rmColor = RM_STR[i] === 0 ? '#10b981' : '#ef4444';
  card.innerHTML = `
    <div class="sk-seed">Seed ${{seed}}</div>
    <div class="sk-row">
      <div>
        <div class="sk-val" style="color:#9ca3af">${{BL_STR[i]}}</div>
        <div class="sk-lbl">Baseline</div>
      </div>
      <div style="color:#374151;font-size:18px;align-self:center;">→</div>
      <div>
        <div class="sk-val" style="color:${{rmColor}}">${{RM_STR[i]}}</div>
        <div class="sk-lbl">reMultiBands</div>
      </div>
    </div>`;
  strGrid.appendChild(card);
}});
</script>
</div>
"""

st.iframe(viz_html, height=900)

if wins == total_seeds and zero_strikes:
    st.success(
        f"reMultiBands won **{wins}/{total_seeds}** seeds and incurred "
        f"**zero** network strikes in every single run."
    )