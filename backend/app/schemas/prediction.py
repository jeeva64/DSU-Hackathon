from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.prediction import PredictionType


class PredictionGenerateRequest(BaseModel):
    dpc_id: int
    target_date: date
    prediction_type: PredictionType = PredictionType.arrival_count
    history_days: int = Field(default=30, ge=7, le=90)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_id: int
    prediction_date: date
    target_date: date
    prediction_type: PredictionType
    predicted_value: float
    confidence: float
    model_version: str
    created_at: datetime


class PredictionResponse(BaseModel):
    dpc_id: int
    dpc_name: str
    target_date: date
    prediction_type: PredictionType
    predicted_value: float
    confidence: float
    model_version: str
    data_source: str = "synthetic"
