from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class HarvestReadiness(str, enum.Enum):
    not_ready = "not_ready"
    partially_ready = "partially_ready"
    ready = "ready"
    overdue = "overdue"


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    farmer_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    village: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cultivated_area: Mapped[float] = mapped_column(Float, nullable=False)
    paddy_variety: Mapped[str] = mapped_column(String(100), nullable=False, default="paddy")
    expected_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    harvest_readiness: Mapped[HarvestReadiness | None] = mapped_column(
        Enum(HarvestReadiness), nullable=True
    )
    mobile: Mapped[str | None] = mapped_column(String(15), nullable=True)
    sowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
