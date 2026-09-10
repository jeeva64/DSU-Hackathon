from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
from sqlalchemy.orm import Session

from backend.app.models.prediction import Prediction, PredictionType
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.prediction_repo import PredictionRepository
from backend.app.repositories.procurement_repo import ProcurementRepository

logger = logging.getLogger("backend.services.prediction")


class PredictionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dpc_repo = DPCRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.procurement_repo = ProcurementRepository(db)

    def generate_prediction(
        self,
        dpc_id: int,
        target_date: date,
        prediction_type: PredictionType = PredictionType.arrival_count,
        history_days: int = 30,
    ) -> Prediction:
        dpc = self.dpc_repo.get_by_id(dpc_id)
        if not dpc:
            raise ValueError(f"DPC with ID {dpc_id} not found")

        start_date = target_date - timedelta(days=history_days)
        history = self.procurement_repo.get_by_dpc_and_date_range(dpc_id, start_date, target_date)

        if not history:
            base_value = 50.0
        else:
            daily_bags = [p.bags for p in history]
            base_value = float(np.mean(daily_bags)) if daily_bags else 50.0

        day_of_week = target_date.weekday()
        weekend_factor = 0.6 if day_of_week >= 5 else 1.0

        predicted_value = max(0.0, base_value * weekend_factor)
        confidence = min(0.95, max(0.3, 0.7 + (0.1 if len(history or []) > 14 else 0)))

        existing = self.prediction_repo.get_by_dpc_and_date(dpc_id, target_date, prediction_type)
        if existing:
            existing.predicted_value = predicted_value
            existing.confidence = confidence
            self.db.commit()
            self.db.refresh(existing)
            return existing

        prediction = self.prediction_repo.create(
            dpc_id=dpc_id,
            prediction_date=date.today(),
            target_date=target_date,
            prediction_type=prediction_type,
            predicted_value=predicted_value,
            confidence=confidence,
            model_version="v0.1-statistical",
        )
        logger.info(
            "Generated %s prediction for DPC %s on %s: %.1f",
            prediction_type.value, dpc_id, target_date, predicted_value,
        )
        return prediction

    def get_predictions(
        self, dpc_id: int, prediction_type: PredictionType | None = None, limit: int = 30
    ) -> list[Prediction]:
        return self.prediction_repo.get_by_dpc(dpc_id, prediction_type=prediction_type, limit=limit)

    def get_latest_prediction(self, dpc_id: int) -> Prediction | None:
        predictions = self.prediction_repo.get_by_dpc(dpc_id, limit=1)
        return predictions[0] if predictions else None
