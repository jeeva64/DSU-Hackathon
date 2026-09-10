from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class OperatingStatus(str, enum.Enum):
    active = "active"
    maintenance = "maintenance"
    closed = "closed"
    overloaded = "overloaded"


class DPC(Base):
    __tablename__ = "dpcs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dpc_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    daily_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    processing_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    storage_capacity: Mapped[float] = mapped_column(Float, nullable=False, default=250.0)
    operating_status: Mapped[OperatingStatus] = mapped_column(
        Enum(OperatingStatus), nullable=False, default=OperatingStatus.active
    )
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
