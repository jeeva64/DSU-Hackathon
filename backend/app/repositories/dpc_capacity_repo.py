from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.dpc_capacity import DPCCapacity


class DPCCapacityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, capacity_id: int) -> DPCCapacity | None:
        return self.db.get(DPCCapacity, capacity_id)

    def get_by_dpc_and_date(self, dpc_id: int, target_date: date) -> DPCCapacity | None:
        result = self.db.execute(
            select(DPCCapacity).where(
                DPCCapacity.dpc_id == dpc_id,
                DPCCapacity.date == target_date,
            )
        )
        return result.scalar_one_or_none()

    def get_by_dpc(self, dpc_id: int, limit: int = 30) -> list[DPCCapacity]:
        result = self.db.execute(
            select(DPCCapacity)
            .where(DPCCapacity.dpc_id == dpc_id)
            .order_by(DPCCapacity.date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[DPCCapacity]:
        result = self.db.execute(
            select(DPCCapacity).order_by(DPCCapacity.date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(DPCCapacity.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> DPCCapacity:
        cap = DPCCapacity(**kwargs)
        self.db.add(cap)
        self.db.commit()
        self.db.refresh(cap)
        return cap

    def upsert(self, dpc_id: int, target_date: date, **kwargs) -> DPCCapacity:
        existing = self.get_by_dpc_and_date(dpc_id, target_date)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create(dpc_id=dpc_id, date=target_date, **kwargs)
