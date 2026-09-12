from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.deps import (
    get_optimization_service,
    get_recommendation_service,
    get_slot_recommendation_service,
)
from backend.app.models.recommendation import RecommendationStatus
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.optimization import OptimizationRequest, OptimizationResultRead
from backend.app.schemas.recommendation import (
    RecommendationActionResponse,
    RecommendationAnalysisItem,
    RecommendationAnalysisRequest,
    RecommendationApproveRequest,
    RecommendationRead,
    RecommendationRejectRequest,
)
from backend.app.services.optimization_service import OptimizationService
from backend.app.services.recommendation_service import RecommendationService
from backend.app.services.slot_recommendation_service import SlotRecommendationService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[RecommendationRead],
    summary="List recommendations with optional status/DPC/date filters",
)
def list_recommendations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: RecommendationStatus | None = Query(default=None, description="Filter by status"),
    dpc_id: int | None = Query(default=None, description="Filter by DPC"),
    date: date | None = Query(default=None, alias="date", description="Filter by recommendation date"),
    service: RecommendationService = Depends(get_recommendation_service),
) -> PaginatedResponse[RecommendationRead]:
    recs, total = service.list_recommendations_filtered(
        skip=skip, limit=limit, status=status, dpc_id=dpc_id, target_date=date
    )
    return PaginatedResponse(
        items=[RecommendationRead.model_validate(r) for r in recs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/analysis", response_model=list[RecommendationAnalysisItem])
def analyze_recommendations(
    request: RecommendationAnalysisRequest,
    service: SlotRecommendationService = Depends(get_slot_recommendation_service),
) -> list[RecommendationAnalysisItem]:
    results = service.analyze(target_date=request.target_date, persist=request.persist)
    return [RecommendationAnalysisItem(**r) for r in results]


@router.post(
    "/analyze",
    response_model=list[RecommendationAnalysisItem],
    summary="Run slot recommendation analysis (alias of /analysis)",
)
def analyze_recommendations_alias(
    request: RecommendationAnalysisRequest,
    service: SlotRecommendationService = Depends(get_slot_recommendation_service),
) -> list[RecommendationAnalysisItem]:
    results = service.analyze(target_date=request.target_date, persist=request.persist)
    return [RecommendationAnalysisItem(**r) for r in results]


@router.post("/optimize", response_model=OptimizationResultRead)
def optimize_recommendations(
    request: OptimizationRequest,
    service: OptimizationService = Depends(get_optimization_service),
) -> OptimizationResultRead:
    result = service.optimize(target_date=request.target_date, persist=request.persist)
    return OptimizationResultRead(**result)


@router.get("/pending", response_model=list[RecommendationRead])
def list_pending_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
) -> list[RecommendationRead]:
    recs = service.get_pending()
    return [RecommendationRead.model_validate(r) for r in recs]


@router.get("/{rec_id}", response_model=RecommendationRead)
def get_recommendation(
    rec_id: int,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationRead:
    try:
        return RecommendationRead.model_validate(service.get_by_id(rec_id))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")


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
