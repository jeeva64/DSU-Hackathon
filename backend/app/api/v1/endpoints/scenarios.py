from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_scenario_service
from backend.app.schemas.scenario import ScenarioRead, ScenarioResultResponse, ScenarioRunRequest
from backend.app.services.scenario_service import ScenarioService

router = APIRouter()


@router.get("", response_model=list[ScenarioRead])
def list_scenarios(
    service: ScenarioService = Depends(get_scenario_service),
) -> list[ScenarioRead]:
    scenarios = service.list_scenarios()
    return [ScenarioRead.model_validate(s) for s in scenarios]


@router.get("/{scenario_name}", response_model=ScenarioRead)
def get_scenario(
    scenario_name: str,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRead:
    scenario = service.get_scenario(scenario_name)
    return ScenarioRead.model_validate(scenario)


@router.post("/run", response_model=ScenarioResultResponse)
def run_scenario(
    request: ScenarioRunRequest,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioResultResponse:
    result = service.run_scenario(request.scenario_name)
    return ScenarioResultResponse(**result)
