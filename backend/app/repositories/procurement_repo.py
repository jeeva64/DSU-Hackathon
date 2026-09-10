from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.procurement import ProcurementRecord, ProcurementStatus
from backend.app.schemas.procurement import ProcurementCreate


class ProcurementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, procurement_id: int) -> ProcurementRecord | None:
        return self.db.get(ProcurementRecord, procurement_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ProcurementRecord]:
        result = self.db.execute(select(ProcurementRecord).offset(skip).limit(limit))
        return list(result.scalars().all())

    def get_by_dpc_and_date_range(
        self, dpc_id: int, start_date: date, end_date: date
    ) -> list[ProcurementRecord]:
        result = self.db.execute(
            select(ProcurementRecord).where(
                ProcurementRecord.dpc_id == dpc_id,
                ProcurementRecord.date >= start_date,
                ProcurementRecord.date <= end_date,
            ).order_by(ProcurementRecord.date)
        )
        return list(result.scalars().all())

    def get_by_date_range(self, start_date: date, end_date: date) -> list[ProcurementRecord]:
        result = self.db.execute(
            select(ProcurementRecord).where(
                ProcurementRecord.date >= start_date,
                ProcurementRecord.date <= end_date,
            ).order_by(ProcurementRecord.date)
        )
        return list(result.scalars().all())

    def get_summary(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> dict:
        filters = []
        if start_date:
            filters.append(ProcurementRecord.date >= start_date)
        if end_date:
            filters.append(ProcurementRecord.date <= end_date)

        row = self.db.execute(
            select(
                func.count(ProcurementRecord.id).label("total_records"),
                func.coalesce(func.sum(ProcurementRecord.bags), 0).label("total_bags"),
                func.coalesce(func.sum(ProcurementRecord.quantity_quintal), 0.0).label("total_quantity"),
                func.coalesce(func.avg(ProcurementRecord.moisture_pct), 0.0).label("avg_moisture"),
                func.min(ProcurementRecord.date).label("date_start"),
                func.max(ProcurementRecord.date).label("date_end"),
            ).where(*filters)
        ).one()

        status_counts = {}
        for status in ProcurementStatus:
            count = self.db.execute(
                select(func.count(ProcurementRecord.id)).where(
                    ProcurementRecord.status == status, *filters
                )
            ).scalar_one()
            status_counts[status.value] = count

        return {
            "total_records": row.total_records,
            "total_bags": int(row.total_bags),
            "total_quantity_quintal": float(row.total_quantity),
            "accepted_count": status_counts.get("accepted", 0),
            "rejected_count": status_counts.get("rejected", 0),
            "pending_count": status_counts.get("pending", 0),
            "avg_moisture_pct": round(float(row.avg_moisture), 2),
            "date_range_start": row.date_start,
            "date_range_end": row.date_end,
        }

    def create(self, data: ProcurementCreate) -> ProcurementRecord:
        procurement = ProcurementRecord(**data.model_dump())
        self.db.add(procurement)
        self.db.commit()
        self.db.refresh(procurement)
        return procurement

    def count(self) -> int:
        result = self.db.execute(select(func.count(ProcurementRecord.id)))
        return result.scalar_one()
