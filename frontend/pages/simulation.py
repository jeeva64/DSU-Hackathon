"""Scenario Simulation page: run "what-if" scenarios and see AI-assisted insight."""

from __future__ import annotations

import streamlit as st

from frontend.components.cards import risk_card
from frontend.components.metrics import (
    fallback_note,
    kpi_row,
    pipeline_diagram,
    section_header,
    severity_pill,
    status_badge,
)
from frontend.config import (
    DEFAULT_SCENARIO,
    DEMO_SCENARIOS,
    DEMO_SCENARIO_PARAMS,
)
from frontend.utils.formatting import fmt_number, fmt_pct, severity_color, severity_rank
from frontend.utils.state import get_client, demo_mode_enabled


# ── Deterministic helpers (pure, no API) ──────────────────────────────


def _risk_level(capacity_pct: float) -> str:
    if capacity_pct > 95:
        return "Critical"
    if capacity_pct > 85:
        return "High"
    if capacity_pct > 70:
        return "Medium"
    return "Low"


def _compute_before_state(params: dict) -> dict:
    """Derive BEFORE state from scenario params."""
    arrivals = int(120 * params["arrival_multiplier"])
    capacity_pct = params["capacity_utilization"] * 100
    queue = "High" if capacity_pct > 85 else ("Medium" if capacity_pct > 70 else "Low")
    return {
        "expected_arrivals": arrivals,
        "expected_bags": arrivals * 3,
        "capacity_utilization_pct": round(capacity_pct, 1),
        "queue_pressure": queue,
        "transport_availability_pct": params["transport_availability_pct"],
        "rainfall_risk_mm": params["rain_mm"],
        "labour_availability_pct": params["labour_availability_pct"],
        "storage_utilization_pct": params["storage_utilization_pct"],
    }


def _compute_after_state(params: dict, recommendations: list[dict]) -> dict:
    """Simulate post-recommendation state (deterministic heuristic)."""
    before = _compute_before_state(params)
    slot_recs = [r for r in recommendations if r.get("recommendation_type") == "slot"]
    resource_recs = [r for r in recommendations if r.get("recommendation_type") == "resource"]
    weather_recs = [r for r in recommendations if r.get("recommendation_type") == "weather"]

    redistributed_pct = min(40, len(slot_recs) * 18)
    new_capacity = max(35, before["capacity_utilization_pct"] - redistributed_pct)
    congestion_reduction = min(65, len(recommendations) * 14)
    transport_improvement = min(70, len(resource_recs) * 18)
    new_transport = min(100, before["transport_availability_pct"] + transport_improvement)
    rain_mitigated = len(weather_recs) > 0

    if redistributed_pct > 0:
        new_risk = _risk_level(new_capacity)
    else:
        new_risk = _risk_level(before["capacity_utilization_pct"])

    return {
        "redistributed_slots": f"{redistributed_pct}% of arrivals redistributed",
        "changed_allocation": f"{len(slot_recs)} DPC{'s' if len(slot_recs) != 1 else ''} rebalanced",
        "expected_congestion_reduction_pct": congestion_reduction,
        "improved_capacity_utilization_pct": round(new_capacity, 1),
        "reduced_risk": new_risk,
        "transport_availability_pct": new_transport,
        "rainfall_mitigated": rain_mitigated,
    }


def _detect_bottlenecks(params: dict) -> list[dict]:
    """Identify operational bottlenecks from scenario params."""
    bottlenecks = []
    if params["transport_availability_pct"] < 50:
        sev = "critical" if params["transport_availability_pct"] < 30 else "high"
        bottlenecks.append({"type": "transport", "severity": sev,
                            "description": f"Transport at {params['transport_availability_pct']}% — "
                                           f"insufficient for paddy movement between DPC and godown"})
    if params["capacity_utilization"] > 0.85:
        sev = "critical" if params["capacity_utilization"] > 0.95 else "high"
        bottlenecks.append({"type": "capacity", "severity": sev,
                            "description": f"DPC capacity at {params['capacity_utilization']*100:.0f}% — "
                                           f"processing bottleneck likely"})
    if params["rain_mm"] > 15:
        sev = "high" if params["rain_mm"] > 20 else "medium"
        bottlenecks.append({"type": "weather", "severity": sev,
                            "description": f"Rainfall forecast {params['rain_mm']}mm — "
                                           f"procurement and stored paddy at risk"})
    if params["labour_availability_pct"] < 70:
        sev = "high" if params["labour_availability_pct"] < 50 else "medium"
        bottlenecks.append({"type": "labour", "severity": sev,
                            "description": f"Labour at {params['labour_availability_pct']}% — "
                                           f"throughput severely reduced"})
    return bottlenecks


def _calculate_impact(before: dict, after: dict) -> dict:
    """Compute expected improvement metrics."""
    return {
        "capacity_improvement_pct": round(before["capacity_utilization_pct"] - after["improved_capacity_utilization_pct"], 1),
        "transport_improvement_pct": round(after["transport_availability_pct"] - before["transport_availability_pct"], 1),
        "congestion_reduction_pct": after["expected_congestion_reduction_pct"],
        "risk_level_change": f"{_risk_level(before['capacity_utilization_pct'])} → {after['reduced_risk']}",
    }


# ── Scenario engine (deterministic offline mirror) ────────────────────


def _demo_run(scenario_name: str) -> dict:
    """Run the full analysis pipeline locally so demos stay fast + deterministic."""
    params = DEMO_SCENARIO_PARAMS.get(scenario_name, DEMO_SCENARIO_PARAMS[DEFAULT_SCENARIO])
    cap = params["capacity_utilization"]
    rain = params["rain_mm"]
    transport = params["transport_availability_pct"]
    labour = params["labour_availability_pct"]
    humidity = params["humidity_pct"]

    # 1. Risks
    risks = []
    if cap > 0.85:
        risks.append({"risk_type": "overload", "severity": "critical" if cap > 0.95 else "high",
                       "dpc_name": "DPC-02",
                       "description": f"DPC-02 at {cap*100:.0f}% predicted capacity",
                       "metric": round(cap * 100, 1)})
    if rain > 15:
        risks.append({"risk_type": "rain", "severity": "high" if rain > 20 else "medium",
                       "dpc_name": "System-wide",
                       "description": f"Heavy rain forecast: {rain}mm",
                       "metric": rain})
    if transport < 50:
        risks.append({"risk_type": "transport", "severity": "critical" if transport < 30 else "high",
                       "dpc_name": "System-wide",
                       "description": f"Transport at {transport}% availability",
                       "metric": transport})
    if labour < 70:
        risks.append({"risk_type": "labour", "severity": "high" if labour < 50 else "medium",
                       "dpc_name": "System-wide",
                       "description": f"Labour at {labour}% availability",
                       "metric": labour})
    if humidity > 80:
        risks.append({"risk_type": "moisture", "severity": "medium",
                       "dpc_name": "System-wide",
                       "description": f"High humidity ({humidity}%) increases moisture rejection risk",
                       "metric": humidity})
    if not risks:
        risks.append({"risk_type": "none", "severity": "low", "dpc_name": "System-wide",
                       "description": "No significant risks", "metric": 0})
    risks.sort(key=lambda r: severity_rank(r["severity"]))

    arrivals = int(120 * params["arrival_multiplier"])
    bags = arrivals * 3

    # 2. Recommendations
    recommendations = []
    if cap > 0.85:
        pri = "critical" if cap > 0.95 else "high"
        recommendations.append({
            "id": 1, "recommendation_type": "slot", "priority": pri,
            "title": "Redistribute arrivals at DPC-02",
            "explanation": f"DPC-02 predicted at {cap*100:.0f}% capacity. "
                           f"Redistribute selected arrivals to available later slots or neighbouring DPC capacity.",
            "expected_impact": "Reduced congestion and improved capacity utilization.",
            "dpc_name": "DPC-02",
        })
    if rain > 10:
        recommendations.append({
            "id": 2, "recommendation_type": "weather", "priority": "high",
            "title": "Deploy tarpaulins and pre-position cover",
            "explanation": f"Rainfall forecast: {rain}mm. Protect stored paddy and cover open procurement areas.",
            "expected_impact": "Reduced moisture damage and quality loss.",
            "dpc_name": "System-wide",
        })
    if transport < 50:
        recommendations.append({
            "id": 3, "recommendation_type": "resource", "priority": "high",
            "title": "Arrange additional transport immediately",
            "explanation": f"Transport availability at {transport}%. Coordinate with nearby DPCs for shared logistics.",
            "expected_impact": "Improved paddy movement and reduced bottleneck.",
            "dpc_name": "System-wide",
        })
    if labour < 70:
        recommendations.append({
            "id": 4, "recommendation_type": "resource", "priority": "medium",
            "title": "Deploy temporary labour from neighbouring blocks",
            "explanation": f"Labour at {labour}% — throughput severely reduced.",
            "expected_impact": "Faster processing and reduced queue wait time.",
            "dpc_name": "System-wide",
        })
    if not recommendations:
        recommendations.append({
            "id": 0, "recommendation_type": "slot", "priority": "low",
            "title": "Continue normal operations",
            "explanation": "No critical issues detected. Maintain current procurement schedule.",
            "expected_impact": "Standard operations maintained.",
            "dpc_name": "System-wide",
        })

    # 3. Before / after / bottlenecks / impact
    before = _compute_before_state(params)
    after = _compute_after_state(params, recommendations)
    bottlenecks = _detect_bottlenecks(params)
    impact = _calculate_impact(before, after)

    return {
        "scenario_name": scenario_name,
        "risks": risks,
        "recommendations": recommendations,
        "summary": {
            "total_risks": len([r for r in risks if r["risk_type"] != "none"]),
            "critical_risks": len([r for r in risks if r["severity"] == "critical"]),
            "total_recommendations": len([r for r in recommendations if r["priority"] != "low"]),
            "predicted_arrivals": arrivals,
            "predicted_bags": bags,
            "capacity_utilization_pct": before["capacity_utilization_pct"],
        },
        "before_state": before,
        "after_state": after,
        "bottlenecks": bottlenecks,
        "impact": impact,
        "data_source": "synthetic",
    }


def demo_run(scenario_name: str = DEFAULT_SCENARIO) -> dict:
    """Public wrapper around the deterministic offline analysis engine."""
    return _demo_run(scenario_name)


# ── Insight / conditions formatters ───────────────────────────────────


def _insight_text(result: dict, params: dict) -> str:
    types = {r.get("risk_type") for r in result.get("risks", []) if r.get("severity") in ("high", "critical")}
    parts = []
    if "overload" in types:
        parts.append("predicted capacity exceeds safe thresholds")
    if "rain" in types:
        parts.append("rain risk threatens stored paddy and transport")
    if "transport" in types:
        parts.append("transport availability is a binding constraint")
    if "labour" in types:
        parts.append("labour shortage limits throughput")
    if "moisture" in types:
        parts.append("high humidity raises moisture-rejection odds")
    mult = params.get("arrival_multiplier", 1.0)
    if mult > 1.0:
        parts.append(f"arrival volume scaled x{mult} vs normal day")
    elif mult < 0.7:
        parts.append("arrival volume scaled below normal")
    if parts:
        return "AI-Assisted Operational Insight: " + ". ".join(parts).capitalize() + "."
    return "AI-Assisted Operational Insight: no critical conditions detected; proceed with normal operations."


def _conditions_rows(params: dict) -> dict:
    keys = {
        "arrival_multiplier": "Arrival multiplier",
        "capacity_utilization": "Capacity utilization",
        "rain_mm": "Rain (mm)",
        "transport_availability_pct": "Transport availability",
        "labour_availability_pct": "Labour availability",
        "storage_utilization_pct": "Storage utilization",
        "humidity_pct": "Humidity",
    }
    rows = {}
    for key, label in keys.items():
        value = params.get(key)
        if value is None:
            continue
        if key == "arrival_multiplier":
            rows[label] = f"x{value}"
        elif key in ("capacity_utilization", "storage_utilization_pct"):
            rows[label] = f"{float(value) * 100:.0f}%"
        elif key in ("transport_availability_pct", "labour_availability_pct", "humidity_pct"):
            rows[label] = f"{value:.0f}%"
        elif key == "rain_mm":
            rows[label] = f"{value:.0f} mm"
    return rows


# ── UI sub-renderers ─────────────────────────────────────────────────


def _render_bottlenecks(bottlenecks: list[dict]) -> None:
    section_header(f"Bottlenecks Detected ({len(bottlenecks)})", "Operational constraints limiting throughput")
    for bn in bottlenecks:
        color = severity_color(bn["severity"])
        st.markdown(
            f'<div style="border-left:4px solid {color};padding:12px 16px;margin:8px 0;'
            f'background:{color}0D;color:#263746;border-radius:0 8px 8px 0;">'
            f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;'
            f'font-size:12px;font-weight:700;margin-right:8px;">{bn["severity"].upper()}</span>'
            f'<span style="font-weight:600;">{bn["type"].title()}</span>'
            f'<div style="color:#555;margin-top:4px;">{bn["description"]}</div></div>',
            unsafe_allow_html=True,
        )


def _render_before_after(before: dict, after: dict, impact: dict) -> None:
    section_header("Before vs After Recommendation", "COMBINED CRISIS — projected impact of recommended actions")
    c_before, c_after = st.columns(2)

    with c_before:
        st.markdown("#### BEFORE")
        st.metric("Expected Arrivals", fmt_number(before["expected_arrivals"]))
        st.metric("DPC Capacity", f"{before['capacity_utilization_pct']:.1f}%")
        st.metric("Queue Pressure", before["queue_pressure"])
        st.metric("Transport Availability", f"{before['transport_availability_pct']}%")
        st.metric("Rainfall Risk", f"{before['rainfall_risk_mm']} mm")

    with c_after:
        st.markdown("#### AFTER RECOMMENDATION")
        st.metric("Redistributed Slots", after["redistributed_slots"])
        st.metric("Changed Allocation", after["changed_allocation"])
        st.metric("Expected Congestion Reduction", f"{after['expected_congestion_reduction_pct']}%")
        st.metric("Improved Capacity Utilization", f"{after['improved_capacity_utilization_pct']:.1f}%")
        st.metric("Reduced Risk", after["reduced_risk"])

    st.info(
        f"**Expected Impact:** Capacity improvement {impact['capacity_improvement_pct']}%  |  "
        f"Transport improvement {impact['transport_improvement_pct']}%  |  "
        f"Risk level: {impact['risk_level_change']}"
    )


def _render_recommendation_panel(rec: dict, demo: bool, client) -> None:
    """Render a single highly-visible recommendation card with officer action buttons."""
    priority = rec.get("priority", "medium")
    pcolor = {"critical": "#b00020", "high": "#d1495b", "medium": "#e07c24", "low": "#2e7d32"}.get(priority, "#666")
    rec_id = rec.get("id", 0)
    rec_type = (rec.get("recommendation_type") or "").title()

    st.markdown(
        f'<div style="border:2px solid {pcolor};border-radius:12px;padding:20px 24px;margin:10px 0;'
        f'background:linear-gradient(135deg,{pcolor}06,{pcolor}10);color:#263746;">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">'
        f'{status_badge(f"{priority.upper()} PRIORITY", pcolor)}'
        f'<span style="color:#888;font-size:13px;">{rec_type}</span>'
        f'</div>'
        f'<h4 style="margin:0 0 8px 0;">{rec.get("title", "Recommendation")}</h4>'
        f'<p style="margin:0 0 6px 0;"><b>Recommended action:</b> {rec.get("explanation", "")}</p>'
        f'<p style="margin:0 0 6px 0;"><b>Reason:</b> Predicted arrivals exceed available processing capacity '
        f'while transport availability is constrained.</p>'
        f'<p style="margin:0 0 10px 0;"><b>Expected impact:</b> {rec.get("expected_impact", "")}</p>'
        f'<p style="margin:0;color:#888;font-size:13px;"><b>Officer action:</b></p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    b1, b2, _ = st.columns([1, 1, 3])
    with b1:
        if st.button("Approve Recommendation", key=f"sim_approve_{rec_id}", type="primary"):
            if not demo and rec_id:
                resp, _, _ = client.approve_recommendation(rec_id)
            st.success(f"Recommendation {rec_id} approved (prototype state only)")
    with b2:
        if st.button("Reject Recommendation", key=f"sim_reject_{rec_id}"):
            if not demo and rec_id:
                resp, _, _ = client.reject_recommendation(rec_id)
            st.warning(f"Recommendation {rec_id} rejected (prototype state only)")


# ── Main render ───────────────────────────────────────────────────────


def render() -> None:
    demo = demo_mode_enabled()
    client = get_client()

    st.markdown("## Scenario Simulation")

    # Scenario selection
    if demo:
        scenarios = DEMO_SCENARIOS
        demo_fallback = True
    else:
        scenarios, src, _ = client.get_scenarios(fallback=DEMO_SCENARIOS)
        demo_fallback = src == "demo"

    valid_names = [s.get("name") for s in scenarios if s.get("name")]
    if not valid_names:
        valid_names = [s.get("name") for s in DEMO_SCENARIOS]
    default_index = valid_names.index(DEFAULT_SCENARIO) if DEFAULT_SCENARIO in valid_names else 0

    c_sel, c_desc = st.columns([2, 1])
    selected_name = c_sel.selectbox("Scenario", valid_names, index=default_index)
    selected_scenario = next((s for s in scenarios if s.get("name") == selected_name), None)
    c_desc.caption(selected_scenario.get("description", "") if selected_scenario else "")

    # Run analysis
    if st.button("Run AI Analysis", type="primary", use_container_width=True):
        with st.spinner("Running AI analysis pipeline..."):
            if demo or demo_fallback:
                result = _demo_run(selected_name)
            else:
                result, r_src, r_err = client.run_scenario(selected_name, fallback=_demo_run(selected_name))
            st.session_state["ns_sim_result"] = result
            st.session_state["ns_sim_source"] = "demo" if (demo or demo_fallback) else "backend"

    result = st.session_state.get("ns_sim_result")
    if demo:
        result = result or _demo_run(selected_name)
    result_src = st.session_state.get("ns_sim_source", "demo" if demo else None)

    if not result:
        st.info("Select a scenario and click **Run AI Analysis** to begin the analysis.")
        return

    params = DEMO_SCENARIO_PARAMS.get(result.get("scenario_name", selected_name), {})

    # Source banner
    if demo:
        fallback_note("Prototype / Synthetic Data — deterministic local analysis")
    elif result_src == "demo":
        st.caption("Demo fallback data — backend scenario run unavailable.")

    # ── Pipeline diagram ──────────────────────────────────────────────
    bottlenecks = result.get("bottlenecks", [])
    n_recs = result["summary"].get("total_recommendations", 0)
    pipeline_diagram([
        ("Load Scenario", "Loaded"),
        ("Update Conditions", "Applied"),
        ("ML Predictions", "Generated"),
        ("Risk Analysis", f"{result['summary']['total_risks']} risks"),
        ("Bottleneck Detection", f"{len(bottlenecks)} found"),
        ("Recommendations", f"{n_recs} generated"),
        ("Impact Assessment", "Calculated"),
    ])

    # ── KPIs ──────────────────────────────────────────────────────────
    summary = result.get("summary", {})
    kpi_row([
        ("Predicted Arrivals", fmt_number(summary.get("predicted_arrivals", 0)), "farmers"),
        ("Predicted Bags", fmt_number(summary.get("predicted_bags", 0)), "bags"),
        ("Capacity Utilization", f"{summary.get('capacity_utilization_pct', 0):.1f}%", "projected"),
        ("Risks Detected", str(summary.get("total_risks", 0)), None),
        ("Critical Risks", str(summary.get("critical_risks", 0)), None),
        ("Recommendations", str(n_recs), None),
    ])

    # ── Conditions ────────────────────────────────────────────────────
    st.markdown("---")
    section_header("Operational Conditions", "Scenario parameters applied")
    cond_rows = _conditions_rows(params)
    cols = st.columns(4)
    for i, (label, value) in enumerate(cond_rows.items()):
        cols[i % 4].metric(label, value)

    # ── Bottlenecks ───────────────────────────────────────────────────
    if bottlenecks:
        st.markdown("---")
        _render_bottlenecks(bottlenecks)

    # ── Risks ─────────────────────────────────────────────────────────
    st.markdown("---")
    section_header("AI Risk Analysis", "What the risk engine flags under this scenario")
    risks = result.get("risks", [])
    if risks:
        rc = st.columns(min(3, len(risks)))
        for i, r in enumerate(risks):
            with rc[i % len(rc)]:
                risk_card(r)
    else:
        st.success("No risks under this scenario.")

    # ── Insight ───────────────────────────────────────────────────────
    st.markdown("---")
    section_header("AI-Assisted Operational Insight")
    st.info(_insight_text(result, params))

    # ── BEFORE / AFTER (COMBINED CRISIS only) ─────────────────────────
    if result.get("before_state") and result.get("after_state"):
        st.markdown("---")
        _render_before_after(result["before_state"], result["after_state"], result.get("impact", {}))

    # ── Recommendations (highly visible panel) ────────────────────────
    st.markdown("---")
    section_header("Recommended Actions", "Prioritized decision support — officers decide")
    recommendations = result.get("recommendations", [])
    if recommendations:
        for rec in recommendations:
            _render_recommendation_panel(rec, demo, client)
    else:
        st.info("No recommendations from the engine.")

    # ── Source footer ──────────────────────────────────────────────────
    if demo:
        fallback_note("Prototype / Synthetic Data — buttons change prototype state only")
