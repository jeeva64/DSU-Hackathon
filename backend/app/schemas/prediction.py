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


class PredictionForecast(BaseModel):
    """One forecast row for arrivals/quantity/congestion.

    `data_source` is "ml" when computed from trained scikit-learn models,
    "statistical" when the deterministic mean+weekend heuristic is used.
    """

    dpc_id: int
    dpc_name: str | None = None
    target_date: date
    prediction_type: str
    predicted_value: float | None = None
    probability: float | None = None
    severity: str | None = None
    score: float | None = None
    confidence: float | None = None
    model_version: str | None = None
    data_source: str = "statistical"


class PredictionTrainResponse(BaseModel):
    status: str
    validation_days: int | None = None
    current_version: str | None = None
    targets: dict[str, dict] = Field(default_factory=dict)


class PredictionStatusResponse(BaseModel):
    trained: bool
    current_version: str | None = None
    trained_at: str | None = None
    active_engine: str = "ml"
    fallback_engine: str = "statistical"
    message: str
