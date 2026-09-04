"""
info_cards.py

Horizontal card grid for 'How It Works'. Clicking a card opens a centered
modal overlay with the full content - not below the cards, but floating in
the middle of the screen.
"""

import html as html_lib
import json

import streamlit.components.v1 as components

ACCENT = "#10b981"


def render_info_cards(cards, height=600):
    """
    cards: list of {"title": str, "teaser": str, "body_html": str}
    Clicking a card opens a fixed-position modal centered in the iframe.
    """
    tile_blocks = []
    for i, card in enumerate(cards):
        tile_blocks.append(f"""
        <div class="info-card" id="card-{i}" onclick="openCard({i})">
          <div class="card-num">{'0' + str(i + 1)}</div>
          <div class="card-title">{html_lib.escape(card['title'])}</div>
          <div class="card-teaser">{html_lib.escape(card['teaser'])}</div>
          <div class="card-cta">Click to read more &rarr;</div>
        </div>
        """)

    bodies_js = json.dumps([c["body_html"] for c in cards])
    titles_js = json.dumps([c["title"] for c in cards])

    html_doc = f"""
    <div id="cards-root" style="font-family:'Segoe UI',Roboto,sans-serif;">
      <style>
        * {{ box-sizing: border-box; }}
        body, html {{ margin:0; padding:0; }}

        #cards-root {{ padding: 4px 2px; }}

        /* ---- Card grid ---- */
        #cards-root .card-grid {{
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
        }}
        #cards-root .info-card {{
          flex: 1 1 calc(33.33% - 9px);
          min-width: 150px;
          background: #131826;
          border: 1.5px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 18px 16px 14px;
          cursor: pointer;
          transition: border-color 0.22s ease, transform 0.18s ease, box-shadow 0.22s ease;
        }}
        #cards-root .info-card:hover {{
          border-color: {ACCENT};
          transform: translateY(-3px);
          box-shadow: 0 8px 28px rgba(16,185,129,0.18);
        }}
        #cards-root .card-num {{
          font-size: 11px; font-weight: 800; color: {ACCENT};
          letter-spacing: 0.08em; margin-bottom: 10px;
        }}
        #cards-root .card-title {{
          color: #f3f4f6; font-size: 15px; font-weight: 700;
          line-height: 1.3; margin-bottom: 8px;
        }}
        #cards-root .card-teaser {{
          color: #9ca3af; font-size: 12px; line-height: 1.5;
          margin-bottom: 14px;
        }}
        #cards-root .card-cta {{
          color: {ACCENT}; font-size: 11px; font-weight: 600;
          opacity: 0.7;
        }}
        #cards-root .info-card:hover .card-cta {{ opacity: 1; }}

        /* ---- Backdrop ---- */
        #modal-backdrop {{
          display: none;
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.72);
          z-index: 998;
          cursor: pointer;
        }}

        /* ---- Modal ---- */
        #modal-panel {{
          display: none;
          position: fixed;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          z-index: 999;
          width: 82%;
          max-height: 72vh;
          overflow-y: auto;
          background: #0c1520;
          border: 1.5px solid rgba(16,185,129,0.4);
          border-radius: 18px;
          padding: 24px 28px;
          box-shadow: 0 30px 90px rgba(0,0,0,0.85);
        }}
        @keyframes modalIn {{
          from {{ opacity:0; transform:translate(-50%,-46%); }}
          to   {{ opacity:1; transform:translate(-50%,-50%); }}
        }}
        #modal-panel.visible {{
          display: block;
          animation: modalIn 0.26s cubic-bezier(0.22,1,0.36,1);
        }}

        /* ---- Modal header ---- */
        #modal-header {{
          display: flex; justify-content: space-between; align-items: flex-start;
          margin-bottom: 16px; padding-bottom: 12px;
          border-bottom: 1px solid rgba(16,185,129,0.2);
        }}
        #modal-title {{
          color: #f3f4f6; font-size: 18px; font-weight: 800;
          line-height: 1.2;
        }}
        #modal-close {{
          background: rgba(255,255,255,0.08); border: none;
          color: #9ca3af; font-size: 20px; width: 32px; height: 32px;
          border-radius: 8px; cursor: pointer; flex-shrink: 0;
          margin-left: 16px; line-height: 1;
          transition: background 0.15s, color 0.15s;
        }}
        #modal-close:hover {{ background: rgba(255,255,255,0.15); color: #f3f4f6; }}

        /* ---- Modal body content ---- */
        #modal-body {{ color: #d1d5db; font-size: 14px; line-height: 1.7; }}
        #modal-body b  {{ color: #f3f4f6; }}
        #modal-body a  {{ color: {ACCENT}; }}
        #modal-body em {{ color: #e5e7eb; font-style: italic; }}
        #modal-body code {{
          background: rgba(255,255,255,0.08); padding: 1px 6px;
          border-radius: 4px; font-size: 12.5px;
        }}
        #modal-body ul {{ margin: 8px 0; padding-left: 20px; }}
        #modal-body li {{ margin-bottom: 6px; }}
        #modal-body p  {{ margin: 0 0 10px 0; }}
        #modal-body table {{
          width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px;
        }}
        #modal-body th,
        #modal-body td {{
          text-align: left; padding: 7px 10px;
          border-bottom: 1px solid rgba(255,255,255,0.08);
        }}
        #modal-body th {{ color: {ACCENT}; font-weight: 700; }}
      </style>

      <div class="card-grid">
        {''.join(tile_blocks)}
      </div>

      <!-- Backdrop -->
      <div id="modal-backdrop" onclick="closeModal()"></div>

      <!-- Centered modal -->
      <div id="modal-panel">
        <div id="modal-header">
          <div id="modal-title"></div>
          <button id="modal-close" onclick="closeModal()">&#10005;</button>
        </div>
        <div id="modal-body"></div>
      </div>
    </div>

    <script>
      const BODIES = {bodies_js};
      const TITLES = {titles_js};

      function openCard(i) {{
        document.getElementById('modal-title').textContent = TITLES[i];
        document.getElementById('modal-body').innerHTML    = BODIES[i];
        document.getElementById('modal-backdrop').style.display = 'block';
        const panel = document.getElementById('modal-panel');
        panel.classList.remove('visible');
        void panel.offsetWidth;  // force reflow for animation restart
        panel.classList.add('visible');
      }}

      function closeModal() {{
        document.getElementById('modal-backdrop').style.display = 'none';
        document.getElementById('modal-panel').classList.remove('visible');
      }}

      // Close on Escape key
      document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') closeModal();
      }});
    </script>
    """
    components.html(html_doc, height=height, scrolling=False)