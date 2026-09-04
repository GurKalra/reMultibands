"""
app.py

reMultiBands dashboard entrypoint. Defines the top navigation bar and
routes to each page.

Run with (from the reMultiBands project root):

    streamlit run dashboard/app.py
"""

import streamlit as st

from shared.theme import apply_custom_css

st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_custom_css()

pages = {
    "": [
        st.Page("views/overview.py",            title="Overview",             default=True),
        st.Page("views/segment_leaderboard.py", title="Segment Leaderboard"),
        st.Page("views/how_it_works.py",        title="How It Works"),
        st.Page("views/watch_it_learn.py",      title="Watch It Learn"),
        st.Page("views/compliance_audit.py",    title="Compliance & Audit"),
        st.Page("views/network_effects.py",     title="Network Effects"),
        st.Page("views/robustness.py",          title="Robustness"),
    ]
}

pg = st.navigation(pages, position="top")
pg.run()