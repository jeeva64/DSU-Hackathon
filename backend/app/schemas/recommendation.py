from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.recommendation import (
    RecommendationPriority,
    RecommendationStatus,
    RecommendationType,
)


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_id: int | None
    date: date
    recommendation_type: RecommendationType
    priority: RecommendationPriority
    title: str
    explanation: str
    expected_impact: str
    source: str | None = None
    target: str | None = None
    farmer_count: int | None = None
    quantity: float | None = None
    feasibility_score: float | None = None
    status: RecommendationStatus
    officer_notes: str | None
    created_at: datetime
    updated_at: datetime | None


class RecommendationAnalysisRequest(BaseModel):
    target_date: date | None = Field(default=None, description="Defaults to today")
    persist: bool = Field(
        default=True,
        description="Persist generated recommendations for the officer approve/reject workflow",
    )


class RecommendationAnalysisItem(BaseModel):
    id: int | None = None
    date: date
    dpc_id: int | None = None
    recommendation_type: RecommendationType
    priority: RecommendationPriority
    title: str
    explanation: str
    expected_impact: str
    source: str | None = None
    target: str | None = None
    farmer_count: int | None = None
    quantity: float | None = None
    feasibility_score: float | None = None
    action: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)


class RecommendationApproveRequest(BaseModel):
    officer_notes: str | None = None


class RecommendationRejectRequest(BaseModel):
    officer_notes: str | None = None


class RecommendationActionResponse(BaseModel):
    id: int
    status: RecommendationStatus
    message: str
