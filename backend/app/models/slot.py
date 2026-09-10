from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SlotStatus(str, enum.Enum):
    available = "available"
    partially_booked = "partially_booked"
    full = "full"
    closed = "closed"


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        Index("ix_slot_dpc_date_time", "dpc_id", "date", "start_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dpc_id: Mapped[int] = mapped_column(ForeignKey("dpcs.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    max_farmers: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    max_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=200.0)
    booked_farmers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    booked_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus), nullable=False, default=SlotStatus.available
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
