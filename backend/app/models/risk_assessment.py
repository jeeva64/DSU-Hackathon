from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class RiskType(str, enum.Enum):
    overload = "overload"
    congestion = "congestion"
    rain = "rain"
    transport = "transport"
    labour = "labour"
    storage = "storage"
    moisture = "moisture"
    combined = "combined"


class RiskSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        Index("ix_risk_dpc_date_type", "dpc_id", "date", "risk_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dpc_id: Mapped[int] = mapped_column(ForeignKey("dpcs.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_type: Mapped[RiskType] = mapped_column(Enum(RiskType), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(Enum(RiskSeverity), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
