from __future__ import annotations

import enum
from datetime import date

from pydantic import BaseModel, Field


class MLTargetKind(str, enum.Enum):
    arrivals = "arrivals"
    quantity = "quantity"
    congestion = "congestion"
    all = "all"


class MLStatusResponse(BaseModel):
    trained: bool
    current_version: str | None = None
    trained_at: str | None = None
    artifacts_dir: str
    targets: dict[str, dict]
    message: str


class MLTrainRequest(BaseModel):
    validation_days: int | None = Field(default=None, ge=5, le=30)


class MLPredictionRequest(BaseModel):
    dpc_id: int
    target_date: date
    target: MLTargetKind = MLTargetKind.all
    persist: bool = True


class MLPredictionValue(BaseModel):
    prediction_type: str | None = None
    predicted_value: float | None = None
    probability: float | None = None
    severity: str | None = None
    score: float | None = None
    confidence: float | None = None
    model_version: str | None = None
    persisted: bool = False


class MLPredictionResponse(BaseModel):
    status: str
    message: str
    dpc_id: int
    target_date: date
    results: dict[str, MLPredictionValue]