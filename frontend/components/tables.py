"""Styled dataframe rendering helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def show_table(
    df: pd.DataFrame,
    column_config: dict[str, Any] | None = None,
    height: int | None = None,
) -> None:
    """Render a pandas DataFrame with optional per-column Streamlit config."""
    if df is None or df.empty:
        st.info("No data to display.")
        return
    st.dataframe(
        df,
        column_config=column_config or {},
        hide_index=True,
        use_container_width=True,
        height=height,
    )


def pct_progress(label: str) -> Any:
    """Column config that shows a value as 0-100 progress bar (value must be percent)."""
    return st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.1f%%")


def number_col(label: str, fmt: str = "%.2f") -> Any:
    return st.column_config.NumberColumn(label, format=fmt)


def status_col(label: str) -> Any:
    return st.column_config.TextColumn(label)