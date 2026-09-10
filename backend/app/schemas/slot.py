from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.slot import SlotStatus


class SlotCreate(BaseModel):
    dpc_id: int
    date: date
    start_time: time
    end_time: time
    max_farmers: int = Field(gt=0, default=50)
    max_quantity: float = Field(gt=0, default=200.0)
    booked_farmers: int = Field(ge=0, default=0)
    booked_quantity: float = Field(ge=0, default=0.0)
    status: SlotStatus = SlotStatus.available


class SlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_id: int
    date: date
    start_time: time
    end_time: time
    max_farmers: int
    max_quantity: float
    booked_farmers: int
    booked_quantity: float
    status: SlotStatus
    created_at: datetime
