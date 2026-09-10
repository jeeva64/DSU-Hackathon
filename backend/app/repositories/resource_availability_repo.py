from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.resource_availability import ResourceAvailability


class ResourceAvailabilityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, resource_id: int) -> ResourceAvailability | None:
        return self.db.get(ResourceAvailability, resource_id)

    def get_by_dpc_and_date(self, dpc_id: int, target_date: date) -> ResourceAvailability | None:
        result = self.db.execute(
            select(ResourceAvailability).where(
                ResourceAvailability.dpc_id == dpc_id,
                ResourceAvailability.date == target_date,
            )
        )
        return result.scalar_one_or_none()

    def get_by_dpc(self, dpc_id: int, limit: int = 30) -> list[ResourceAvailability]:
        result = self.db.execute(
            select(ResourceAvailability)
            .where(ResourceAvailability.dpc_id == dpc_id)
            .order_by(ResourceAvailability.date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ResourceAvailability]:
        result = self.db.execute(
            select(ResourceAvailability).order_by(ResourceAvailability.date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(ResourceAvailability.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> ResourceAvailability:
        res = ResourceAvailability(**kwargs)
        self.db.add(res)
        self.db.commit()
        self.db.refresh(res)
        return res

    def upsert(self, dpc_id: int, target_date: date, **kwargs) -> ResourceAvailability:
        existing = self.get_by_dpc_and_date(dpc_id, target_date)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create(dpc_id=dpc_id, date=target_date, **kwargs)
