from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.ml.service import MLService
from backend.app.services.farmer_service import FarmerService
from backend.app.services.dpc_service import DPCService
from backend.app.services.prediction_service import PredictionService
from backend.app.services.risk_service import RiskService
from backend.app.services.recommendation_service import RecommendationService
from backend.app.services.scenario_service import ScenarioService

DbSession = Annotated[Session, Depends(get_db)]


def get_farmer_service(db: DbSession) -> FarmerService:
    return FarmerService(db)


def get_dpc_service(db: DbSession) -> DPCService:
    return DPCService(db)


def get_prediction_service(db: DbSession) -> PredictionService:
    return PredictionService(db)


def get_ml_service(db: DbSession) -> MLService:
    return MLService(db)


def get_risk_service(db: DbSession) -> RiskService:
    return RiskService(db)


def get_recommendation_service(db: DbSession) -> RecommendationService:
    return RecommendationService(db)


def get_scenario_service(db: DbSession) -> ScenarioService:
    return ScenarioService(db)
