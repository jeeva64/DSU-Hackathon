from __future__ import annotations

from pydantic import BaseModel


class RiskItem(BaseModel):
    """One detected operational risk, mirroring RiskService.detect_risks() output."""

    risk_type: str
    severity: str
    dpc_id: int | None = None
    dpc_name: str | None = None
    description: str
    metric: float = 0.0