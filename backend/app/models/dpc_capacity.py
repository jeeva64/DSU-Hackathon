from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class DPCCapacity(Base):
    __tablename__ = "dpc_capacities"
    __table_args__ = (
        UniqueConstraint("dpc_id", "date", name="uq_dpc_capacity_dpc_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dpc_id: Mapped[int] = mapped_column(ForeignKey("dpcs.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    used_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remaining_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    utilization_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
