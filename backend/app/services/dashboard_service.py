from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.dpc import OperatingStatus
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.farmer_repo import FarmerRepository
from backend.app.repositories.procurement_repo import ProcurementRepository
from backend.app.repositories.recommendation_repo import RecommendationRepository

logger = logging.getLogger("backend.services.dashboard")


class DashboardService:
    """Aggregates operational KPIs across repositories for the dashboard endpoint."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.farmer_repo = FarmerRepository(db)
        self.dpc_repo = DPCRepository(db)
        self.procurement_repo = ProcurementRepository(db)
        self.recommendation_repo = RecommendationRepository(db)

    def summary(
        self,
        target_date: date | None = None,
        risks: list[dict] | None = None,
        ml_trained: bool = False,
    ) -> dict:
        if target_date is None:
            target_date = date.today()

        total_farmers = self.farmer_repo.count()
        dpcs = self.dpc_repo.get_all(skip=0, limit=500)
        active_dpcs = [d for d in dpcs if d.operating_status == OperatingStatus.active]
        total_daily_capacity = sum(d.daily_capacity for d in active_dpcs or dpcs)

        proc = self.procurement_repo.get_summary(start_date=target_date, end_date=target_date)
        pending = len(self.recommendation_repo.get_pending())

        risks = risks or []
        by_severity: dict[str, int] = {}
        for risk in risks:
            severity = risk.get("severity", "low")
            by_severity[severity] = by_severity.get(severity, 0) + 1
        open_risks = len(risks)
        critical_risks = by_severity.get("critical", 0)

        average_utilization = 0.0
        if total_daily_capacity > 0:
            average_utilization = round(
                (proc.get("total_bags", 0) / total_daily_capacity) * 100, 2
            )

        logger.info(
            "Dashboard summary for %s: %d farmers, %d dpcs, %d risks",
            target_date, total_farmers, len(dpcs), open_risks,
        )
        return {
            "date": target_date,
            "total_farmers": total_farmers,
            "total_dpcs": len(dpcs),
            "active_dpcs": len(active_dpcs),
            "total_daily_capacity": total_daily_capacity,
            "average_utilization_pct": round(average_utilization, 2),
            "procured_today_bags": proc.get("total_bags", 0),
            "procured_today_quantity": proc.get("total_quantity_quintal", 0.0),
            "pending_recommendations": pending,
            "open_risks": open_risks,
            "critical_risks": critical_risks,
            "risk_by_severity": by_severity,
            "ml_trained": ml_trained,
        }