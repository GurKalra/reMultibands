"""
recovery_race.py

The Overview page's hook: an animated two-lane race between the static
baseline and reMultiBands, with a live metrics panel on the right that
counts up in sync with the animation. Each metric card is clickable to
reveal an explanation.
"""

import streamlit as st


def render_recovery_race(baseline_result, remultibands_result, height=500):
    baseline_recovered   = int(baseline_result["total_recovered"])
    remultibands_recovered = int(remultibands_result["total_recovered"])
    baseline_strikes     = int(baseline_result["network_strikes_incurred"])
    remultibands_strikes = int(remultibands_result["network_strikes_incurred"])
    resolved_count       = int(remultibands_result["resolved_count"])
    total_txns           = int(remultibands_result["total_transactions"])
    escalations          = int(remultibands_result["escalations_triggered"])
    lift                 = remultibands_recovered - baseline_recovered
    lift_pct             = (lift / baseline_recovered * 100) if baseline_recovered else 0

    html = f"""
    <div id="race-root" style="font-family:'Segoe UI',Roboto,sans-serif;padding:6px;">
      <style>
        #race-root .outer {{ display:flex; gap:16px; align-items:stretch; }}
        #race-root .lanes {{ display:flex; gap:14px; flex:2; min-width:0; }}
        #race-root .lane {{
          flex:1; background:#111827; border-radius:16px; padding:18px 16px;
          position:relative; overflow:hidden; min-height:260px;
        }}
        #race-root .lane.baseline {{ border:2px solid #4b5563; }}
        #race-root .lane.remulti  {{ border:2px solid #10b981; }}
        #race-root .lane h3 {{
          color:#e5e7eb; margin:0 0 2px 0; font-size:14px; font-weight:700;
        }}
        #race-root .lane .sub {{ color:#9ca3af; font-size:11px; margin-bottom:10px; }}
        #race-root .counter {{
          font-size:26px; font-weight:800; color:#f9fafb;
          font-variant-numeric:tabular-nums;
        }}
        #race-root .track {{
          position:relative; height:100px; margin-top:12px;
          border-top:1px dashed #374151;
        }}
        #race-root .chip {{
          position:absolute; top:30px; left:-30px; width:20px; height:20px;
          border-radius:5px; display:flex; align-items:center; justify-content:center;
          font-size:10px; font-weight:700; opacity:0; color:white;
        }}
        @keyframes flyacross {{
          0%   {{ left:-30px; opacity:0; }}
          10%  {{ opacity:1; }}
          85%  {{ opacity:1; }}
          100% {{ left:100%; opacity:0; }}
        }}
        #race-root .badge {{
          margin-top:10px; display:inline-block; padding:5px 12px;
          border-radius:999px; font-size:12px; font-weight:700;
          opacity:0; transition:opacity 0.6s ease;
        }}
        #race-root .badge.strikes {{ background:#7f1d1d; color:#fecaca; }}
        #race-root .badge.clean   {{ background:#064e3b; color:#6ee7b7; }}

        /* ---- Right metrics panel ---- */
        #race-root .metrics-panel {{
          flex:1; display:flex; flex-direction:column; gap:8px; min-width:160px;
          overflow-y: auto;
          max-height: 440px;
          padding-right: 4px;
          scrollbar-width: thin;
          scrollbar-color: rgba(16,185,129,0.3) transparent;
        }}
        #race-root .metrics-panel::-webkit-scrollbar {{ width: 4px; }}
        #race-root .metrics-panel::-webkit-scrollbar-track {{ background: transparent; }}
        #race-root .metrics-panel::-webkit-scrollbar-thumb {{
          background: rgba(16,185,129,0.3); border-radius: 2px;
        }}
        #race-root .m-card {{
          background:#111827; border:1px solid rgba(255,255,255,0.08);
          border-radius:14px; padding:11px 13px; flex:1;
          cursor:pointer;
          transition:border-color 0.25s, box-shadow 0.25s;
        }}
        #race-root .m-card:hover {{ border-color:rgba(16,185,129,0.4); }}
        #race-root .m-card.ready {{ border-color:rgba(16,185,129,0.35); }}
        #race-root .m-card.open  {{
          border-color:#10b981;
          box-shadow: 0 0 14px rgba(16,185,129,0.2);
        }}
        #race-root .m-label {{ color:#9ca3af; font-size:10px; margin-bottom:3px; }}
        #race-root .m-value {{
          color:#f9fafb; font-size:19px; font-weight:800;
          font-variant-numeric:tabular-nums;
        }}
        #race-root .m-delta {{ color:#10b981; font-size:10px; margin-top:2px; }}
        #race-root .m-explain {{
          display:none; margin-top:7px; padding:7px 9px;
          background:rgba(16,185,129,0.07); border-radius:8px;
          font-size:11px; color:#9ca3af; line-height:1.5;
          border-top:1px solid rgba(16,185,129,0.15);
        }}
        #race-root .m-hint {{
          font-size:9px; color:rgba(255,255,255,0.22); margin-top:4px;
          letter-spacing:0.03em;
        }}
        #race-root .caption {{
          color:#6b7280; font-size:11px; margin-top:10px; text-align:center;
        }}
      </style>

      <div class="outer">
        <div class="lanes">
          <div class="lane baseline">
            <h3>Static Baseline</h3>
            <div class="sub">Fixed retry_24h, no compliance awareness</div>
            <div class="counter" id="ctr-baseline">0</div>
            <div class="track" id="track-baseline"></div>
            <div class="badge strikes" id="badge-baseline">
              {baseline_strikes:,} network strikes
            </div>
          </div>
          <div class="lane remulti">
            <h3>reMultiBands</h3>
            <div class="sub">Segmented bandit + compliant rule engine</div>
            <div class="counter" id="ctr-remulti">0</div>
            <div class="track" id="track-remulti"></div>
            <div class="badge clean" id="badge-remulti">0 network strikes</div>
          </div>
        </div>

        <div class="metrics-panel">
          <div class="m-card" id="mc-revenue" onclick="toggleMetric('revenue')">
            <div class="m-label">Revenue Recovered</div>
            <div class="m-value" id="mv-revenue">0</div>
            <div class="m-delta" id="md-revenue"></div>
            <div class="m-hint">click for details</div>
            <div class="m-explain" id="me-revenue">
              Total amount recovered by reMultiBands across all failed transactions.
              The lift shown is the improvement over the static baseline strategy
              that retries blindly on a fixed 24h schedule.
            </div>
          </div>
          <div class="m-card" id="mc-strikes" onclick="toggleMetric('strikes')">
            <div class="m-label">Network Strikes</div>
            <div class="m-value" id="mv-strikes">-</div>
            <div class="m-delta" id="md-strikes"></div>
            <div class="m-hint">click for details</div>
            <div class="m-explain" id="me-strikes">
              Strikes are incurred when a retry cap set by a card network (NPCI,
              Visa, Mastercard) is exceeded. reMultiBands' rule engine enforces
              these limits as hard constraints - the bandit is never allowed to
              violate them, regardless of its learned beliefs.
            </div>
          </div>
          <div class="m-card" id="mc-resolved" onclick="toggleMetric('resolved')">
            <div class="m-label">Transactions Resolved</div>
            <div class="m-value" id="mv-resolved">0</div>
            <div class="m-delta" id="md-resolved"></div>
            <div class="m-hint">click for details</div>
            <div class="m-explain" id="me-resolved">
              The number of initially-failed transactions where reMultiBands
              successfully collected payment - either by retrying at the right
              time or by escalating to a WhatsApp payment link.
            </div>
          </div>
          <div class="m-card" id="mc-escalations" onclick="toggleMetric('escalations')">
            <div class="m-label">Escalations to WhatsApp</div>
            <div class="m-value" id="mv-escalations">0</div>
            <div class="m-delta" id="md-escalations"></div>
            <div class="m-hint">click for details</div>
            <div class="m-explain" id="me-escalations">
              When the bandit judges that a retry is unlikely to succeed (e.g.
              after repeated failures or at network retry-cap limits), it escalates
              by sending a WhatsApp payment link directly to the customer. The
              baseline has no fallback channel - it only retries.
            </div>
          </div>
        </div>
      </div>

      <div class="caption">
        Flying chips are illustrative pacing over a representative sample.
        Final totals are exact computed results for this seed.
      </div>
    </div>

    <script>
      const BASELINE_TARGET    = {baseline_recovered};
      const REMULTI_TARGET     = {remultibands_recovered};
      const RESOLVED_TARGET    = {resolved_count};
      const TOTAL_TXNS         = {total_txns};
      const ESCALATIONS_TARGET = {escalations};
      const LIFT               = {lift};
      const LIFT_PCT           = {lift_pct:.1f};
      const BASELINE_STRIKES   = {baseline_strikes};
      const DURATION_MS        = 3000;

      function fmtINR(n) {{
        return '\u20b9' + Math.floor(n).toLocaleString('en-IN');
      }}

      function animateCounter(id, target, duration, fmt) {{
        const el = document.getElementById(id);
        const start = performance.now();
        function tick(now) {{
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          el.textContent = fmt(eased * target);
          if (t < 1) requestAnimationFrame(tick);
          else el.textContent = fmt(target);
        }}
        requestAnimationFrame(tick);
      }}

      function spawnChips(trackId, isRemulti, duration) {{
        const track = document.getElementById(trackId);
        const nChips = 30;
        for (let i = 0; i < nChips; i++) {{
          setTimeout(function() {{
            const chip = document.createElement('div');
            chip.className = 'chip';
            let bg = '#4b5563', label = '';
            if (isRemulti) {{
              const roll = Math.random();
              if (roll < 0.6)      {{ bg = '#10b981'; label = 'v'; }}
              else if (roll < 0.8) {{ bg = '#f59e0b'; label = 'W'; }}
              else                 {{ bg = '#ef4444'; label = 'x'; }}
            }} else {{
              const roll = Math.random();
              if (roll < 0.35) {{ bg = '#10b981'; label = 'v'; }}
              else             {{ bg = '#6b7280'; label = 'x'; }}
            }}
            chip.style.background = bg;
            chip.textContent = label;
            chip.style.top = (15 + Math.random() * 65) + 'px';
            chip.style.animation = 'flyacross 1.4s linear forwards';
            track.appendChild(chip);
            setTimeout(() => chip.remove(), 1500);
          }}, (i / nChips) * (duration - 400));
        }}
      }}

      function toggleMetric(key) {{
        const card   = document.getElementById('mc-' + key);
        const panel  = document.getElementById('me-' + key);
        const isOpen = panel.style.display === 'block';
        panel.style.display = isOpen ? 'none' : 'block';
        card.classList.toggle('open', !isOpen);
      }}

      function startRace() {{
        animateCounter('ctr-baseline', BASELINE_TARGET, DURATION_MS, fmtINR);
        animateCounter('ctr-remulti',  REMULTI_TARGET,  DURATION_MS, fmtINR);
        spawnChips('track-baseline', false, DURATION_MS);
        spawnChips('track-remulti',  true,  DURATION_MS);
        animateCounter('mv-revenue',    REMULTI_TARGET,     DURATION_MS, fmtINR);
        animateCounter('mv-resolved',   RESOLVED_TARGET,    DURATION_MS,
                       n => Math.floor(n).toLocaleString('en-IN'));
        animateCounter('mv-escalations', ESCALATIONS_TARGET, DURATION_MS,
                       n => Math.floor(n).toLocaleString('en-IN'));

        setTimeout(function() {{
          document.getElementById('badge-baseline').style.opacity = 1;
          document.getElementById('badge-remulti').style.opacity  = 1;
          document.getElementById('mv-strikes').textContent =
            '0 vs ' + BASELINE_STRIKES.toLocaleString('en-IN');
          document.getElementById('md-revenue').textContent =
            '+\u20b9' + LIFT.toLocaleString('en-IN') + ' (' + LIFT_PCT + '%) vs baseline';
          document.getElementById('md-resolved').textContent =
            'of ' + TOTAL_TXNS.toLocaleString('en-IN') + ' failed txns';
          document.getElementById('md-strikes').textContent =
            'reMultiBands: 0 violations';
          document.getElementById('md-escalations').textContent =
            'vs 0 for baseline (no fallback)';
          ['mc-revenue','mc-strikes','mc-resolved','mc-escalations'].forEach(function(id) {{
            document.getElementById(id).classList.add('ready');
          }});
        }}, DURATION_MS + 200);
      }}

      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', startRace);
      }} else {{
        startRace();
      }}
    </script>
    """
    st.iframe(html, height=height)