"""Plotly chart builders. Run purely offline (bundled plotly, no CDN/web)."""

from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go

from frontend.utils.formatting import severity_color

_BASE_LAYOUT = {
    "font": {"family": "Segoe UI, Arial, sans-serif", "size": 12, "color": "#263746"},
    "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
    "paper_bgcolor": "white",
    "plot_bgcolor": "white",
    "hoverlabel": {"namelength": -1, "font": {"color": "#263746"}},
    "legend": {"font": {"color": "#263746"}},
}


def _apply_layout(fig: go.Figure, title: str | None) -> go.Figure:
    layout = dict(_BASE_LAYOUT)
    if title:
        layout["title"] = {
            "text": title,
            "x": 0.01,
            "xanchor": "left",
            "font": {"size": 15, "color": "#12395b"},
        }
    fig.update_layout(**layout)
    fig.update_xaxes(tickfont={"color": "#526475"}, title_font={"color": "#526475"})
    fig.update_yaxes(tickfont={"color": "#526475"}, title_font={"color": "#526475"})
    return fig


def hbar(df: Any, y: str, x: str, title: str | None = None,
         color_col: str | None = None, color_map: dict[str, str] | None = None) -> go.Figure:
    fig = px.bar(
        df,
        y=y,
        x=x,
        orientation="h",
        color=color_col,
        color_discrete_map=color_map,
        text=x,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(categoryorder="array", categoryarray=list(df[y])[::-1], showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor="#eef2f7")
    return _apply_layout(fig, title)


def bar(df: Any, x: str, y: str, title: str | None = None,
        color_col: str | None = None, color_map: dict[str, str] | None = None) -> go.Figure:
    fig = px.bar(df, x=x, y=y, color=color_col, color_discrete_map=color_map, text=y)
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
    return _apply_layout(fig, title)


def line(df: Any, x: str, y: str, title: str | None = None, color_col: str | None = None) -> go.Figure:
    fig = px.line(df, x=x, y=y, color=color_col, markers=True)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
    return _apply_layout(fig, title)


def pie(df: Any, names: str, values: str, title: str | None = None,
        color_map: dict[str, str] | None = None) -> go.Figure:
    fig = px.pie(df, names=names, values=values, hole=0.45, color_discrete_map=color_map)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _apply_layout(fig, title)


def gauge(value: float, title: str, color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=min(100, max(0, value)),
        number={"suffix": "%", "font": {"size": 26, "color": "#12395b"}},
        title={"text": title, "font": {"size": 13, "color": "#526475"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 70], "color": "#e8f5e9"},
                {"range": [70, 85], "color": "#fff3e0"},
                {"range": [85, 100], "color": "#fdecea"},
            ],
        },
    ))
    fig.update_layout(
        height=220,
        margin={"l": 20, "r": 20, "t": 40, "b": 10},
        paper_bgcolor="white",
        font={"color": "#263746"},
    )
    return fig


def stacked_bar(df: Any, x: str, y: str, color: str, title: str | None,
                color_map: dict[str, str] | None = None) -> go.Figure:
    fig = px.bar(df, x=x, y=y, color=color, barmode="relative", color_discrete_map=color_map)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
    return _apply_layout(fig, title)


def risk_gauge_color(severity: str) -> str:
    return severity_color(severity)