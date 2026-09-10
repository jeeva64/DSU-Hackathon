from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ArrivalRecordCreate(BaseModel):
    farmer_id: int
    dpc_id: int
    slot_id: int | None = None
    date: date
    arrival_time: datetime
    bags_brought: int = Field(gt=0)
    quantity_brought: float = Field(gt=0)
    wait_time_minutes: int | None = Field(default=None, ge=0)
    status: str = Field(default="pending", pattern="^(accepted|rejected|pending)$")


class ArrivalRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_id: int
    dpc_id: int
    slot_id: int | None
    date: date
    arrival_time: datetime
    bags_brought: int
    quantity_brought: float
    wait_time_minutes: int | None
    status: str
    created_at: datetime
