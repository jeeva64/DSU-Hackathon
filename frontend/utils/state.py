"""Session-scoped state helpers: shared API client, demo mode, refresh keys."""

from __future__ import annotations

import streamlit as st

from frontend.api_client import ApiClient, error_summary


def get_client() -> ApiClient:
    if "ns_api_client" not in st.session_state:
        st.session_state["ns_api_client"] = ApiClient()
    return st.session_state["ns_api_client"]


def demo_mode_enabled() -> bool:
    return bool(st.session_state.get("ns_demo_mode", True))


def set_demo_mode(enabled: bool) -> None:
    st.session_state["ns_demo_mode"] = bool(enabled)


def refresh_key(page: str) -> int:
    key = f"ns_refresh_{page}"
    if key not in st.session_state:
        st.session_state[key] = 0
    return int(st.session_state[key])


def bump_refresh(page: str) -> None:
    st.session_state[f"ns_refresh_{page}"] = refresh_key(page) + 1


def display_source_banner(source: str, error: dict | None) -> None:
    """Show a one-line banner when any section uses fallback/synthetic data."""
    if source == "demo":
        st.caption("Demo fallback data - synthetic values for prototype illustration.")
    elif error:
        st.caption(error_summary(error))