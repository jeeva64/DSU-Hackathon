"""Dashboard page: high-level KPIs, DPC overview and risk distribution."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components import charts
from frontend.components.metrics import fallback_note, kpi_row, section_header
from frontend.components.tables import pct_progress, show_table
from frontend.config import CAPACITY_THRESHOLDS, DEMO_DPCS, DEMO_PROCUREMENT_SUMMARY, DEMO_RISKS
from frontend.utils.formatting import fmt_number, severity_color
from frontend.utils.state import bump_refresh, demo_mode_enabled, get_client, refresh_key


def _load_pct(d: dict) -> float:
    """Read the demand/load % from live or demo DPC payloads."""
    return float(d.get("current_utilization_pct") or d.get("utilization_pct") or 0)


def _imbalance_band(load_pct: float) -> str:
    if load_pct >= CAPACITY_THRESHOLDS["critical"]:
        return "OVERLOADED"
    if load_pct >= CAPACITY_THRESHOLDS["high"]:
        return "OVERLOADED"
    if load_pct >= CAPACITY_THRESHOLDS["watch"]:
        return "NORMAL"
    return "UNDERUTILIZED"


_IMBALANCE_COLORS = {
    "UNDERUTILIZED": "#2e7d32",
    "NORMAL": "#e07c24",
    "OVERLOADED": "#b00020",
}


@st.cache_data(ttl=20, show_spinner=False)
def _dashboard_data(rev: int, demo: bool):
    if demo:
        return DEMO_DPCS, "demo", None, DEMO_RISKS

    client = get_client()
    dpcs, src, err = client.get_dpcs()
    if src == "demo":
        return DEMO_DPCS, "demo", err, DEMO_RISKS

    overview, src_ov, err_ov = client.get_dpc_overview(dpcs, fallback=DEMO_DPCS)
    risks, src_risk, err_risk = client.get_risks(fallback=DEMO_RISKS)
    fallback_used = src_ov == "demo" or src_risk == "demo"
    return overview, ("demo" if fallback_used else "backend"), None, risks


def render() -> None:
    demo = demo_mode_enabled()
    rev = refresh_key("dashboard")
    dpcs, source, error, risks = _dashboard_data(rev, demo)

    st.markdown("## Operational Dashboard")
    if demo:
        fallback_note("Prototype / Synthetic Data")
    else:
        st.caption("Live view of the NelSync AI backend (synthetic seeded data).")
        if source == "demo":
            st.caption("Demo fallback data - backend data unavailable.")

    active_dpcs = len([d for d in dpcs if str(d.get("operating_status", "active")).lower() == "active"]) or 1
    total_capacity = sum(float(d.get("daily_capacity", 0) or 0) for d in dpcs)
    avg_util = sum(float(d.get("current_utilization_pct", 0) or 0) for d in dpcs) / max(1, len(dpcs))
    high_risk_dpcs = len({
        r.get("dpc_id") for r in risks
        if r.get("severity") in ("high", "critical") and r.get("dpc_id")
    })

    kpi_row([
        ("Active DPCs", fmt_number(active_dpcs), None),
        ("Total daily capacity", f"{fmt_number(total_capacity, 0)} bags", None),
        ("Avg capacity utilization", f"{avg_util:.1f}%", None),
        ("High-risk DPCs", fmt_number(high_risk_dpcs), "overload / congestion"),
        ("Procurement records", fmt_number(DEMO_PROCUREMENT_SUMMARY["total_records"]) if demo else "live", None),
    ])

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        section_header("DPC Operational Overview", "Capacity position per procurement centre")
        df_dpc = pd.DataFrame([{
            "DPC": d.get("name"),
            "District": d.get("district"),
            "Status": str(d.get("operating_status", "active")).title(),
            "Daily capacity (bags)": float(d.get("daily_capacity", 0) or 0),
            "Received today (bags)": float(d.get("bags_received_today", 0) or 0),
            "Remaining (bags)": float(d.get("remaining_capacity_bags", 0) or 0),
            "Utilization %": float(d.get("current_utilization_pct", 0) or 0),
        } for d in dpcs])

        show_table(
            df_dpc,
            column_config={
                "DPC": st.column_config.TextColumn("DPC"),
                "District": st.column_config.TextColumn("District"),
                "Status": st.column_config.TextColumn("Status"),
                "Daily capacity (bags)": st.column_config.NumberColumn("Daily capacity", format="%d"),
                "Received today (bags)": st.column_config.NumberColumn("Received today", format="%d"),
                "Remaining (bags)": st.column_config.NumberColumn("Remaining", format="%d"),
                "Utilization %": pct_progress("Utilization %"),
            },
            height=180,
        )

    with col_right:
        section_header("Risk Distribution")
        if risks:
            risk_df = pd.DataFrame([
                {"Risk": str(r.get("risk_type", "unknown")).replace("_", " ").title(),
                 "Count": 1, "Color": severity_color(r.get("severity", "low"))}
                for r in risks
            ])
            dist = risk_df.groupby("Risk").agg(Count=("Count", "sum"), Color=("Color", "first")).reset_index()
            color_map = dict(zip(dist["Risk"], dist["Color"]))
            st.plotly_chart(charts.pie(dist, names="Risk", values="Count",
                                       color_map=color_map), use_container_width=True)
        else:
            st.info("No risks detected.")

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        section_header("Capacity Utilization by DPC")
        df_util = pd.DataFrame([
            {"DPC": d.get("name"), "Utilization %": float(d.get("current_utilization_pct", 0) or 0),
             "Color": severity_color("high" if float(d.get("current_utilization_pct", 0)) >= 85 else "low")}
            for d in dpcs
        ])
        color_map = dict(zip(df_util["DPC"], df_util["Color"]))
        st.plotly_chart(
            charts.hbar(df_util, y="DPC", x="Utilization %", color_col="DPC", color_map=color_map),
            use_container_width=True,
        )

    with col_chart2:
        section_header("Received vs Remaining Capacity", "Bags today")
        df_cap = pd.DataFrame([
            {"DPC": d.get("name"), "Received": float(d.get("bags_received_today", 0) or 0),
             "Remaining": float(d.get("remaining_capacity_bags", 0) or 0)}
            for d in dpcs
        ])
        df_stack = df_cap.melt(id_vars="DPC", var_name="Bucket", value_name="Bags")
        st.plotly_chart(
            charts.stacked_bar(df_stack, x="DPC", y="Bags", color="Bucket", title="",
                               color_map={"Received": "#2e7d32", "Remaining": "#90a4ae"}),
            use_container_width=True,
        )

    st.markdown("---")

    section_header(
        "Expected Demand vs Available DPC Capacity",
        "Demand colour bands: UNDERUTILIZED <70% | NORMAL 70-85% | OVERLOADED >85%",
    )
    df_imbalance = pd.DataFrame([
        {"DPC": d.get("name"),
         "Demand vs capacity %": _load_pct(d),
         "Band": _imbalance_band(_load_pct(d))}
        for d in dpcs
    ]).sort_values("Demand vs capacity %", ascending=True)
    color_map = {b: c for b, c in _IMBALANCE_COLORS.items() if b in set(df_imbalance["Band"])}
    st.plotly_chart(
        charts.hbar(df_imbalance, y="DPC", x="Demand vs capacity %",
                    color_col="Band", color_map=color_map),
        use_container_width=True,
    )
    imbalance_hint = (
        "Uneven procurement demand concentrates arrivals at some centres while "
        "capacity sits idle elsewhere - the core problem NelSync AI addresses."
    )
    if demo or source == "demo":
        st.caption(f"{imbalance_hint} (synthetic demo data)")
    else:
        st.caption(imbalance_hint)

    st.markdown("---")
    if st.button("Refresh dashboard"):
        bump_refresh("dashboard")
        st.rerun()