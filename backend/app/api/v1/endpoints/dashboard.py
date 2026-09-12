from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_dashboard_service
from backend.app.db.database import get_db
from backend.app.ml.service import MLService
from backend.app.schemas.dashboard import DashboardSummary
from backend.app.services.dashboard_service import DashboardService
from backend.app.services.risk_service import RiskService

router = APIRouter()


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Aggregated operational KPIs for the dashboard",
)
def get_dashboard_summary(
    target_date: date | None = Query(default=None, description="Defaults to today"),
    service: DashboardService = Depends(get_dashboard_service),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    risks = RiskService(db).detect_risks(target_date=target_date)
    ml_trained = MLService(db).is_trained()
    data = service.summary(target_date=target_date, risks=risks, ml_trained=ml_trained)
    return DashboardSummary(**data)