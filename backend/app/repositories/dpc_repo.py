from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.dpc import DPC, OperatingStatus
from backend.app.schemas.dpc import DPCCreate, DPCUpdate


class DPCRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, dpc_id: int) -> DPC | None:
        return self.db.get(DPC, dpc_id)

    def get_by_code(self, dpc_code: str) -> DPC | None:
        result = self.db.execute(select(DPC).where(DPC.dpc_code == dpc_code))
        return result.scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[DPC]:
        result = self.db.execute(select(DPC).offset(skip).limit(limit))
        return list(result.scalars().all())

    def get_active(self) -> list[DPC]:
        result = self.db.execute(
            select(DPC).where(DPC.operating_status == OperatingStatus.active)
        )
        return list(result.scalars().all())

    def get_by_district(self, district: str) -> list[DPC]:
        result = self.db.execute(select(DPC).where(DPC.district == district))
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(DPC.id)))
        return result.scalar_one()

    def create(self, data: DPCCreate) -> DPC:
        dpc = DPC(**data.model_dump())
        self.db.add(dpc)
        self.db.commit()
        self.db.refresh(dpc)
        return dpc

    def update(self, dpc_id: int, data: DPCUpdate) -> DPC | None:
        dpc = self.get_by_id(dpc_id)
        if not dpc:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(dpc, field, value)
        self.db.commit()
        self.db.refresh(dpc)
        return dpc

    def delete(self, dpc_id: int) -> bool:
        dpc = self.get_by_id(dpc_id)
        if not dpc:
            return False
        self.db.delete(dpc)
        self.db.commit()
        return True
