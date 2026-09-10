from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class PredictionType(str, enum.Enum):
    arrival_count = "arrival_count"
    quantity = "quantity"
    queue_length = "queue_length"
    processing_time = "processing_time"


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_prediction_dpc_target_type", "dpc_id", "target_date", "prediction_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dpc_id: Mapped[int] = mapped_column(ForeignKey("dpcs.id"), nullable=False, index=True)
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    prediction_type: Mapped[PredictionType] = mapped_column(Enum(PredictionType), nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v0.1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
