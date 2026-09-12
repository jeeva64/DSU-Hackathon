from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.risk import RiskAnalyzeRequest, RiskItem, RiskSummary
from backend.app.services.risk_service import RiskService

router = APIRouter()


def _filter_risks(
    risks: list[dict],
    severity: str | None = None,
    risk_type: str | None = None,
    dpc_id: int | None = None,
) -> list[dict]:
    filtered = risks
    if severity:
        filtered = [r for r in filtered if str(r.get("severity", "")) == severity]
    if risk_type:
        filtered = [r for r in filtered if str(r.get("risk_type", "")) == risk_type]
    if dpc_id is not None:
        filtered = [r for r in filtered if r.get("dpc_id") == dpc_id]
    return filtered


def _to_items(risks: list[dict]) -> list[RiskItem]:
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


@router.get(
    "",
    response_model=PaginatedResponse[RiskItem],
    summary="Run the risk engine and list detected risks (filterable)",
)
def get_risks(
    target_date: date | None = Query(default=None, description="Date to analyze; defaults to today"),
    severity: str | None = Query(default=None, description="Filter by severity (low/medium/high/critical)"),
    risk_type: str | None = Query(default=None, description="Filter by risk type (e.g. overload, rain)"),
    dpc_id: int | None = Query(default=None, description="Filter by DPC"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RiskItem]:
    """Run the deterministic risk engine and return the detected operational risks."""
    service = RiskService(db)
    risks = service.detect_risks(target_date=target_date)
    filtered = _filter_risks(risks, severity=severity, risk_type=risk_type, dpc_id=dpc_id)
    page = filtered[skip : skip + limit]
    return PaginatedResponse(
        items=_to_items(page),
        total=len(filtered),
        skip=skip,
        limit=limit,
    )


@router.get(
    "/summary",
    response_model=RiskSummary,
    summary="Aggregated risk counts by severity/type for a target date",
)
def get_risks_summary(
    target_date: date | None = Query(default=None, description="Date to analyze; defaults to today"),
    db: Session = Depends(get_db),
) -> RiskSummary:
    service = RiskService(db)
    risks = service.detect_risks(target_date=target_date)
    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for r in risks:
        by_severity[str(r.get("severity", "low"))] = by_severity.get(str(r.get("severity", "low")), 0) + 1
        by_type[str(r.get("risk_type", "unknown"))] = by_type.get(str(r.get("risk_type", "unknown")), 0) + 1
    return RiskSummary(
        target_date=target_date or date.today(),
        total_risks=len(risks),
        critical_count=by_severity.get("critical", 0),
        by_severity=by_severity,
        by_type=by_type,
    )


@router.post(
    "/analyze",
    response_model=list[RiskItem],
    summary="Re-run the risk engine for a given target date (persists assessments)",
)
def analyze_risks(
    request: RiskAnalyzeRequest,
    db: Session = Depends(get_db),
) -> list[RiskItem]:
    service = RiskService(db)
    risks = service.detect_risks(target_date=request.target_date)
    filtered = _filter_risks(risks, dpc_id=request.dpc_id)
    return _to_items(filtered)