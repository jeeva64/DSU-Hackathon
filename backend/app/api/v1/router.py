from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    health,
    farmers,
    dpcs,
    procurement,
    predictions,
    recommendations,
    scenarios,
    simulation,
    risks,
    ml,
    slots,
    dashboard,
)

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_v1_router.include_router(farmers.router, prefix="/farmers", tags=["farmers"])
api_v1_router.include_router(dpcs.router, prefix="/dpcs", tags=["dpcs"])
api_v1_router.include_router(procurement.router, prefix="/procurement", tags=["procurement"])
api_v1_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_v1_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_v1_router.include_router(scenarios.router, prefix="/scenarios", tags=["scenarios"])
api_v1_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
api_v1_router.include_router(risks.router, prefix="/risks", tags=["risks"])
api_v1_router.include_router(ml.router, prefix="/ml", tags=["ml"])
api_v1_router.include_router(slots.router, prefix="/slots", tags=["slots"])
