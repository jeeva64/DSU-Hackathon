from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ResourceAvailabilityCreate(BaseModel):
    dpc_id: int
    date: date
    labour_available: int = Field(ge=0, default=0)
    transport_available: int = Field(ge=0, default=0)
    weighing_capacity: int = Field(ge=0, default=0)
    storage_available: float = Field(ge=0, default=0.0)


class ResourceAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_id: int
    date: date
    labour_available: int
    transport_available: int
    weighing_capacity: int
    storage_available: float
    created_at: datetime
