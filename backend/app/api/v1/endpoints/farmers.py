from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_farmer_service
from backend.app.schemas.common import PaginatedResponse, SuccessResponse
from backend.app.schemas.farmer import FarmerCreate, FarmerRead, FarmerUpdate
from backend.app.services.farmer_service import FarmerService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[FarmerRead])
def list_farmers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: FarmerService = Depends(get_farmer_service),
) -> PaginatedResponse[FarmerRead]:
    farmers, total = service.list_farmers(skip=skip, limit=limit)
    return PaginatedResponse(
        items=[FarmerRead.model_validate(f) for f in farmers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{farmer_id}", response_model=FarmerRead)
def get_farmer(
    farmer_id: int,
    service: FarmerService = Depends(get_farmer_service),
) -> FarmerRead:
    farmer = service.get_farmer(farmer_id)
    return FarmerRead.model_validate(farmer)


@router.post("", response_model=FarmerRead, status_code=201)
def create_farmer(
    data: FarmerCreate,
    service: FarmerService = Depends(get_farmer_service),
) -> FarmerRead:
    farmer = service.create_farmer(data)
    return FarmerRead.model_validate(farmer)


@router.put("/{farmer_id}", response_model=FarmerRead)
def update_farmer(
    farmer_id: int,
    data: FarmerUpdate,
    service: FarmerService = Depends(get_farmer_service),
) -> FarmerRead:
    farmer = service.update_farmer(farmer_id, data)
    return FarmerRead.model_validate(farmer)


@router.delete("/{farmer_id}", response_model=SuccessResponse)
def delete_farmer(
    farmer_id: int,
    service: FarmerService = Depends(get_farmer_service),
) -> SuccessResponse:
    service.delete_farmer(farmer_id)
    return SuccessResponse(message="Farmer deleted successfully", id=farmer_id)
