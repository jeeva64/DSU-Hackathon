from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_recommendation_service
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.recommendation import (
    RecommendationActionResponse,
    RecommendationApproveRequest,
    RecommendationRead,
    RecommendationRejectRequest,
)
from backend.app.services.recommendation_service import RecommendationService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[RecommendationRead])
def list_recommendations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: RecommendationService = Depends(get_recommendation_service),
) -> PaginatedResponse[RecommendationRead]:
    recs, total = service.list_recommendations(skip=skip, limit=limit)
    return PaginatedResponse(
        items=[RecommendationRead.model_validate(r) for r in recs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/pending", response_model=list[RecommendationRead])
def list_pending_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
) -> list[RecommendationRead]:
    recs = service.get_pending()
    return [RecommendationRead.model_validate(r) for r in recs]


@router.post("/{rec_id}/approve", response_model=RecommendationActionResponse)
def approve_recommendation(
    rec_id: int,
    request: RecommendationApproveRequest = RecommendationApproveRequest(),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationActionResponse:
    result = service.approve_recommendation(rec_id, request.officer_notes)
    return RecommendationActionResponse(**result)


@router.post("/{rec_id}/reject", response_model=RecommendationActionResponse)
def reject_recommendation(
    rec_id: int,
    request: RecommendationRejectRequest = RecommendationRejectRequest(),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationActionResponse:
    result = service.reject_recommendation(rec_id, request.officer_notes)
    return RecommendationActionResponse(**result)


@router.post("/generate", response_model=list[dict])
def generate_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
) -> list[dict]:
    return service.generate_recommendations()
