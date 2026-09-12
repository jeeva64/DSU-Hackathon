from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.models.procurement import ProcurementStatus
from backend.app.repositories.procurement_repo import ProcurementRepository
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.procurement import ProcurementCreate, ProcurementRead, ProcurementSummary

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[ProcurementRead],
    summary="List procurement records with optional date/DPC/status filters",
)
def list_procurement(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    start_date: date | None = Query(default=None, description="Earliest record date (inclusive)"),
    end_date: date | None = Query(default=None, description="Latest record date (inclusive)"),
    dpc_id: int | None = Query(default=None, description="Filter by DPC"),
    status: ProcurementStatus | None = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProcurementRead]:
    repo = ProcurementRepository(db)
    items = repo.get_all(
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        dpc_id=dpc_id,
        status=status,
    )
    total = repo.count_filtered(
        start_date=start_date,
        end_date=end_date,
        dpc_id=dpc_id,
        status=status,
    )
    return PaginatedResponse(
        items=[ProcurementRead.model_validate(p) for p in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/summary", response_model=ProcurementSummary)
def get_procurement_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
) -> ProcurementSummary:
    repo = ProcurementRepository(db)
    summary = repo.get_summary(start_date=start_date, end_date=end_date)
    return ProcurementSummary(**summary)


@router.post("", response_model=ProcurementRead, status_code=201)
def create_procurement(
    data: ProcurementCreate,
    db: Session = Depends(get_db),
) -> ProcurementRead:
    repo = ProcurementRepository(db)
    procurement = repo.create(data)
    return ProcurementRead.model_validate(procurement)
