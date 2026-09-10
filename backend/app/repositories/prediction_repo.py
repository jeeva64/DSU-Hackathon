from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.prediction import Prediction, PredictionType


class PredictionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, prediction_id: int) -> Prediction | None:
        return self.db.get(Prediction, prediction_id)

    def get_by_dpc(
        self, dpc_id: int, prediction_type: PredictionType | None = None, limit: int = 30
    ) -> list[Prediction]:
        query = select(Prediction).where(Prediction.dpc_id == dpc_id)
        if prediction_type:
            query = query.where(Prediction.prediction_type == prediction_type)
        query = query.order_by(Prediction.target_date.desc()).limit(limit)
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_by_dpc_and_date(
        self, dpc_id: int, target_date: date, prediction_type: PredictionType
    ) -> Prediction | None:
        result = self.db.execute(
            select(Prediction).where(
                Prediction.dpc_id == dpc_id,
                Prediction.target_date == target_date,
                Prediction.prediction_type == prediction_type,
            )
        )
        return result.scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Prediction]:
        result = self.db.execute(
            select(Prediction).order_by(Prediction.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(Prediction.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> Prediction:
        prediction = Prediction(**kwargs)
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        return prediction

    def create_many(self, predictions: list[dict]) -> list[Prediction]:
        objects = [Prediction(**p) for p in predictions]
        self.db.add_all(objects)
        self.db.commit()
        for obj in objects:
            self.db.refresh(obj)
        return objects
