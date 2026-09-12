from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.farmer import HarvestReadiness
from backend.app.models.prediction import PredictionType
from backend.app.models.recommendation import RecommendationPriority, RecommendationType
from backend.app.repositories.dpc_capacity_repo import DPCCapacityRepository
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.repositories.farmer_repo import FarmerRepository
from backend.app.repositories.prediction_repo import PredictionRepository
from backend.app.repositories.recommendation_repo import RecommendationRepository
from backend.app.repositories.resource_availability_repo import ResourceAvailabilityRepository
from backend.app.repositories.slot_repo import SlotRepository
from backend.app.repositories.weather_condition_repo import WeatherConditionRepository

logger = logging.getLogger("backend.services.slot_recommendation")

LOCATION_NAMES = ("Thanjavur", "Papanasam", "Kumbakonam", "Pattukkottai")

WEATHER_SCORE_MAP = {
    "none": 1.0,
    "low": 0.75,
    "medium": 0.50,
    "high": 0.25,
    "critical": 0.0,
}


@dataclass
class DpcContext:
    dpc_id: int
    code: str
    name: str
    district: str
    daily_capacity: float
    processing_rate: float | None
    storage_capacity: float
    operating_status: str
    lat: float | None = None
    lon: float | None = None
    predicted_arrivals: float = 0.0
    predicted_quantity: float = 0.0
    remaining_capacity: float | None = None
    weather_risk: str = "none"
    labour_available: int = 0
    transport_available: int = 0
    weighing_capacity: int = 0
    storage_available: float | None = None
    ready_farmers: int = 0
    overdue_farmers: int = 0


@dataclass
class SlotContext:
    slot_id: int
    dpc_id: int
    start_time: str
    end_time: str
    max_farmers: int
    max_quantity: float
    booked_farmers: int
    booked_quantity: float


class SlotRecommender:
    HIGH_LOAD = 0.85
    CRITICAL_LOAD = 0.95
    LOW_LOAD = 0.30
    TARGET_MAX_LOAD = 0.90
    MAX_DISTANCE_KM = 200.0
    DEFAULT_QUINTALS_PER_FARMER = 1.0
    OPERATING_HOURS = 8.0

    WEIGHTS = {
        "capacity": 0.30,
        "time": 0.15,
        "weather": 0.15,
        "resource": 0.15,
        "assignment": 0.10,
        "processing": 0.15,
    }

    def analyze(
        self,
        target_date: date,
        contexts: list[DpcContext],
        slots_by_dpc: dict[int, list[SlotContext]],
    ) -> list[dict]:
        projected_qty = {c.dpc_id: c.predicted_quantity for c in contexts}
        projected_farmers = {c.dpc_id: c.predicted_arrivals for c in contexts}
        projected_slot_qty: dict[int, float] = {}
        projected_slot_farmers: dict[int, float] = {}
        for context in contexts:
            for slot, qty, farmers in self._slot_distribution(context, slots_by_dpc.get(context.dpc_id, [])):
                projected_slot_qty[slot.slot_id] = qty
                projected_slot_farmers[slot.slot_id] = farmers

        recommendations: list[dict] = []

        overloaded = []
        for context in contexts:
            load = self._quantity_load(context)
            if load > self.HIGH_LOAD or context.operating_status == "overloaded":
                severity = (
                    "critical"
                    if load > self.CRITICAL_LOAD or context.operating_status == "overloaded"
                    else "high"
                )
                overloaded.append((context, load, severity))
        overloaded.sort(key=lambda item: item[1], reverse=True)

        for context, load, severity in overloaded:
            avg = self._avg_per_farmer(context)
            excess_farmers = max(0.0, self._excess(context) / avg) if avg > 0 else 0.0
            remaining = excess_farmers
            taken_slot_farmers: dict[int, float] = {}

            feasible = self._rank_targets(
                context, contexts, slots_by_dpc, projected_qty, projected_farmers,
                projected_slot_qty, projected_slot_farmers,
            )
            for alt in feasible:
                if remaining <= 0.5:
                    break
                if alt["kind"] == "slot":
                    already = taken_slot_farmers.get(alt["slot_id"], 0.0)
                    accept_farmers = min(remaining, alt["farmers_headroom"] - already)
                else:
                    accept_farmers = min(remaining, alt["farmers_headroom"])
                if accept_farmers <= 0.5:
                    continue
                accept_qty = accept_farmers * avg
                if alt["kind"] == "dpc":
                    projected_qty[alt["dpc_id"]] += accept_qty
                    projected_farmers[alt["dpc_id"]] += accept_farmers
                    target_after_qty = projected_qty[alt["dpc_id"]]
                else:
                    taken_slot_farmers[alt["slot_id"]] = already + accept_farmers
                    projected_slot_qty[alt["slot_id"]] += accept_qty
                    projected_slot_farmers[alt["slot_id"]] += accept_farmers
                    target_after_qty = projected_slot_qty[alt["slot_id"]]
                remaining -= accept_farmers

                recommendations.append(
                    self._build_movement(
                        target_date, context, load, severity, alt, accept_farmers, accept_qty,
                        target_after_qty,
                    )
                )

            if remaining >= 0.5:
                rec = self._build_boost(target_date, context, remaining, severity)
                if rec:
                    recommendations.append(rec)

        for context in contexts:
            urgent = context.ready_farmers + context.overdue_farmers
            if urgent <= 0:
                continue
            load = self._quantity_load(context)
            slot = self._earliest_slot(context, slots_by_dpc.get(context.dpc_id, []))
            recommendations.append(
                self._build_priority(target_date, context, urgent, load, slot)
            )

        for context in contexts:
            load = self._quantity_load(context)
            if load < self.LOW_LOAD:
                slot = self._earliest_slot(context, slots_by_dpc.get(context.dpc_id, []))
                rec = self._build_underutilized(target_date, context, load, slot)
                if rec:
                    recommendations.append(rec)

        for context in contexts:
            rec = self._build_weather(target_date, context)
            if rec:
                recommendations.append(rec)

        recommendations.sort(
            key=lambda r: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["priority"], 4),
                -float(r["feasibility_score"]),
            )
        )
        return recommendations

    def _quantity_load(self, context: DpcContext) -> float:
        capacity = context.daily_capacity if context.daily_capacity > 0 else 1.0
        return context.predicted_quantity / capacity

    def _excess(self, context: DpcContext) -> float:
        return max(0.0, context.predicted_quantity - self.HIGH_LOAD * (context.daily_capacity or 1.0))

    def _avg_per_farmer(self, context: DpcContext) -> float:
        if context.predicted_arrivals > 0 and context.predicted_quantity > 0:
            return context.predicted_quantity / context.predicted_arrivals
        return self.DEFAULT_QUINTALS_PER_FARMER

    def _slot_distribution(self, context: DpcContext, slots: list[SlotContext]) -> list[tuple[SlotContext, float, float]]:
        if not slots:
            return []
        farmer_total = sum(s.max_farmers for s in slots)
        qty_total = sum(s.max_quantity for s in slots)
        out = []
        for slot in slots:
            farmer_share = (
                context.predicted_arrivals * slot.max_farmers / farmer_total if farmer_total else 0.0
            )
            qty_share = (
                context.predicted_quantity * slot.max_quantity / qty_total if qty_total else 0.0
            )
            out.append((slot, qty_share + slot.booked_quantity, farmer_share + slot.booked_farmers))
        return out

    def _rank_targets(
        self,
        source: DpcContext,
        contexts: list[DpcContext],
        slots_by_dpc: dict[int, list[SlotContext]],
        projected_qty: dict[int, float],
        projected_farmers: dict[int, float],
        projected_slot_qty: dict[int, float],
        projected_slot_farmers: dict[int, float],
    ) -> list[dict]:
        ranked: list[dict] = []
        for target in contexts:
            if target.dpc_id == source.dpc_id:
                continue
            if target.operating_status != "active":
                continue
            alt = self._dpc_target_alt(source, target, projected_qty, projected_farmers)
            if alt is not None:
                ranked.append(alt)

        for slot in slots_by_dpc.get(source.dpc_id, []):
            alt = self._slot_target_alt(
                source, slot, projected_slot_qty.get(slot.slot_id, 0.0),
                projected_slot_farmers.get(slot.slot_id, 0.0),
            )
            if alt is not None:
                ranked.append(alt)

        ranked.sort(key=lambda r: -r["feasibility"])
        return ranked

    def _dpc_target_alt(self, source: DpcContext, target: DpcContext,
                        projected_qty: dict[int, float], projected_farmers: dict[int, float]) -> dict | None:
        if self._quantity_load(target) > self.HIGH_LOAD:
            return None
        capacity = target.daily_capacity if target.daily_capacity > 0 else 0.0
        used = projected_qty.get(target.dpc_id, target.predicted_quantity)
        headroom_qty = max(0.0, self.TARGET_MAX_LOAD * capacity - used)
        avg = self._avg_per_farmer(target)
        farmers_headroom = headroom_qty / avg if avg > 0 else 0.0
        if headroom_qty <= 0.0:
            return None

        alt = {
            "kind": "dpc",
            "dpc_id": target.dpc_id,
            "slot_id": None,
            "name": target.name,
            "capacity": capacity,
            "operating_status": target.operating_status,
            "weather_risk": target.weather_risk,
            "labour": target.labour_available,
            "transport": target.transport_available,
            "weighing": target.weighing_capacity,
            "processing": target.processing_rate,
            "storage": target.storage_available if target.storage_available is not None else target.storage_capacity,
            "lat": target.lat,
            "lon": target.lon,
            "district": target.district,
        }
        scores = self._scores(source, alt)
        if not self._passes_filters(scores):
            return None
        return {
            **alt,
            "headroom_qty": round(headroom_qty, 1),
            "farmers_headroom": round(farmers_headroom, 1),
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "feasibility": round(100.0 * sum(self.WEIGHTS[k] * v for k, v in scores.items()), 1),
            "load": used / capacity if capacity else 1.0,
        }

    def _slot_target_alt(self, source: DpcContext, slot: SlotContext, proj_qty: float,
                         proj_farmers: float) -> dict | None:
        qty_headroom = max(0.0, slot.max_quantity - proj_qty)
        farmer_headroom = max(0.0, slot.max_farmers - proj_farmers)
        qty_cap = self.TARGET_MAX_LOAD * slot.max_quantity - proj_qty
        farmer_cap = self.TARGET_MAX_LOAD * slot.max_farmers - proj_farmers
        qty_headroom = min(qty_headroom, max(0.0, qty_cap))
        farmer_headroom = min(farmer_headroom, max(0.0, farmer_cap))
        avg = self._avg_per_farmer(source)
        headroom_qty = min(qty_headroom, farmer_headroom * avg)
        if headroom_qty <= 0.0:
            return None

        alt = {
            "kind": "slot",
            "dpc_id": source.dpc_id,
            "slot_id": slot.slot_id,
            "name": f"{slot.start_time}-{slot.end_time} at {source.name}",
            "capacity": slot.max_quantity,
            "operating_status": source.operating_status,
            "weather_risk": source.weather_risk,
            "labour": source.labour_available,
            "transport": source.transport_available,
            "weighing": source.weighing_capacity,
            "processing": source.processing_rate,
            "storage": source.storage_available if source.storage_available is not None else source.storage_capacity,
            "lat": source.lat,
            "lon": source.lon,
            "district": source.district,
        }
        scores = self._scores(source, alt)
        if not self._passes_filters(scores):
            return None
        return {
            **alt,
            "headroom_qty": round(headroom_qty, 1),
            "farmers_headroom": round(farmer_headroom, 1),
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "feasibility": round(100.0 * sum(self.WEIGHTS[k] * v for k, v in scores.items()), 1),
            "load": proj_qty / slot.max_quantity if slot.max_quantity else 1.0,
        }

    def _passes_filters(self, scores: dict) -> bool:
        return (
            scores["weather"] >= 0.50
            and scores["resource"] >= 0.40
            and scores["processing"] >= 0.50
        )

    def _scores(self, source: DpcContext, alt: dict) -> dict:
        capacity = alt["capacity"] or 1.0
        headroom_qty = alt.get("headroom_qty", capacity)
        capacity_score = min(1.0, headroom_qty / capacity)
        time_score = 1.0
        weather_score = WEATHER_SCORE_MAP.get(alt["weather_risk"], 0.75)
        labour_score = min(1.0, alt["labour"] / max(1.0, source.predicted_arrivals / 10.0))
        transport_score = min(1.0, alt["transport"] / max(1.0, source.predicted_arrivals / 40.0))
        storage_score = min(1.0, alt["storage"] / max(1.0, 0.5 * capacity))
        resource_score = 0.5 * labour_score + 0.3 * transport_score + 0.2 * storage_score
        assignment_score = self._assignment_score(source, alt)
        processing_rate = alt["processing"]
        if processing_rate:
            processing_score = min(
                1.0, processing_rate * self.OPERATING_HOURS / max(1.0, source.predicted_arrivals)
            )
        else:
            processing_score = min(
                1.0, alt["weighing"] * self.OPERATING_HOURS / max(1.0, source.predicted_arrivals)
            )
        return {
            "capacity": capacity_score,
            "time": time_score,
            "weather": weather_score,
            "resource": resource_score,
            "assignment": assignment_score,
            "processing": processing_score,
        }

    def _assignment_score(self, source: DpcContext, alt: dict) -> float:
        if alt["kind"] == "slot" or alt.get("dpc_id") == source.dpc_id:
            return 1.0
        if alt["district"] == source.district:
            return 1.0
        if (
            alt.get("lat") is not None
            and alt.get("lon") is not None
            and source.lat is not None
            and source.lon is not None
        ):
            distance = haversine_km(source.lat, source.lon, alt["lat"], alt["lon"])
            return max(0.10, 1.0 - distance / self.MAX_DISTANCE_KM)
        return 0.55

    def _build_movement(
        self,
        target_date: date,
        source: DpcContext,
        load: float,
        severity: str,
        alt: dict,
        farmers: float,
        qty: float,
        target_after_qty: float,
    ) -> dict:
        action = "redistribute_slots" if alt["kind"] == "slot" else "divert_to_dpc"
        priority = severity if severity == "critical" else "high"
        source_after = max(0.0, load - (qty / source.daily_capacity if source.daily_capacity else 0.0))
        target_after = target_after_qty / (alt["capacity"] or 1.0)
        reason = (
            f"Predicted arrivals {source.predicted_arrivals:.0f} or {source.predicted_quantity:.0f} "
            f"quintals put {source.name} at {load * 100:.0f}% of daily capacity (over the "
            f"{self.HIGH_LOAD * 100:.0f}% threshold). Alternative '{alt['name']}' has {alt['headroom_qty']:.0f} "
            f"quintals headroom after applying the {self.TARGET_MAX_LOAD * 100:.0f}% ceiling, weather risk "
            f"{alt['weather_risk']}, feasibility {alt['feasibility']:.0f}/100."
        )
        impact = (
            f"Source utilization {load * 100:.0f}% → {min(1.0, source_after) * 100:.0f}%; target reaches "
            f"{target_after * 100:.0f}% (capped at {self.TARGET_MAX_LOAD * 100:.0f}%). "
            f"Queue relief ≈ {farmers / max(1.0, source.processing_rate or 1.0):.1f}h."
        )
        return {
            "date": target_date,
            "dpc_id": source.dpc_id,
            "recommendation_type": RecommendationType.slot.value,
            "priority": priority,
            "title": f"Reduce load at {source.name}",
            "explanation": reason,
            "expected_impact": impact,
            "source": source.name,
            "target": alt["name"],
            "farmer_count": int(round(farmers)),
            "quantity": round(qty, 1),
            "feasibility_score": alt["feasibility"],
            "scores": alt["scores"],
            "action": action,
        }

    def _build_boost(self, target_date: date, context: DpcContext, remaining: float, severity: str) -> dict | None:
        required = max(1, int(round(context.predicted_arrivals / 10.0)))
        labour_needed = max(0, required - context.labour_available)
        if labour_needed <= 0 and context.transport_available > 0:
            return None
        priority = "high" if severity == "high" else "critical"
        return {
            "date": target_date,
            "dpc_id": context.dpc_id,
            "recommendation_type": RecommendationType.resource.value,
            "priority": priority,
            "title": f"Deploy additional staff at {context.name}",
            "explanation": (
                f"Predicted load still exceeds usable capacity by ~{remaining * self._avg_per_farmer(context):.0f} "
                f"quintals; labour availability {context.labour_available} is below the ~{required} needed. "
                f"Adding staff and transport raises effective processing throughput."
            ),
            "expected_impact": f"Processing throughput roughly +{labour_needed * 12:.0f} quintals/day",
            "source": context.name,
            "target": f"{context.name} (staffing)",
            "farmer_count": int(round(remaining)),
            "quantity": round(remaining * self._avg_per_farmer(context), 1),
            "feasibility_score": round(100.0 * min(1.0, context.labour_available / max(1, required)) + 0.05, 1),
            "scores": {},
            "action": "boost_resources",
        }

    def _build_priority(self, target_date: date, context: DpcContext, urgent: int, load: float,
                        slot: SlotContext | None) -> dict:
        if slot:
            target = f"{slot.start_time}-{slot.end_time} at {context.name}"
        else:
            target = f"{context.name} (first available allotment)"
        priority = "high" if load > self.HIGH_LOAD else "medium"
        return {
            "date": target_date,
            "dpc_id": context.dpc_id,
            "recommendation_type": RecommendationType.slot.value,
            "priority": priority,
            "title": f"Prioritize {urgent} ready/overdue farmers at {context.name}",
            "explanation": (
                f"{context.ready_farmers} farmers are harvest-ready and {context.overdue_farmers} are overdue. "
                f"Give them the earliest feasible slot ({target}) so crop quality is not degraded by waiting."
            ),
            "expected_impact": f"Protects an estimated {round(urgent * self._avg_per_farmer(context), 1)} quintals of crop quality",
            "source": context.name,
            "target": target,
            "farmer_count": urgent,
            "quantity": round(urgent * self._avg_per_farmer(context), 1),
            "feasibility_score": round(100.0 * (0.5 + 0.5 * min(1.0, load)), 1),
            "scores": {},
            "action": "prioritize_ready_farmers",
        }

    def _build_underutilized(self, target_date: date, context: DpcContext, load: float,
                             slot: SlotContext | None) -> dict | None:
        if not slot:
            return None
        headroom_farmers = max(0, slot.max_farmers - slot.booked_farmers)
        if headroom_farmers <= 0:
            return None
        target = f"{slot.start_time}-{slot.end_time} at {context.name}"
        return {
            "date": target_date,
            "dpc_id": context.dpc_id,
            "recommendation_type": RecommendationType.slot.value,
            "priority": "low",
            "title": f"Open underutilized slot at {context.name}",
            "explanation": (
                f"Slot {target} is at {load * 100:.0f}% projected utilization ({self.LOW_LOAD * 100:.0f}% "
                f"threshold). Invite ready farmers from nearby villages to raise throughput."
            ),
            "expected_impact": f"Recovers up to {headroom_farmers * self._avg_per_farmer(context):.0f} quintals of idle capacity",
            "source": f"{context.name} (underutilized)",
            "target": target,
            "farmer_count": headroom_farmers,
            "quantity": round(headroom_farmers * self._avg_per_farmer(context), 1),
            "feasibility_score": round(100.0 * (1.0 - load), 1),
            "scores": {},
            "action": "open_underutilized_slots",
        }

    def _build_weather(self, target_date: date, context: DpcContext) -> dict | None:
        if context.weather_risk not in ("high", "critical"):
            return None
        if context.predicted_quantity <= 0:
            return None
        priority = "critical" if context.weather_risk == "critical" else "high"
        return {
            "date": target_date,
            "dpc_id": context.dpc_id,
            "recommendation_type": RecommendationType.weather.value,
            "priority": priority,
            "title": f"Reschedule arrivals at {context.name} due to weather",
            "explanation": (
                f"Weather risk at {context.name} is {context.weather_risk} for {target_date.isoformat()}. "
                f"Move {context.predicted_arrivals:.0f} predicted arrivals to the next low-risk window to "
                f"protect paddy moisture and weights."
            ),
            "expected_impact": f"Protects an estimated {context.predicted_quantity:.0f} quintals from moisture damage",
            "source": context.name,
            "target": f"{context.name} (next-day window)",
            "farmer_count": int(round(context.predicted_arrivals)),
            "quantity": round(context.predicted_quantity, 1),
            "feasibility_score": round(100.0 * WEATHER_SCORE_MAP.get(context.weather_risk, 0.0), 1),
            "scores": {},
            "action": "weather_reschedule",
        }

    def _earliest_slot(self, context: DpcContext, slots: list[SlotContext]) -> SlotContext | None:
        available = [s for s in slots if s.booked_farmers < s.max_farmers]
        if not available:
            return None
        return min(available, key=lambda s: (s.start_time, s.slot_id))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class SlotRecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dpc_repo = DPCRepository(db)
        self.prediction_repo = PredictionRepository(db)
        self.dpc_capacity_repo = DPCCapacityRepository(db)
        self.slot_repo = SlotRepository(db)
        self.weather_repo = WeatherConditionRepository(db)
        self.resource_repo = ResourceAvailabilityRepository(db)
        self.farmer_repo = FarmerRepository(db)
        self.recommendation_repo = RecommendationRepository(db)
        self._slots_cache: dict[tuple[int, date], list[SlotContext]] = {}

    def analyze(self, target_date: date | None = None, persist: bool = True) -> list[dict]:
        if target_date is None:
            target_date = date.today()

        contexts, slots_by_dpc = self.build_contexts(target_date)
        results = SlotRecommender().analyze(target_date, contexts, slots_by_dpc)

        if persist and results:
            rows = [
                {
                    "dpc_id": r["dpc_id"],
                    "date": r["date"],
                    "recommendation_type": RecommendationType(r["recommendation_type"]),
                    "priority": RecommendationPriority(r["priority"]),
                    "title": r["title"],
                    "explanation": r["explanation"],
                    "expected_impact": r["expected_impact"],
                    "source": r["source"],
                    "target": r["target"],
                    "farmer_count": r["farmer_count"],
                    "quantity": r["quantity"],
                    "feasibility_score": r["feasibility_score"],
                }
                for r in results
            ]
            created = self.recommendation_repo.create_many(rows)
            for result, rec in zip(results, created):
                result["id"] = rec.id

        logger.info("Slot recommendation analysis produced %d recommendations for %s", len(results), target_date)
        return results

    def build_contexts(self, target_date: date) -> tuple[list[DpcContext], dict[int, list[SlotContext]]]:
        contexts: list[DpcContext] = []
        slots_by_dpc: dict[int, list[SlotContext]] = {}
        farmer_readiness = self._farmer_readiness_by_district()
        for dpc in self.dpc_repo.get_active():
            contexts.append(self._build_dpc_context(dpc, target_date, farmer_readiness))
            slots_by_dpc[dpc.id] = self._slots(dpc.id, target_date)
        return contexts, slots_by_dpc

    def _build_dpc_context(self, dpc, target_date: date, farmer_readiness: dict[str, tuple[int, int]]) -> DpcContext:
        arrivals_pred = self._prediction(dpc.id, target_date, PredictionType.arrival_count)
        quantity_pred = self._prediction(dpc.id, target_date, PredictionType.quantity)
        capacity = self.dpc_capacity_repo.get_by_dpc_and_date(dpc.id, target_date)
        weather = self._weather_for(dpc, target_date)
        resource = self.resource_repo.get_by_dpc_and_date(dpc.id, target_date)
        ready, overdue = farmer_readiness.get(dpc.district, (0, 0))

        return DpcContext(
            dpc_id=dpc.id,
            code=dpc.dpc_code,
            name=dpc.name,
            district=dpc.district,
            daily_capacity=dpc.daily_capacity or 0.0,
            processing_rate=dpc.processing_rate,
            storage_capacity=dpc.storage_capacity or 0.0,
            operating_status=dpc.operating_status.value if dpc.operating_status else "active",
            lat=dpc.lat,
            lon=dpc.lon,
            predicted_arrivals=arrivals_pred.predicted_value if arrivals_pred else 0.0,
            predicted_quantity=quantity_pred.predicted_value if quantity_pred else 0.0,
            remaining_capacity=capacity.remaining_capacity if capacity else None,
            weather_risk=weather.weather_risk.value if weather else "none",
            labour_available=resource.labour_available if resource else 0,
            transport_available=resource.transport_available if resource else 0,
            weighing_capacity=resource.weighing_capacity if resource else 0,
            storage_available=resource.storage_available if resource else None,
            ready_farmers=ready,
            overdue_farmers=overdue,
        )

    def _prediction(self, dpc_id: int, target_date: date, prediction_type: PredictionType):
        pred = self.prediction_repo.get_by_dpc_and_date(dpc_id, target_date, prediction_type)
        if pred is None:
            recent = self.prediction_repo.get_by_dpc(dpc_id, prediction_type=prediction_type, limit=1)
            pred = recent[0] if recent else None
        return pred

    def _weather_for(self, dpc, target_date: date):
        name = (dpc.name or "").lower()
        for location in LOCATION_NAMES:
            if location.lower() in name:
                return self.weather_repo.get_by_date_and_location(target_date, location)
        return None

    def _slots(self, dpc_id: int, target_date: date) -> list[SlotContext]:
        key = (dpc_id, target_date)
        if key in self._slots_cache:
            return self._slots_cache[key]
        slots = self.slot_repo.get_by_dpc_and_date(dpc_id, target_date)
        contexts = [
            SlotContext(
                slot_id=s.id,
                dpc_id=s.dpc_id,
                start_time=s.start_time.isoformat(),
                end_time=s.end_time.isoformat(),
                max_farmers=s.max_farmers,
                max_quantity=s.max_quantity,
                booked_farmers=s.booked_farmers,
                booked_quantity=s.booked_quantity,
            )
            for s in slots
        ]
        self._slots_cache[key] = contexts
        return contexts

    def _farmer_readiness_by_district(self) -> dict[str, tuple[int, int]]:
        counts: dict[str, tuple[int, int]] = {}
        for farmer in self.farmer_repo.get_all(limit=10000):
            if not farmer.harvest_readiness:
                continue
            ready, overdue = counts.get(farmer.district, (0, 0))
            if farmer.harvest_readiness == HarvestReadiness.ready:
                ready += 1
            elif farmer.harvest_readiness == HarvestReadiness.overdue:
                overdue += 1
            counts[farmer.district] = (ready, overdue)
        return counts