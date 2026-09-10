from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.recommendation import (
    Recommendation,
    RecommendationStatus,
)
from backend.app.schemas.recommendation import RecommendationApproveRequest, RecommendationRejectRequest


class RecommendationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, recommendation_id: int) -> Recommendation | None:
        return self.db.get(Recommendation, recommendation_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Recommendation]:
        result = self.db.execute(
            select(Recommendation).order_by(Recommendation.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def get_pending(self) -> list[Recommendation]:
        result = self.db.execute(
            select(Recommendation)
            .where(Recommendation.status == RecommendationStatus.pending)
            .order_by(Recommendation.priority.desc(), Recommendation.created_at.desc())
        )
        return list(result.scalars().all())

    def get_by_dpc(self, dpc_id: int) -> list[Recommendation]:
        result = self.db.execute(
            select(Recommendation)
            .where(Recommendation.dpc_id == dpc_id)
            .order_by(Recommendation.created_at.desc())
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(Recommendation.id)))
        return result.scalar_one()

    def approve(self, recommendation_id: int, notes: str | None = None) -> Recommendation | None:
        rec = self.get_by_id(recommendation_id)
        if not rec:
            return None
        rec.status = RecommendationStatus.approved
        rec.officer_notes = notes
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def reject(self, recommendation_id: int, notes: str | None = None) -> Recommendation | None:
        rec = self.get_by_id(recommendation_id)
        if not rec:
            return None
        rec.status = RecommendationStatus.rejected
        rec.officer_notes = notes
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def create(self, **kwargs) -> Recommendation:
        rec = Recommendation(**kwargs)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def create_many(self, recommendations: list[dict]) -> list[Recommendation]:
        objects = [Recommendation(**r) for r in recommendations]
        self.db.add_all(objects)
        self.db.commit()
        for obj in objects:
            self.db.refresh(obj)
        return objects
