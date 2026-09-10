"""Risk Center page: run the operational risk engine and review detected risks."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components import charts
from frontend.components.cards import risk_card
from frontend.components.metrics import (
    fallback_note,
    pipeline_diagram,
    section_header,
    severity_pill,
)
from frontend.components.tables import show_table
from frontend.config import DEMO_RISKS
from frontend.utils.formatting import fmt_number, iso_today, severity_color, severity_rank
from frontend.utils.state import bump_refresh, demo_mode_enabled, get_client, refresh_key


@st.cache_data(ttl=20, show_spinner=False)
def _load_risks(rev: int, demo: bool):
    if demo:
        return DEMO_RISKS, "demo", None
    client = get_client()
    return client.get_risks(target_date=iso_today(), fallback=DEMO_RISKS)


def _overall_level(risks: list[dict]) -> str:
    if not risks:
        return "low"
    return min(((r.get("severity") or "low") for r in risks), key=severity_rank)


def render() -> None:
    demo = demo_mode_enabled()
    rev = refresh_key("risks")
    risks, source, error = _load_risks(rev, demo)

    st.markdown("## Risk Center")

    pipeline_diagram([
        ("DATA", "procurement history + DPC capacity"),
        ("ML", "overload probability per DPC"),
        ("RISK ENGINE", "capacity %, queue, weather, logistics"),
        ("OFFICER", "decides mitigation & diversion"),
    ])

    if demo:
        fallback_note()
    else:
        st.caption("Operational risk engine from the backend (persisted risk assessments).")
        if source == "demo":
            st.caption("Demo fallback data - backend data unavailable.")

    overall = _overall_level(risks)
    c_metric, c_actions = st.columns([1, 2])
    c_metric.metric("Overall Operational Risk", overall.upper(), "risks analyzed")
    c_actions.markdown(f"<div style='padding-top:6px;'>{severity_pill(overall)}</div>", unsafe_allow_html=True)

    risky = [r for r in risks if r.get("severity") in ("high", "critical")]
    st.markdown(
        f"Risk engine assessed **{len(risks)}** risk(s) for **{iso_today()}**; "
        f"**{len(risky)}** require officer attention today."
    )

    st.markdown("---")
    col_left, col_right = st.columns([3, 1])

    with col_left:
        section_header("Detected Risks", "Overload and congestion from predicted demand")
        if risks:
            for r in risks:
                risk_card(r)
        else:
            st.success("No risks detected.")

    with col_right:
        section_header("Risk Distribution")
        if risks:
            dfr = pd.DataFrame([
                {"Risk": str(r.get("risk_type")).replace("_", " ").title(),
                 "Severity": r.get("severity"), "Count": 1}
                for r in risks
            ])
            dist = dfr.groupby("Risk").agg(Count=("Count", "sum"), Severity=("Severity", "first")).reset_index()
            dist["Color"] = dist["Severity"].map(severity_color)
            st.plotly_chart(
                charts.pie(dist, names="Risk", values="Count",
                           color_map=dict(zip(dist["Risk"], dist["Color"]))),
                use_container_width=True,
            )
        else:
            st.info("No risk data.")

    st.markdown("---")
    section_header("DPC Risk Ranking", "Aggregated per procurement centre")
    if risks and any(r.get("dpc_id") for r in risks):
        rows = []
        for r in risks:
            if not r.get("dpc_id"):
                continue
            seed = (r.get("dpc_name") or str(r.get("dpc_id")))
            rows.append({
                "DPC": r.get("dpc_name", seed),
                "Risk": str(r.get("risk_type")).replace("_", " ").title(),
                "Severity": (r.get("severity") or "low").upper(),
                "Metric": float(r.get("metric") or 0),
                "Description": r.get("description", ""),
            })
        df_rank = pd.DataFrame(rows).sort_values("Metric", ascending=False)
        show_table(df_rank, height=200)
    else:
        st.info("No DPC-specific risks to rank.")

    st.markdown("---")
    section_header("Risk Analysis Controls")
    if st.button("Re-analyze risks"):
        bump_refresh("risks")
        st.rerun()