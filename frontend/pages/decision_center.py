"""AI Decision Center page: consolidated operational state, AI analysis,
recommendation, expected impact and officer review in one flow."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.cards import recommendation_card, risk_card
from frontend.components.metrics import fallback_note, pipeline_diagram, section_header
from frontend.components.tables import show_table
from frontend.config import DEFAULT_SCENARIO, DEMO_RISKS
from frontend.pages.simulation import demo_run
from frontend.utils.formatting import fmt_number, fmt_pct, iso_today, severity_color
from frontend.utils.state import demo_mode_enabled, get_client, refresh_key

_PAIRED_METRICS = [
    ("congestion", "congestion_relief", "System congestion", "units"),
    ("delay_hours", "delay_hours_saved", "Predicted delay", "hours"),
    ("weather_exposure", "weather_exposure_reduction_units", "Weather exposure", "units"),
    ("capacity_utilization_health", "capacity_utilization_gain", "Capacity utilization health", "ratio"),
    ("operational_balance", "balance_improvement", "Operational balance", "ratio"),
    ("resource_slack", "resource_slack_after", "Resource slack", "ratio"),
]

_TYPE_LABELS = {
    "overload": "Overload",
    "congestion": "Congestion",
    "rain": "Rain",
    "transport": "Transport",
    "labour": "Labour",
    "moisture": "Moisture",
}


@st.cache_data(ttl=20, show_spinner=False)
def _load_state(rev: int, demo: bool):
    """Read-only operational snapshot (cacheable)."""
    if demo:
        return demo_run(DEFAULT_SCENARIO), "demo", None
    client = get_client()
    dashboard, _, _ = client.get_dashboard_summary(target_date=iso_today(), fallback=None)
    if dashboard is None:
        dashboard, _, _ = client.get_dashboard_summary(target_date=iso_today(), fallback={})
    risks, src, err = client.get_risks(target_date=iso_today(), fallback=DEMO_RISKS)
    return {"dashboard": dashboard or {}, "risks": risks}, (src or "backend"), err


def _forecast_arrivals(client) -> float | None:
    payload, _, _ = client.get_prediction_forecast("arrivals", target_date=iso_today())
    if payload is None:
        return None
    if isinstance(payload, dict):
        for key in ("predicted_value", "expected_arrivals", "value"):
            if key in payload and isinstance(payload[key], (int, float)):
                return float(payload[key])
        items = payload.get("items") or []
        if items:
            first = items[0]
            for key in ("predicted_value", "expected_arrivals", "value"):
                if key in first and isinstance(first[key], (int, float)):
                    return float(first[key])
    elif isinstance(payload, list):
        if payload:
            first = payload[0]
            for key in ("predicted_value", "expected_arrivals", "value"):
                if key in first and isinstance(first[key], (int, float)):
                    return float(first[key])
    return None


def _bottlenecks_from_state(state_rows: list[dict]) -> list[dict]:
    """Derive bottleneck notices from backend DPC state fields only."""
    bottlenecks = []
    for row in state_rows or []:
        name = row.get("name") or f"DPC {row.get('dpc_id', '?')}"
        load = float(row.get("load_pct") or 0)
        if load >= 95:
            sev, label = "critical", f"{name} is critically overloaded ({load:.0f}% predicted capacity)"
        elif load >= 85:
            sev, label = "high", f"{name} is near capacity ({load:.0f}% predicted load)"
        else:
            sev, label = None, None
        if sev:
            bottlenecks.append({"type": "capacity", "severity": sev, "description": label})
        weather = str(row.get("weather_risk") or "low")
        if weather in ("high", "critical"):
            bottlenecks.append({"type": "weather", "severity": weather,
                                "description": f"{name} faces {weather} weather risk"})
        if int(row.get("transport_available") or 0) <= 0:
            bottlenecks.append({"type": "transport", "severity": "high",
                                "description": f"{name} has no transport available"})
        if int(row.get("labour_available") or 0) <= 0:
            bottlenecks.append({"type": "labour", "severity": "high",
                                "description": f"{name} has no labour available"})
    return bottlenecks


def _bottleneck_cards(bottlenecks: list[dict]) -> None:
    if not bottlenecks:
        return
    section_header(f"Detected Bottlenecks ({len(bottlenecks)})", "From backend DPC state / scenario analysis")
    for bn in bottlenecks:
        color = severity_color(bn["severity"])
        st.markdown(
            f'<div style="border-left:4px solid {color};padding:10px 14px;margin:6px 0;'
            f'background:{color}0D;border-radius:0 8px 8px 0;">'
            f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;'
            f'font-size:12px;font-weight:700;margin-right:8px;">{bn["severity"].upper()}</span>'
            f'<b>{_TYPE_LABELS.get(bn["type"], bn["type"].title())}</b>'
            f'<div style="color:#555;margin-top:4px;">{bn["description"]}</div></div>',
            unsafe_allow_html=True,
        )


def _analysis_table(items: list[dict]) -> pd.DataFrame:
    rows = []
    for it in items or []:
        rows.append({
            "Rec ID": it.get("id", "-"),
            "Date": it.get("date", "-"),
            "DPC": it.get("source") or it.get("dpc_id") or "-",
            "Priority": str(it.get("priority") or "low").upper(),
            "Type": str(it.get("recommendation_type") or "slot").title(),
            "Action": it.get("action") or it.get("title") or "-",
            "Source \u2192 Target": f"{it.get('source') or '-'} \u2192 {it.get('target') or '-'}",
            "Farmers": it.get("farmer_count", "-"),
            "Quantity": it.get("quantity", ""),
            "Feasibility": it.get("feasibility_score", "-"),
            "Expected impact": (it.get("expected_impact") or "-")[:80],
            "Status": "PENDING",
        })
    return pd.DataFrame(rows)


def _render_selected_action(selected: dict) -> None:
    if not selected:
        st.info("Optimization selected no actionable recommendation - no material action needed.")
        return
    card_input = dict(selected)
    card_input.setdefault("title", (selected.get("action") or "AI recommendation"))
    recommendation_card(card_input)


def _render_officer_review(demo: bool, client) -> None:
    section_header("Officer Decision", "Officer Review - prototype state change only; the system never schedules execution")
    pending = st.session_state.get("ns_dc_pending")

    if demo:
        st.caption("Demo mode: connect to the backend to review persisted recommendations.")
        return

    if st.button("Load pending recommendations"):
        payload, src, err = client.get_recommendations(status="pending")
        if err:
            st.session_state["ns_dc_review_notice"] = f"Could not load recommendations: {err.get('message', '')}"
            pending = []
        else:
            pending = payload or []
            st.session_state["ns_dc_review_notice"] = None
        st.session_state["ns_dc_pending"] = pending

    notice = st.session_state.get("ns_dc_review_notice")
    if notice:
        st.warning(notice)

    if not pending:
        st.info("No pending recommendations loaded. Click above to review the officer queue.")
        return

    for rec in pending:
        rec_id = rec.get("id")
        priority = str(rec.get("priority") or "medium").upper()
        rec_type = str(rec.get("recommendation_type") or "slot").replace("_", " ").title()
        dpc = rec.get("source") or rec.get("dpc_name") or rec.get("dpc_id") or "System-wide"
        title = rec.get("title") or rec.get("action")
        impact = rec.get("expected_impact") or rec.get("explanation") or ""
        with st.container(border=True):
            st.markdown(
                f"**#{rec_id}** \u00b7 {rec_type} \u00b7 {dpc} \u00b7 "
                f"<span style='color:{severity_color(str(rec.get('priority') or 'medium').lower())};'>"
                f"{priority}</span>",
                unsafe_allow_html=True,
            )
            if title:
                st.markdown(f"{title}")
            if impact:
                st.caption(impact)
            if rec.get("feasibility_score") is not None:
                st.caption(f"Feasibility: {fmt_pct(rec.get('feasibility_score'))}")
            b1, b2, _ = st.columns([1, 1, 3])
            with b1:
                if st.button("Approve", key=f"dc_approve_{rec_id}", type="primary"):
                    resp, _, err = client.approve_recommendation(rec_id)
                    if err:
                        st.session_state["ns_dc_review_notice"] = err.get("message", "Approve failed")
                    elif isinstance(resp, dict):
                        st.session_state["ns_dc_review_notice"] = resp.get("message", f"Recommendation {rec_id} approved")
                    rec["status"] = "approved"
                    st.rerun()
            with b2:
                if st.button("Reject", key=f"dc_reject_{rec_id}"):
                    resp, _, err = client.reject_recommendation(rec_id)
                    if err:
                        st.session_state["ns_dc_review_notice"] = err.get("message", "Reject failed")
                    elif isinstance(resp, dict):
                        st.session_state["ns_dc_review_notice"] = resp.get("message", f"Recommendation {rec_id} rejected")
                    rec["status"] = "rejected"
                    st.rerun()


def render() -> None:
    demo = demo_mode_enabled()
    client = get_client()
    rev = refresh_key("decision_center")

    st.markdown("## AI Decision Center")
    st.caption("Consolidated operational picture, AI recommendation and officer review.")

    pipeline_diagram([
        ("OPERATIONAL STATE", "live + predicted"),
        ("AI ANALYSIS", "predictions \u00b7 risks \u00b7 bottlenecks"),
        ("RECOMMENDED ACTION", "slot / resource adjustment"),
        ("EXPECTED IMPACT", "before \u2192 after"),
        ("OFFICER DECISION", "approve / reject"),
    ])

    if demo:
        fallback_note("Prototype / Synthetic Data - deterministic offline analysis")
    else:
        st.caption("Backend values when available; unpopulated fields show '- (run optimization)'.")

    snapshot, source, _ = _load_state(rev, demo)

    # ── 1. CURRENT OPERATIONAL STATE ─────────────────────────────────
    section_header("Current Operational State", "Where the system stands right now")
    demo_state = demo_run(DEFAULT_SCENARIO)
    dashboard = (snapshot or {}).get("dashboard") or {}
    risks = (snapshot or {}).get("risks") or demo_state["risks"]
    opt = st.session_state.get("ns_dc_optimize") or {}

    demo_before = demo_state["before_state"] if "before_state" in demo_state else {}
    expected_arrivals = _forecast_arrivals(client) if not demo else demo_before.get("expected_arrivals")
    expected_arrivals = expected_arrivals if expected_arrivals is not None else dashboard.get("total_farmers")

    avg_util = dashboard.get("average_utilization_pct") if dashboard else demo_before.get("capacity_utilization_pct")
    queue_risk = next((r for r in risks if r.get("risk_type") == "congestion"), None)
    queue_pressure = (queue_risk.get("severity") or "").capitalize() if queue_risk else (
        demo_before.get("queue_pressure") if demo_before else "-")

    weather_risk = next((r for r in risks if r.get("risk_type") == "rain"), None)
    transport_avail = opt.get("transport_available")
    labour_avail = opt.get("labour_available")
    storage_avail = opt.get("storage_available")

    st_metrics = [
        ("Expected arrivals", fmt_number(expected_arrivals) if expected_arrivals is not None else "-", "farmers"),
        ("Expected procurement", fmt_number(dashboard.get("procured_today_bags")) if dashboard else
         fmt_number(demo_before.get("expected_bags")), "bags"),
        ("DPC utilization", f"{avg_util:.1f}%" if avg_util is not None else "-", "avg"),
        ("Queue pressure", queue_pressure or "-", None),
        ("Weather risk", f"{weather_risk.get('severity','-').upper()} ({weather_risk.get('metric','')} mm)"
         if weather_risk else ("-" if demo is False else f"{demo_before.get('rainfall_risk_mm')} mm"), None),
        ("Transport availability", f"{transport_avail} trucks" if transport_avail is not None
         else f"{demo_before.get('transport_availability_pct')}%" if demo_before else "-", None),
        ("Labour availability", f"{labour_avail} staff" if labour_avail is not None
         else f"{demo_before.get('labour_availability_pct')}%" if demo_before else "-", None),
        ("Storage availability", f"{storage_avail} tonnes" if storage_avail is not None
         else f"{demo_before.get('storage_utilization_pct')}% used" if demo_before else "-", None),
    ]
    cols = st.columns(4)
    for i, (label, value, sub) in enumerate(st_metrics):
        cols[i % 4].metric(label, value, sub)

    # ── 2. AI ANALYSIS ───────────────────────────────────────────────
    st.markdown("---")
    section_header("AI Analysis", "Predictions, risk assessments and detected bottlenecks")

    c_risks, c_bn = st.columns([2, 1])
    with c_risks:
        section_header("Risk Assessments", "From the operational risk engine")
        if risks:
            for r in risks:
                risk_card(r)
        else:
            st.success("No risks detected.")

    with c_bn:
        if demo:
            _bottleneck_cards(demo_state.get("bottlenecks") or [])
        elif opt.get("current_state"):
            _bottleneck_cards(_bottlenecks_from_state(opt["current_state"]))
        else:
            st.caption("Bottlenecks appear here after running AI optimization.")

    # ── 3. RECOMMENDED ACTION ────────────────────────────────────────
    st.markdown("---")
    section_header("Recommended Action", "Slot / resource adjustment proposed by the engine")

    c_opt, c_an = st.columns(2)
    with c_opt:
        if st.button("Run AI Optimization", type="primary", use_container_width=True):
            if demo:
                st.session_state["ns_dc_opt_notice"] = "Demo mode: connect to the backend to run optimization."
                st.session_state["ns_dc_optimize"] = None
            else:
                payload, src, err = client.optimize_recommendations(persist=True)
                if err:
                    st.session_state["ns_dc_opt_notice"] = err.get("message", "Optimization unavailable")
                    st.session_state["ns_dc_optimize"] = None
                else:
                    st.session_state["ns_dc_opt_notice"] = None
                    st.session_state["ns_dc_optimize"] = payload or {}
                    st.session_state["ns_dc_analysis_items"] = None
        if st.session_state.get("ns_dc_opt_notice"):
            st.caption(st.session_state["ns_dc_opt_notice"])

    with c_an:
        if st.button("Generate Slot Recommendations", use_container_width=True):
            if demo:
                st.session_state["ns_dc_an_notice"] = "Demo mode: connect to the backend to generate recommendations."
                st.session_state["ns_dc_analysis_items"] = None
            else:
                payload, src, err = client.analyze_recommendations(persist=True)
                if err:
                    st.session_state["ns_dc_an_notice"] = err.get("message", "Recommendation engine unavailable")
                    st.session_state["ns_dc_analysis_items"] = None
                else:
                    st.session_state["ns_dc_an_notice"] = None
                    st.session_state["ns_dc_analysis_items"] = payload or []
        if st.session_state.get("ns_dc_an_notice"):
            st.caption(st.session_state["ns_dc_an_notice"])

    if demo:
        demo_recs = [r for r in demo_state.get("recommendations", []) if r.get("priority") != "low"]
        if demo_recs:
            _render_selected_action(demo_recs[0])

    opt = st.session_state.get("ns_dc_optimize") or {}
    if opt.get("selected_recommendation"):
        section_header("Selected Recommendation", "Optimization engine's chosen action")
        _render_selected_action(opt["selected_recommendation"])
        if opt.get("reasons"):
            st.markdown("**Why:** " + " ".join(f"- {r}" for r in opt["reasons"]))
        st.caption("Approve or reject this recommendation in the Officer Review section below.")

    items = st.session_state.get("ns_dc_analysis_items")
    if items is not None:
        section_header("Slot Recommendation View", "Generated by POST /recommendations/analyze")
        if items:
            show_table(_analysis_table(items), height=240)
        else:
            st.info("Recommendation engine returned no suggestions for today.")

    # ── 4. EXPECTED IMPACT ───────────────────────────────────────────
    st.markdown("---")
    section_header("Expected Impact", "Before vs after - values are backend-computed, never invented")

    if demo and demo_state.get("before_state") and demo_state.get("after_state"):
        b = demo_state["before_state"]
        a = demo_state["after_state"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### BEFORE")
            st.metric("Capacity utilization", f"{b.get('capacity_utilization_pct', 0):.1f}%")
            st.metric("Queue pressure", b.get("queue_pressure", "-"))
            st.metric("Transport availability", f"{b.get('transport_availability_pct', 0)}%")
        with c2:
            st.markdown("#### AFTER RECOMMENDATION")
            st.metric("Improved capacity utilization", f"{a.get('improved_capacity_utilization_pct', 0):.1f}%")
            st.metric("Congestion reduction", f"{a.get('expected_congestion_reduction_pct', 0)}%")
            st.metric("Reduced risk", a.get("reduced_risk", "-"))
        st.caption("Synthetic demo impact - deterministic offline analysis, not backend metrics.")
    elif not opt:
        st.info("Run **AI Optimization** to see backend-computed before/after metrics.")
    else:
        baseline = opt.get("baseline") or {}
        improvement = opt.get("expected_improvement") or {}
        rows = []
        for baseline_key, improvement_key, label, unit in _PAIRED_METRICS:
            if baseline_key not in baseline and improvement_key not in improvement:
                continue
            rows.append({
                "Metric": label,
                "Baseline (before)": baseline.get(baseline_key, "-"),
                "Expected change / after": improvement.get(improvement_key, "-"),
                "Unit": unit,
            })
        if rows:
            show_table(pd.DataFrame(rows), height=200)

        state_rows = opt.get("current_state") or []
        if state_rows:
            section_header("Current DPC State", "Backend optimization snapshot")
            df_state = pd.DataFrame([{
                "DPC": r.get("name") or f"DPC {r.get('dpc_id', '?')}",
                "District": r.get("district", ""),
                "Load %": float(r.get("load_pct") or 0),
                "Congestion %": float(r.get("congestion_pct") or 0),
                "Predicted arrivals": fmt_number(r.get("predicted_arrivals")),
                "Weather": str(r.get("weather_risk") or "-").title(),
                "Free slots": r.get("free_slots", "-"),
                "Urgent farmers": r.get("urgent_farmers", "-"),
            } for r in state_rows])
            show_table(df_state, height=200)

    # ── 5. OFFICER DECISION ──────────────────────────────────────────
    st.markdown("---")
    _render_officer_review(demo, client)

    if demo:
        fallback_note("Prototype / Synthetic Data - buttons change prototype state only")

    st.markdown("---")
    if st.button("Reset decision center"):
        for key in ("ns_dc_optimize", "ns_dc_analysis_items", "ns_dc_pending",
                    "ns_dc_opt_notice", "ns_dc_an_notice", "ns_dc_review_notice"):
            st.session_state.pop(key, None)
        st.rerun()