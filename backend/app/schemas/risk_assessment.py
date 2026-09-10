from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from backend.app.models.risk_assessment import RiskSeverity, RiskType


class RiskAssessmentCreate(BaseModel):
    dpc_id: int
    date: date
    risk_type: RiskType
    severity: RiskSeverity
    score: float
    explanation: str
    mitigation: str | None = None


class RiskAssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_id: int
    date: date
    risk_type: RiskType
    severity: RiskSeverity
    score: float
    explanation: str
    mitigation: str | None
    created_at: datetime
