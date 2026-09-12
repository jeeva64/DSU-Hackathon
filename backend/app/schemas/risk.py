from __future__ import annotations

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RiskItem(BaseModel):
    """One detected operational risk, mirroring RiskService.detect_risks() output."""

    risk_type: str
    severity: str
    dpc_id: int | None = None
    dpc_name: str | None = None
    description: str
    metric: float = 0.0


class RiskSummary(BaseModel):
    """Aggregate view of detected risks for a target date."""

    target_date: date
    total_risks: int
    critical_count: int
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)


class RiskAnalyzeRequest(BaseModel):
    target_date: date | None = Field(default=None, description="Date to analyze; defaults to today")
    dpc_id: int | None = Field(default=None, description="Optional DPC to focus on")