"""Procurement page: farmer roster with readiness, expected arrival and moisture risk."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from frontend.components.metrics import fallback_note, kpi_row, section_header
from frontend.components.tables import show_table
from frontend.config import (
    DEMO_DPCS,
    DEMO_FARMERS,
    DEMO_PROCUREMENT_SUMMARY,
    PLANTING_TO_HARVEST_DAYS,
)
from frontend.utils.formatting import (
    deterministic_hash,
    fmt_number,
    fmt_qty,
    iso_today,
    moisture_risk_from_code,
    readiness_label,
)
from frontend.utils.state import bump_refresh, demo_mode_enabled, get_client, refresh_key

_READINESS_COLORS = {
    "ready": "#2e7d32",
    "partially_ready": "#e07c24",
    "overdue": "#b00020",
    "not_ready": "#78909c",
}


@st.cache_data(ttl=20, show_spinner=False)
def _build_demo_farmers():
    rows = []
    today = date.today()
    for f in DEMO_FARMERS:
        readiness = f.get("harvest_readiness", "ready")
        # deterministic pseudo sowing date so demo tables stay stable
        offset = 130 - (deterministic_hash(f["farmer_code"]) % 40)
        sowing = today - timedelta(days=offset)
        rows.append({**f, "id": None, "sowing_date": sowing.isoformat()})
    return rows


@st.cache_data(ttl=20, show_spinner=False)
def _load_procurement(rev: int, demo: bool):
    client = get_client()
    if demo:
        return _build_demo_farmers(), DEMO_PROCUREMENT_SUMMARY, DEMO_DPCS, [], "demo", None

    farmers, src_f, err_f = client.get_farmers()
    summary, src_s, err_s = client.get_procurement_summary()
    dpcs, src_d, err_d = client.get_dpcs()
    proc, src_p, err_p = client.get_procurement()
    if src_f == "demo":
        return _build_demo_farmers(), DEMO_PROCUREMENT_SUMMARY, DEMO_DPCS, [], "demo", err_f
    fallback_used = src_s == "demo" or src_d == "demo" or src_p == "demo"
    return farmers, summary, dpcs, proc, ("demo" if fallback_used else "backend"), None


def render() -> None:
    demo = demo_mode_enabled()
    rev = refresh_key("procurement")
    farmers, summary, dpcs, procurement, source, error = _load_procurement(rev, demo)

    st.markdown("## Procurement Roster")
    if demo:
        fallback_note("Prototype / Synthetic Data")
    else:
        st.caption("Live farmer + procurement records from the NelSync AI backend.")
        if source == "demo":
            st.caption("Demo fallback data - backend data unavailable.")

    dpc_by_id = {}
    for d in dpcs:
        if d.get("id") is not None:
            dpc_by_id[int(d["id"])] = d.get("name")

    # farmer id -> dpc name (from procurement records)
    farmer_dpc = {}
    idx = 0
    for p in procurement or []:
        fid = p.get("farmer_id")
        did = p.get("dpc_id")
        if fid is not None and did is not None:
            farmer_dpc[int(fid)] = dpc_by_id.get(int(did), f"DPC {did}")
        elif fid is not None and demo:
            farmer_dpc[int(fid)] = dpc_by_id.get(did, DEMO_DPCS[idx % len(DEMO_DPCS)]["name"])
            idx += 1

    rows = []
    for f in farmers:
        farmer_id = f.get("id")
        dpc_name = farmer_dpc.get(int(farmer_id)) if farmer_id is not None else None
        if dpc_name is None and demo:
            dpc_name = DEMO_DPCS[(deterministic_hash(str(f.get("farmer_code"))) % len(DEMO_DPCS))]["name"]
        if dpc_name is None:
            dpc_name = "-"

        sow = f.get("sowing_date")
        arrival = "-"
        if sow:
            try:
                arrival = (date.fromisoformat(str(sow)) + timedelta(days=PLANTING_TO_HARVEST_DAYS)).isoformat()
            except ValueError:
                arrival = "-"
        elif demo:
            arrival = "Demo estimate"

        readiness = str(f.get("harvest_readiness") or "not_ready")
        rows.append({
            "Farmer Code": f.get("farmer_code"),
            "Name": f.get("name"),
            "Village": f.get("village"),
            "DPC": dpc_name,
            "Paddy Variety": f.get("paddy_variety", "paddy"),
            "Expected Qty (q)": float(f.get("expected_quantity") or 0),
            "Harvest Readiness": readiness_label(readiness),
            "Expected Arrival": arrival,
            "Moisture Risk": moisture_risk_from_code(str(f.get("farmer_code"))),
        })

    df = pd.DataFrame(rows)

    kpi_row([
        ("Farmers listed", fmt_number(len(df)), None),
        ("Ready / overdue", fmt_number(len(df[df["Harvest Readiness"].isin(["Ready", "Overdue"])])), "harvesting now"),
        ("Total expected qty", f"{fmt_qty(df['Expected Qty (q)'].sum())} quintals", None),
        ("Avg expected qty", f"{fmt_qty(df['Expected Qty (q)'].mean(), 1)} q", "per farmer"),
        ("Avg moisture (recent)", f"{summary.get('avg_moisture_pct', 0):.1f}%", None),
    ])

    st.markdown("---")
    section_header("Filters")
    c1, c2, c3, c4 = st.columns(4)
    dpc_options = ["All"] + sorted(df["DPC"].dropna().unique().tolist())
    selected_dpc = c1.selectbox("DPC", dpc_options)
    readiness_options = ["All", "Ready", "Overdue", "Partially ready", "Not ready"]
    selected_readiness = c2.multiselect("Harvest readiness", readiness_options[1:], default=[])
    variety_options = sorted(df["Paddy Variety"].dropna().unique().tolist())
    selected_varieties = c3.multiselect("Paddy variety", variety_options, default=[])
    search = c4.text_input("Search farmer / village", "")

    filtered = df.copy()
    if selected_dpc != "All":
        filtered = filtered[filtered["DPC"] == selected_dpc]
    if selected_readiness:
        filtered = filtered[filtered["Harvest Readiness"].isin(selected_readiness)]
    if selected_varieties:
        filtered = filtered[filtered["Paddy Variety"].isin(selected_varieties)]
    if search.strip():
        needle = search.strip().lower()
        mask = (
            filtered["Farmer Code"].str.lower().str.contains(needle)
            | filtered["Name"].str.lower().str.contains(needle)
            | filtered["Village"].str.lower().str.contains(needle)
        )
        filtered = filtered[mask]

    section_header("Farmers", f"{len(filtered)} of {len(df)} records")
    show_table(
        filtered,
        column_config={
            "Farmer Code": st.column_config.TextColumn("Farmer Code"),
            "Name": st.column_config.TextColumn("Name"),
            "Village": st.column_config.TextColumn("Village"),
            "DPC": st.column_config.TextColumn("Procurement Center"),
            "Paddy Variety": st.column_config.TextColumn("Paddy Variety"),
            "Expected Qty (q)": st.column_config.NumberColumn("Expected Qty (quintal)", format="%.1f"),
            "Harvest Readiness": st.column_config.TextColumn("Harvest Readiness"),
            "Expected Arrival": st.column_config.TextColumn("Expected Arrival"),
            "Moisture Risk": st.column_config.TextColumn("Moisture Risk"),
        },
        height=420,
    )
    if source == "demo" and not demo:
        st.caption("Expected Arrival is a prototype estimate (sowing date + 120 days).")

    st.markdown("---")
    if st.button("Refresh procurement data"):
        bump_refresh("procurement")
        st.rerun()