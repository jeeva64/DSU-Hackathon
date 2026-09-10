"""DPC Monitoring page: per-DPC cards, utilization and forecast charts."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from frontend.components import charts
from frontend.components.cards import dpc_card
from frontend.components.metrics import fallback_note, section_header
from frontend.config import DEMO_DPCS, DEMO_ML_PREDICTIONS
from frontend.utils.formatting import fmt_number
from frontend.utils.state import bump_refresh, demo_mode_enabled, get_client, refresh_key


@st.cache_data(ttl=20, show_spinner=False)
def _load_monitoring(rev: int, demo: bool):
    client = get_client()
    if demo:
        return DEMO_DPCS, "demo", None

    dpcs, src, err = client.get_dpcs()
    if src == "demo":
        return DEMO_DPCS, "demo", err

    overview, src_ov, err_ov = client.get_dpc_overview(dpcs, fallback=DEMO_DPCS)
    return overview, ("demo" if src_ov == "demo" else "backend"), None


@st.cache_data(ttl=20, show_spinner=False)
def _demo_forecast(dpc_name: str):
    base = DEMO_ML_PREDICTIONS.get(dpc_name, {"arrivals": 100})["arrivals"]
    rows = []
    for i in range(14):
        day = date.today() + timedelta(days=i)
        wave = base * (1 + 0.10 * math.sin(i / 2.0) + 0.04 * ((i * 37) % 5 - 2))
        rows.append({"target_date": day.isoformat(), "predicted_value": round(wave, 1)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=20, show_spinner=False)
def _forecast_series(dpc_id: int, dpc_name: str, demo: bool):
    if demo:
        return _demo_forecast(dpc_name), "demo"

    client = get_client()
    predictions, src, err = client.get_predictions_for_dpc(dpc_id)
    if src == "demo" or not predictions:
        return _demo_forecast(dpc_name), "demo"
    series = [p for p in predictions if p.get("prediction_type") == "arrival_count"]
    if not series:
        series = predictions
    rows = [
        {"target_date": p.get("target_date"), "predicted_value": float(p.get("predicted_value", 0))}
        for p in series
    ]
    return pd.DataFrame(rows), "backend"


def render() -> None:
    demo = demo_mode_enabled()
    rev = refresh_key("dpc_monitoring")
    dpcs, source, error = _load_monitoring(rev, demo)

    st.markdown("## DPC Monitoring")
    if demo:
        fallback_note("Prototype / Synthetic Data")
    else:
        st.caption("Live DPC capacity position.")
        if source == "demo":
            st.caption("Demo fallback data - backend data unavailable.")

    names = [d.get("name") for d in dpcs]
    selected_name = st.selectbox("Focus DPC", names, index=0)
    selected = next((d for d in dpcs if d.get("name") == selected_name), dpcs[0] if dpcs else {})
    dpc_id = selected.get("id")

    st.markdown("---")
    section_header("Capacity Position", "Status derived from predicted capacity utilization")
    cols_per_row = 2
    for start in range(0, len(dpcs), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, dpc in zip(cols, dpcs[start:start + cols_per_row]):
            with col:
                dpc_card(
                    dpc,
                    utilization_pct=dpc.get("current_utilization_pct"),
                    bags_received=dpc.get("bags_received_today"),
                    remaining_bags=dpc.get("remaining_capacity_bags"),
                )

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        section_header("Utilization Across DPCs")
        df_util = pd.DataFrame([
            {"DPC": d.get("name"), "Utilization %": float(d.get("current_utilization_pct", 0) or 0)}
            for d in dpcs
        ])
        st.plotly_chart(charts.hbar(df_util, y="DPC", x="Utilization %"), use_container_width=True)

    with c2:
        section_header(f"Forecast: Expected Visits (Arrivals) - {selected_name}")
        forecast, forecast_src = _forecast_series(dpc_id, selected_name, demo)
        if forecast_src == "demo" and not demo:
            st.caption("Demo fallback forecast - backend predictions unavailable.")
        st.plotly_chart(
            charts.line(forecast, x="target_date", y="predicted_value", title=""),
            use_container_width=True,
        )

    st.markdown("---")
    kpi_row = st.columns(4)
    if selected:
        kpi_row[0].metric("Daily capacity", f"{fmt_number(selected.get('daily_capacity', 0))} bags")
        kpi_row[1].metric("Received today", f"{fmt_number(selected.get('bags_received_today', 0))} bags")
        kpi_row[2].metric("Remaining capacity", f"{fmt_number(selected.get('remaining_capacity_bags', 0))} bags")
        kpi_row[3].metric(
            "Storage capacity",
            f"{fmt_number(selected.get('storage_capacity', 0), 0)} tonnes",
        )

    st.markdown("---")
    if st.button("Refresh DPC data"):
        bump_refresh("dpc_monitoring")
        st.rerun()