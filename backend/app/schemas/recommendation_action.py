from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationActionCreate(BaseModel):
    recommendation_id: int
    action: str
    source_dpc_id: int | None = None
    target_dpc_id: int | None = None
    source_slot_id: int | None = None
    target_slot_id: int | None = None
    quantity: float | None = None
    rationale: str


class RecommendationActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int
    action: str
    source_dpc_id: int | None
    target_dpc_id: int | None
    source_slot_id: int | None
    target_slot_id: int | None
    quantity: float | None
    rationale: str
    created_at: datetime
