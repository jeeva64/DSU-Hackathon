from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.prediction import PredictionType
from backend.app.models.recommendation import (
    RecommendationPriority,
    RecommendationType,
)
from backend.app.repositories.recommendation_repo import RecommendationRepository
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.prediction_repo import PredictionRepository

logger = logging.getLogger("backend.services.recommendation")


class RecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = RecommendationRepository(db)
        self.dpc_repo = DPCRepository(db)
        self.prediction_repo = PredictionRepository(db)

    def list_recommendations(self, skip: int = 0, limit: int = 100) -> tuple[list, int]:
        recs = self.repo.get_all(skip=skip, limit=limit)
        total = self.repo.count()
        return recs, total

    def get_pending(self) -> list:
        return self.repo.get_pending()

    def approve_recommendation(self, rec_id: int, notes: str | None = None) -> dict:
        rec = self.repo.approve(rec_id, notes)
        if not rec:
            raise ValueError(f"Recommendation with ID {rec_id} not found")
        logger.info("Recommendation %s approved", rec_id)
        return {"id": rec.id, "status": rec.status, "message": "Recommendation approved"}

    def reject_recommendation(self, rec_id: int, notes: str | None = None) -> dict:
        rec = self.repo.reject(rec_id, notes)
        if not rec:
            raise ValueError(f"Recommendation with ID {rec_id} not found")
        logger.info("Recommendation %s rejected", rec_id)
        return {"id": rec.id, "status": rec.status, "message": "Recommendation rejected"}

    def generate_recommendations(self, target_date: date | None = None) -> list[dict]:
        if target_date is None:
            target_date = date.today()

        generated = []
        dpcs = self.dpc_repo.get_active()

        for dpc in dpcs:
            preds = self.prediction_repo.get_by_dpc(
                dpc.id, prediction_type=PredictionType.quantity, limit=1
            )
            if not preds:
                continue
            pred = preds[0]

            capacity_pct = (pred.predicted_value / dpc.daily_capacity * 100) if dpc.daily_capacity > 0 else 0

            if capacity_pct > 85:
                priority = RecommendationPriority.critical if capacity_pct > 95 else RecommendationPriority.high
                rec = self.repo.create(
                    dpc_id=dpc.id,
                    date=target_date,
                    recommendation_type=RecommendationType.slot,
                    priority=priority,
                    title=f"Reduce load at {dpc.name}",
                    explanation=f"Predicted capacity utilization at {capacity_pct:.0f}%. Recommend diverting farmers to adjacent DPCs.",
                    expected_impact="Reduce queue wait time by approximately 30-40%",
                )
                generated.append({
                    "id": rec.id,
                    "title": rec.title,
                    "priority": rec.priority,
                    "explanation": rec.explanation,
                })

            queue_preds = self.prediction_repo.get_by_dpc(
                dpc.id, prediction_type=PredictionType.queue_length, limit=1
            )
            if queue_preds and queue_preds[0].predicted_value > 50:
                queue_val = queue_preds[0].predicted_value
                priority = RecommendationPriority.critical if queue_val > 100 else RecommendationPriority.medium
                rec = self.repo.create(
                    dpc_id=dpc.id,
                    date=target_date,
                    recommendation_type=RecommendationType.resource,
                    priority=priority,
                    title=f"Increase staff at {dpc.name}",
                    explanation=f"Expected queue of {int(queue_val)} farmers. Additional staff needed.",
                    expected_impact="Process 25% more farmers per hour",
                )
                generated.append({
                    "id": rec.id,
                    "title": rec.title,
                    "priority": rec.priority,
                    "explanation": rec.explanation,
                })

        logger.info("Generated %d recommendations for %s", len(generated), target_date)
        return generated

    def get_by_dpc(self, dpc_id: int) -> list:
        return self.repo.get_by_dpc(dpc_id)
