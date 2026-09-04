"""
watch_it_learn.py

Pick a (bank, error_code, network) segment and watch the bandit's belief
about each recovery arm converge as synthetic observations are fed in.
Animated SVG line chart with play/pause controls, plus a 'What did it learn'
summary panel on the right showing key insights from the run.
"""

import json

import streamlit as st

from shared.simulation_runner import run_segment_walkthrough, BANKS, ERROR_CODES, PAYMENT_NETWORKS
from shared.theme import prettify

st.title("Watch It Learn")
st.caption("Pick a segment and watch the bandit's beliefs converge in real time - animated, step by step.")

col1, col2, col3 = st.columns(3)
bank       = col1.selectbox("Bank",            BANKS)
error_code = col2.selectbox("Error code",      ERROR_CODES)
network    = col3.selectbox("Payment network", PAYMENT_NETWORKS, format_func=prettify)

n_steps = st.slider("Number of synthetic observations", min_value=10, max_value=200, value=60, step=10)

if st.button("Simulate", type="primary"):
    st.session_state["watch_history"] = run_segment_walkthrough(bank, error_code, network, n_steps)
    st.session_state["watch_meta"]    = (bank, error_code, network)

if "watch_history" not in st.session_state:
    st.info("Choose a segment above and press Simulate to watch the bandit learn.")
else:
    history = st.session_state["watch_history"]
    b, e, n = st.session_state["watch_meta"]

    # ── Compute summary insights in Python ────────────────────────────────
    arms       = list(history[0]["beliefs"].keys())
    last       = history[-1]
    best_arm   = max(last["beliefs"], key=lambda a: last["beliefs"][a])
    best_prob  = last["beliefs"][best_arm]
    sorted_arms = sorted(last["beliefs"], key=lambda a: last["beliefs"][a], reverse=True)
    second_arm  = sorted_arms[1]
    second_prob = last["beliefs"][second_arm]
    gap_pp      = (best_prob - second_prob) * 100

    chosen_set  = set(h["arm_chosen"] for h in history)
    never_chosen = [a for a in arms if a not in chosen_set]

    # Step where best arm first exceeded 70%
    conv_step = None
    for h in history:
        if h["beliefs"][best_arm] >= 0.70:
            conv_step = h["step"]
            break

    # Count choices
    chosen_counts = {}
    for h in history:
        chosen_counts[h["arm_chosen"]] = chosen_counts.get(h["arm_chosen"], 0) + 1

    # Build the insight paragraph
    never_str = ", ".join(prettify(a) for a in never_chosen) if never_chosen else "none"
    conv_str  = f"by step {conv_step}" if conv_step else "not yet reached"

    insight = (
        f"The bandit settled on <strong>{prettify(best_arm)}</strong> as the dominant strategy "
        f"({best_prob:.1%} final belief), reaching 70% confidence {conv_str}. "
        f"It leads the runner-up <em>{prettify(second_arm)}</em> by {gap_pp:.1f} percentage points. "
    )
    if never_chosen:
        insight += (
            f"Arms that were never chosen ({never_str}) are not useless - "
            f"their beliefs reflect prior knowledge only, since Thompson Sampling "
            f"rarely explores arms it has already learned to be weak."
        )
    else:
        insight += "All arms were explored at least once during this run."

    # ── Prepare JS data ───────────────────────────────────────────────────
    arm_colors = {
        "retry_2h":          "#60a5fa",
        "retry_24h":         "#f59e0b",
        "retry_72h":         "#a78bfa",
        "whatsapp_escalate": "#10b981",
    }
    arm_pretty  = {a: prettify(a) for a in arms}
    colors_list = [arm_colors.get(a, "#9ca3af") for a in arms]
    steps_data  = [{"step": h["step"], "beliefs": h["beliefs"], "arm_chosen": h["arm_chosen"]} for h in history]
    counts_list = [chosen_counts.get(a, 0) for a in arms]
    max_count   = max(counts_list) if counts_list else 1

    steps_json  = json.dumps(steps_data)
    arms_json   = json.dumps(arms)
    colors_json = json.dumps(colors_list)
    pretty_json = json.dumps([arm_pretty[a] for a in arms])
    counts_json = json.dumps(counts_list)
    best_idx    = arms.index(best_arm)

    # Summary cards for the right panel
    summary_items = [
        {"label": "Best strategy",  "value": prettify(best_arm),       "color": arm_colors.get(best_arm, "#10b981")},
        {"label": "Final confidence","value": f"{best_prob:.1%}",       "color": "#f3f4f6"},
        {"label": "Confidence by",  "value": conv_str,                  "color": "#f3f4f6"},
        {"label": "Lead over #2",   "value": f"+{gap_pp:.1f}pp",        "color": "#10b981"},
        {"label": "Never explored", "value": never_str if never_chosen else "All arms chosen",
         "color": "#9ca3af"},
    ]
    summary_json = json.dumps(summary_items)

    animated_html = f"""
    <div id="wil-root" style="font-family:'Segoe UI',Roboto,sans-serif; color:#f3f4f6;">
    <style>
      #wil-root {{ padding: 4px; }}
      #wil-root .section-title {{
        font-size: 14px; font-weight: 700; margin: 0 0 10px 0; color: #f3f4f6;
        border-bottom: 1px solid rgba(16,185,129,0.2); padding-bottom: 7px;
      }}
      #wil-root .section {{ margin-bottom: 26px; }}

      /* ---- Controls ---- */
      #wil-root .controls {{
        display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
        flex-wrap: wrap;
      }}
      #wil-root .ctrl-btn {{
        background: #131826; border: 1.5px solid rgba(255,255,255,0.12);
        color: #f3f4f6; border-radius: 8px; padding: 5px 13px;
        font-size: 12px; font-weight: 600; cursor: pointer;
        transition: border-color 0.15s, background 0.15s;
      }}
      #wil-root .ctrl-btn:hover {{ border-color: #10b981; background: #0f1e18; }}
      #wil-root .ctrl-btn.active {{ border-color: #10b981; color: #10b981; }}
      #wil-root .step-label {{ color: #9ca3af; font-size: 12px; font-variant-numeric: tabular-nums; }}
      #wil-root .speed-label {{ color: #9ca3af; font-size: 11px; }}
      #wil-root input[type=range] {{ accent-color: #10b981; }}

      /* ---- Legend ---- */
      #wil-root .legend {{
        display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px;
      }}
      #wil-root .leg-item {{
        display: flex; align-items: center; gap: 5px;
        font-size: 11px; color: #d1d5db;
      }}
      #wil-root .leg-dot {{ width: 9px; height: 9px; border-radius: 50%; }}

      /* ---- Chart + summary row ---- */
      #wil-root .chart-row {{
        display: flex; gap: 16px; align-items: flex-start;
      }}
      #wil-root .chart-col {{ flex: 3; min-width: 0; }}
      #wil-root .summary-col {{
        flex: 2; min-width: 160px;
        display: flex; flex-direction: column; gap: 8px;
      }}

      /* ---- Summary panel ---- */
      #wil-root .summary-card {{
        background: #111827; border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px; padding: 11px 13px;
      }}
      #wil-root .summary-card.highlight {{
        border-color: rgba(16,185,129,0.4);
      }}
      #wil-root .s-label {{ color: #9ca3af; font-size: 10px; margin-bottom: 3px; }}
      #wil-root .s-value {{ font-size: 15px; font-weight: 800; }}
      #wil-root .insight-box {{
        background: #0c1520; border: 1px solid rgba(16,185,129,0.25);
        border-radius: 12px; padding: 13px 14px; font-size: 12px;
        color: #d1d5db; line-height: 1.6;
      }}
      #wil-root .insight-box strong {{ color: #f3f4f6; }}
      #wil-root .insight-box em {{ color: #e5e7eb; }}

      /* ---- Bar chart ---- */
      #wil-root .bar-row {{
        display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
      }}
      #wil-root .bar-lbl {{
        width: 150px; font-size: 11px; color: #d1d5db; flex-shrink: 0;
      }}
      #wil-root .bar-track {{
        flex: 1; height: 18px; background: rgba(255,255,255,0.05);
        border-radius: 9px; overflow: hidden;
      }}
      #wil-root .bar-fill {{
        height: 100%; width: 0%; border-radius: 9px;
        transition: width 0.9s cubic-bezier(0.22,1,0.36,1);
      }}
      #wil-root .bar-cnt {{
        width: 36px; font-size: 11px; font-weight: 700; color: #f3f4f6;
        text-align: right; font-variant-numeric: tabular-nums;
      }}
      #wil-root .zero-note {{
        font-size: 10px; color: #6b7280; margin-left: 4px; font-style: italic;
      }}

      /* ---- Final beliefs ---- */
      #wil-root .belief-grid {{
        display: flex; gap: 10px; flex-wrap: wrap;
      }}
      #wil-root .belief-card {{
        flex: 1 1 110px; background: #131826;
        border: 1.5px solid rgba(255,255,255,0.08);
        border-radius: 12px; padding: 10px 12px;
        transition: border-color 0.25s;
      }}
      #wil-root .belief-card.winner {{ border-color: #10b981; }}
      #wil-root .bc-label {{ font-size: 10px; color: #9ca3af; margin-bottom: 4px; }}
      #wil-root .bc-value {{
        font-size: 20px; font-weight: 800;
        font-variant-numeric: tabular-nums;
      }}
      #wil-root .bc-note {{
        font-size: 10px; color: #6b7280; margin-top: 3px;
      }}
    </style>

    <!-- Belief convergence chart -->
    <div class="section">
      <div class="section-title">Belief Convergence per Arm</div>
      <div class="legend" id="legend"></div>
      <div class="controls">
        <button class="ctrl-btn" id="btn-play" onclick="playPause()">Play</button>
        <button class="ctrl-btn" onclick="resetAnim()">Reset</button>
        <span class="step-label">Step: <span id="step-display">0</span> / {len(history)}</span>
        <span class="speed-label">Speed:</span>
        <input type="range" id="speed-slider" min="1" max="5" value="3"
               style="width:70px;" oninput="updateSpeed(this.value)">
      </div>

      <div class="chart-row">
        <div class="chart-col">
          <svg id="belief-svg" width="100%" height="240"
               viewBox="0 0 700 240" preserveAspectRatio="xMidYMid meet">
            <g id="grid-group"></g>
            <g id="axes-group"></g>
            <g id="lines-group"></g>
            <g id="cursor-group"></g>
          </svg>
        </div>

        <div class="summary-col" id="summary-col">
          <!-- Populated by JS -->
        </div>
      </div>
    </div>

    <!-- Arm choice bar chart -->
    <div class="section">
      <div class="section-title">How Often Each Arm Was Chosen</div>
      <div id="bar-chart"></div>
      <div style="font-size:11px; color:#6b7280; margin-top:6px; line-height:1.5;">
        Counts show how many times Thompson Sampling chose each arm.
        An arm showing 0 picks was outcompeted early - its belief still reflects
        prior knowledge (see Final Beliefs below), not a bug.
      </div>
    </div>

    <!-- Final beliefs -->
    <div class="section">
      <div class="section-title">Final Beliefs After {len(history)} Observations</div>
      <div class="belief-grid" id="belief-grid"></div>
    </div>

    <script>
    const STEPS   = {steps_json};
    const ARMS    = {arms_json};
    const COLORS  = {colors_json};
    const PRETTY  = {pretty_json};
    const COUNTS  = {counts_json};
    const SUMMARY = {summary_json};
    const BEST_IDX = {best_idx};
    const INSIGHT = {json.dumps(insight)};
    const N       = STEPS.length;
    const MAX_CNT = {max_count};

    const W = 700, H = 240;
    const PAD = {{ left:44, right:14, top:12, bottom:26 }};
    const CW = W - PAD.left - PAD.right;
    const CH = H - PAD.top  - PAD.bottom;

    function svgEl(tag, attrs) {{
      const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
      return el;
    }}
    function xPos(step) {{ return PAD.left + ((step - 1) / Math.max(N - 1, 1)) * CW; }}
    function yPos(p)    {{ return PAD.top  + (1 - p) * CH; }}

    // Legend
    const legend = document.getElementById('legend');
    ARMS.forEach((arm, i) => {{
      const item = document.createElement('div'); item.className = 'leg-item';
      item.innerHTML = `<div class="leg-dot" style="background:${{COLORS[i]}}"></div>${{PRETTY[i]}}`;
      legend.appendChild(item);
    }});

    // Grid + axes
    const gridG = document.getElementById('grid-group');
    const axesG = document.getElementById('axes-group');
    [0, 0.25, 0.5, 0.75, 1.0].forEach(p => {{
      const y = yPos(p);
      gridG.appendChild(svgEl('line', {{
        x1: PAD.left, y1: y, x2: W - PAD.right, y2: y,
        stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 1
      }}));
      const lbl = svgEl('text', {{ x: PAD.left - 5, y: y + 4,
        'text-anchor': 'end', fill: '#9ca3af', 'font-size': 9 }});
      lbl.textContent = (p * 100).toFixed(0) + '%';
      axesG.appendChild(lbl);
    }});
    const stepInterval = Math.ceil(N / 7);
    for (let s = 1; s <= N; s += stepInterval) {{
      const x = xPos(s);
      const lbl = svgEl('text', {{ x, y: H - 4, 'text-anchor': 'middle',
        fill: '#6b7280', 'font-size': 9 }});
      lbl.textContent = s;
      axesG.appendChild(lbl);
    }}

    // Path elements
    const linesG = document.getElementById('lines-group');
    const cursorG = document.getElementById('cursor-group');
    const paths = ARMS.map((arm, i) => {{
      const path = svgEl('path', {{
        stroke: COLORS[i], 'stroke-width': 2.2, fill: 'none',
        'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: ''
      }});
      linesG.appendChild(path);
      return path;
    }});
    const curLine = svgEl('line', {{
      x1: PAD.left, y1: PAD.top, x2: PAD.left, y2: H - PAD.bottom,
      stroke: 'rgba(255,255,255,0.2)', 'stroke-width': 1, 'stroke-dasharray': '3,3'
    }});
    cursorG.appendChild(curLine);

    // Animation state
    let currentStep = 0;
    let playing     = false;
    let timer       = null;
    let intervalMs  = 80;

    function updateSpeed(v) {{
      const speeds = [200, 130, 80, 45, 20];
      intervalMs = speeds[v - 1];
      if (playing) {{ clearInterval(timer); timer = setInterval(stepForward, intervalMs); }}
    }}
    function drawUpTo(step) {{
      ARMS.forEach((arm, i) => {{
        let d = '';
        for (let s = 0; s < step; s++) {{
          const prob = STEPS[s].beliefs[arm];
          const x = xPos(s + 1), y = yPos(prob);
          d += (s === 0 ? 'M' : 'L') + x + ' ' + y + ' ';
        }}
        paths[i].setAttribute('d', d);
      }});
      if (step > 0) {{
        const cx = xPos(step);
        curLine.setAttribute('x1', cx); curLine.setAttribute('x2', cx);
      }}
      document.getElementById('step-display').textContent = step;
    }}
    function stepForward() {{
      if (currentStep >= N) {{ clearInterval(timer); playing = false; updatePlayBtn(); return; }}
      currentStep++;
      drawUpTo(currentStep);
    }}
    function playPause() {{
      if (playing) {{
        clearInterval(timer); playing = false;
      }} else {{
        if (currentStep >= N) currentStep = 0;
        playing = true;
        timer = setInterval(stepForward, intervalMs);
      }}
      updatePlayBtn();
    }}
    function resetAnim() {{
      clearInterval(timer); playing = false; currentStep = 0;
      drawUpTo(0); updatePlayBtn();
    }}
    function updatePlayBtn() {{
      const btn = document.getElementById('btn-play');
      btn.textContent = playing ? 'Pause' : 'Play';
      btn.classList.toggle('active', playing);
    }}

    // Summary panel
    const sumCol = document.getElementById('summary-col');
    SUMMARY.forEach(function(item, i) {{
      const card = document.createElement('div');
      card.className = 'summary-card' + (i === 0 ? ' highlight' : '');
      card.innerHTML = `
        <div class="s-label">${{item.label}}</div>
        <div class="s-value" style="color:${{item.color}}">${{item.value}}</div>`;
      sumCol.appendChild(card);
    }});
    // Insight box
    const insightBox = document.createElement('div');
    insightBox.className = 'insight-box';
    insightBox.innerHTML = INSIGHT;
    sumCol.appendChild(insightBox);

    // Bar chart
    const barDiv = document.getElementById('bar-chart');
    ARMS.forEach(function(arm, i) {{
      const row  = document.createElement('div'); row.className = 'bar-row';
      const lbl  = document.createElement('div'); lbl.className = 'bar-lbl'; lbl.textContent = PRETTY[i];
      const trk  = document.createElement('div'); trk.className = 'bar-track';
      const fill = document.createElement('div'); fill.className = 'bar-fill'; fill.style.background = COLORS[i];
      const cnt  = document.createElement('div'); cnt.className = 'bar-cnt'; cnt.textContent = COUNTS[i];
      trk.appendChild(fill);
      row.appendChild(lbl); row.appendChild(trk); row.appendChild(cnt);
      if (COUNTS[i] === 0) {{
        const note = document.createElement('span'); note.className = 'zero-note';
        note.textContent = '(never chosen - belief is prior only)';
        row.appendChild(note);
      }}
      barDiv.appendChild(row);
      setTimeout(() => {{
        fill.style.width = (COUNTS[i] / MAX_CNT * 100) + '%';
      }}, i * 120 + 300);
    }});

    // Final belief cards
    const lastBeliefs = STEPS[N - 1].beliefs;
    const maxProb = Math.max(...ARMS.map(a => lastBeliefs[a]));
    const bgrid = document.getElementById('belief-grid');
    ARMS.forEach(function(arm, i) {{
      const p    = lastBeliefs[arm];
      const card = document.createElement('div');
      card.className = 'belief-card' + (p === maxProb ? ' winner' : '');
      const isNeverChosen = COUNTS[i] === 0;
      card.innerHTML = `
        <div class="bc-label">${{PRETTY[i]}}</div>
        <div class="bc-value" style="color:${{COLORS[i]}}" id="bcv-${{i}}">0%</div>
        ${{isNeverChosen ? '<div class="bc-note">prior only - never explored</div>' : ''}}`;
      bgrid.appendChild(card);
      const valEl = card.querySelector('.bc-value');
      const endP  = parseFloat((p * 100).toFixed(1));
      const start = performance.now();
      function tick(now) {{
        const t = Math.min(1, (now - start) / 900);
        valEl.textContent = (t * endP).toFixed(1) + '%';
        if (t < 1) requestAnimationFrame(tick);
        else valEl.textContent = endP.toFixed(1) + '%';
      }}
      setTimeout(() => requestAnimationFrame(tick), i * 120 + 400);
    }});

    // Auto-play
    setTimeout(() => {{ playing = true; timer = setInterval(stepForward, intervalMs); updatePlayBtn(); }}, 600);
    </script>
    </div>
    """

    st.iframe(animated_html, height=960)