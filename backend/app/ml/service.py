from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.ml.errors import InsufficientDataError, ModelNotTrainedError
from backend.app.ml.features import FEATURE_COLUMNS, FeatureBuilder
from backend.app.ml.models import MLTarget
from backend.app.ml.registry import ModelRegistry
from backend.app.ml.trainer import Trainer
from backend.app.models.prediction import PredictionType
from backend.app.models.risk_assessment import RiskSeverity, RiskType
from backend.app.repositories.prediction_repo import PredictionRepository
from backend.app.repositories.risk_assessment_repo import RiskAssessmentRepository

SEVERITY_BY_PROBABILITY = [
    (0.85, RiskSeverity.critical),
    (0.65, RiskSeverity.high),
    (0.40, RiskSeverity.medium),
]


def severity_for_probability(probability: float) -> RiskSeverity:
    for threshold, severity in SEVERITY_BY_PROBABILITY:
        if probability >= threshold:
            return severity
    return RiskSeverity.low


class MLService:
    """Reusable ML orchestration, fully decoupled from the API layer.

    Training reads synthetic history straight from the DB, persists joblib
    artifacts + a model registry, and prediction writes results back to the
    `predictions` / `risk_assessments` tables (upserts).
    """

    def __init__(
        self,
        db: Session,
        artifacts_dir: str | Path | None = None,
        validation_days: int | None = None,
    ) -> None:
        self.db = db
        self.registry = ModelRegistry(artifacts_dir or settings.ML_ARTIFACTS_DIR)
        self.validation_days = validation_days or settings.ML_VALIDATION_DAYS
        self.features = FeatureBuilder(db)
        self.prediction_repo = PredictionRepository(db)
        self.risk_repo = RiskAssessmentRepository(db)

    # ------------------------------------------------------------------
    # Status / training / evaluation
    # ------------------------------------------------------------------

    def is_trained(self) -> bool:
        return self.registry.is_trained()

    def status(self) -> dict[str, Any]:
        data = self.registry.status()
        data["message"] = self._status_message(data["trained"])
        return data

    @staticmethod
    def _status_message(trained: bool) -> str:
        if trained:
            return "ML models are trained and ready for prediction."
        return (
            "ML models are not trained yet. Train with POST /api/v1/ml/train, "
            "or use the statistical fallback endpoints under /api/v1/predictions."
        )

    def train_models(self) -> dict[str, Any]:
        trainer = Trainer(self.db, self.registry, validation_days=self.validation_days)
        results: dict[str, Any] = {}
        for target in MLTarget:
            try:
                entry = trainer.train(target)
                summary = {
                    "trained": True,
                    "version": entry["version"],
                    "model_type": entry["model_type"],
                    "metrics": entry["metrics"],
                    "train_range": entry["train_range"],
                    "valid_range": entry["valid_range"],
                    "n_train": entry["n_train"],
                    "n_valid": entry["n_valid"],
                }
            except (InsufficientDataError, RuntimeError) as exc:
                summary = {"trained": False, "error": str(exc)}
            results[target.value] = summary
        trained_any = any(r.get("trained") for r in results.values())
        return {
            "status": "trained" if all(r.get("trained") for r in results.values())
            else ("partial" if trained_any else "failed"),
            "validation_days": self.validation_days,
            "targets": results,
            "current_version": self.registry.status().get("current_version"),
        }

    def evaluate_models(self) -> dict[str, Any]:
        metrics = self.registry.metrics()
        return {
            "trained": self.registry.is_trained(),
            "message": self._status_message(self.registry.is_trained()),
            "targets": metrics,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_arrivals(self, dpc_id: int, target_date: date, persist: bool = True) -> dict[str, Any]:
        return self._predict_regression(
            MLTarget.arrival_count, PredictionType.arrival_count, dpc_id, target_date, persist
        )

    def predict_quantity(self, dpc_id: int, target_date: date, persist: bool = True) -> dict[str, Any]:
        return self._predict_regression(
            MLTarget.quantity, PredictionType.quantity, dpc_id, target_date, persist
        )

    def predict_congestion(self, dpc_id: int, target_date: date, persist: bool = True) -> dict[str, Any]:
        model, entry = self.registry.load_current(MLTarget.overload.value)
        row = self._feature_row(dpc_id, target_date, entry["features"])
        probability = float(model.predict_proba(pd.DataFrame([row]))[:, 1][0])
        severity = severity_for_probability(probability)
        score = round(probability * 100, 1)
        result = {
            "dpc_id": int(dpc_id),
            "target_date": target_date.isoformat(),
            "predicted_value": probability,
            "probability": round(probability, 4),
            "severity": severity.value,
            "score": score,
            "model_version": entry["version"],
            "confidence": round(probability, 4),
        }
        if persist:
            self._persist_overload(dpc_id, target_date, probability, severity, score, entry["version"])
            result["persisted"] = True
        else:
            result["persisted"] = False
        return result

    def predict_all(self, dpc_id: int, target_date: date, persist: bool = True) -> dict[str, Any]:
        return {
            "dpc_id": int(dpc_id),
            "target_date": target_date.isoformat(),
            "arrivals": self.predict_arrivals(dpc_id, target_date, persist),
            "quantity": self.predict_quantity(dpc_id, target_date, persist),
            "congestion": self.predict_congestion(dpc_id, target_date, persist),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _predict_regression(
        self,
        target: MLTarget,
        prediction_type: PredictionType,
        dpc_id: int,
        target_date: date,
        persist: bool,
    ) -> dict[str, Any]:
        model, entry = self.registry.load_current(target.value)
        row = self._feature_row(dpc_id, target_date, entry["features"])
        value = float(model.predict(pd.DataFrame([row]))[0])
        value = max(0.0, value)
        confidence = self._confidence(entry, model, row)
        result = {
            "dpc_id": int(dpc_id),
            "target_date": target_date.isoformat(),
            "prediction_type": prediction_type.value,
            "predicted_value": round(value, 4),
            "confidence": confidence,
            "model_version": entry["version"],
        }
        if persist:
            self._persist_prediction(dpc_id, target_date, prediction_type, value, confidence, entry["version"])
            result["persisted"] = True
        else:
            result["persisted"] = False
        return result

    def _feature_row(self, dpc_id: int, target_date: date, feature_columns: list[str]) -> dict[str, float]:
        features = self.features.row_for(dpc_id, target_date)
        frame = pd.DataFrame(
            [[features[col] if col in features else 0.0 for col in feature_columns]],
            columns=feature_columns,
        )
        return frame.iloc[0].to_dict()

    def _confidence(self, entry: dict[str, Any], model, row: dict[str, Any]) -> float:
        try:
            if getattr(model, "predict_proba", None) is not None:
                proba = model.predict_proba(pd.DataFrame([row]))[0]
                return round(float(max(proba)), 4)
        except Exception:
            pass
        metrics = entry.get("metrics") or {}
        mae = metrics.get("mae")
        mean_actual = metrics.get("mean_actual")
        if mae is None or not mean_actual:
            return 0.3
        return round(float(np.clip(1.0 - mae / max(mean_actual, 1e-9), 0.3, 0.95)), 4)

    def _persist_prediction(
        self,
        dpc_id: int,
        target_date: date,
        prediction_type: PredictionType,
        value: float,
        confidence: float,
        version: str,
    ) -> None:
        existing = self.prediction_repo.get_by_dpc_and_date(int(dpc_id), target_date, prediction_type)
        if existing:
            existing.predicted_value = value
            existing.confidence = confidence
            existing.model_version = version
            existing.prediction_date = date.today()
            self.db.commit()
            self.db.refresh(existing)
            return
        self.prediction_repo.create(
            dpc_id=int(dpc_id),
            prediction_date=date.today(),
            target_date=target_date,
            prediction_type=prediction_type,
            predicted_value=value,
            confidence=confidence,
            model_version=version,
        )

    def _persist_overload(
        self,
        dpc_id: int,
        target_date: date,
        probability: float,
        severity: RiskSeverity,
        score: float,
        version: str,
    ) -> None:
        existing = None
        for risk in self.risk_repo.get_by_dpc_and_date(int(dpc_id), target_date):
            if risk.risk_type == RiskType.overload:
                existing = risk
                break
        explanation = (
            f"ML-model (v{version}) estimates overload probability at "
            f"{probability * 100:.1f}% for {target_date.isoformat()}."
        )
        mitigation = "Divert farmers to adjacent DPC or extend processing hours."
        if existing:
            existing.severity = severity
            existing.score = score
            existing.explanation = explanation
            existing.mitigation = mitigation
            self.db.commit()
            self.db.refresh(existing)
            return
        self.risk_repo.create(
            dpc_id=int(dpc_id),
            date=target_date,
            risk_type=RiskType.overload,
            severity=severity,
            score=score,
            explanation=explanation,
            mitigation=mitigation,
        )