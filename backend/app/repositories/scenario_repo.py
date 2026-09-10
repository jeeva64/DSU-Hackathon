from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.scenario import SimulationScenario


class ScenarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, scenario_id: int) -> SimulationScenario | None:
        return self.db.get(SimulationScenario, scenario_id)

    def get_by_name(self, name: str) -> SimulationScenario | None:
        result = self.db.execute(
            select(SimulationScenario).where(SimulationScenario.name == name)
        )
        return result.scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[SimulationScenario]:
        result = self.db.execute(
            select(SimulationScenario).order_by(SimulationScenario.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    def count(self) -> int:
        result = self.db.execute(select(func.count(SimulationScenario.id)))
        return result.scalar_one()

    def create(self, **kwargs) -> SimulationScenario:
        scenario = SimulationScenario(**kwargs)
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def update_results(self, scenario_id: int, results_json: dict) -> SimulationScenario | None:
        scenario = self.get_by_id(scenario_id)
        if not scenario:
            return None
        scenario.results_json = results_json
        self.db.commit()
        self.db.refresh(scenario)
        return scenario
