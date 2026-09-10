from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.farmer import HarvestReadiness


class FarmerCreate(BaseModel):
    farmer_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    village: str = Field(min_length=1, max_length=255)
    district: str = Field(min_length=1, max_length=255)
    location_area: str | None = Field(default=None, max_length=255)
    cultivated_area: float = Field(gt=0)
    paddy_variety: str = Field(default="paddy", max_length=100)
    expected_quantity: float | None = Field(default=None, gt=0)
    harvest_readiness: HarvestReadiness | None = None
    mobile: str | None = Field(default=None, max_length=15)
    sowing_date: date | None = None


class FarmerUpdate(BaseModel):
    farmer_code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    village: str | None = Field(default=None, min_length=1, max_length=255)
    district: str | None = Field(default=None, min_length=1, max_length=255)
    location_area: str | None = Field(default=None, max_length=255)
    cultivated_area: float | None = Field(default=None, gt=0)
    paddy_variety: str | None = Field(default=None, max_length=100)
    expected_quantity: float | None = Field(default=None, gt=0)
    harvest_readiness: HarvestReadiness | None = None
    mobile: str | None = Field(default=None, max_length=15)
    sowing_date: date | None = None


class FarmerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_code: str
    name: str
    village: str
    district: str
    location_area: str | None
    cultivated_area: float
    paddy_variety: str
    expected_quantity: float | None
    harvest_readiness: HarvestReadiness | None
    mobile: str | None
    sowing_date: date | None
    created_at: datetime
