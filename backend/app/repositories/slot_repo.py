from __future__ import annotations

from datetime import date, time

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.slot import Slot, SlotStatus


class SlotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, slot_id: int) -> Slot | None:
        return self.db.get(Slot, slot_id)

    def get_by_dpc_and_date(self, dpc_id: int, target_date: date) -> list[Slot]:
        result = self.db.execute(
            select(Slot).where(
                Slot.dpc_id == dpc_id,
                Slot.date == target_date,
            ).order_by(Slot.start_time)
        )
        return list(result.scalars().all())

    def get_available_slots(self, dpc_id: int, target_date: date) -> list[Slot]:
        result = self.db.execute(
            select(Slot).where(
                Slot.dpc_id == dpc_id,
                Slot.date == target_date,
                Slot.status.in_([SlotStatus.available, SlotStatus.partially_booked]),
            ).order_by(Slot.start_time)
        )
        return list(result.scalars().all())

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        dpc_id: int | None = None,
        target_date: date | None = None,
    ) -> list[Slot]:
        query = select(Slot)
        if dpc_id is not None:
            query = query.where(Slot.dpc_id == dpc_id)
        if target_date is not None:
            query = query.where(Slot.date == target_date)
        query = query.order_by(Slot.date.desc(), Slot.start_time).offset(skip).limit(limit)
        result = self.db.execute(query)
        return list(result.scalars().all())

    def count(
        self,
        dpc_id: int | None = None,
        target_date: date | None = None,
    ) -> int:
        query = select(func.count(Slot.id))
        if dpc_id is not None:
            query = query.where(Slot.dpc_id == dpc_id)
        if target_date is not None:
            query = query.where(Slot.date == target_date)
        result = self.db.execute(query)
        return result.scalar_one()

    def get_available_all(self, target_date: date | None = None) -> list[Slot]:
        query = select(Slot).where(
            Slot.status.in_([SlotStatus.available, SlotStatus.partially_booked])
        )
        if target_date is not None:
            query = query.where(Slot.date == target_date)
        query = query.order_by(Slot.date, Slot.dpc_id, Slot.start_time)
        result = self.db.execute(query)
        return list(result.scalars().all())

    def create(self, **kwargs) -> Slot:
        slot = Slot(**kwargs)
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        return slot
