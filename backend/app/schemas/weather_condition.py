from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.weather_condition import WeatherRisk


class WeatherConditionCreate(BaseModel):
    date: date
    location: str = Field(min_length=1, max_length=255)
    rainfall_probability: float = Field(ge=0, le=100, default=0.0)
    rainfall_mm: float = Field(ge=0, default=0.0)
    humidity: float = Field(ge=0, le=100, default=50.0)
    temperature_max: float | None = None
    weather_risk: WeatherRisk = WeatherRisk.none


class WeatherConditionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    location: str
    rainfall_probability: float
    rainfall_mm: float
    humidity: float
    temperature_max: float | None
    weather_risk: WeatherRisk
    created_at: datetime
