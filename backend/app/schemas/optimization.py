from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class OptimizationRequest(BaseModel):
    target_date: date | None = Field(default=None, description="Defaults to today")
    persist: bool = Field(
        default=True,
        description="Persist the single best action for the officer approve/reject workflow",
    )


class DpcStateRead(BaseModel):
    dpc_id: int
    name: str
    code: str | None = None
    district: str
    operating_status: str
    load_pct: float
    congestion_pct: float
    predicted_arrivals: float
    predicted_quantity: float
    weather_risk: str
    labour_available: int
    transport_available: int
    weighing_capacity: int
    storage_available: float | None = None
    free_slots: int
    urgent_farmers: int


class CandidateActionRead(BaseModel):
    id: int | None = Field(default=None, description="Recommendation id when the action was persisted")
    action: str
    title: str
    explanation: str
    expected_impact: str
    source: str
    target: str
    priority: str
    farmer_count: int
    quantity: float
    feasible: bool
    infeasible_reason: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    expected_improvement: dict[str, float] = Field(default_factory=dict)


class OptimizationResultRead(BaseModel):
    target_date: date
    current_state: list[DpcStateRead]
    baseline: dict[str, float]
    candidate_actions: list[CandidateActionRead]
    selected_recommendation: CandidateActionRead | None = None
    reasons: list[str] = Field(default_factory=list)
    expected_improvement: dict[str, float] = Field(default_factory=dict)