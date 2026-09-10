from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.schemas.risk import RiskItem
from backend.app.services.risk_service import RiskService

router = APIRouter()


@router.get("", response_model=list[RiskItem])
def get_risks(
    target_date: date | None = Query(default=None, description="Date to analyze; defaults to today"),
    db: Session = Depends(get_db),
) -> list[RiskItem]:
    """Run the risk engine and return the detected operational risks (diagnostic perspective)."""
    service = RiskService(db)
    risks = service.detect_risks(target_date=target_date)

    items: list[RiskItem] = []
    for r in risks:
        items.append(
            RiskItem(
                risk_type=str(r.get("risk_type", "unknown")),
                severity=str(r.get("severity", "medium")),
                dpc_id=int(r["dpc_id"]) if r.get("dpc_id") is not None else None,
                dpc_name=str(r.get("dpc_name") or ""),
                description=str(r.get("description", "")),
                metric=float(r.get("metric", 0) or 0),
            )
        )
    return items