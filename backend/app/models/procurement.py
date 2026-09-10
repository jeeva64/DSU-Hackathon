from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ProcurementStatus(str, enum.Enum):
    accepted = "accepted"
    rejected = "rejected"
    pending = "pending"


class ProcurementRecord(Base):
    __tablename__ = "procurement_records"
    __table_args__ = (
        Index("ix_procurement_dpc_date", "dpc_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"), nullable=False, index=True)
    dpc_id: Mapped[int] = mapped_column(ForeignKey("dpcs.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bags: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_quintal: Mapped[float] = mapped_column(Float, nullable=False)
    moisture_pct: Mapped[float] = mapped_column(Float, nullable=False)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[ProcurementStatus] = mapped_column(
        Enum(ProcurementStatus), nullable=False, default=ProcurementStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
