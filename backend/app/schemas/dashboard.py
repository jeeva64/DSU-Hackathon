from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """Aggregated operational snapshot for the dashboard."""

    date: date
    total_farmers: int
    total_dpcs: int
    active_dpcs: int
    total_daily_capacity: int
    average_utilization_pct: float
    procured_today_bags: int
    procured_today_quantity: float
    pending_recommendations: int
    open_risks: int
    critical_risks: int
    risk_by_severity: dict[str, int] = Field(default_factory=dict)
    ml_trained: bool = False