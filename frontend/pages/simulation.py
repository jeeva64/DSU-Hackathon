"""Scenario Simulation page: run "what-if" scenarios and see AI-assisted insight."""

from __future__ import annotations

import streamlit as st

from frontend.components import charts
from frontend.components.cards import recommendation_card, risk_card
from frontend.components.metrics import fallback_note, kpi_row, section_header
from frontend.config import (
    DEFAULT_SCENARIO,
    DEMO_SCENARIOS,
    DEMO_SCENARIO_PARAMS,
)
from frontend.utils.formatting import fmt_number, iso_today, severity_rank
from frontend.utils.state import get_client, demo_mode_enabled


def _demo_run(scenario_name: str) -> dict:
    """Mirror of the backend scenario engine so offline demos stay deterministic."""
    params = DEMO_SCENARIO_PARAMS.get(scenario_name, DEMO_SCENARIO_PARAMS[DEFAULT_SCENARIO])
    cap_util = params["capacity_utilization"]
    rain = params["rain_mm"]
    transport = params["transport_availability_pct"]
    labour = params["labour_availability_pct"]
    humidity = params["humidity_pct"]

    risks = []
    if cap_util > 0.85:
        risks.append({"risk_type": "overload", "severity": "critical" if cap_util > 0.95 else "high",
                      "description": f"Capacity at {cap_util*100:.0f}%", "metric": round(cap_util * 100, 1)})
    if rain > 15:
        risks.append({"risk_type": "rain", "severity": "high" if rain > 20 else "medium",
                      "description": f"Heavy rain forecast: {rain}mm", "metric": rain})
    if transport < 50:
        risks.append({"risk_type": "transport", "severity": "critical" if transport < 30 else "high",
                      "description": f"Transport at {transport}% availability", "metric": transport})
    if labour < 70:
        risks.append({"risk_type": "labour", "severity": "high" if labour < 50 else "medium",
                      "description": f"Labour at {labour}% availability", "metric": labour})
    if humidity > 80:
        risks.append({"risk_type": "moisture", "severity": "medium",
                      "description": f"High humidity ({humidity}%) increases moisture rejection risk", "metric": humidity})
    if not risks:
        risks.append({"risk_type": "none", "severity": "low", "description": "No significant risks", "metric": 0})

    arrivals = int(120 * params["arrival_multiplier"])
    bags = int(arrivals * 3)

    recommendations = []
    if cap_util > 0.85:
        recommendations.append({"title": "Divert farmers to adjacent DPCs",
                                "explanation": f"Capacity at {cap_util*100:.0f}% - overflow likely",
                                "priority": "critical", "recommendation_type": "slot"})
    if rain > 10:
        recommendations.append({"title": "Cover stored paddy with tarpaulins",
                                "explanation": f"{rain}mm rain forecast - paddy damage risk",
                                "priority": "high", "recommendation_type": "weather"})
    if transport < 50:
        recommendations.append({"title": "Arrange additional lorries immediately",
                                "explanation": f"Only {transport}% transport available",
                                "priority": "high", "recommendation_type": "resource"})
    if labour < 70:
        recommendations.append({"title": "Request temporary labour from neighbouring blocks",
                                "explanation": f"Labour at {labour}% - throughput severely reduced",
                                "priority": "medium", "recommendation_type": "resource"})
    if not recommendations:
        recommendations.append({"title": "Continue normal operations",
                                "explanation": "No critical issues detected",
                                "priority": "low", "recommendation_type": "slot"})

    return {
        "scenario_name": scenario_name,
        "risks": risks,
        "recommendations": recommendations,
        "summary": {
            "total_risks": len(risks),
            "critical_risks": len([r for r in risks if r["severity"] == "critical"]),
            "total_recommendations": len(recommendations),
            "predicted_arrivals": arrivals,
            "predicted_bags": bags,
            "capacity_utilization_pct": round(cap_util * 100, 1),
        },
        "data_source": "synthetic",
    }


def _insight_text(result: dict, params: dict) -> str:
    risks = result.get("risks", [])
    types = {r.get("risk_type") for r in risks if r.get("severity") in ("high", "critical")}
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

    arrival_mult = params.get("arrival_multiplier", 1.0)
    if arrival_mult > 1.0:
        parts.append(f"arrival volume scaled x{arrival_mult} vs normal day")
    elif arrival_mult < 0.7:
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
        if key in ("arrival_multiplier",):
            rows[label] = f"x{value}"
        elif key in ("capacity_utilization", "storage_utilization_pct"):
            rows[label] = f"{float(value) * 100:.0f}%"
        elif key in ("transport_availability_pct", "labour_availability_pct", "humidity_pct"):
            rows[label] = f"{value:.0f}%"
        elif key == "rain_mm":
            rows[label] = f"{value:.0f} mm"
    return rows


def render() -> None:
    demo = demo_mode_enabled()
    client = get_client()

    st.markdown("## Scenario Simulation")
    section_header("Prepared Scenario", "Run a what-if analysis targeting today's procurement")

    if demo:
        scenarios = DEMO_SCENARIOS
        demo_fallback = True
    else:
        scenarios, src, err = client.get_scenarios(fallback=DEMO_SCENARIOS)
        if src == "demo":
            st.caption("Demo fallback data - backend data unavailable.")
        demo_fallback = src == "demo"

    valid_names = [s.get("name") for s in scenarios if s.get("name")]
    if not valid_names:
        valid_names = [s.get("name") for s in DEMO_SCENARIOS]
    default_index = valid_names.index(DEFAULT_SCENARIO) if DEFAULT_SCENARIO in valid_names else 0

    c1, c2 = st.columns([2, 1])
    selected_name = c1.selectbox("Scenario", valid_names, index=default_index)

    selected_scenario = next((s for s in scenarios if s.get("name") == selected_name), None)
    description = selected_scenario.get("description", "") if selected_scenario else ""
    c1.caption(description)

    if st.button("Run AI Analysis", type="primary"):
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

    if demo:
        fallback_note("Simulation / Prototype Scenario - Synthetic")
    elif result_src == "demo":
        st.caption("Demo fallback data - backend scenario run unavailable.")

    if not result:
        st.info("Press **Run AI Analysis** to execute this scenario through the risk engine.")
        st.markdown("---")
        return

    summary = result.get("summary", {})
    if summary:
        kpi_row([
            ("Predicted arrivals", fmt_number(summary.get("predicted_arrivals", 0)), "farmers"),
            ("Predicted bags", fmt_number(summary.get("predicted_bags", 0)), "bags"),
            ("Capacity utilization", f"{summary.get('capacity_utilization_pct', 0):.1f}%", "projected"),
            ("Risks", fmt_number(summary.get("total_risks", 0)), None),
            ("Critical risks", fmt_number(summary.get("critical_risks", 0)), None),
        ])

    st.markdown("---")
    col_conditions, col_risks = st.columns([1, 2])

    with col_conditions:
        section_header("Current Conditions", "Simulation parameters")
        params = (selected_scenario.get("parameters") or {} ) if selected_scenario else {}
        if not params:
            params = DEMO_SCENARIO_PARAMS.get(selected_name, {})
        rows = _conditions_rows(params)
        for label, value in rows.items():
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;border-bottom:1px solid #eef2f7;'
                f'padding:3px 0;"><span style="color:#667;">{label}</span><b>{value}</b></div>',
                unsafe_allow_html=True,
            )

    with col_risks:
        section_header("AI Risk Analysis", "What the risk engine flags under this scenario")
        risks = result.get("risks", [])
        if risks:
            for r in risks:
                risk_card(r)
        else:
            st.success("No risks under this scenario.")

    st.markdown("---")
    section_header("AI-Assisted Operational Insight")
    insight = _insight_text(result, params)
    st.info(insight)

    st.markdown("---")
    col_recs, _ = st.columns([2, 1])
    with col_recs:
        section_header("Recommended Actions", "Prioritized decision support - officers decide")
        recommendations = result.get("recommendations", [])
        if recommendations:
            for rec in recommendations:
                recommendation_card(rec)
        else:
            st.info("No recommendations from the engine.")