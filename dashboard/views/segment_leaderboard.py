"""
segment_leaderboard.py

The whole trained model at once: a heatmap of banks x error types, colored
by which arm the bandit currently prefers and how confident it is.
A network selector lets you slice across the four payment rails.
"""

import json

import streamlit as st

from shared.simulation_runner import get_bandit_snapshots, BANKS, ERROR_CODES, PAYMENT_NETWORKS
from shared.theme import apply_custom_css, prettify

apply_custom_css()

st.title("Segment Leaderboard")
st.caption(
    "Every bank x failure type at once - colored by which recovery arm the bandit "
    "has learned to prefer, and how confident it is. Click any cell for a full breakdown."
)

if "seed" not in st.session_state:
    st.session_state.seed = 7

# ── Network selector ─────────────────────────────────────────────────────
network = st.selectbox(
    "Payment network",
    PAYMENT_NETWORKS,
    format_func=prettify,
    key="sb_network",
)

# ── Load trained snapshots ────────────────────────────────────────────────
snapshots = get_bandit_snapshots(st.session_state.seed)

# ── Build per-cell data for the selected network ──────────────────────────
ARM_COLORS = {
    "retry_2h":          "#60a5fa",
    "retry_24h":         "#f59e0b",
    "retry_72h":         "#a78bfa",
    "whatsapp_escalate": "#10b981",
}
ARM_LABEL = {
    "retry_2h":          "Retry 2h",
    "retry_24h":         "Retry 24h",
    "retry_72h":         "Retry 72h",
    "whatsapp_escalate": "WhatsApp",
}

cells      = {}
arm_wins   = {a: 0 for a in ARM_COLORS}
margins    = []

for bank in BANKS:
    for error_code in ERROR_CODES:
        key     = f"{bank}|{error_code}|{network}"
        segment = snapshots[key]                      # {arm: prob}
        sorted_arms = sorted(segment, key=lambda a: segment[a], reverse=True)
        best_arm    = sorted_arms[0]
        best_prob   = segment[best_arm]
        second_prob = segment[sorted_arms[1]] if len(sorted_arms) > 1 else 0.0
        margin      = best_prob - second_prob

        arm_wins[best_arm] += 1
        margins.append(margin)
        cells[f"{bank}|{error_code}"] = {
            "bank":       bank,
            "error":      error_code,
            "best_arm":   best_arm,
            "best_prob":  best_prob,
            "margin":     round(margin, 4),
            "color":      ARM_COLORS[best_arm],
            "label":      ARM_LABEL[best_arm],
            "beliefs":    {a: round(segment[a] * 100, 1) for a in segment},
        }

avg_confidence = sum(c["best_prob"] for c in cells.values()) / len(cells)
avg_margin     = sum(margins) / len(margins)
dominant_arm   = max(arm_wins, key=lambda a: arm_wins[a])
total_cells    = len(cells)

# ── Serialise for JS ──────────────────────────────────────────────────────
banks_json      = json.dumps(BANKS)
errors_json     = json.dumps(ERROR_CODES)
cells_json      = json.dumps(cells)
arm_wins_json   = json.dumps(arm_wins)
arm_colors_json = json.dumps(ARM_COLORS)
arm_label_json  = json.dumps(ARM_LABEL)
arm_pretty_json = json.dumps({a: prettify(a) for a in ARM_COLORS})
network_label   = prettify(network)

# ── Heatmap + summary component ───────────────────────────────────────────
html = f"""
<div id="lb-root" style="font-family:'Segoe UI',Roboto,sans-serif; color:#f3f4f6;">
<style>
  * {{ box-sizing:border-box; }}
  #lb-root {{ padding:4px; }}

  /* ---- Legend ---- */
  #lb-root .legend {{
    display:flex; flex-wrap:wrap; gap:10px; margin-bottom:18px;
  }}
  #lb-root .leg-pill {{
    display:flex; align-items:center; gap:7px; padding:5px 12px;
    border-radius:999px; background:rgba(255,255,255,0.04);
    border:1px solid rgba(255,255,255,0.1); font-size:12px; color:#e5e7eb;
    cursor:pointer; transition:border-color 0.15s;
  }}
  #lb-root .leg-pill:hover {{ border-color:rgba(255,255,255,0.3); }}
  #lb-root .leg-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}

  /* ---- Heatmap grid ---- */
  #lb-root .heatmap-wrap {{ overflow-x:auto; }}
  #lb-root .heatmap {{
    display:grid;
    gap:5px;
    min-width:max-content;
  }}
  #lb-root .hm-corner {{ }}
  #lb-root .hm-col-header {{
    padding:6px 8px; text-align:center; font-size:11px; font-weight:700;
    color:#9ca3af; white-space:nowrap;
  }}
  #lb-root .hm-row-header {{
    padding:6px 12px 6px 2px; display:flex; align-items:center;
    font-size:12px; font-weight:700; color:#d1d5db; white-space:nowrap;
  }}
  #lb-root .hm-cell {{
    border-radius:10px; padding:10px 8px; cursor:pointer;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    min-width:110px; min-height:72px; position:relative;
    transition:transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
    border:1.5px solid transparent;
  }}
  #lb-root .hm-cell:hover {{
    transform:scale(1.06) translateY(-2px);
    box-shadow:0 8px 28px rgba(0,0,0,0.5);
    filter:brightness(1.15);
    border-color:rgba(255,255,255,0.35);
    z-index:10;
  }}
  #lb-root .hm-cell.selected {{
    border-color:white !important;
    box-shadow:0 0 0 2px white, 0 8px 28px rgba(0,0,0,0.5) !important;
    z-index:20;
  }}
  #lb-root .cell-arm {{
    font-size:11px; font-weight:800; color:rgba(255,255,255,0.95);
    text-align:center; line-height:1.2; margin-bottom:4px;
  }}
  #lb-root .cell-prob {{
    font-size:18px; font-weight:900; color:white;
    font-variant-numeric:tabular-nums; line-height:1;
  }}
  #lb-root .cell-margin {{
    font-size:9px; color:rgba(255,255,255,0.6); margin-top:3px;
  }}
  /* Pulse animation for very confident cells (margin > 0.25) */
  @keyframes confPulse {{
    0%,100% {{ opacity:1; }}
    50%      {{ opacity:0.75; }}
  }}
  #lb-root .hm-cell.high-conf::after {{
    content:''; position:absolute; top:5px; right:6px;
    width:7px; height:7px; border-radius:50%; background:rgba(255,255,255,0.8);
    animation:confPulse 2s ease-in-out infinite;
  }}

  /* ---- Tooltip ---- */
  #lb-tooltip {{
    position:fixed; z-index:9999; pointer-events:none;
    background:#0c1520; border:1.5px solid rgba(255,255,255,0.15);
    border-radius:14px; padding:14px 16px; min-width:220px;
    box-shadow:0 20px 60px rgba(0,0,0,0.8);
    transition:opacity 0.12s ease;
    display:none;
  }}
  #lb-tooltip .tt-header {{
    font-size:11px; font-weight:700; color:#9ca3af;
    margin-bottom:10px; padding-bottom:7px;
    border-bottom:1px solid rgba(255,255,255,0.08);
  }}
  #lb-tooltip .tt-bar-row {{
    display:flex; align-items:center; gap:8px; margin-bottom:8px;
  }}
  #lb-tooltip .tt-label {{ width:90px; font-size:11px; color:#d1d5db; flex-shrink:0; }}
  #lb-tooltip .tt-track {{
    flex:1; height:12px; background:rgba(255,255,255,0.06); border-radius:6px; overflow:hidden;
  }}
  #lb-tooltip .tt-fill {{ height:100%; border-radius:6px; }}
  #lb-tooltip .tt-pct {{
    width:38px; text-align:right; font-size:11px; font-weight:700;
    color:#f3f4f6; font-variant-numeric:tabular-nums;
  }}
  #lb-tooltip .tt-winner {{ color:#f3f4f6; font-weight:700; }}

  /* ---- Detail panel ---- */
  #lb-root .detail-panel {{
    background:#0c1520; border:1.5px solid rgba(16,185,129,0.3);
    border-radius:16px; padding:18px 22px; margin-top:16px;
    animation:fadeUp 0.25s cubic-bezier(0.22,1,0.36,1);
  }}
  @keyframes fadeUp {{
    from {{ opacity:0; transform:translateY(8px); }}
    to   {{ opacity:1; transform:translateY(0); }}
  }}
  #lb-root .detail-header {{
    font-size:15px; font-weight:800; color:#f3f4f6; margin-bottom:14px;
    padding-bottom:10px; border-bottom:1px solid rgba(16,185,129,0.2);
    display:flex; justify-content:space-between; align-items:center;
  }}
  #lb-root .detail-close {{
    background:rgba(255,255,255,0.08); border:none; color:#9ca3af;
    font-size:16px; width:28px; height:28px; border-radius:7px; cursor:pointer;
    transition:background 0.15s; line-height:1;
  }}
  #lb-root .detail-close:hover {{ background:rgba(255,255,255,0.16); color:#f3f4f6; }}
  #lb-root .detail-bar-row {{
    display:flex; align-items:center; gap:10px; margin-bottom:10px;
  }}
  #lb-root .detail-label {{ width:130px; font-size:12px; color:#d1d5db; flex-shrink:0; }}
  #lb-root .detail-track {{
    flex:1; height:16px; background:rgba(255,255,255,0.06); border-radius:8px; overflow:hidden;
  }}
  #lb-root .detail-fill {{
    height:100%; border-radius:8px;
    transition:width 0.8s cubic-bezier(0.22,1,0.36,1);
  }}
  #lb-root .detail-pct {{
    width:46px; text-align:right; font-size:12px; font-weight:700;
    color:#f3f4f6; font-variant-numeric:tabular-nums;
  }}

  /* ---- Summary row ---- */
  #lb-root .summary-row {{
    display:flex; gap:12px; margin-top:16px; flex-wrap:wrap;
  }}
  #lb-root .sum-card {{
    flex:1; min-width:130px; background:#111827;
    border:1px solid rgba(255,255,255,0.08);
    border-radius:14px; padding:13px 14px; text-align:center;
  }}
  #lb-root .sum-label {{ color:#9ca3af; font-size:11px; margin-bottom:4px; }}
  #lb-root .sum-value {{ font-size:20px; font-weight:800; font-variant-numeric:tabular-nums; }}
  #lb-root .sum-sub   {{ color:#6b7280; font-size:10px; margin-top:3px; }}

  /* ---- Arm win bars ---- */
  #lb-root .win-section {{ margin-top:20px; }}
  #lb-root .win-title {{
    font-size:13px; font-weight:700; color:#f3f4f6;
    margin-bottom:10px; padding-bottom:7px;
    border-bottom:1px solid rgba(255,255,255,0.07);
  }}
  #lb-root .win-row {{
    display:flex; align-items:center; gap:10px; margin-bottom:9px;
  }}
  #lb-root .win-label {{ width:130px; font-size:11px; color:#d1d5db; flex-shrink:0; }}
  #lb-root .win-track {{
    flex:1; height:16px; background:rgba(255,255,255,0.05); border-radius:8px; overflow:hidden;
  }}
  #lb-root .win-fill {{
    height:100%; border-radius:8px;
    transition:width 0.9s cubic-bezier(0.22,1,0.36,1);
  }}
  #lb-root .win-cnt {{
    width:42px; text-align:right; font-size:11px; font-weight:700;
    color:#f3f4f6; font-variant-numeric:tabular-nums;
  }}
</style>

<!-- Tooltip -->
<div id="lb-tooltip"></div>

<!-- Legend -->
<div class="legend" id="legend-row"></div>

<!-- Heatmap -->
<div class="heatmap-wrap">
  <div class="heatmap" id="heatmap"></div>
</div>

<!-- Detail panel (hidden until cell clicked) -->
<div class="detail-panel" id="detail-panel" style="display:none;">
  <div class="detail-header">
    <span id="detail-title"></span>
    <button class="detail-close" onclick="closeDetail()">&#10005;</button>
  </div>
  <div id="detail-bars"></div>
</div>

<!-- Summary row -->
<div class="summary-row">
  <div class="sum-card">
    <div class="sum-label">Avg confidence</div>
    <div class="sum-value" id="sv-conf" style="color:#10b981;">0%</div>
    <div class="sum-sub">across all segments</div>
  </div>
  <div class="sum-card">
    <div class="sum-label">Avg margin over #2</div>
    <div class="sum-value" id="sv-margin" style="color:#f59e0b;">0pp</div>
    <div class="sum-sub">higher = more decisive</div>
  </div>
  <div class="sum-card">
    <div class="sum-label">Dominant arm</div>
    <div class="sum-value" id="sv-dom" style="font-size:14px;">{ARM_LABEL[dominant_arm]}</div>
    <div class="sum-sub">{arm_wins[dominant_arm]}/{total_cells} segments</div>
  </div>
</div>

<!-- Arm win chart -->
<div class="win-section">
  <div class="win-title">Arm wins across all segments (this network)</div>
  <div id="win-bars"></div>
</div>

<script>
const BANKS       = {banks_json};
const ERRORS      = {errors_json};
const CELLS       = {cells_json};
const ARM_COLORS  = {arm_colors_json};
const ARM_LABEL   = {arm_label_json};
const ARM_PRETTY  = {arm_pretty_json};
const ARM_WINS    = {arm_wins_json};
const AVG_CONF    = {avg_confidence:.4f};
const AVG_MARGIN  = {avg_margin:.4f};
const TOTAL_CELLS = {total_cells};
const NETWORK_LBL = "{network_label}";

const ARMS = Object.keys(ARM_COLORS);
const tooltip = document.getElementById('lb-tooltip');
let selectedCell = null;

// ── Legend ────────────────────────────────────────────────────────────────
const legRow = document.getElementById('legend-row');
ARMS.forEach(arm => {{
  const pill = document.createElement('div'); pill.className = 'leg-pill';
  pill.innerHTML = `<div class="leg-dot" style="background:${{ARM_COLORS[arm]}}"></div>${{ARM_PRETTY[arm]}}`;
  legRow.appendChild(pill);
}});

// ── Build heatmap grid ────────────────────────────────────────────────────
const hm = document.getElementById('heatmap');
const nCols = ERRORS.length;
hm.style.gridTemplateColumns = '120px repeat(' + nCols + ', minmax(110px, 1fr))';

// Header row
const corner = document.createElement('div'); corner.className = 'hm-corner';
hm.appendChild(corner);
ERRORS.forEach(err => {{
  const h = document.createElement('div'); h.className = 'hm-col-header';
  h.textContent = err.replace(/_/g, ' ');
  hm.appendChild(h);
}});

// Data rows
BANKS.forEach(bank => {{
  const rowHdr = document.createElement('div'); rowHdr.className = 'hm-row-header';
  rowHdr.textContent = bank;
  hm.appendChild(rowHdr);

  ERRORS.forEach((err, ei) => {{
    const key  = bank + '|' + err;
    const data = CELLS[key];
    const prob = data.best_prob;
    // Opacity: map prob to 0.22 - 0.85
    const alpha = 0.22 + prob * 0.63;
    const hexAlpha = Math.round(alpha * 255).toString(16).padStart(2,'0');
    const bg = data.color + hexAlpha;

    const cell = document.createElement('div');
    cell.className = 'hm-cell' + (data.margin > 0.25 ? ' high-conf' : '');
    cell.style.background = bg;
    cell.style.setProperty('--arm-color', data.color);
    cell.dataset.key = key;
    cell.innerHTML = `
      <div class="cell-arm">${{data.label}}</div>
      <div class="cell-prob">${{(prob * 100).toFixed(0)}}%</div>
      <div class="cell-margin">+${{(data.margin * 100).toFixed(0)}}pp lead</div>`;

    // Staggered fade-in
    const idx = BANKS.indexOf(bank) * ERRORS.length + ei;
    cell.style.opacity = '0';
    cell.style.transform = 'scale(0.88)';
    cell.style.transition = 'opacity 0.35s ease, transform 0.35s ease, border-color 0.18s, box-shadow 0.18s, filter 0.18s';
    setTimeout(() => {{
      cell.style.opacity = '1';
      cell.style.transform = 'scale(1)';
    }}, idx * 45 + 200);

    // Hover tooltip
    cell.addEventListener('mousemove', e => showTooltip(e, data));
    cell.addEventListener('mouseleave', () => {{
      tooltip.style.display = 'none';
    }});

    // Click - detail panel
    cell.addEventListener('click', () => openDetail(cell, data));

    hm.appendChild(cell);
  }});
}});

// ── Tooltip ───────────────────────────────────────────────────────────────
function showTooltip(e, data) {{
  const bw = data.beliefs;
  const maxB = Math.max(...Object.values(bw));
  let rows = '';
  ARMS.forEach(arm => {{
    const pct = bw[arm] || 0;
    const isWinner = pct === maxB;
    rows += `
      <div class="tt-bar-row">
        <div class="tt-label ${{isWinner ? 'tt-winner' : ''}}">${{ARM_PRETTY[arm]}}</div>
        <div class="tt-track">
          <div class="tt-fill" style="width:${{pct}}%; background:${{ARM_COLORS[arm]}}"></div>
        </div>
        <div class="tt-pct ${{isWinner ? 'tt-winner' : ''}}">${{pct.toFixed(1)}}%</div>
      </div>`;
  }});

  tooltip.innerHTML = `
    <div class="tt-header">${{data.bank}} · ${{data.error.replace(/_/g,' ')}} · ${{NETWORK_LBL}}</div>
    ${{rows}}`;
  tooltip.style.display = 'block';

  const margin = 12;
  let x = e.clientX + margin;
  let y = e.clientY + margin;
  if (x + 240 > window.innerWidth)  x = e.clientX - 240 - margin;
  if (y + 180 > window.innerHeight) y = e.clientY - 180 - margin;
  tooltip.style.left = x + 'px';
  tooltip.style.top  = y + 'px';
}}

// ── Detail panel ──────────────────────────────────────────────────────────
function openDetail(cellEl, data) {{
  // Deselect previous
  if (selectedCell) selectedCell.classList.remove('selected');
  if (selectedCell === cellEl) {{
    selectedCell = null;
    document.getElementById('detail-panel').style.display = 'none';
    return;
  }}
  selectedCell = cellEl;
  cellEl.classList.add('selected');

  const panel   = document.getElementById('detail-panel');
  const titleEl = document.getElementById('detail-title');
  const barsEl  = document.getElementById('detail-bars');

  titleEl.textContent = data.bank + ' · ' + data.error.replace(/_/g,' ') + ' · ' + NETWORK_LBL;

  // Animate bars
  barsEl.innerHTML = '';
  const bw = data.beliefs;
  const maxB = Math.max(...Object.values(bw));
  ARMS.forEach((arm, i) => {{
    const pct = bw[arm] || 0;
    const row  = document.createElement('div'); row.className = 'detail-bar-row';
    const lbl  = document.createElement('div'); lbl.className = 'detail-label';
    lbl.textContent = ARM_PRETTY[arm] + (pct === maxB ? ' - Winner' : '');
    lbl.style.fontWeight = pct === maxB ? '700' : '400';
    lbl.style.color      = pct === maxB ? ARM_COLORS[arm] : '#d1d5db';
    const trk  = document.createElement('div'); trk.className = 'detail-track';
    const fill = document.createElement('div'); fill.className = 'detail-fill';
    fill.style.background = ARM_COLORS[arm];
    fill.style.width = '0%';
    const pctEl = document.createElement('div'); pctEl.className = 'detail-pct';
    pctEl.textContent = pct.toFixed(1) + '%';
    trk.appendChild(fill);
    row.appendChild(lbl); row.appendChild(trk); row.appendChild(pctEl);
    barsEl.appendChild(row);
    setTimeout(() => {{ fill.style.width = pct + '%'; }}, i * 120 + 50);
  }});

  panel.style.display = 'none';
  void panel.offsetWidth;
  panel.style.display = 'block';
  panel.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
}}

function closeDetail() {{
  if (selectedCell) selectedCell.classList.remove('selected');
  selectedCell = null;
  document.getElementById('detail-panel').style.display = 'none';
}}

// ── Summary counters ──────────────────────────────────────────────────────
function animNum(el, end, duration, fmt) {{
  const start = performance.now();
  (function tick(now) {{
    const t = Math.min(1, (now - start) / duration);
    const e2 = 1 - Math.pow(1 - t, 3);
    el.textContent = fmt(e2 * end);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = fmt(end);
  }})(performance.now());
}}
setTimeout(() => {{
  animNum(document.getElementById('sv-conf'),   AVG_CONF * 100,   900, n => n.toFixed(1) + '%');
  animNum(document.getElementById('sv-margin'), AVG_MARGIN * 100, 900, n => '+' + n.toFixed(1) + 'pp');
}}, 400);

// ── Arm win bars ──────────────────────────────────────────────────────────
const winDiv = document.getElementById('win-bars');
const maxWins = Math.max(...Object.values(ARM_WINS));
ARMS.forEach((arm, i) => {{
  const cnt  = ARM_WINS[arm] || 0;
  const row  = document.createElement('div'); row.className = 'win-row';
  const lbl  = document.createElement('div'); lbl.className = 'win-label'; lbl.textContent = ARM_PRETTY[arm];
  const trk  = document.createElement('div'); trk.className = 'win-track';
  const fill = document.createElement('div'); fill.className = 'win-fill'; fill.style.background = ARM_COLORS[arm];
  const cntEl = document.createElement('div'); cntEl.className = 'win-cnt'; cntEl.textContent = cnt + '/' + TOTAL_CELLS;
  trk.appendChild(fill);
  row.appendChild(lbl); row.appendChild(trk); row.appendChild(cntEl);
  winDiv.appendChild(row);
  setTimeout(() => {{ fill.style.width = (cnt / maxWins * 100) + '%'; }}, i * 120 + 500);
}});
</script>
</div>
"""

st.iframe(html, height=1050)
