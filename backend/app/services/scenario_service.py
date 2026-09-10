from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.app.models.scenario import SimulationScenario, SimulationStatus
from backend.app.repositories.scenario_repo import ScenarioRepository

logger = logging.getLogger("backend.services.scenario")


SCENARIO_CONFIGS = {
    "NORMAL_DAY": {
        "description": "Typical procurement day with moderate arrivals and normal operations",
        "parameters": {
            "arrival_multiplier": 0.6,
            "capacity_utilization": 0.4,
            "rain_mm": 0,
            "transport_availability_pct": 100,
            "labour_availability_pct": 100,
            "storage_utilization_pct": 40,
            "humidity_pct": 60,
        },
    },
    "DPC_OVERLOAD": {
        "description": "High arrivals pushing DPC capacity limits",
        "parameters": {
            "arrival_multiplier": 1.2,
            "capacity_utilization": 0.85,
            "rain_mm": 0,
            "transport_availability_pct": 100,
            "labour_availability_pct": 100,
            "storage_utilization_pct": 80,
            "humidity_pct": 55,
        },
    },
    "RAIN_RISK": {
        "description": "Heavy rain forecast threatening procurement and stored paddy",
        "parameters": {
            "arrival_multiplier": 0.8,
            "capacity_utilization": 0.6,
            "rain_mm": 25,
            "transport_availability_pct": 70,
            "labour_availability_pct": 90,
            "storage_utilization_pct": 60,
            "humidity_pct": 85,
        },
    },
    "TRANSPORT_BOTTLENECK": {
        "description": "Limited transport preventing paddy movement from DPC to godown",
        "parameters": {
            "arrival_multiplier": 0.9,
            "capacity_utilization": 0.7,
            "rain_mm": 5,
            "transport_availability_pct": 30,
            "labour_availability_pct": 90,
            "storage_utilization_pct": 75,
            "humidity_pct": 65,
        },
    },
    "COMBINED_CRISIS": {
        "description": "Multiple simultaneous crises: overload + rain + transport + labour constraints",
        "parameters": {
            "arrival_multiplier": 1.3,
            "capacity_utilization": 0.92,
            "rain_mm": 20,
            "transport_availability_pct": 25,
            "labour_availability_pct": 50,
            "storage_utilization_pct": 90,
            "humidity_pct": 88,
        },
    },
}


class ScenarioService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ScenarioRepository(db)

    def seed_scenarios(self) -> int:
        count = 0
        for key, scenario_data in SCENARIO_CONFIGS.items():
            existing = self.repo.get_by_name(key)
            if not existing:
                self.repo.create(
                    name=key,
                    description=scenario_data["description"],
                    parameters=scenario_data["parameters"],
                    status=SimulationStatus.draft,
                )
                count += 1
                logger.info("Seeded scenario: %s", key)
        return count

    def list_scenarios(self) -> list[SimulationScenario]:
        return self.repo.get_all()

    def get_scenario(self, scenario_name: str) -> SimulationScenario:
        scenario = self.repo.get_by_name(scenario_name)
        if not scenario:
            raise ValueError(f"Scenario '{scenario_name}' not found")
        return scenario

    def run_scenario(self, scenario_name: str) -> dict:
        scenario = self.get_scenario(scenario_name)
        params = scenario.parameters or {}

        arrival_mult = params.get("arrival_multiplier", 1.0)
        capacity_util = params.get("capacity_utilization", 0.5)
        rain_mm = params.get("rain_mm", 0)
        transport_pct = params.get("transport_availability_pct", 100)
        labour_pct = params.get("labour_availability_pct", 100)
        humidity = params.get("humidity_pct", 60)

        risks = []
        if capacity_util > 0.85:
            risks.append({
                "risk_type": "overload",
                "severity": "critical" if capacity_util > 0.95 else "high",
                "description": f"Capacity at {capacity_util*100:.0f}%",
                "metric": round(capacity_util * 100, 1),
            })
        if rain_mm > 15:
            risks.append({
                "risk_type": "rain",
                "severity": "high" if rain_mm > 20 else "medium",
                "description": f"Heavy rain forecast: {rain_mm}mm",
                "metric": rain_mm,
            })
        if transport_pct < 50:
            risks.append({
                "risk_type": "transport",
                "severity": "critical" if transport_pct < 30 else "high",
                "description": f"Transport at {transport_pct}% availability",
                "metric": transport_pct,
            })
        if labour_pct < 70:
            risks.append({
                "risk_type": "labour",
                "severity": "high" if labour_pct < 50 else "medium",
                "description": f"Labour at {labour_pct}% availability",
                "metric": labour_pct,
            })
        if humidity > 80:
            risks.append({
                "risk_type": "moisture",
                "severity": "medium",
                "description": f"High humidity ({humidity}%) increases moisture rejection risk",
                "metric": humidity,
            })

        if not risks:
            risks.append({"risk_type": "none", "severity": "low", "description": "No significant risks", "metric": 0})

        base_arrivals = 120
        predicted_arrivals = int(base_arrivals * arrival_mult)
        predicted_bags = int(predicted_arrivals * 3)

        recommendations = []
        if capacity_util > 0.85:
            recommendations.append({
                "title": "Divert farmers to adjacent DPCs",
                "explanation": f"Capacity at {capacity_util*100:.0f}% — overflow likely",
                "priority": "critical",
                "recommendation_type": "slot",
            })
        if rain_mm > 10:
            recommendations.append({
                "title": "Cover stored paddy with tarpaulins",
                "explanation": f"{rain_mm}mm rain forecast — paddy damage risk",
                "priority": "high",
                "recommendation_type": "weather",
            })
        if transport_pct < 50:
            recommendations.append({
                "title": "Arrange additional lorries immediately",
                "explanation": f"Only {transport_pct}% transport available",
                "priority": "high",
                "recommendation_type": "resource",
            })
        if labour_pct < 70:
            recommendations.append({
                "title": "Request temporary labour from neighbouring blocks",
                "explanation": f"Labour at {labour_pct}% — throughput severely reduced",
                "priority": "medium",
                "recommendation_type": "resource",
            })

        if not recommendations:
            recommendations.append({
                "title": "Continue normal operations",
                "explanation": "No critical issues detected",
                "priority": "low",
                "recommendation_type": "slot",
            })

        summary = {
            "total_risks": len(risks),
            "critical_risks": len([r for r in risks if r["severity"] == "critical"]),
            "total_recommendations": len(recommendations),
            "predicted_arrivals": predicted_arrivals,
            "predicted_bags": predicted_bags,
            "capacity_utilization_pct": round(capacity_util * 100, 1),
        }

        results = {
            "risks": risks,
            "predictions": [{"arrivals": predicted_arrivals, "bags": predicted_bags}],
            "recommendations": recommendations,
            "summary": summary,
        }

        self.repo.update_results(scenario.id, results)
        logger.info("Scenario '%s' executed: %d risks, %d recommendations", scenario_name, len(risks), len(recommendations))

        return {
            "scenario_name": scenario.name,
            "description": scenario.description,
            **results,
            "data_source": "synthetic",
        }
