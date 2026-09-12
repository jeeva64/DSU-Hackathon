from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from backend.app.api.deps import get_ml_service
from backend.app.ml.errors import ModelNotTrainedError
from backend.app.ml.service import MLService
from backend.app.schemas.ml import (
    MLPredictionRequest,
    MLPredictionResponse,
    MLPredictionValue,
    MLStatusResponse,
    MLTargetKind,
    MLTrainRequest,
    MLTrainResponse,
)

router = APIRouter()

NOT_TRAINED_MESSAGE = (
    "ML models are not trained yet. POST /api/v1/ml/train first, "
    "or use the statistical fallback endpoints under /api/v1/predictions."
)


@router.get("/status", response_model=MLStatusResponse)
def ml_status(service: MLService = Depends(get_ml_service)) -> MLStatusResponse:
    data = service.status()
    trained = bool(data["trained"])
    trained_at = None
    version = data.get("current_version")
    targets = data.get("targets", {})
    for target_state in targets.values():
        if target_state.get("trained"):
            trained_at = target_state.get("trained_at")
            break
    return MLStatusResponse(
        trained=trained,
        current_version=version,
        trained_at=trained_at,
        artifacts_dir=data.get("artifacts_dir", ""),
        targets=targets,
        message=data.get("message", ""),
    )


@router.post("/train", response_model=MLTrainResponse)
def ml_train(
    request: MLTrainRequest | None = None,
    service: MLService = Depends(get_ml_service),
) -> MLTrainResponse:
    if request and request.validation_days is not None:
        service.validation_days = request.validation_days
    data = service.train_models()
    return MLTrainResponse(
        status=data.get("status", "failed"),
        validation_days=data.get("validation_days"),
        current_version=data.get("current_version"),
        targets=data.get("targets", {}),
    )


@router.get("/evaluate")
def ml_evaluate(service: MLService = Depends(get_ml_service)) -> dict:
    return service.evaluate_models()


def _parse_target(target: str) -> MLTargetKind:
    try:
        return MLTargetKind(target)
    except ValueError as exc:
        raise ValidationError.from_exception_data(
            "MLTargetKind", [{"type": "value_error", "loc": ("target",), "input": target}]
        ) from exc


def _single_prediction(
    kind: MLTargetKind, dpc_id: int, target_date: date, persist: bool, service: MLService
) -> MLPredictionValue:
    if kind == MLTargetKind.arrivals:
        data = service.predict_arrivals(dpc_id, target_date, persist)
        return MLPredictionValue(
            prediction_type=data["prediction_type"],
            predicted_value=data["predicted_value"],
            confidence=data["confidence"],
            model_version=data["model_version"],
            persisted=data["persisted"],
        )
    if kind == MLTargetKind.quantity:
        data = service.predict_quantity(dpc_id, target_date, persist)
        return MLPredictionValue(
            prediction_type=data["prediction_type"],
            predicted_value=data["predicted_value"],
            confidence=data["confidence"],
            model_version=data["model_version"],
            persisted=data["persisted"],
        )
    data = service.predict_congestion(dpc_id, target_date, persist)
    return MLPredictionValue(
        prediction_type="overload_probability",
        probability=data["probability"],
        severity=data["severity"],
        score=data["score"],
        confidence=data["confidence"],
        model_version=data["model_version"],
        persisted=data["persisted"],
    )


@router.post("/predict", response_model=MLPredictionResponse)
def ml_predict(
    request: MLPredictionRequest,
    service: MLService = Depends(get_ml_service),
) -> MLPredictionResponse:
    if not service.is_trained():
        results = {
            "arrivals": MLPredictionValue(prediction_type="arrival_count"),
            "quantity": MLPredictionValue(prediction_type="quantity"),
            "congestion": MLPredictionValue(prediction_type="overload_probability"),
        }
        return MLPredictionResponse(
            status="not_trained",
            message=NOT_TRAINED_MESSAGE,
            dpc_id=request.dpc_id,
            target_date=request.target_date,
            results=results,
        )

    target = _parse_target(request.target.value)
    if target == MLTargetKind.all:
        data = service.predict_all(request.dpc_id, request.target_date, request.persist)
        results = {
            "arrivals": MLPredictionValue(
                prediction_type=data["arrivals"]["prediction_type"],
                predicted_value=data["arrivals"]["predicted_value"],
                confidence=data["arrivals"]["confidence"],
                model_version=data["arrivals"]["model_version"],
                persisted=data["arrivals"]["persisted"],
            ),
            "quantity": MLPredictionValue(
                prediction_type=data["quantity"]["prediction_type"],
                predicted_value=data["quantity"]["predicted_value"],
                confidence=data["quantity"]["confidence"],
                model_version=data["quantity"]["model_version"],
                persisted=data["quantity"]["persisted"],
            ),
            "congestion": MLPredictionValue(
                prediction_type="overload_probability",
                probability=data["congestion"]["probability"],
                severity=data["congestion"]["severity"],
                score=data["congestion"]["score"],
                confidence=data["congestion"]["confidence"],
                model_version=data["congestion"]["model_version"],
                persisted=data["congestion"]["persisted"],
            ),
        }
    else:
        value = _single_prediction(target, request.dpc_id, request.target_date, request.persist, service)
        results = {target.value: value}

    return MLPredictionResponse(
        status="ok",
        message="Prediction computed from trained ML models.",
        dpc_id=request.dpc_id,
        target_date=request.target_date,
        results=results,
    )


@router.get("/predict/{dpc_id}/{target_date}", response_model=MLPredictionResponse)
def ml_predict_all_for_dpc(
    dpc_id: int,
    target_date: date,
    persist: bool = True,
    service: MLService = Depends(get_ml_service),
) -> MLPredictionResponse:
    request = MLPredictionRequest(
        dpc_id=dpc_id, target_date=target_date, target=MLTargetKind.all, persist=persist
    )
    return ml_predict(request, service)