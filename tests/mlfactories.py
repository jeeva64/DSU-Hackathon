"""Synthetic (>85% utilization) dataset helper for ML tests.

Builds 2 DPCs x n_days of weather/resources/capacity/arrivals/procurements
with controllable overload days so the classifier can be trained and
validated without touching the real Postgres database.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from backend.app.models.arrival_record import ArrivalRecord
from backend.app.models.dpc import DPC, OperatingStatus
from backend.app.models.dpc_capacity import DPCCapacity
from backend.app.models.farmer import Farmer, HarvestReadiness
from backend.app.models.procurement import ProcurementRecord, ProcurementStatus
from backend.app.models.resource_availability import ResourceAvailability
from backend.app.models.weather_condition import WeatherCondition, WeatherRisk

OVERLOAD_OFFSETS = {2, 3, 5, 10, 12, 18, 19, 20}


def seed_ml_dataset(db, n_days: int = 24, start: date | None = None) -> dict:
    rng = random.Random(7)
    day0 = start or date(2026, 1, 5)
    dates = [day0 + timedelta(days=o) for o in range(n_days)]

    farmer = Farmer(
        farmer_code="FRM-ML1",
        name="ML Farmer",
        village="Thanjavur",
        district="Thanjavur",
        cultivated_area=3.0,
        paddy_variety="CO-51",
        expected_quantity=60.0,
        harvest_readiness=HarvestReadiness.ready,
    )
    db.add(farmer)
    db.flush()

    dpcs = [
        DPC(
            dpc_code="DPC-ML1",
            name="Thanjavur Central DPC",
            district="Thanjavur",
            daily_capacity=1000,
            processing_rate=50.0,
            storage_capacity=250.0,
            operating_status=OperatingStatus.active,
            open_date=day0 - timedelta(days=10),
        ),
        DPC(
            dpc_code="DPC-ML2",
            name="Kumbakonam DPC",
            district="Thanjavur",
            daily_capacity=1000,
            processing_rate=50.0,
            storage_capacity=250.0,
            operating_status=OperatingStatus.active,
            open_date=day0 - timedelta(days=10),
        ),
    ]
    db.add_all(dpcs)
    db.flush()

    for loc in ("Thanjavur", "Kumbakonam"):
        for d in dates:
            db.add(
                WeatherCondition(
                    date=d,
                    location=loc,
                    rainfall_probability=float(rng.uniform(0, 80)),
                    rainfall_mm=float(rng.uniform(0, 20)),
                    humidity=float(rng.uniform(45, 90)),
                    temperature_max=float(rng.uniform(28, 36)),
                    weather_risk=WeatherRisk.low,
                )
            )

    dpc_ids = [d.id for d in dpcs]
    for dpc_id in dpc_ids:
        for d in dates:
            db.add(
                ResourceAvailability(
                    dpc_id=dpc_id,
                    date=d,
                    labour_available=rng.randint(10, 30),
                    transport_available=rng.randint(1, 6),
                    weighing_capacity=rng.randint(30, 60),
                    storage_available=float(rng.uniform(80, 220)),
                )
            )

    for o, d in enumerate(dates):
        for idx, dpc_id in enumerate(dpc_ids):
            overload = idx == 0 and o in OVERLOAD_OFFSETS
            util = float(rng.uniform(88, 100)) if overload else float(rng.uniform(20, 55))
            planned = 1000
            used = planned * util / 100.0
            db.add(
                DPCCapacity(
                    dpc_id=dpc_id,
                    date=d,
                    planned_capacity=planned,
                    used_capacity=used,
                    remaining_capacity=planned - used,
                    utilization_pct=round(util, 1),
                )
            )

    depot = {"arrivals": 0, "quantity": 0.0}
    for o, d in enumerate(dates):
        for idx, dpc_id in enumerate(dpc_ids):
            overload = idx == 0 and o in OVERLOAD_OFFSETS
            n = rng.randint(8, 12) if overload else rng.randint(2, 5) if idx == 0 else rng.randint(3, 4)
            for _ in range(n):
                depot["arrivals"] += 1
                qty = rng.uniform(2.0, 5.0)
                depot["quantity"] += qty
                db.add(
                    ArrivalRecord(
                        farmer_id=farmer.id,
                        dpc_id=dpc_id,
                        date=d,
                        arrival_time=datetime.combine(d, time(9, 0)),
                        bags_brought=rng.randint(5, 15),
                        quantity_brought=qty,
                        wait_time_minutes=rng.randint(10, 60),
                        status="accepted",
                    )
                )
                db.add(
                    ProcurementRecord(
                        farmer_id=farmer.id,
                        dpc_id=dpc_id,
                        date=d,
                        bags=rng.randint(5, 15),
                        quantity_quintal=qty,
                        moisture_pct=float(rng.uniform(12, 16)),
                        grade="A",
                        status=ProcurementStatus.accepted,
                    )
                )
    db.commit()
    return {"dpcs": dpcs, "dates": dates, "start": day0, "farmer": farmer, "depot": depot}