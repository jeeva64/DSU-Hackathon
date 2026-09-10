from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DPCCapacityCreate(BaseModel):
    dpc_id: int
    date: date
    planned_capacity: int = Field(gt=0)
    used_capacity: int = Field(ge=0, default=0)
    remaining_capacity: int = Field(ge=0)
    utilization_pct: float = Field(ge=0, le=100, default=0.0)


class DPCCapacityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_id: int
    date: date
    planned_capacity: int
    used_capacity: int
    remaining_capacity: int
    utilization_pct: float
    created_at: datetime
