from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_dpc_service
from backend.app.schemas.common import PaginatedResponse, SuccessResponse
from backend.app.schemas.dpc import DPCCapacityResponse, DPCCreate, DPCRead, DPCUpdate
from backend.app.services.dpc_service import DPCService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[DPCRead])
def list_dpcs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: DPCService = Depends(get_dpc_service),
) -> PaginatedResponse[DPCRead]:
    dpcs, total = service.list_dpcs(skip=skip, limit=limit)
    return PaginatedResponse(
        items=[DPCRead.model_validate(d) for d in dpcs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{dpc_id}", response_model=DPCRead)
def get_dpc(
    dpc_id: int,
    service: DPCService = Depends(get_dpc_service),
) -> DPCRead:
    dpc = service.get_dpc(dpc_id)
    return DPCRead.model_validate(dpc)


@router.get("/{dpc_id}/capacity", response_model=DPCCapacityResponse)
def get_dpc_capacity(
    dpc_id: int,
    service: DPCService = Depends(get_dpc_service),
) -> DPCCapacityResponse:
    info = service.get_capacity_info(dpc_id)
    return DPCCapacityResponse(**info)


@router.post("", response_model=DPCRead, status_code=201)
def create_dpc(
    data: DPCCreate,
    service: DPCService = Depends(get_dpc_service),
) -> DPCRead:
    dpc = service.create_dpc(data)
    return DPCRead.model_validate(dpc)


@router.put("/{dpc_id}", response_model=DPCRead)
def update_dpc(
    dpc_id: int,
    data: DPCUpdate,
    service: DPCService = Depends(get_dpc_service),
) -> DPCRead:
    dpc = service.update_dpc(dpc_id, data)
    return DPCRead.model_validate(dpc)


@router.delete("/{dpc_id}", response_model=SuccessResponse)
def delete_dpc(
    dpc_id: int,
    service: DPCService = Depends(get_dpc_service),
) -> SuccessResponse:
    service.delete_dpc(dpc_id)
    return SuccessResponse(message="DPC deleted successfully", id=dpc_id)
