"""NelSync AI - Streamlit demo frontend entry point.

Run from repo root:
    streamlit run frontend/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable no matter how the app is launched
# (repo path contains a space; Streamlit only adds the script's own dir).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from frontend.components.metrics import status_badge
from frontend.config import APP_TAGLINE, APP_TITLE, PAGE_LABELS
from frontend.pages import (
    dashboard,
    dpc_monitoring,
    predictions,
    procurement,
    risks,
    simulation,
)
from frontend.utils.state import demo_mode_enabled, set_demo_mode

st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    div[data-testid="stSidebar"] {background: #f7f9fc;}
    h1, h2, h3 {color: #12395b;}
    </style>
    """,
    unsafe_allow_html=True,
)

_PAGES = {
    "Dashboard": dashboard,
    "Procurement": procurement,
    "DPC Monitoring": dpc_monitoring,
    "AI Predictions": predictions,
    "Risk Center": risks,
    "Scenario Simulation": simulation,
}


def _sidebar() -> str:
    st.sidebar.markdown(f"# {APP_TITLE}")
    st.sidebar.caption(APP_TAGLINE)

    selection = st.sidebar.radio("Navigate", PAGE_LABELS, label_visibility="collapsed")

    st.sidebar.markdown("---")
    demo = st.sidebar.toggle(
        "Demo Mode (synthetic data)",
        value=demo_mode_enabled(),
        help="On: uses built-in synthetic demo data. Off: queries the FastAPI backend.",
    )
    set_demo_mode(demo)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"{status_badge('PROTOTYPE', '#12395b')} {status_badge('SYNTHETIC DATA', '#8a5a00')} "
        f"{status_badge('OFFLINE MVP', '#2e7d32')}",
        unsafe_allow_html=True,
    )
    st.sidebar.caption("AI recommends · officers decide")
    return selection


def main() -> None:
    selection = _sidebar()
    module = _PAGES[selection]
    module.render()


if __name__ == "__main__":
    main()