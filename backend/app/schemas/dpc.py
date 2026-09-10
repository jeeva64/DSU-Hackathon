from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.dpc import OperatingStatus


class DPCCreate(BaseModel):
    dpc_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    district: str = Field(min_length=1, max_length=255)
    daily_capacity: int = Field(gt=0, default=1000)
    processing_rate: float | None = Field(default=None, gt=0)
    storage_capacity: float = Field(gt=0, default=250.0)
    operating_status: OperatingStatus = OperatingStatus.active
    lat: float | None = None
    lon: float | None = None
    open_date: date | None = None
    close_date: date | None = None


class DPCUpdate(BaseModel):
    dpc_code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    district: str | None = Field(default=None, min_length=1, max_length=255)
    daily_capacity: int | None = Field(default=None, gt=0)
    processing_rate: float | None = Field(default=None, gt=0)
    storage_capacity: float | None = Field(default=None, gt=0)
    operating_status: OperatingStatus | None = None
    lat: float | None = None
    lon: float | None = None
    open_date: date | None = None
    close_date: date | None = None


class DPCRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dpc_code: str
    name: str
    district: str
    daily_capacity: int
    processing_rate: float | None
    storage_capacity: float
    operating_status: OperatingStatus
    lat: float | None
    lon: float | None
    open_date: date | None
    close_date: date | None
    created_at: datetime


class DPCCapacityResponse(BaseModel):
    dpc_id: int
    dpc_name: str
    daily_capacity: int
    storage_capacity: float
    current_utilization_pct: float
    bags_received_today: int
    remaining_capacity_bags: int
