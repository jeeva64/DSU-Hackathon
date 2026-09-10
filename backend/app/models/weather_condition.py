from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class WeatherRisk(str, enum.Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class WeatherCondition(Base):
    __tablename__ = "weather_conditions"
    __table_args__ = (
        UniqueConstraint("date", "location", name="uq_weather_date_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    rainfall_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rainfall_mm: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    humidity: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    temperature_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_risk: Mapped[WeatherRisk] = mapped_column(
        Enum(WeatherRisk), nullable=False, default=WeatherRisk.none
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
