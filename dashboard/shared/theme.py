"""
theme.py

Shared, site-wide CSS polish: nav centering, hover dynamics on buttons,
metrics and cards, and general table/container styling. Also provides the
prettify() utility for converting internal identifier strings to human-
readable display labels.

Call apply_custom_css() once near the top of every page (after
`import streamlit as st`, before any other st.* calls that should be styled).
"""

import streamlit as st

ACCENT = "#10b981"
ACCENT_SOFT = "rgba(16, 185, 129, 0.12)"

_PRETTY_MAP = {
    # Arms
    "retry_2h": "Retry in 2h",
    "retry_24h": "Retry in 24h",
    "retry_72h": "Retry in 72h",
    "whatsapp_escalate": "WhatsApp Escalate",
    # Payment networks
    "UPI_AUTOPAY": "UPI Autopay",
    "RUPAY": "RuPay",
    "VISA": "Visa",
    "MASTERCARD": "Mastercard",
    # Decision sources
    "bandit": "Bandit",
    "rule_engine_override": "Rule Engine Override",
}


def prettify(s: str) -> str:
    """Convert snake_case / UPPER_UNDERSCORE identifiers to human-readable labels."""
    if s in _PRETTY_MAP:
        return _PRETTY_MAP[s]
    # Generic fallback: replace underscores with spaces, title-case
    return str(s).replace("_", " ").title()


def apply_custom_css():
    st.markdown(
        f"""
        <style>
        /* ---- Center the top navigation bar ----
           Covers multiple Streamlit versions / DOM shapes. */
        [data-testid="stNavigation"] {{
            display: flex !important;
            justify-content: center !important;
        }}
        [data-testid="stNavigation"] > div,
        [data-testid="stNavigation"] > nav {{
            display: flex !important;
            justify-content: center !important;
            width: 100%;
        }}
        [data-testid="stHeader"] [role="tablist"],
        [data-testid="stNavigation"] [role="tablist"] {{
            justify-content: center !important;
            width: 100%;
        }}
        header[data-testid="stHeader"] nav {{
            display: flex !important;
            justify-content: center !important;
            width: 100%;
        }}
        header[data-testid="stHeader"] nav ul {{
            justify-content: center !important;
            width: 100%;
        }}
        /* Streamlit ≥1.35 wraps nav links in an <li> row */
        [data-testid="stNavigation"] ul {{
            display: flex !important;
            justify-content: center !important;
            list-style: none;
            padding: 0;
            margin: 0;
            width: 100%;
        }}

        /* ---- Buttons: hover lift + accent glow ---- */
        .stButton > button {{
            transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
            border-radius: 10px !important;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 18px {ACCENT_SOFT};
            border-color: {ACCENT} !important;
        }}

        /* ---- Metrics: subtle card feel with hover lift ---- */
        [data-testid="stMetric"] {{
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 14px 16px;
            transition: transform 0.15s ease, border-color 0.15s ease;
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            border-color: {ACCENT};
        }}

        /* ---- DataFrames: rounded container, subtle border ---- */
        [data-testid="stDataFrame"] {{
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.08);
        }}

        /* ---- Expanders: card-like, hover highlight ---- */
        [data-testid="stExpander"] {{
            border-radius: 12px !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            transition: border-color 0.15s ease;
        }}
        [data-testid="stExpander"]:hover {{
            border-color: {ACCENT} !important;
        }}

        /* ---- Headings: subtle accent underline flourish ---- */
        h2 {{
            border-bottom: 2px solid {ACCENT_SOFT};
            padding-bottom: 6px;
        }}

        /* ---- Forms: rounded, faint border so filter blocks read as one unit ---- */
        [data-testid="stForm"] {{
            border-radius: 14px !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            padding: 18px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )