from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.api.exceptions import register_exception_handlers
from backend.app.api.v1.router import api_v1_router
from backend.app.db.database import init_db

logger = logging.getLogger("backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    if settings.is_development:
        try:
            init_db()
            logger.info("Database tables initialized.")
        except Exception:
            logger.exception("Failed to initialize database tables.")

    yield

    logger.info("Shutting down %s", settings.APP_NAME)


OPENAPI_TAGS = [
    {"name": "health", "description": "Liveness and diagnostics."},
    {"name": "dashboard", "description": "Aggregated operational KPIs for the Streamlit dashboard."},
    {"name": "farmers", "description": "Farmer registry management."},
    {"name": "dpcs", "description": "DPC registry, capacity and status."},
    {"name": "procurement", "description": "Procurement records, summaries and filters."},
    {"name": "slots", "description": "Procurement slot scheduling and availability."},
    {"name": "predictions", "description": "Forecasts: ML-first with statistical fallback, plus training/status."},
    {"name": "recommendations", "description": "Deterministic slot/optimization recommendation engines and officer workflow."},
    {"name": "scenarios", "description": "Predefined simulation scenarios (legacy path)."},
    {"name": "simulation", "description": "Predefined simulation scenarios (frontend-facing path)."},
    {"name": "risks", "description": "Deterministic risk engine output and aggregation."},
    {"name": "ml", "description": "Low-level scikit-learn model training, status and prediction."},
]


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-assisted decision-support for Tamil Nadu paddy procurement. "
            "All data is synthetic demo data; AI recommends, officers decide."
        ),
        summary="NelSync AI decision-support API",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # API routes
    app.include_router(api_v1_router)

    return app
