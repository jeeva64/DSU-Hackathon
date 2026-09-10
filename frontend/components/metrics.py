"""Reusable metric / status components rendered via Streamlit primitives."""

from __future__ import annotations

import streamlit as st

from frontend.utils.formatting import severity_color, severity_label


def kpi_row(items: list[tuple[str, str, str | None]]) -> None:
    """Render a row of KPI metrics. Each item: (label, value, subtext)."""
    cols = st.columns(len(items))
    for col, (label, value, subtext) in zip(cols, items):
        col.metric(label=label, value=value, delta=subtext or None)


def severity_pill(severity: str) -> str:
    color = severity_color(severity)
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}66;'
        f'border-radius:10px;padding:1px 10px;font-size:0.75rem;font-weight:600;">'
        f"{severity_label(severity)}</span>"
    )


def status_badge(text: str, hex_color: str) -> str:
    return (
        f'<span style="background:{hex_color}22;color:{hex_color};border:1px solid {hex_color}66;'
        f'border-radius:10px;padding:1px 10px;font-size:0.75rem;font-weight:600;">{text}</span>'
    )


def section_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"#### {title}")
    if subtitle:
        st.caption(subtitle)


def fallback_note(message: str = "Prototype / Synthetic Data") -> None:
    st.markdown(
        f'<span style="color:#8a5a00;background:#fff4e0;border:1px solid #e0a800;'
        f'border-radius:10px;padding:2px 12px;font-size:0.75rem;font-weight:600;">{message}</span>',
        unsafe_allow_html=True,
    )


def pipeline_diagram(steps: list[tuple[str, str]]) -> None:
    """Render a horizontal pipeline diagram (e.g. Data -> ML -> Risk -> Insight)."""
    html_parts = []
    for index, (title, subtitle) in enumerate(steps):
        html_parts.append(
            f'<div style="flex:1;background:#f3f6fb;border:1px solid #d7deea;border-radius:8px;'
            f'padding:8px 10px;text-align:center;">'
            f'<div style="font-weight:600;font-size:0.85rem;">{title}</div>'
            f'<div style="font-size:0.68rem;color:#667;">{subtitle}</div></div>'
        )
        if index < len(steps) - 1:
            html_parts.append('<div style="padding:0 4px;color:#889;">&#8594;</div>')
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;margin:6px 0 16px 0;">{"".join(html_parts)}</div>',
        unsafe_allow_html=True,
    )