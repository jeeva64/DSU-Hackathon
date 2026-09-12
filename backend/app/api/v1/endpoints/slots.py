from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.repositories.slot_repo import SlotRepository
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.slot import SlotCreate, SlotRead

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[SlotRead],
    summary="List slots with optional DPC/date filtering",
)
def list_slots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    dpc_id: int | None = Query(default=None, description="Filter by DPC"),
    date: date | None = Query(default=None, alias="date", description="Filter by slot date"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SlotRead]:
    repo = SlotRepository(db)
    items = repo.get_all(skip=skip, limit=limit, dpc_id=dpc_id, target_date=date)
    total = repo.count(dpc_id=dpc_id, target_date=date)
    return PaginatedResponse(
        items=[SlotRead.model_validate(s) for s in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/available",
    response_model=list[SlotRead],
    summary="List available/partially-booked slots",
)
def list_available_slots(
    dpc_id: int | None = Query(default=None, description="Filter by DPC"),
    date: date | None = Query(default=None, alias="date", description="Filter by slot date"),
    db: Session = Depends(get_db),
) -> list[SlotRead]:
    repo = SlotRepository(db)
    if dpc_id is not None and date is not None:
        items = repo.get_available_slots(dpc_id, date)
    else:
        items = repo.get_available_all(target_date=date)
        if dpc_id is not None:
            items = [s for s in items if s.dpc_id == dpc_id]
    return [SlotRead.model_validate(s) for s in items]


@router.post(
    "",
    response_model=SlotRead,
    status_code=201,
    summary="Create a procurement slot for a DPC",
)
def create_slot(
    data: SlotCreate,
    db: Session = Depends(get_db),
) -> SlotRead:
    repo = SlotRepository(db)
    slot = repo.create(**data.model_dump())
    return SlotRead.model_validate(slot)