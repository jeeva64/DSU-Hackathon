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

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Slot]:
        result = self.db.execute(
            select(Slot).order_by(Slot.date.desc(), Slot.start_time).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(Slot.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> Slot:
        slot = Slot(**kwargs)
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        return slot
