from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_scenario_service
from backend.app.schemas.scenario import ScenarioRead, ScenarioResultResponse, ScenarioRunRequest
from backend.app.services.scenario_service import ScenarioService

router = APIRouter()


@router.get(
    "/scenarios",
    response_model=list[ScenarioRead],
    summary="List available simulation scenarios",
)
def list_scenarios(
    service: ScenarioService = Depends(get_scenario_service),
) -> list[ScenarioRead]:
    scenarios = service.list_scenarios()
    return [ScenarioRead.model_validate(s) for s in scenarios]


@router.post(
    "/run",
    response_model=ScenarioResultResponse,
    summary="Run a simulation scenario",
)
def run_scenario(
    request: ScenarioRunRequest,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioResultResponse:
    result = service.run_scenario(request.scenario_name)
    return ScenarioResultResponse(**result)