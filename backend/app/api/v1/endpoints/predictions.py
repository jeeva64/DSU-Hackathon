from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_prediction_service
from backend.app.models.prediction import PredictionType
from backend.app.schemas.prediction import PredictionGenerateRequest, PredictionRead, PredictionResponse
from backend.app.services.prediction_service import PredictionService

router = APIRouter()


@router.get("/{dpc_id}", response_model=list[PredictionRead])
def get_predictions(
    dpc_id: int,
    limit: int = Query(30, ge=1, le=100),
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionRead]:
    predictions = service.get_predictions(dpc_id, limit=limit)
    return [PredictionRead.model_validate(p) for p in predictions]


@router.post("/generate", response_model=PredictionResponse)
def generate_prediction(
    request: PredictionGenerateRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionResponse:
    prediction = service.generate_prediction(
        dpc_id=request.dpc_id,
        target_date=request.target_date,
        prediction_type=request.prediction_type,
        history_days=request.history_days,
    )
    dpc = service.dpc_repo.get_by_id(request.dpc_id)
    return PredictionResponse(
        dpc_id=prediction.dpc_id,
        dpc_name=dpc.name if dpc else "Unknown",
        target_date=prediction.target_date,
        prediction_type=prediction.prediction_type,
        predicted_value=prediction.predicted_value,
        confidence=prediction.confidence,
        model_version=prediction.model_version,
        data_source="synthetic",
    )
