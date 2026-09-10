from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.models.scenario import SimulationStatus


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    parameters: dict
    results_json: dict | None
    status: SimulationStatus
    created_at: datetime


class ScenarioRunRequest(BaseModel):
    scenario_name: str


class ScenarioResultResponse(BaseModel):
    scenario_name: str
    description: str
    risks: list[dict]
    predictions: list[dict]
    recommendations: list[dict]
    summary: dict
    data_source: str = "synthetic"
