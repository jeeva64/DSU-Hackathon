from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.risk_assessment import RiskAssessment, RiskSeverity


class RiskAssessmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, risk_id: int) -> RiskAssessment | None:
        return self.db.get(RiskAssessment, risk_id)

    def get_by_dpc_and_date(self, dpc_id: int, target_date: date) -> list[RiskAssessment]:
        result = self.db.execute(
            select(RiskAssessment).where(
                RiskAssessment.dpc_id == dpc_id,
                RiskAssessment.date == target_date,
            ).order_by(RiskAssessment.score.desc())
        )
        return list(result.scalars().all())

    def get_by_date(self, target_date: date) -> list[RiskAssessment]:
        result = self.db.execute(
            select(RiskAssessment)
            .where(RiskAssessment.date == target_date)
            .order_by(RiskAssessment.score.desc())
        )
        return list(result.scalars().all())

    def get_critical(self, target_date: date | None = None) -> list[RiskAssessment]:
        query = select(RiskAssessment).where(
            RiskAssessment.severity.in_([RiskSeverity.critical, RiskSeverity.high])
        )
        if target_date:
            query = query.where(RiskAssessment.date == target_date)
        query = query.order_by(RiskAssessment.score.desc())
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[RiskAssessment]:
        result = self.db.execute(
            select(RiskAssessment).order_by(RiskAssessment.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(RiskAssessment.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> RiskAssessment:
        risk = RiskAssessment(**kwargs)
        self.db.add(risk)
        self.db.commit()
        self.db.refresh(risk)
        return risk
