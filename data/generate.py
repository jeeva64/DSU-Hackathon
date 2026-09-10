from __future__ import annotations

import argparse
import random
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, time as dt_time
from typing import Any

from backend.app.core.config import settings
from backend.app.db.database import SessionLocal, init_db
from backend.app.db.base import Base
from backend.app.models.farmer import Farmer, HarvestReadiness
from backend.app.models.dpc import DPC, OperatingStatus
from backend.app.models.procurement import ProcurementRecord, ProcurementStatus
from backend.app.models.dpc_capacity import DPCCapacity
from backend.app.models.slot import Slot, SlotStatus
from backend.app.models.arrival_record import ArrivalRecord
from backend.app.models.resource_availability import ResourceAvailability
from backend.app.models.weather_condition import WeatherCondition, WeatherRisk
from backend.app.models.prediction import Prediction, PredictionType
from backend.app.models.risk_assessment import RiskAssessment, RiskType, RiskSeverity
from backend.app.models.recommendation import (
    Recommendation,
    RecommendationType,
    RecommendationPriority,
    RecommendationStatus,
)
from backend.app.models.recommendation_action import RecommendationAction
from backend.app.models.scenario import SimulationScenario, SimulationStatus
from data.scenarios import SCENARIO_CONFIGS


# ---------------------------------------------------------------------------
# Reference Data
# ---------------------------------------------------------------------------

FARMER_SEED_DATA = [
    {"code": "FRM-001", "name": "Ramasamy P",    "village": "Thanjavur",    "variety": "CO-51",   "area_range": (3.0, 7.0)},
    {"code": "FRM-002", "name": "Lakshmi Devi",   "village": "Thanjavur",    "variety": "CR-1009", "area_range": (2.0, 5.0)},
    {"code": "FRM-003", "name": "Murugan K",      "village": "Papanasam",    "variety": "ADT-37",  "area_range": (1.5, 4.5)},
    {"code": "FRM-004", "name": "Priya S",        "village": "Papanasam",    "variety": "CO-51",   "area_range": (2.5, 6.0)},
    {"code": "FRM-005", "name": "Selvaraj M",     "village": "Kumbakonam",   "variety": "CO-43",   "area_range": (4.0, 8.0)},
    {"code": "FRM-006", "name": "Meena K",        "village": "Kumbakonam",   "variety": "BPT-5204","area_range": (1.5, 3.5)},
    {"code": "FRM-007", "name": "Karuppu R",      "village": "Pattukkottai", "variety": "CR-1009", "area_range": (3.5, 7.5)},
    {"code": "FRM-008", "name": "Anandhi V",      "village": "Pattukkottai", "variety": "CO-51",   "area_range": (2.0, 5.5)},
    {"code": "FRM-009", "name": "Ganesan T",      "village": "Orathanadu",   "variety": "ADT-37",  "area_range": (3.0, 6.0)},
    {"code": "FRM-010", "name": "Kavitha R",      "village": "Orathanadu",   "variety": "CO-43",   "area_range": (1.5, 4.0)},
    {"code": "FRM-011", "name": "Sundaram P",     "village": "Thanjavur",    "variety": "BPT-5204","area_range": (2.5, 5.0)},
    {"code": "FRM-012", "name": "Parvathi S",     "village": "Papanasam",    "variety": "CO-51",   "area_range": (2.0, 4.5)},
    {"code": "FRM-013", "name": "Veerapandi M",   "village": "Kumbakonam",   "variety": "CR-1009", "area_range": (4.0, 7.0)},
    {"code": "FRM-014", "name": "Sakthi K",       "village": "Pattukkottai", "variety": "ADT-37",  "area_range": (1.5, 3.0)},
    {"code": "FRM-015", "name": "Palaniappan R",  "village": "Orathanadu",   "variety": "CO-51",   "area_range": (3.5, 6.5)},
    {"code": "FRM-016", "name": "Revathi T",      "village": "Thanjavur",    "variety": "CO-43",   "area_range": (2.0, 4.0)},
    {"code": "FRM-017", "name": "Balu N",         "village": "Papanasam",    "variety": "BPT-5204","area_range": (3.0, 5.5)},
    {"code": "FRM-018", "name": "Jeyalakshmi V",  "village": "Kumbakonam",   "variety": "CO-51",   "area_range": (2.5, 5.0)},
    {"code": "FRM-019", "name": "Thirunavukkarasu","village":"Pattukkottai", "variety": "CR-1009", "area_range": (4.0, 8.0)},
    {"code": "FRM-020", "name": "Poongodi M",     "village": "Orathanadu",   "variety": "ADT-37",  "area_range": (1.5, 3.5)},
]

DPC_SEED_DATA = [
    {
        "dpc_code": "DPC-001",
        "name": "Thanjavur Central DPC",
        "district": "Thanjavur",
        "location": "Thanjavur",
        "lat": 10.7870, "lon": 79.1378,
        "daily_capacity": 1000,
        "processing_rate": 60.0,
        "storage_capacity": 300.0,
        "typical_labour": 22,
        "typical_weighing": 45,
    },
    {
        "dpc_code": "DPC-002",
        "name": "Papanasam Procurement Center",
        "district": "Thanjavur",
        "location": "Papanasam",
        "lat": 10.9260, "lon": 79.2710,
        "daily_capacity": 800,
        "processing_rate": 50.0,
        "storage_capacity": 250.0,
        "typical_labour": 18,
        "typical_weighing": 35,
    },
    {
        "dpc_code": "DPC-003",
        "name": "Kumbakonam DPC",
        "district": "Thanjavur",
        "location": "Kumbakonam",
        "lat": 10.9600, "lon": 79.3800,
        "daily_capacity": 1200,
        "processing_rate": 70.0,
        "storage_capacity": 400.0,
        "typical_labour": 28,
        "typical_weighing": 55,
    },
    {
        "dpc_code": "DPC-004",
        "name": "Pattukkottai DPC",
        "district": "Thanjavur",
        "location": "Pattukkottai",
        "lat": 10.4240, "lon": 79.3170,
        "daily_capacity": 900,
        "processing_rate": 55.0,
        "storage_capacity": 280.0,
        "typical_labour": 20,
        "typical_weighing": 40,
    },
]

VARIETY_YIELD = {
    "CO-51": 18.0,
    "CR-1009": 16.0,
    "ADT-37": 15.0,
    "CO-43": 17.0,
    "BPT-5204": 14.0,
}

VARIETY_CROP_DAYS = {
    "CO-51": 120,
    "CR-1009": 130,
    "ADT-37": 115,
    "CO-43": 125,
    "BPT-5204": 135,
}

SLOT_WINDOWS = [
    (dt_time(8, 0), dt_time(11, 0), "morning"),
    (dt_time(11, 0), dt_time(14, 0), "afternoon"),
    (dt_time(14, 0), dt_time(17, 0), "evening"),
]

DAILY_HISTORY_DAYS = 60


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class SyntheticDataGenerator:
    def __init__(self, seed: int | None = None, db_session=None, days: int = DAILY_HISTORY_DAYS):
        self.rng = random.Random(seed)
        self.db = db_session or SessionLocal()
        self.days = max(2, days)
        self._dpc_location_map: dict[int, str] = {}
        self._weather_cache: dict[tuple[date, str], WeatherCondition] = {}
        self._resource_cache: dict[tuple[int, date], ResourceAvailability] = {}
        self._capacity_cache: dict[tuple[int, date], DPCCapacity] = {}
        self._slot_cache: dict[tuple[int, date], list[Slot]] = {}
        self._demand_factor: dict[tuple[int, date], float] = {}
        self._peak_state: dict[int, int] = {}
        self._dpcs: list[DPC] = []
        self._farmers: list[Farmer] = []
        self._today = date.today()
        self._start_date = self._today - timedelta(days=self.days - 1)
        self._counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_all(self, reset: bool = False) -> dict[str, int]:
        t0 = time.time()
        if reset:
            self._reset_database()

        self._generate_farmers()
        self._generate_dpcs()
        self._generate_weather()
        self._generate_resources()
        self._generate_capacities_and_slots()
        self._generate_arrivals_and_procurements()
        self._generate_predictions()
        self._generate_risks_and_recommendations()
        self._generate_scenarios()
        self._print_summary(time.time() - t0)
        return dict(self._counts)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def _reset_database(self) -> None:
        print("  Resetting database... ", end="", flush=True)
        from sqlalchemy import text
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Farmers
    # ------------------------------------------------------------------

    def _generate_farmers(self) -> None:
        print(f"  Generating farmers ({len(FARMER_SEED_DATA)})... ", end="", flush=True)
        for fd in FARMER_SEED_DATA:
            area = round(self.rng.uniform(*fd["area_range"]), 1)
            variety = fd["variety"]
            crop_days = VARIETY_CROP_DAYS[variety]
            days_since_sowing = self.rng.randint(crop_days - 40, crop_days + 15)
            sowing_date = self._today - timedelta(days=days_since_sowing)

            if days_since_sowing < crop_days - 15:
                readiness = HarvestReadiness.not_ready
            elif days_since_sowing < crop_days - 5:
                readiness = HarvestReadiness.partially_ready
            elif days_since_sowing <= crop_days + 5:
                readiness = HarvestReadiness.ready
            else:
                readiness = HarvestReadiness.overdue

            expected_qty = round(area * VARIETY_YIELD[variety] * self.rng.uniform(0.85, 1.1), 1)

            farmer = Farmer(
                farmer_code=fd["code"],
                name=fd["name"],
                village=fd["village"],
                district="Thanjavur",
                location_area=f"{fd['village']} West",
                cultivated_area=area,
                paddy_variety=variety,
                expected_quantity=expected_qty,
                harvest_readiness=readiness,
                mobile=f"98765{10000 + int(fd['code'][-3:]):05d}",
                sowing_date=sowing_date,
            )
            self.db.add(farmer)
            self._farmers.append(farmer)

        self.db.commit()
        for f in self._farmers:
            self.db.refresh(f)
        self._counts["farmers"] = len(self._farmers)
        print("Done.")

    # ------------------------------------------------------------------
    # DPCs
    # ------------------------------------------------------------------

    def _generate_dpcs(self) -> None:
        print(f"  Generating DPCs ({len(DPC_SEED_DATA)})... ", end="", flush=True)
        for dd in DPC_SEED_DATA:
            dpc = DPC(
                dpc_code=dd["dpc_code"],
                name=dd["name"],
                district=dd["district"],
                daily_capacity=dd["daily_capacity"],
                processing_rate=dd["processing_rate"],
                storage_capacity=dd["storage_capacity"],
                operating_status=OperatingStatus.active,
                lat=dd["lat"],
                lon=dd["lon"],
                open_date=date(2025, 10, 1),
                close_date=date(2026, 1, 31),
            )
            self.db.add(dpc)
            self._dpcs.append(dpc)

        self.db.commit()
        for d in self._dpcs:
            self.db.refresh(d)
            dd = next(x for x in DPC_SEED_DATA if x["dpc_code"] == d.dpc_code)
            self._dpc_location_map[d.id] = dd["location"]
        self._counts["dpcs"] = len(self._dpcs)
        print("Done.")

    # ------------------------------------------------------------------
    # Weather — correlated across nearby locations
    # ------------------------------------------------------------------

    def _generate_weather(self) -> None:
        locations = [d["location"] for d in DPC_SEED_DATA]
        total = self.days * len(locations)
        print(f"  Generating weather conditions ({total})... ", end="", flush=True)

        base_rain_prob = 0.25
        prev_rain_prob = base_rain_prob

        for day_offset in range(self.days):
            d = self._start_date + timedelta(days=day_offset)
            seasonal_ramp = 1.0 + (day_offset / self.days) * 0.35
            system_rain_prob = min(0.9, prev_rain_prob * seasonal_ramp * self.rng.uniform(0.6, 1.4))
            prev_rain_prob = system_rain_prob

            for loc in locations:
                local_factor = self.rng.uniform(0.85, 1.15)
                rain_prob = min(0.95, system_rain_prob * local_factor)

                if rain_prob > 0.35:
                    rainfall_mm = round(self.rng.expovariate(1.0 / (rain_prob * 22)), 1)
                else:
                    rainfall_mm = round(self.rng.uniform(0, 3), 1)
                rainfall_mm = min(45, rainfall_mm)

                humidity = round(self.rng.uniform(52, 72) + rainfall_mm * 0.7, 1)
                humidity = min(98, humidity)

                temp_max = round(self.rng.uniform(30, 36) - rainfall_mm * 0.15, 1)

                if rainfall_mm > 20:
                    risk = WeatherRisk.critical
                elif rainfall_mm > 10:
                    risk = WeatherRisk.high
                elif rainfall_mm > 5:
                    risk = WeatherRisk.medium
                elif rain_prob > 0.5:
                    risk = WeatherRisk.low
                else:
                    risk = WeatherRisk.none

                weather = WeatherCondition(
                    date=d,
                    location=loc,
                    rainfall_probability=round(rain_prob * 100, 1),
                    rainfall_mm=rainfall_mm,
                    humidity=humidity,
                    temperature_max=temp_max,
                    weather_risk=risk,
                )
                self.db.add(weather)
                self._weather_cache[(d, loc)] = weather
                self._counts["weather"] += 1

        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Resources — weather-correlated labour and transport
    # ------------------------------------------------------------------

    def _generate_resources(self) -> None:
        total = self.days * len(self._dpcs)
        print(f"  Generating resource availability ({total})... ", end="", flush=True)

        for dpc in self._dpcs:
            dd = next(d for d in DPC_SEED_DATA if d["dpc_code"] == dpc.dpc_code)
            for day_offset in range(self.days):
                d = self._start_date + timedelta(days=day_offset)
                weather = self._weather_cache.get((d, dd["location"]))
                rain_mm = weather.rainfall_mm if weather else 0
                rain_factor = max(0.35, 1.0 - rain_mm * 0.022)

                labour = max(4, int(dd["typical_labour"] * rain_factor * self.rng.uniform(0.75, 1.1)))
                transport = max(1, int(5 * rain_factor * self.rng.uniform(0.5, 1.2)))
                weighing = max(10, int(dd["typical_weighing"] * self.rng.uniform(0.8, 1.0)))

                cumul_used = self._estimate_cumulative_storage(dpc.id, d)
                storage_avail = round(max(0, dpc.storage_capacity - cumul_used), 1)

                res = ResourceAvailability(
                    dpc_id=dpc.id,
                    date=d,
                    labour_available=labour,
                    transport_available=transport,
                    weighing_capacity=weighing,
                    storage_available=storage_avail,
                )
                self.db.add(res)
                self._resource_cache[(dpc.id, d)] = res
                self._counts["resources"] += 1

        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Capacities and Slots
    # ------------------------------------------------------------------

    def _generate_capacities_and_slots(self) -> None:
        cap_total = self.days * len(self._dpcs)
        slot_total = cap_total * 3
        print(f"  Generating capacities ({cap_total}) and slots ({slot_total})... ", end="", flush=True)

        for dpc in self._dpcs:
            for day_offset in range(self.days):
                d = self._start_date + timedelta(days=day_offset)
                weather = self._weather_cache.get((d, self._dpc_location_map[dpc.id]))
                rain_factor = max(0.3, 1.0 - (weather.rainfall_mm * 0.03 if weather else 0))

                ready_count = self._count_ready_farmers()
                demand_factor = self._demand_factor_for(dpc.id, d, day_offset)
                expected_arrivals = int(round(ready_count * 0.35 * rain_factor
                                              * demand_factor * self.rng.uniform(0.7, 1.3)))
                expected_bags = int(round(expected_arrivals
                                          * int(dpc.daily_capacity * 0.4 / max(1, ready_count))
                                          * demand_factor))

                planned = int(dpc.daily_capacity * self.rng.uniform(0.88, 1.05))
                used = min(planned, expected_bags)
                remaining = max(0, planned - used)
                util_pct = round(used / planned * 100, 1) if planned > 0 else 0

                cap = DPCCapacity(
                    dpc_id=dpc.id,
                    date=d,
                    planned_capacity=planned,
                    used_capacity=used,
                    remaining_capacity=remaining,
                    utilization_pct=util_pct,
                )
                self.db.add(cap)
                self._capacity_cache[(dpc.id, d)] = cap
                self._counts["capacities"] += 1

                dpc_slots = []
                for start_t, end_t, _label in SLOT_WINDOWS:
                    slot_cap = planned // 3
                    arrival_share = expected_arrivals // 3
                    booked = max(0, int(arrival_share * self.rng.uniform(0.6, 1.1)))
                    booked = min(booked, slot_cap)
                    booked_q = round(booked * self.rng.uniform(2.5, 4.0), 1)

                    if booked >= slot_cap:
                        status = SlotStatus.full
                    elif booked > slot_cap * 0.5:
                        status = SlotStatus.partially_booked
                    else:
                        status = SlotStatus.available

                    slot = Slot(
                        dpc_id=dpc.id,
                        date=d,
                        start_time=start_t,
                        end_time=end_t,
                        max_farmers=slot_cap,
                        max_quantity=round(slot_cap * 3.5, 1),
                        booked_farmers=booked,
                        booked_quantity=booked_q,
                        status=status,
                    )
                    self.db.add(slot)
                    dpc_slots.append(slot)
                    self._counts["slots"] += 1

                self._slot_cache[(dpc.id, d)] = dpc_slots

        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Arrivals and Procurements — fully correlated
    # ------------------------------------------------------------------

    def _generate_arrivals_and_procurements(self) -> None:
        print("  Generating arrivals and procurements... ", end="", flush=True)

        for day_offset in range(self.days):
            d = self._start_date + timedelta(days=day_offset)
            day_of_week = d.weekday()
            weekend_factor = 0.55 if day_of_week >= 5 else 1.0

            weather = self._weather_cache.get(("Thanjavur", d))
            if not weather:
                for loc in ["Thanjavur", "Papanasam", "Kumbakonam", "Pattukkottai"]:
                    weather = self._weather_cache.get((loc, d))
                    if weather:
                        break
            rain_mm = weather.rainfall_mm if weather else 0
            humidity = weather.humidity if weather else 60
            rain_factor = max(0.25, 1.0 - rain_mm * 0.035)

            for dpc in self._dpcs:
                dd = next(x for x in DPC_SEED_DATA if x["dpc_code"] == dpc.dpc_code)
                dpc_weather = self._weather_cache.get((d, dd["location"]))
                dpc_rain = dpc_weather.rainfall_mm if dpc_weather else rain_mm
                dpc_humidity = dpc_weather.humidity if dpc_weather else humidity
                dpc_rain_factor = max(0.25, 1.0 - dpc_rain * 0.035)

                res = self._resource_cache.get((dpc.id, d))
                labour_avail = res.labour_available if res else 20
                transport_avail = res.transport_available if res else 5
                labour_factor = min(1.0, labour_avail / dd["typical_labour"])
                transport_factor = min(1.0, transport_avail / 5)

                all_ready = [f for f in self._farmers
                             if f.harvest_readiness in (HarvestReadiness.ready, HarvestReadiness.overdue)]
                ready_farmers = [f for f in all_ready if f.village == dd["location"]]
                if not ready_farmers:
                    ready_farmers = all_ready

                demand_factor = self._demand_factor_for(dpc.id, d, day_offset)
                base_arrival_rate = 0.4
                num_arrivals = int(round(len(all_ready) * base_arrival_rate * dpc_rain_factor
                                         * weekend_factor * labour_factor * demand_factor
                                         * self.rng.uniform(0.65, 1.35)))
                num_arrivals = max(0, min(num_arrivals, len(all_ready)))

                dpc_slots = self._slot_cache.get((dpc.id, d), [])
                available_slots = [s for s in dpc_slots if s.status != SlotStatus.full]
                hour_weights = [3, 4, 3]

                for _ in range(num_arrivals):
                    farmer = self.rng.choice(ready_farmers)

                    slot = None
                    if available_slots and self.rng.random() < 0.82:
                        slot = self.rng.choices(available_slots, weights=hour_weights[:len(available_slots)])[0]

                    season_span = max(1, self.days // 6)
                    base_qty = (farmer.expected_quantity or 50.0) / season_span * (0.5 + 0.5 * demand_factor)
                    qty = round(base_qty * self.rng.uniform(0.7, 1.3), 1)
                    bags = max(1, int(qty / 0.55))

                    base_moisture = self.rng.uniform(10, 15)
                    humidity_effect = max(0, (dpc_humidity - 68) * 0.18)
                    rain_effect = max(0, dpc_rain * 0.35)
                    moisture = round(min(26, base_moisture + humidity_effect + rain_effect), 1)

                    if moisture < 14:
                        grade = "A"
                    elif moisture < 17:
                        grade = "B"
                    elif moisture < 20:
                        grade = "C"
                    else:
                        grade = "D"

                    status = "accepted" if moisture < 17 else "rejected"
                    proc_status = ProcurementStatus.accepted if status == "accepted" else ProcurementStatus.rejected

                    queue_depth = self._count_arrivals_so_far(dpc.id, d)
                    proc_rate = dpc.processing_rate or 50
                    wait = max(5, int(8 + queue_depth * 1.5 + (100 - proc_rate) * 0.4 + dpc_rain * 0.5))
                    if transport_avail < 3:
                        wait += self.rng.randint(10, 30)

                    hour = self.rng.choices(range(8, 17), weights=[2, 3, 4, 4, 3, 2, 2, 1, 1])[0]
                    minute = self.rng.randint(0, 59)

                    arrival = ArrivalRecord(
                        farmer_id=farmer.id,
                        dpc_id=dpc.id,
                        slot_id=slot.id if slot else None,
                        date=d,
                        arrival_time=datetime(d.year, d.month, d.day, hour, minute),
                        bags_brought=bags,
                        quantity_brought=qty,
                        wait_time_minutes=wait,
                        status=status,
                    )
                    self.db.add(arrival)
                    self._counts["arrivals"] += 1

                    if slot:
                        slot.booked_farmers += 1
                        slot.booked_quantity = round(slot.booked_quantity + qty, 1)

                    procurement = ProcurementRecord(
                        farmer_id=farmer.id,
                        dpc_id=dpc.id,
                        date=d,
                        bags=bags,
                        quantity_quintal=qty,
                        moisture_pct=moisture,
                        grade=grade,
                        status=proc_status,
                    )
                    self.db.add(procurement)
                    self._counts["procurements"] += 1

        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def _generate_predictions(self) -> None:
        total = self.days * len(self._dpcs) * 3
        print(f"  Generating predictions ({total})... ", end="", flush=True)

        for dpc in self._dpcs:
            hist_arrivals = []
            for day_offset in range(self.days):
                d = self._start_date + timedelta(days=day_offset)
                count = self._count_arrivals_so_far(dpc.id, d)
                hist_arrivals.append(count)

            avg_arrivals = sum(hist_arrivals) / max(1, len(hist_arrivals))
            std_arrivals = (sum((x - avg_arrivals) ** 2 for x in hist_arrivals) / max(1, len(hist_arrivals))) ** 0.5

            for day_offset in range(self.days):
                d = self._start_date + timedelta(days=day_offset)
                weather = self._weather_cache.get((d, self._dpc_location_map[dpc.id]))
                rain_factor = max(0.3, 1.0 - ((weather.rainfall_mm if weather else 0) * 0.03))

                predicted_arrivals = max(0, round(avg_arrivals * rain_factor * self.rng.uniform(0.88, 1.12), 1))
                avg_bags_per_farmer = max(1, dpc.daily_capacity // 30)
                predicted_qty = round(predicted_arrivals * avg_bags_per_farmer, 1)
                predicted_queue = max(0, round(predicted_arrivals - dpc.daily_capacity / 8, 1))

                history_len = day_offset + 1
                confidence = min(0.95, max(0.35, 0.55 + history_len * 0.025 - std_arrivals * 0.01))

                for ptype, pval in [
                    (PredictionType.arrival_count, predicted_arrivals),
                    (PredictionType.quantity, predicted_qty),
                    (PredictionType.queue_length, predicted_queue),
                ]:
                    pred = Prediction(
                        dpc_id=dpc.id,
                        prediction_date=d,
                        target_date=d,
                        prediction_type=ptype,
                        predicted_value=pval,
                        confidence=round(confidence, 2),
                        model_version="v0.1-synthetic",
                    )
                    self.db.add(pred)
                    self._counts["predictions"] += 1

        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Risks and Recommendations
    # ------------------------------------------------------------------

    def _generate_risks_and_recommendations(self) -> None:
        print("  Generating risks and recommendations... ", end="", flush=True)

        for dpc in self._dpcs:
            dd = next(x for x in DPC_SEED_DATA if x["dpc_code"] == dpc.dpc_code)

            for day_offset in range(self.days):
                d = self._start_date + timedelta(days=day_offset)
                weather = self._weather_cache.get((d, dd["location"]))
                res = self._resource_cache.get((dpc.id, d))
                cap = self._capacity_cache.get((dpc.id, d))

                rain_mm = weather.rainfall_mm if weather else 0
                humidity = weather.humidity if weather else 60
                transport = res.transport_available if res else 5
                labour = res.labour_available if res else 20
                util_pct = cap.utilization_pct if cap else 50

                risks_today: list[dict] = []

                if util_pct > 85:
                    sev = RiskSeverity.critical if util_pct > 95 else RiskSeverity.high
                    score = min(100, util_pct + self.rng.uniform(-3, 3))
                    risk = RiskAssessment(
                        dpc_id=dpc.id, date=d,
                        risk_type=RiskType.overload, severity=sev,
                        score=round(score, 1),
                        explanation=f"DPC at {util_pct:.0f}% capacity utilization",
                        mitigation="Divert farmers to adjacent DPC or extend processing hours",
                    )
                    self.db.add(risk)
                    risks_today.append({"type": "overload", "sev": sev})

                if rain_mm > 8:
                    sev = RiskSeverity.critical if rain_mm > 20 else (RiskSeverity.high if rain_mm > 12 else RiskSeverity.medium)
                    score = min(100, rain_mm * 3.5)
                    risk = RiskAssessment(
                        dpc_id=dpc.id, date=d,
                        risk_type=RiskType.rain, severity=sev,
                        score=round(score, 1),
                        explanation=f"Heavy rain: {rain_mm:.0f}mm forecasted. Paddy transport and drying affected.",
                        mitigation="Cover stored paddy; prepare tarpaulins for open yards",
                    )
                    self.db.add(risk)
                    risks_today.append({"type": "rain", "sev": sev})

                if transport < 3:
                    sev = RiskSeverity.critical if transport < 2 else RiskSeverity.high
                    score = 100 - transport * 18
                    risk = RiskAssessment(
                        dpc_id=dpc.id, date=d,
                        risk_type=RiskType.transport, severity=sev,
                        score=round(max(0, score), 1),
                        explanation=f"Only {transport} vehicles available for DPC-to-godown movement",
                        mitigation="Request additional lorries from regional transport depot",
                    )
                    self.db.add(risk)
                    risks_today.append({"type": "transport", "sev": sev})

                if labour < 12:
                    sev = RiskSeverity.high if labour < 8 else RiskSeverity.medium
                    score = 100 - labour * 6
                    risk = RiskAssessment(
                        dpc_id=dpc.id, date=d,
                        risk_type=RiskType.labour, severity=sev,
                        score=round(max(0, score), 1),
                        explanation=f"Labour at {labour} workers — below operational minimum",
                        mitigation="Deploy temporary workers from neighbouring blocks",
                    )
                    self.db.add(risk)
                    risks_today.append({"type": "labour", "sev": sev})

                if humidity > 82 and rain_mm > 3:
                    moisture_score = min(100, humidity * 0.6 + rain_mm * 1.5)
                    risk = RiskAssessment(
                        dpc_id=dpc.id, date=d,
                        risk_type=RiskType.moisture, severity=RiskSeverity.medium,
                        score=round(moisture_score, 1),
                        explanation=f"Humidity {humidity:.0f}% with {rain_mm:.0f}mm rain — elevated moisture rejection risk",
                        mitigation="Extend drying time before intake; check moisture at multiple points",
                    )
                    self.db.add(risk)
                    risks_today.append({"type": "moisture", "sev": RiskSeverity.medium})

                if len(risks_today) >= 3:
                    db_risks = self.db.query(RiskAssessment).filter(
                        RiskAssessment.dpc_id == dpc.id, RiskAssessment.date == d
                    ).all()
                    combined_score = max(r.score for r in db_risks) if db_risks else 80
                    risk = RiskAssessment(
                        dpc_id=dpc.id, date=d,
                        risk_type=RiskType.combined, severity=RiskSeverity.critical,
                        score=round(min(100, combined_score * 1.1), 1),
                        explanation="Multiple concurrent risks: " + ", ".join(r["type"] for r in risks_today),
                        mitigation="Activate emergency procurement protocol; coordinate across all DPCs",
                    )
                    self.db.add(risk)

                self._generate_recommendations_for_day(dpc, d, risks_today, dd)

        self.db.commit()
        print("Done.")

    def _generate_recommendations_for_day(
        self, dpc: DPC, d: date, risks: list[dict], dpc_meta: dict
    ) -> None:
        for risk in risks:
            rtype = risk["type"]
            sev = risk["sev"]

            if rtype == "overload":
                rec = Recommendation(
                    dpc_id=dpc.id, date=d,
                    recommendation_type=RecommendationType.slot,
                    priority=RecommendationPriority.critical if sev == RiskSeverity.critical else RecommendationPriority.high,
                    title=f"Divert farmers from {dpc.name}",
                    explanation=f"Capacity at {dpc.name} critically high. Farmers should be redirected to nearby DPCs.",
                    expected_impact="Reduce queue wait by 35-40%; prevent overflow",
                    status=self.rng.choice([
                        RecommendationStatus.pending,
                        RecommendationStatus.pending,
                        RecommendationStatus.approved,
                    ]),
                )
                self.db.add(rec)
                self._counts["recommendations"] += 1

            elif rtype == "rain":
                rec = Recommendation(
                    dpc_id=dpc.id, date=d,
                    recommendation_type=RecommendationType.weather,
                    priority=RecommendationPriority.high,
                    title=f"Protect stored paddy at {dpc.name}",
                    explanation="Rain forecasted. Uncovered paddy in open yards at risk of water damage.",
                    expected_impact="Prevent quality loss; maintain grade standards",
                    status=RecommendationStatus.pending,
                )
                self.db.add(rec)
                self._counts["recommendations"] += 1

            elif rtype == "transport":
                rec = Recommendation(
                    dpc_id=dpc.id, date=d,
                    recommendation_type=RecommendationType.resource,
                    priority=RecommendationPriority.high,
                    title=f"Arrange transport for {dpc.name}",
                    explanation="Transport shortage preventing movement of procured paddy to godown.",
                    expected_impact="Clear DPC yard; free capacity for new procurement",
                    status=self.rng.choice([RecommendationStatus.pending, RecommendationStatus.approved]),
                )
                self.db.add(rec)
                self._counts["recommendations"] += 1

            elif rtype == "labour":
                rec = Recommendation(
                    dpc_id=dpc.id, date=d,
                    recommendation_type=RecommendationType.resource,
                    priority=RecommendationPriority.medium,
                    title=f"Deploy additional labour at {dpc.name}",
                    explanation="Labour shortage reducing processing throughput.",
                    expected_impact="Increase processing rate by 25-30%",
                    status=RecommendationStatus.pending,
                )
                self.db.add(rec)
                self._counts["recommendations"] += 1

            elif rtype == "moisture":
                rec = Recommendation(
                    dpc_id=dpc.id, date=d,
                    recommendation_type=RecommendationType.risk,
                    priority=RecommendationPriority.medium,
                    title=f"Extended drying protocol at {dpc.name}",
                    explanation="High humidity and rain increasing moisture content of arriving paddy.",
                    expected_impact="Reduce rejection rate by 15-20%",
                    status=RecommendationStatus.pending,
                )
                self.db.add(rec)
                self._counts["recommendations"] += 1

    # ------------------------------------------------------------------
    # Scenario seed records
    # ------------------------------------------------------------------

    def _generate_scenarios(self) -> None:
        print(f"  Generating scenarios ({len(SCENARIO_CONFIGS)})... ", end="", flush=True)
        for name, cfg in SCENARIO_CONFIGS.items():
            existing = self.db.query(SimulationScenario).filter(SimulationScenario.name == name).first()
            if not existing:
                scenario = SimulationScenario(
                    name=name,
                    description=cfg["description"],
                    parameters=cfg["parameters"],
                    status=SimulationStatus.draft,
                )
                self.db.add(scenario)
                self._counts["scenarios"] += 1
        self.db.commit()
        print("Done.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _demand_factor_for(self, dpc_id: int, d: date, day_offset: int) -> float:
        cached = self._demand_factor.get((dpc_id, d))
        if cached is not None:
            return cached
        season_ramp = 1.0 + (day_offset / max(1, self.days)) * 0.75
        dow = d.weekday()
        dow_factor = 1.0 if dow < 5 else (0.75 if dow == 5 else 0.65)
        burst_remaining = self._peak_state.get(dpc_id, 0)
        if burst_remaining > 0:
            self._peak_state[dpc_id] = max(0, burst_remaining - 1)
            peak_mult = self.rng.uniform(1.9, 2.6)
        else:
            late_season = day_offset >= self.days * 0.6
            peak_prob = 0.26 if late_season else 0.13
            if self.rng.random() < peak_prob:
                peak_mult = self.rng.uniform(1.9, 2.6)
                max_burst = max(0, self.days - 1 - day_offset)
                if max_burst > 0 and self.rng.random() < 0.55:
                    self._peak_state[dpc_id] = min(2, max_burst)
            else:
                peak_mult = 1.0
        factor = season_ramp * dow_factor * peak_mult * self.rng.uniform(0.7, 1.3)
        self._demand_factor[(dpc_id, d)] = factor
        return factor

    def _count_ready_farmers(self) -> int:
        return sum(1 for f in self._farmers
                   if f.harvest_readiness in (HarvestReadiness.ready, HarvestReadiness.overdue))

    def _estimate_cumulative_storage(self, dpc_id: int, up_to_date: date) -> float:
        from sqlalchemy import func
        result = self.db.query(
            func.coalesce(func.sum(ProcurementRecord.quantity_quintal), 0)
        ).filter(
            ProcurementRecord.dpc_id == dpc_id,
            ProcurementRecord.date < up_to_date,
        ).scalar()
        return float(result)

    def _count_arrivals_so_far(self, dpc_id: int, d: date) -> int:
        return self.db.query(ArrivalRecord).filter(
            ArrivalRecord.dpc_id == dpc_id,
            ArrivalRecord.date == d,
        ).count()

    def _print_summary(self, elapsed: float) -> None:
        print("\n" + "=" * 50)
        print("  NelSync AI — Synthetic Data Generation Complete")
        print("=" * 50)
        print(f"  Seed: {'deterministic' if self.rng.seed is not None else 'random'}")
        print()
        labels = [
            ("farmers", "Farmers"),
            ("dpcs", "DPCs"),
            ("weather", "Weather conditions"),
            ("resources", "Resource records"),
            ("capacities", "Capacity records"),
            ("slots", "Slot records"),
            ("arrivals", "Arrival records"),
            ("procurements", "Procurement records"),
            ("predictions", "Predictions"),
            ("recommendations", "Recommendations"),
            ("scenarios", "Scenarios"),
        ]
        total = 0
        for key, label in labels:
            count = self._counts.get(key, 0)
            total += count
            print(f"  {label:<28s} {count:>5d}")
            print(f"  {'-' * 36}")
        print(f"  {'Total':<28s} {total:>5d}")
        print(f"\n  Generation time: {elapsed:.1f}s")
        print("=" * 50)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="NelSync AI — Synthetic Data Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m data.generate                     Generate with random seed (60 days)
  python -m data.generate --seed 42           Deterministic generation
  python -m data.generate --reset             Reset DB and regenerate
  python -m data.generate --reset --seed 42   Reset + deterministic
  python -m data.generate --reset --seed 42 --days 90   Longer training history
        """,
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--reset", action="store_true", help="Drop all data before generating")
    parser.add_argument("--days", type=int, default=DAILY_HISTORY_DAYS,
                        help="Number of historical days to generate (default: %(default)s)")
    args = parser.parse_args()

    print("NelSync AI — Synthetic Data Generator")
    print("=" * 50)
    print(f"  Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print(f"  Seed: {args.seed if args.seed is not None else 'random'}")
    print(f"  Reset: {args.reset}")
    print(f"  Days: {args.days}")
    print()

    init_db()
    gen = SyntheticDataGenerator(seed=args.seed, days=args.days)
    gen.generate_all(reset=args.reset)


if __name__ == "__main__":
    main()
