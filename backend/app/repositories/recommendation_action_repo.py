from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.recommendation_action import RecommendationAction


class RecommendationActionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, action_id: int) -> RecommendationAction | None:
        return self.db.get(RecommendationAction, action_id)

    def get_by_recommendation(self, recommendation_id: int) -> list[RecommendationAction]:
        result = self.db.execute(
            select(RecommendationAction)
            .where(RecommendationAction.recommendation_id == recommendation_id)
            .order_by(RecommendationAction.created_at)
        )
        return list(result.scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[RecommendationAction]:
        result = self.db.execute(
            select(RecommendationAction).order_by(RecommendationAction.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(RecommendationAction.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> RecommendationAction:
        action = RecommendationAction(**kwargs)
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action
