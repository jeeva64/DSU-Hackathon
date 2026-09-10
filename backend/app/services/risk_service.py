from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.dpc import DPC
from backend.app.models.prediction import PredictionType
from backend.app.models.risk_assessment import RiskType, RiskSeverity
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.prediction_repo import PredictionRepository
from backend.app.repositories.risk_assessment_repo import RiskAssessmentRepository

logger = logging.getLogger("backend.services.risk")


class RiskService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dpc_repo = DPCRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.risk_repo = RiskAssessmentRepository(db)

    def detect_risks(self, target_date: date | None = None) -> list[dict]:
        if target_date is None:
            target_date = date.today()

        risks = []
        dpcs = self.dpc_repo.get_active()

        for dpc in dpcs:
            preds = self.prediction_repo.get_by_dpc(
                dpc.id, prediction_type=PredictionType.quantity, limit=1
            )
            if not preds:
                continue
            pred = preds[0]

            capacity_pct = (pred.predicted_value / dpc.daily_capacity * 100) if dpc.daily_capacity > 0 else 0

            if capacity_pct > 85:
                severity = RiskSeverity.critical if capacity_pct > 95 else RiskSeverity.high
                self.risk_repo.create(
                    dpc_id=dpc.id,
                    date=target_date,
                    risk_type=RiskType.overload,
                    severity=severity,
                    score=min(100, capacity_pct),
                    explanation=f"DPC {dpc.name} at {capacity_pct:.0f}% predicted capacity",
                    mitigation="Divert farmers to adjacent DPCs",
                )
                risks.append({
                    "risk_type": "overload",
                    "severity": severity.value,
                    "dpc_id": dpc.id,
                    "dpc_name": dpc.name,
                    "description": f"DPC {dpc.name} at {capacity_pct:.0f}% predicted capacity",
                    "metric": round(capacity_pct, 1),
                })

            queue_preds = self.prediction_repo.get_by_dpc(
                dpc.id, prediction_type=PredictionType.queue_length, limit=1
            )
            if queue_preds and queue_preds[0].predicted_value > 50:
                queue_val = queue_preds[0].predicted_value
                severity = RiskSeverity.critical if queue_val > 100 else RiskSeverity.high
                self.risk_repo.create(
                    dpc_id=dpc.id,
                    date=target_date,
                    risk_type=RiskType.congestion,
                    severity=severity,
                    score=min(100, queue_val),
                    explanation=f"Queue of {int(queue_val)} farmers expected",
                    mitigation="Extend operating hours or add processing stations",
                )
                risks.append({
                    "risk_type": "congestion",
                    "severity": severity.value,
                    "dpc_id": dpc.id,
                    "dpc_name": dpc.name,
                    "description": f"Queue of {int(queue_val)} farmers expected",
                    "metric": queue_val,
                })

        if not risks:
            risks.append({
                "risk_type": "none",
                "severity": "low",
                "dpc_id": None,
                "dpc_name": "System-wide",
                "description": "No significant risks detected",
                "metric": 0,
            })

        risks.sort(key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["severity"], 4))
        logger.info("Detected %d risks for %s", len(risks), target_date)
        return risks
