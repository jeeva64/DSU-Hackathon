from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.dpc import DPC, OperatingStatus
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.procurement_repo import ProcurementRepository
from backend.app.schemas.dpc import DPCCreate, DPCUpdate

logger = logging.getLogger("backend.services.dpc")


class DPCService:
    def __init__(self, db: Session) -> None:
        self.repo = DPCRepository(db)
        self.procurement_repo = ProcurementRepository(db)

    def get_dpc(self, dpc_id: int) -> DPC:
        dpc = self.repo.get_by_id(dpc_id)
        if not dpc:
            raise ValueError(f"DPC with ID {dpc_id} not found")
        return dpc

    def list_dpcs(self, skip: int = 0, limit: int = 100) -> tuple[list[DPC], int]:
        dpcs = self.repo.get_all(skip=skip, limit=limit)
        total = self.repo.count()
        return dpcs, total

    def create_dpc(self, data: DPCCreate) -> DPC:
        logger.info("Creating DPC: %s (%s) in %s", data.dpc_code, data.name, data.village)
        return self.repo.create(data)

    def update_dpc(self, dpc_id: int, data: DPCUpdate) -> DPC:
        dpc = self.repo.update(dpc_id, data)
        if not dpc:
            raise ValueError(f"DPC with ID {dpc_id} not found")
        logger.info("Updated DPC %s", dpc_id)
        return dpc

    def delete_dpc(self, dpc_id: int) -> bool:
        deleted = self.repo.delete(dpc_id)
        if not deleted:
            raise ValueError(f"DPC with ID {dpc_id} not found")
        logger.info("Deleted DPC %s", dpc_id)
        return True

    def get_capacity_info(self, dpc_id: int, target_date: date | None = None) -> dict:
        if target_date is None:
            target_date = date.today()

        dpc = self.get_dpc(dpc_id)

        from sqlalchemy import select, func
        from backend.app.models.procurement import ProcurementRecord

        db = self.procurement_repo.db
        result = db.execute(
            select(func.coalesce(func.sum(ProcurementRecord.bags), 0)).where(
                ProcurementRecord.dpc_id == dpc_id,
                ProcurementRecord.date == target_date,
            )
        )
        bags_today = result.scalar_one()

        capacity_pct = (bags_today / dpc.daily_capacity * 100) if dpc.daily_capacity > 0 else 0.0

        return {
            "dpc_id": dpc.id,
            "dpc_name": dpc.name,
            "daily_capacity": dpc.daily_capacity,
            "storage_capacity": dpc.storage_capacity,
            "current_utilization_pct": round(min(capacity_pct, 100.0), 2),
            "bags_received_today": int(bags_today),
            "remaining_capacity_bags": max(0, dpc.daily_capacity - int(bags_today)),
        }

    def get_active_dpcs(self) -> list[DPC]:
        return self.repo.get_active()
