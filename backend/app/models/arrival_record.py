from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ArrivalRecord(Base):
    __tablename__ = "arrival_records"
    __table_args__ = (
        Index("ix_arrival_dpc_date", "dpc_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), nullable=False, index=True)
    dpc_id: Mapped[int] = mapped_column(ForeignKey("dpcs.id"), nullable=False, index=True)
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"), nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bags_brought: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_brought: Mapped[float] = mapped_column(Float, nullable=False)
    wait_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("accepted", "rejected", "pending", name="arrival_status"),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
