"""Card-style renderers for DPCs, risks and recommendations."""

from __future__ import annotations

import streamlit as st

from frontend.components.metrics import severity_pill, status_badge
from frontend.utils.formatting import (
    capacity_status,
    fmt_number,
    fmt_pct,
    operational_status_label,
    severity_color,
)

_DISTRICT_COLORS = {
    "critical": "#b00020",
    "high": "#d1495b",
    "medium": "#e07c24",
    "low": "#2e7d32",
}


def dpc_card(
    dpc: dict,
    utilization_pct: float | None = None,
    bags_received: int | None = None,
    remaining_bags: int | None = None,
) -> None:
    utilization = float(utilization_pct or dpc.get("current_utilization_pct") or 0)
    level = capacity_status(utilization)
    color = severity_color(level)
    bags = int(bags_received if bags_received is not None else dpc.get("bags_received_today") or 0)
    remaining = int(remaining_bags if remaining_bags is not None else dpc.get("remaining_capacity_bags") or 0)

    bg = "background:#ffffff;color:#263746;border:1px solid #e3e8f0;border-left:4px solid " + color + ";border-radius:8px;"

    html = (
        f'<div style="{bg};padding:12px 14px;margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div><b>{dpc.get("name", "?")}</b>'
        f'<div style="font-size:0.75rem;color:#667;">{dpc.get("district", "")} - '
        f'{operational_status_label(dpc.get("operating_status", "active"))}</div></div>'
        f'{severity_pill(level)}'
        f'</div>'
        f'<div style="margin-top:8px;">'
        f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#667;">'
        f'<span>Utilization</span><span>{fmt_pct(utilization)}</span>'
        f'</div>'
        f'<div style="background:#eef2f7;border-radius:4px;height:8px;margin-top:3px;">'
        f'<div style="background:{color};border-radius:4px;height:8px;width:{min(100, utilization)}%"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;margin-top:8px;font-size:0.78rem;">'
        f'<span>Daily capacity: <b>{fmt_number(dpc.get("daily_capacity", 0))} bags</b></span>'
        f'<span>Received: <b>{fmt_number(bags)}</b></span><span>Remaining: <b>{fmt_number(remaining)}</b></span>'
        f'</div>'
        f'</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def risk_card(risk: dict) -> None:
    risk_type = str(risk.get("risk_type") or "unknown").replace("_", " ").title()
    severity = str(risk.get("severity") or "low")
    metric = risk.get("metric")
    metric_text = f" - {fmt_pct(metric)}" if metric not in (None, "", 0) else ""

    html = (
        f'<div style="background:#ffffff;color:#263746;border:1px solid #e3e8f0;border-radius:8px;padding:10px 12px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<b>{risk_type}{metric_text}</b>{severity_pill(severity)}'
        f'</div>'
        f'<div style="font-size:0.78rem;color:#445;margin-top:4px;">{risk.get("description", "")}</div>'
        f'<div style="font-size:0.72rem;color:#889;margin-top:2px;">{risk.get("dpc_name") or "System-wide"}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def recommendation_card(rec: dict) -> None:
    priority = str(rec.get("priority") or "medium").lower()
    color = _DISTRICT_COLORS.get(priority, "#889")
    badge = status_badge(priority.upper(), color)
    title = rec.get("title") or rec.get("recommendation_type") or "Action"
    explanation = rec.get("explanation") or rec.get("expected_impact") or ""

    html = (
        f'<div style="background:#ffffff;color:#263746;border:1px solid #e3e8f0;border-radius:8px;padding:10px 12px;margin-bottom:8px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;"><b>{title}</b>{badge}</div>'
        f'<div style="font-size:0.78rem;color:#445;margin-top:4px;">{explanation}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)