from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.core.config import settings
from backend.app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    checks = {}
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    all_healthy = all(v == "healthy" for v in checks.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=settings.APP_VERSION,
        checks=checks,
    )
