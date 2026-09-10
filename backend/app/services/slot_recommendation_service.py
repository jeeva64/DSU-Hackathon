from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.farmer import HarvestReadiness
from backend.app.models.prediction import PredictionType
from backend.app.models.recommendation import RecommendationType
from backend.app.models.slot import SlotStatus
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

READINESS_WEIGHT = {
    HarvestReadiness.ready.value: 1.0,
    HarvestReadiness.overdue.value: 1.0,
    HarvestReadiness.partially_ready.value: 0.6,
    HarvestReadiness.not_ready.value: 0.2,
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
    priorities: list[dict] = field(default_factory=list)


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
        by_id = {c.dpc_id: c for c in contexts}
        candidates = self._candidate_targets(contexts, slots_by_dpc)
        recommendations: list[dict] = []

        projected_qty = {c.dpc_id: c.predicted_quantity for c in contexts}
        projected_farmers = {c.dpc_id: c.predicted_arrivals for c in contexts}
        projected_slot_qty: dict[int, float] = {}
        projected_slot_farmers: dict[int, float] = {}

        for context in contexts:
            slots = slots_by_dpc.get(context.dpc_id, [])
            share = self._slot_distribution(context, slots)
            for slot, qty, farmers in share:
                projected_slot_qty[slot.slot_id] = qty
                projected_slot_farmers[slot.slot_id] = farmers

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

            feasible = self._rank_targets(context, candidates, by_id, projected_qty, projected_farmers)
            for alt in feasible:
                if remaining <= 0.5:
                    break
                accept_farmers = min(remaining, alt["farmers_headroom"])
                if accept_farmers <= 0.5:
                    continue
                accept_qty = accept_farmers * avg
                if alt["kind"] == "dpc":
                    projected_qty[alt["dpc_id"]] += accept_qty
                    projected_farmers[alt["dpc_id"]] += accept_farmers
                else:
                    projected_slot_qty[alt["slot_id"]] += accept_qty
                    projected_slot_farmers[alt["slot_id"]] += accept_farmers
                remaining -= accept_farmers

                recommendations.append(
                    self._build_movement(
                        target_date,
                        context,
                        avg,
                        accept_farmers,
                        accept_qty,
                        alt,
                        load,
                        severity,
                    )
                )

            if remaining >= 0.5:
                resource_rec = self._build_boost(target_date, context, remaining, severity)
                if resource_rec:
                    recommendations.append(resource_rec)

        for context in contexts:
            urgent = context.ready_farmers + context.overdue_farmers
            if urgent <= 0:
                continue
            load = self._quantity_load(context)
            slot = self._earliest_slot(context, slots_by_dpc)
            recommendations.append(
                self._build_priority(
                    target_date, context, urgent, load, slot, avg=self._avg_per_farmer(context)
                )
            )

        for context in contexts:
            load = self._quantity_load(context)
            if load < self.LOW_LOAD:
                slot = self._earliest_slot(context, slots_by_dpc)
                rec = self._build_underutilized(
                    target_date, context, load, slot, avg=self._avg_per_farmer(context)
                )
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
            f = self._slot_farmers(context, slot, farmer_total, qty_total)
            out.append((slot, f[1], f[0]))
        return out

    def _slot_farmers(self, context: DpcContext, slot: SlotContext, farmer_total: int, qty_total: float):
        farmer_share = (
            context.predicted_arrivals * slot.max_farmers / farmer_total if farmer_total else 0.0
        )
        qty_share = context.predicted_quantity * slot.max_quantity / qty_total if qty_total else 0.0
        return (
            farmer_share + slot.booked_farmers,
            qty_share + slot.booked_quantity,
        )

    def _candidate_targets(self, contexts: list[DpcContext], slots_by_dpc: dict[int, list[SlotContext]]) -> list[dict]:
        candidates: list[dict] = []
        for dpc in contexts:
            if dpc.operating_status not in ("active", "overloaded"):
                continue
            candidates.append(
                {
                    "kind": "dpc",
                    "dpc_id": dpc.dpc_id,
                    "name": dpc.name,
                    "district": dpc.district,
                    "lat": dpc.lat,
                    "lon": dpc.lon,
                    "capacity": dpc.daily_capacity,
                    "weather_risk": dpc.weather_risk,
                    "labour": dpc.labour_available,
                    "transport": dpc.transport_available,
                    "weighing": dpc.weighing_capacity,
                    "processing": dpc.processing_rate,
                    "storage": dpc.storage_available if dpc.storage_available is not None else dpc.storage_capacity,
                    "load": self._quantity_load(dpc),
                }
            )
            for slot in slots_by_dpc.get(dpc.dpc_id, []):
                f_proj, q_proj = self._slot_farmers(dpc, slot, 0, 0)
                candidates.append(
                    {
                        "kind": "slot",
                        "slot_id": slot.slot_id,
                        "dpc_id": dpc.dpc_id,
                        "name": f"{slot.start_time}-{slot.end_time} at {dpc.name}",
                        "district": dpc.district,
                        "lat": dpc.lat,
                        "lon": dpc.lon,
                        "capacity": slot.max_quantity,
                        "weather_risk": dpc.weather_risk,
                        "labour": dpc.labour_available,
                        "transport": dpc.transport_available,
                        "weighing": dpc.weighing_capacity,
                        "processing": dpc.processing_rate,
                        "storage": dpc.storage_available if dpc.storage_available is not None else dpc.storage_capacity,
                        "load": q_proj / slot.max_quantity if slot.max_quantity else 0.0,
                        "projected_qty": q_proj,
                        "projected_farmers": f_proj,
                    }
                )
        return candidates

    def _rank_targets(
        self,
        source: DpcContext,
        candidates: list[dict],
        dpcs_by_id: dict[int, DpcContext],
        projected_qty: dict[int, float],
        projected_farmers: dict[int, float],
    ) -> list[dict]:
        ranked = []
        for alt in candidates:
            if alt["kind"] == "dpc":
                if alt["dpc_id"] == source.dpc_id:
                    continue
                target = dpcs_by_id[alt["dpc_id"]]
                if self._quantity_load(target) > self.HIGH_LOAD:
                    continue
                used = projected_qty[alt["dpc_id"]]
                headroom_qty = self.TARGET_MAX_LOAD * alt["capacity"] - used
                avg = self._avg_per_farmer(target) if target.predicted_arrivals > 0 else self.DEFAULT_QUINTALS_PER_FARMER
            else:
                if alt["slot_id"] is None:
                    continue
                alt_full = candidate_slot_of(alt)
                proj_qty = alt_full["projected_qty"] + projected_qty[alt["slot_id"]]
                proj_farmers = alt_full["projected_farmers"] + projected_farmers[alt["slot_id"]]
                target = dpcs_by_id[alt["dpc_id"]]
                headroom_qty = min(alt["capacity"] - proj_qty, 0.0)
                if alt["max_farmers"]:
                    headroom_qty = min(
                        alt["max_quantity"] - proj_qty,
                        (alt["max_farmers"] - proj_farmers) * self._avg_per_farmer(target),
                    )
                else:
                    headroom_qty = 0.0
                used = proj_qty
                avg = self._avg_per_farmer(target)

            headroom_qty = max(0.0, headroom_qty)
            farmers_headroom = headroom_qty / avg if avg > 0 else 0.0
            if headroom_qty <= 0.0 or farmers_headroom <= 0.0:
                continue

            scores = self._scores(source, alt, headroom_qty, target_dpc=alt.get("dpc_id"))
            if scores["weather"] < 0.50 or scores["resource"] < 0.40 or scores["processing"] < 0.50:
                continue
            ranked.append(
                {
                    "kind": alt["kind"],
                    "dpc_id": alt["dpc_id"],
                    "slot_id": alt.get("slot_id"),
                    "name": alt["name"],
                    "headroom_qty": round(headroom_qty, 1),
                    "farmers_headroom": round(farmers_headroom, 1),
                    "scores": {k: round(v, 3) for k, v in scores.items()},
                    "feasibility": round(100.0 * sum(self.WEIGHTS[k] * v for k, v in scores.items()), 1),
                    "load": used / alt["capacity"] if alt["capacity"] else 1.0,
                }
            )
        ranked.sort(key=lambda r: -r["feasibility"])
        return ranked

    def _scores(self, source: DpcContext, alt: dict, headroom_qty: float, target_dpc: int | None = None) -> dict:
        capacity = alt["capacity"] or 1.0
        capacity_score = min(1.0, headroom_qty / capacity)
        time_score = 1.0
        weather_score = WEATHER_SCORE_MAP.get(alt["weather_risk"], 0.75)
        labour_score = min(1.0, alt["labour"] / max(1.0, source.predicted_arrivals / 10.0))
        transport_score = min(1.0, alt["transport"] / max(1.0, source.predicted_arrivals / 40.0))
        storage_score = min(1.0, alt["storage"] / max(1.0, 0.5 * capacity))
        resource_score = 0.5 * labour_score + 0.3 * transport_score + 0.2 * storage_score
        assignment_score = self._assignment_score(source, alt, target_dpc)
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

    def _assignment_score(self, source: DpcContext, alt: dict, target_dpc: int | None) -> float:
        if target_dpc is None or target_dpc == source.dpc_id:
            return 1.0
        if alt["district"] == source.district:
            return 1.0
        if alt.get("lat") is not None and alt.get("lon") is not None and source.lat is not None and source.lon is not None:
            distance = haversine_km(source.lat, source.lon, alt["lat"], alt["lon"])
            return max(0.10, 1.0 - distance / self.MAX_DISTANCE_KM)
        return 0.55

    def _build_movement(
        self,
        target_date: date,
        source: DpcContext,
        avg: float,
        farmers: float,
        qty: float,
        alt: dict,
        load: float,
        severity: str,
    ) -> dict:
        kind = alt["kind"]
        action = "redistribute_slots" if kind == "slot" else "divert_to_dpc"
        rec_type = RecommendationType.slot
        priority = severity if severity == "critical" else "high"
        source_after = max(0.0, load - (qty / source.daily_capacity if source.daily_capacity else 0.0))
        target_name = alt["name"]
        reason = (
            f"Predicted arrivals {source.predicted_arrivals:.0f} ({qty_.f:.0f} quintals) put "
            f"{source.name} at {load * 100:.0f}% of daily capacity ({self.HIGH_LOAD * 100:.0f}% threshold). "
            f"Alternative '{target_name}' has {alt['headroom_qty']:.0f} quintals headroom and scores "
            f"{alt['feasibility']:.0f}/100 for feasibility after leaving {self.TARGET_MAX_LOAD * 100:.0f}% "
            f"headroom capped."
        )
        impact = (
            f"Source utilization {load * 100:.0f}% → {source_after * 100:.0f}%; target reaches "
            f"{min(1.0, alt['load'] + qty / (alt['capacity'] or 1.0)) * 100:.0f}%. "
            f"Queue relief ≈ {farmers / max(1.0, source.processing_rate or 1.0):.1f}h."
        )
        return {
            "date": target_date,
            "dpc_id": source.dpc_id,
            "recommendation_type": rec_type.value,
            "priority": priority,
            "title": f"Reduce load at {source.name}",
            "explanation": reason,
            "expected_impact": impact,
            "source": source.name,
            "target": target_name,
            "farmer_count": int(round(farmers)),
            "quantity": round(qty, 1),
            "feasibility_score": alt["feasibility"],
            "scores": alt["scores"],
            "action": action,
        }

    def _build_boost(self, target_date: date, context: DpcContext, remaining: float, severity: str) -> dict | None:
        labour_needed = max(0, int(round(context.predictions_arrivals if hasattr(context, "predictions_arrivals") else context.predicted_arrivals / 10.0)) - context.labour_available)
        if labour_needed <= 0 and context.transport_available > 0:
            return None
        priority = "high" if severity == "high" else "critical"
        extra = max(1, labour_needed)
        return {
            "date": target_date,
            "dpc_id": context.dpc_id,
            "recommendation_type": RecommendationType.resource.value,
            "priority": priority,
            "title": f"Deploy additional staff at {context.name}",
            "explanation": (
                f"Predicted load still exceeds usable capacity by ~{remaining * self._avg_per_farmer(context):.0f} "
                f"quintals; labour availability {context.labour_available} is below the ~{max(1, int(round(context.predicted_arrivals / 10.0)))} "
                f"needed. Adding staff raises effective processing throughput."
            ),
            "expected_impact": f"Processing throughput roughly +{extra * 10:.0f} quintals/day",
            "source": context.name,
            "target": f"{context.name} (staffing)",
            "farmer_count": int(round(remaining)),
            "quantity": round(remaining * self._avg_per_farmer(context), 1),
            "feasibility_score": round(100.0 * min(1.0, context.labour_available / max(1, extra)), 1),
            "scores": {},
            "action": "boost_resources",
        }

    def _build_priority(
        self,
        target_date: date,
        context: DpcContext,
        urgent: int,
        load: float,
        slot: SlotContext | None,
        avg: float,
    ) -> dict:
        target = None
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
            "expected_impact": f"Protects an estimated {round(urgent * avg, 1)} quintals of crop quality",
            "source": context.name,
            "target": target,
            "farmer_count": urgent,
            "quantity": round(urgent * avg, 1),
            "feasibility_score": round(100.0 * (0.5 + 0.5 * min(1.0, load)), 1),
            "scores": {},
            "action": "prioritize_ready_farmers",
        }

    def _build_underutilized(
        self,
        target_date: date,
        context: DpcContext,
        load: float,
        slot: SlotContext | None,
        avg: float,
    ) -> dict | None:
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
                f"Slot {target} is at {load * 100:.0f}% projected utilization ({self.LOW_LOAD * 100:.0f}% threshold). "
                f"Invite ready farmers from nearby villages to raise throughput."
            ),
            "expected_impact": f"Recovers up to {headroom_farmers * avg:.0f} quintals of idle capacity",
            "source": f"{context.name} (underutilized)",
            "target": target,
            "farmer_count": headroom_farmers,
            "quantity": round(headroom_farmers * avg, 1),
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

    def _earliest_slot(self, context: DpcContext, slots_by_dpc: dict[int, list[SlotContext]]) -> SlotContext | None:
        slots = slots_by_dpc.get(context.dpc_id, [])
        slots = [s for s in slots if s.booked_farmers < s.max_farmers]
        if not slots:
            return None
        return min(slots, key=lambda s: (s.start_time, s.slot_id))


def _candidate_slot_of(alt: dict) -> dict:
    return alt


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

    def analyze(self, target_date: date | None = None, persist: bool = True) -> list[dict]:
        if target_date is None:
            target_date = date.today()

        contexts: list[DpcContext] = []
        slots_by_dpc: dict[int, list[SlotContext]] = {}
        dpcs = self.dpc_repo.get_active()
        farmer_readiness = self._farmer_readiness_by_district()

        for dpc in dpcs:
            context = self._build_dpc_context(dpc, target_date, farmer_readiness)
            contexts.append(context)
            slots_by_dpc[dpc.id] = self._build_slots(dpc.id, target_date)

        results = SlotRecommender().analyze(target_date, contexts, slots_by_dpc)

        if persist and results:
            rows = [
                {
                    "dpc_id": r["dpc_id"],
                    "date": r["date"],
                    "recommendation_type": RecommendationType(r["recommendation_type"]),
                    "priority": r["priority"],
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

    def _build_dpc_context(self, dpc, target_date: date, farmer_readiness: dict[str, tuple[int, int]]) -> DpcContext:
        arrivals_pred = self._prediction(dpc.id, target_date, PredictionType.arrival_count)
        quantity_pred = self._prediction(dpc.id, target_date, PredictionType.quantity)
        capacity = self.dpc_capacity_repo.get_by_dpc_and_date(dpc.id, target_date)
        weather = self._weather_for(dpc, target_date)
        resource = self.resource_repo.get_by_dpc_and_date(dpc.id, target_date)
        ready, overdue = farmer_readiness.get(dpc.district, (0, 0))

        name_match = next((loc for loc in LOCATION_NAMES if loc.lower() in (dpc.name or "").lower()), None)
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

    def _build_slots(self, dpc_id: int, target_date: date) -> list[SlotContext]:
        slots = self.slot_repo.get_by_dpc_and_date(dpc_id, target_date)
        return [
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