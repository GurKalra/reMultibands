"""
belief_animation.py

Animated horizontal bar visualization of a bandit's belief per arm.
Bars grow into place with staggered animation, counting-up percentage
labels, and optional glow highlight on a specified arm.
"""

import html as html_lib
import json

import streamlit as st

from shared.theme import prettify

ACCENT = "#10b981"
ARM_COLORS = {
    "retry_2h":          "#60a5fa",
    "retry_24h":         "#f59e0b",
    "retry_72h":         "#a78bfa",
    "whatsapp_escalate": "#10b981",
}


def render_belief_bars(values: dict, title: str = "", height: int = 280,
                       highlight_arm: str = None):
    """
    values: {arm_name: probability (0-1)}
    highlight_arm: if set, that arm's bar gets a glow + badge.
    Renders animated horizontal bars with prettified display labels.
    """
    bars_data = []
    for arm, prob in values.items():
        bars_data.append({
            "arm":       arm,
            "label":     prettify(arm),
            "pct":       round(prob * 100, 1),
            "color":     ARM_COLORS.get(arm, ACCENT),
            "highlight": arm == highlight_arm,
        })

    bars_json = json.dumps(bars_data)
    title_escaped = html_lib.escape(title) if title else ""

    html_doc = f"""
    <div id="bars-root" style="font-family:'Segoe UI',Roboto,sans-serif; padding:8px 4px;">
      <style>
        #bars-root .title {{
          color:#f3f4f6; font-weight:700; font-size:14px; margin-bottom:14px;
        }}
        #bars-root .bar-row {{
          display:flex; align-items:center; gap:12px; margin-bottom:16px;
        }}
        #bars-root .bar-label {{
          width:160px; color:#d1d5db; font-size:13px; flex-shrink:0;
        }}
        #bars-root .bar-track {{
          flex:1; height:18px; background:rgba(255,255,255,0.06);
          border-radius:9px; overflow:hidden;
          position:relative;
        }}
        #bars-root .bar-fill {{
          height:100%; width:0%; border-radius:9px;
          transition:width 1s cubic-bezier(0.22,1,0.36,1);
        }}
        #bars-root .bar-fill.glow {{
          box-shadow: 0 0 10px 2px rgba(16,185,129,0.55);
        }}
        #bars-root .bar-pct {{
          width:50px; text-align:right; color:#f3f4f6;
          font-size:13px; font-weight:700;
          font-variant-numeric:tabular-nums;
        }}
        #bars-root .badge-transfer {{
          background:#064e3b; color:#6ee7b7;
          font-size:10px; font-weight:700; border-radius:999px;
          padding:2px 8px; margin-left:4px; white-space:nowrap;
          animation: fadeIn 0.5s ease;
        }}
        @keyframes fadeIn {{
          from {{ opacity:0; transform:scale(0.85); }}
          to   {{ opacity:1; transform:scale(1); }}
        }}
      </style>
      {f'<div class="title">{title_escaped}</div>' if title_escaped else ''}
      <div id="bars-container"></div>
    </div>

    <script>
    const BARS = {bars_json};

    const container = document.getElementById('bars-container');
    BARS.forEach(function(b, i) {{
      const row   = document.createElement('div'); row.className = 'bar-row';
      const lbl   = document.createElement('div'); lbl.className = 'bar-label'; lbl.textContent = b.label;
      const trk   = document.createElement('div'); trk.className = 'bar-track';
      const fill  = document.createElement('div'); fill.className = 'bar-fill';
      if (b.highlight) fill.classList.add('glow');
      fill.style.background = b.color;
      const pctEl = document.createElement('div'); pctEl.className = 'bar-pct'; pctEl.textContent = '0%';
      trk.appendChild(fill);
      row.appendChild(lbl); row.appendChild(trk); row.appendChild(pctEl);

      if (b.highlight) {{
        const badge = document.createElement('span');
        badge.className = 'badge-transfer';
        badge.textContent = '★ Transferred';
        row.appendChild(badge);
      }}
      container.appendChild(row);

      setTimeout(function() {{
        fill.style.width = b.pct + '%';
        animateNumber(pctEl, 0, b.pct, 1000);
      }}, i * 130);
    }});

    function animateNumber(el, start, end, duration) {{
      const startTime = performance.now();
      function tick(now) {{
        const t   = Math.min(1, (now - startTime) / duration);
        const val = (start + (end - start) * t).toFixed(1);
        el.textContent = val + '%';
        if (t < 1) requestAnimationFrame(tick);
      }}
      requestAnimationFrame(tick);
    }}
    </script>
    """
    st.iframe(html_doc, height=height, scrolling=False)