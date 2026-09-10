from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.procurement import ProcurementStatus


class ProcurementCreate(BaseModel):
    farmer_id: int
    dpc_id: int
    date: date
    bags: int = Field(gt=0)
    quantity_quintal: float = Field(gt=0)
    moisture_pct: float = Field(ge=0, le=100)
    grade: str | None = Field(default=None, max_length=10)
    status: ProcurementStatus = ProcurementStatus.pending


class ProcurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_id: int
    dpc_id: int
    date: date
    bags: int
    quantity_quintal: float
    moisture_pct: float
    grade: str | None
    status: ProcurementStatus
    created_at: datetime


class ProcurementSummary(BaseModel):
    total_records: int
    total_bags: int
    total_quantity_quintal: float
    accepted_count: int
    rejected_count: int
    pending_count: int
    avg_moisture_pct: float
    date_range_start: date | None
    date_range_end: date | None
