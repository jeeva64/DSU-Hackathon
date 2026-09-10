from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.arrival_record import ArrivalRecord


class ArrivalRecordRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, arrival_id: int) -> ArrivalRecord | None:
        return self.db.get(ArrivalRecord, arrival_id)

    def get_by_dpc_and_date(self, dpc_id: int, target_date: date) -> list[ArrivalRecord]:
        result = self.db.execute(
            select(ArrivalRecord).where(
                ArrivalRecord.dpc_id == dpc_id,
                ArrivalRecord.date == target_date,
            ).order_by(ArrivalRecord.arrival_time)
        )
        return list(result.scalars().all())

    def get_by_farmer(self, farmer_id: int, limit: int = 50) -> list[ArrivalRecord]:
        result = self.db.execute(
            select(ArrivalRecord)
            .where(ArrivalRecord.farmer_id == farmer_id)
            .order_by(ArrivalRecord.arrival_time.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ArrivalRecord]:
        result = self.db.execute(
            select(ArrivalRecord).order_by(ArrivalRecord.arrival_time.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(ArrivalRecord.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> ArrivalRecord:
        arrival = ArrivalRecord(**kwargs)
        self.db.add(arrival)
        self.db.commit()
        self.db.refresh(arrival)
        return arrival
