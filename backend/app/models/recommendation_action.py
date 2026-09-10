from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class RecommendationAction(Base):
    __tablename__ = "recommendation_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    source_dpc_id: Mapped[int | None] = mapped_column(ForeignKey("dpcs.id"), nullable=True)
    target_dpc_id: Mapped[int | None] = mapped_column(ForeignKey("dpcs.id"), nullable=True)
    source_slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"), nullable=True)
    target_slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
