from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_ml_service, get_prediction_service
from backend.app.ml.errors import ModelNotTrainedError
from backend.app.ml.service import MLService, severity_for_probability
from backend.app.models.prediction import PredictionType
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.prediction_repo import PredictionRepository
from backend.app.schemas.prediction import (
    PredictionForecast,
    PredictionGenerateRequest,
    PredictionRead,
    PredictionResponse,
    PredictionStatusResponse,
    PredictionTrainResponse,
)
from backend.app.services.prediction_service import PredictionService

router = APIRouter()


@router.get(
    "/status",
    response_model=PredictionStatusResponse,
    summary="Prediction engine status (ML trained? statistical fallback active?)",
)
def predictions_status(
    service: MLService = Depends(get_ml_service),
) -> PredictionStatusResponse:
    data = service.status()
    trained = bool(data["trained"])
    trained_at = None
    for target_state in data.get("targets", {}).values():
        if target_state.get("trained"):
            trained_at = target_state.get("trained_at")
            break
    return PredictionStatusResponse(
        trained=trained,
        current_version=data.get("current_version"),
        trained_at=trained_at,
        message=data.get("message", ""),
    )


@router.post(
    "/train",
    response_model=PredictionTrainResponse,
    summary="Train ML prediction models (scikit-learn stack)",
)
def train_predictions(
    validation_days: int | None = Query(default=None, ge=5, le=30),
    service: MLService = Depends(get_ml_service),
) -> PredictionTrainResponse:
    if validation_days is not None:
        service.validation_days = validation_days
    data = service.train_models()
    return PredictionTrainResponse(
        status=data.get("status", "failed"),
        validation_days=data.get("validation_days"),
        current_version=data.get("current_version"),
        targets=data.get("targets", {}),
    )


def _ml_or_statistical(
    kind: str,
    dpc_id: int,
    target_date: date,
    ml_service: MLService,
    prediction_service: PredictionService,
) -> PredictionForecast:
    """ML-first with statistical fallback for one DPC/kind."""

    def _dpc_name() -> str | None:
        dpc = DPCRepository(prediction_service.db).get_by_id(dpc_id)
        return dpc.name if dpc else None

    forecast: PredictionForecast | None = None
    if ml_service.is_trained():
        try:
            if kind == "arrivals":
                data = ml_service.predict_arrivals(dpc_id, target_date, persist=False)
                forecast = PredictionForecast(
                    dpc_id=dpc_id,
                    dpc_name=_dpc_name(),
                    target_date=target_date,
                    prediction_type="arrival_count",
                    predicted_value=data["predicted_value"],
                    confidence=data["confidence"],
                    model_version=data["model_version"],
                    data_source="ml",
                )
            elif kind == "quantity":
                data = ml_service.predict_quantity(dpc_id, target_date, persist=False)
                forecast = PredictionForecast(
                    dpc_id=dpc_id,
                    dpc_name=_dpc_name(),
                    target_date=target_date,
                    prediction_type="quantity",
                    predicted_value=data["predicted_value"],
                    confidence=data["confidence"],
                    model_version=data["model_version"],
                    data_source="ml",
                )
            else:  # congestion
                data = ml_service.predict_congestion(dpc_id, target_date, persist=False)
                forecast = PredictionForecast(
                    dpc_id=dpc_id,
                    dpc_name=_dpc_name(),
                    target_date=target_date,
                    prediction_type="overload_probability",
                    probability=data["probability"],
                    severity=data["severity"],
                    score=data["score"],
                    confidence=data["confidence"],
                    model_version=data["model_version"],
                    data_source="ml",
                )
        except ModelNotTrainedError:
            forecast = None

    if forecast is not None:
        return forecast

    if kind == "congestion":
        preds = PredictionRepository(prediction_service.db).get_by_dpc(
            dpc_id, prediction_type=PredictionType.quantity, limit=1
        )
        dpc = DPCRepository(prediction_service.db).get_by_id(dpc_id)
        if preds and dpc and dpc.daily_capacity > 0:
            capacity_pct = (preds[0].predicted_value / dpc.daily_capacity) * 100
            capacity_pct = min(100.0, capacity_pct)
            probability = round(capacity_pct / 100.0, 4)
            severity = severity_for_probability(probability).value
            return PredictionForecast(
                dpc_id=dpc_id,
                dpc_name=dpc.name,
                target_date=target_date,
                prediction_type="overload_probability",
                probability=probability,
                severity=severity,
                score=round(capacity_pct, 1),
                confidence=preds[0].confidence,
                model_version="statistical",
                data_source="statistical",
            )
        return PredictionForecast(
            dpc_id=dpc_id,
            dpc_name=_dpc_name(),
            target_date=target_date,
            prediction_type="overload_probability",
            predicted_value=0.0,
            severity="low",
            score=0.0,
            data_source="statistical",
        )

    stat_type = PredictionType.arrival_count if kind == "arrivals" else PredictionType.quantity
    prediction = prediction_service.generate_prediction(
        dpc_id=dpc_id,
        target_date=target_date,
        prediction_type=stat_type,
        history_days=30,
    )
    return PredictionForecast(
        dpc_id=prediction.dpc_id,
        dpc_name=_dpc_name(),
        target_date=prediction.target_date,
        prediction_type=prediction.prediction_type.value,
        predicted_value=prediction.predicted_value,
        confidence=prediction.confidence,
        model_version=prediction.model_version,
        data_source="statistical",
    )


def _make_forecast_endpoint(kind: str):
    def endpoint(
        target_date: date | None = Query(default=None, description="Defaults to today"),
        dpc_id: int | None = Query(default=None, description="Optional DPC; defaults to all active DPCs"),
        ml_service: MLService = Depends(get_ml_service),
        prediction_service: PredictionService = Depends(get_prediction_service),
    ) -> list[PredictionForecast]:
        if target_date is None:
            target_date = date.today()

        if dpc_id is not None:
            items = [_ml_or_statistical(kind, dpc_id, target_date, ml_service, prediction_service)]
        else:
            dpcs = DPCRepository(prediction_service.db).get_active()
            items = [_ml_or_statistical(kind, d.id, target_date, ml_service, prediction_service) for d in dpcs]
        return items

    endpoint.__name__ = f"get_{kind}_forecasts"
    return endpoint


router.get(
    "/arrivals",
    response_model=list[PredictionForecast],
    summary="Forecast paddy arrivals (ML if trained, else statistical)",
)(_make_forecast_endpoint("arrivals"))

router.get(
    "/quantity",
    response_model=list[PredictionForecast],
    summary="Forecast procurement quantity (ML if trained, else statistical)",
)(_make_forecast_endpoint("quantity"))

router.get(
    "/congestion",
    response_model=list[PredictionForecast],
    summary="Forecast overload probability/congestion (ML if trained, else statistical)",
)(_make_forecast_endpoint("congestion"))


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