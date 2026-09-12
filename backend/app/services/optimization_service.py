from __future__ import annotations

import dataclasses
import logging
import math
from datetime import date

from sqlalchemy.orm import Session

from backend.app.models.recommendation import RecommendationPriority, RecommendationType
from backend.app.repositories.recommendation_repo import RecommendationRepository
from backend.app.services.slot_recommendation_service import (
    DpcContext,
    SlotContext,
    SlotRecommendationService,
    SlotRecommender,
)

logger = logging.getLogger("backend.services.optimization")

WEATHER_RISK_LEVEL = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

ACTION_LABELS = {
    "divert_to_dpc": "Diversion to another DPC",
    "redistribute_slots": "Redistribution to idle slots",
    "boost_resources": "Resource boost",
    "weather_reschedule": "Weather rescheduling",
    "prioritize_ready_farmers": "Urgent farmer prioritization",
    "open_underutilized_slots": "Open underutilized slots",
    "no_action": "No action",
}

ACTION_TO_TYPE = {
    "divert_to_dpc": RecommendationType.slot,
    "redistribute_slots": RecommendationType.slot,
    "prioritize_ready_farmers": RecommendationType.slot,
    "open_underutilized_slots": RecommendationType.slot,
    "boost_resources": RecommendationType.resource,
    "weather_reschedule": RecommendationType.weather,
}


class OptimizationEngine:
    HIGH_LOAD = SlotRecommender.HIGH_LOAD
    CRITICAL_LOAD = SlotRecommender.CRITICAL_LOAD
    LOW_LOAD = SlotRecommender.LOW_LOAD
    TARGET_MAX_LOAD = SlotRecommender.TARGET_MAX_LOAD
    OPERATING_HOURS = SlotRecommender.OPERATING_HOURS
    TARGET_UTIL = 0.75
    TRANSPORT_QTY_PER_TRIP = 100.0
    FARMERS_PER_LABOUR = 10
    SELECTION_THRESHOLD = 5.0
    DEFAULT_QUINTALS_PER_FARMER = SlotRecommender.DEFAULT_QUINTALS_PER_FARMER

    WEIGHTS = {
        "congestion_reduction": 0.30,
        "capacity_utilization": 0.15,
        "expected_delay_reduction": 0.15,
        "weather_exposure_reduction": 0.15,
        "resource_feasibility": 0.15,
        "operational_balance": 0.10,
    }

    def optimize(
        self,
        target_date: date,
        contexts: list[DpcContext],
        slots_by_dpc: dict[int, list[SlotContext]],
    ) -> dict:
        before = self._snapshot(contexts, slots_by_dpc)
        candidates = self._generate_candidates(contexts, slots_by_dpc)
        for candidate in candidates:
            self._apply_gates(candidate, contexts, slots_by_dpc)
        for candidate in candidates:
            if not candidate["feasible"]:
                candidate["scores"] = {}
                candidate["overall_score"] = 0.0
                continue
            after = self._simulate(candidate, contexts, slots_by_dpc)
            self._score(candidate, before, after)

        candidates.sort(key=lambda c: (not c["feasible"], -c["overall_score"]))
        actionable = [
            c for c in candidates
            if c["feasible"] and c["action"] != "no_action" and c["overall_score"] >= self.SELECTION_THRESHOLD
        ]
        selected = actionable[0] if actionable else next(c for c in candidates if c["action"] == "no_action")

        return {
            "target_date": target_date,
            "current_state": [self._dpc_state(c, slots_by_dpc.get(c.dpc_id, [])) for c in contexts],
            "baseline": self._baseline(before),
            "candidate_actions": candidates,
            "selected_recommendation": selected,
            "reasons": selected["reasons"],
            "expected_improvement": selected["expected_improvement"],
        }

    def _snapshot(self, contexts: list[DpcContext], slots_by_dpc: dict[int, list[SlotContext]]) -> dict:
        cong = 0.0
        delay = 0.0
        exposure = 0.0
        util_healths: list[float] = []
        slack_healths: list[float] = []
        loads: list[float] = []
        for c in contexts:
            load = self._quantity_load(c)
            loads.append(load)
            cong += max(0.0, load - self.HIGH_LOAD)
            delay += self._delay_hours(c)
            exposure += WEATHER_RISK_LEVEL.get(c.weather_risk, 0) * c.predicted_quantity
            slot_util = self._mean_slot_util(c, slots_by_dpc.get(c.dpc_id, []))
            util_healths.append(self._util_health(load, slot_util))
            slack_healths.append(self._resource_slack(c))
        return {
            "avg_load": round(sum(loads) / len(loads), 4) if loads else 0.0,
            "congestion": round(cong, 4),
            "delay_hours": round(delay, 2),
            "exposure": round(exposure, 2),
            "utilization": round(sum(util_healths) / len(util_healths), 4) if util_healths else 0.0,
            "resource_slack": round(sum(slack_healths) / len(slack_healths), 4) if slack_healths else 0.0,
            "balance": round(self._stdev(loads), 4),
        }

    def _baseline(self, before: dict) -> dict:
        return {
            "average_load_pct": round(before["avg_load"] * 100, 1),
            "congestion": before["congestion"],
            "delay_hours": before["delay_hours"],
            "weather_exposure": before["exposure"],
            "resource_slack": before["resource_slack"],
            "capacity_utilization_health": before["utilization"],
            "operational_balance": before["balance"],
        }

    def _dpc_state(self, c: DpcContext, slots: list[SlotContext]) -> dict:
        load = self._quantity_load(c)
        free_slots = sum(1 for s in slots if s.booked_farmers < s.max_farmers)
        return {
            "dpc_id": c.dpc_id,
            "name": c.name,
            "code": c.code,
            "district": c.district,
            "operating_status": c.operating_status,
            "load_pct": round(load * 100, 1),
            "congestion_pct": round(max(0.0, load - self.HIGH_LOAD) * 100, 1),
            "predicted_arrivals": round(c.predicted_arrivals, 1),
            "predicted_quantity": round(c.predicted_quantity, 1),
            "weather_risk": c.weather_risk,
            "labour_available": c.labour_available,
            "transport_available": c.transport_available,
            "weighing_capacity": c.weighing_capacity,
            "storage_available": round(c.storage_available, 1) if c.storage_available is not None else None,
            "free_slots": free_slots,
            "urgent_farmers": c.ready_farmers + c.overdue_farmers,
        }

    def _generate_candidates(
        self, contexts: list[DpcContext], slots_by_dpc: dict[int, list[SlotContext]]
    ) -> list[dict]:
        candidates: list[dict] = []
        slots_map = {c.dpc_id: slots_by_dpc.get(c.dpc_id, []) for c in contexts}

        for c in contexts:
            load = self._quantity_load(c)
            urgent = c.ready_farmers + c.overdue_farmers
            if load > self.HIGH_LOAD or c.operating_status == "overloaded":
                avg = self._avg_per_farmer(c)
                excess_qty = max(0.0, c.predicted_quantity - self.HIGH_LOAD * (c.daily_capacity or 1.0))
                for target in contexts:
                    if target.dpc_id == c.dpc_id or target.operating_status != "active":
                        continue
                    if self._quantity_load(target) > self.HIGH_LOAD:
                        continue
                    headroom = max(0.0, self.TARGET_MAX_LOAD * (target.daily_capacity or 1.0) - target.predicted_quantity)
                    if headroom <= 0.0:
                        continue
                    qty = min(excess_qty, headroom)
                    candidates.append(
                        self._candidate(
                            "divert_to_dpc", c, target, qty, qty / avg if avg else 0.0, load, None,
                            f"Shift excess arrivals from overloaded {c.name} to a DPC with verified throttled headroom.",
                        )
                    )
                for slot in slots_map[c.dpc_id]:
                    headroom = self._slot_headroom(c, slot, slots_map[c.dpc_id])
                    if headroom <= 0.0:
                        continue
                    qty = min(excess_qty, headroom)
                    candidates.append(
                        self._candidate(
                            "redistribute_slots", c, None, qty, qty / avg if avg else 0.0, load,
                            slot, f"Use idle slot capacity at {c.name} for the excess arrivals.",
                        )
                    )
                if excess_qty > 0.0:
                    candidates.append(
                        self._candidate(
                            "boost_resources", c, None, excess_qty,
                            excess_qty / avg if avg else 0.0, load, None,
                            f"Deploy additional staff and transport to lift effective processing at overloaded {c.name}.",
                        )
                    )
            if c.weather_risk in ("high", "critical") and c.predicted_quantity > 0.0:
                candidates.append(
                    self._candidate(
                        "weather_reschedule", c, None, c.predicted_quantity, c.predicted_arrivals, load, None,
                        f"Move predicted arrivals at {c.name} to the next low-risk window to protect paddy quality.",
                    )
                )
            if urgent > 0:
                avg = self._avg_per_farmer(c)
                candidates.append(
                    self._candidate(
                        "prioritize_ready_farmers", c, None, urgent * avg, urgent, load, None,
                        f"Prioritize {urgent} harvest-ready/overdue farmers at {c.name} in the earliest batch.",
                    )
                )
            if load < self.LOW_LOAD:
                available = [s for s in slots_map[c.dpc_id] if s.booked_farmers < s.max_farmers]
                if available:
                    slot = min(available, key=lambda s: (s.start_time, s.slot_id))
                    headroom_farmers = max(0, slot.max_farmers - slot.booked_farmers)
                    avg = self._avg_per_farmer(c)
                    candidates.append(
                        self._candidate(
                            "open_underutilized_slots", c, None, headroom_farmers * avg,
                            headroom_farmers, load, slot,
                            f"Open the idle slot at {c.name} to invite ready farmers and raise throughput.",
                        )
                    )

        candidates.append(
            self._candidate("no_action", contexts[0], None, 0.0, 0, 0.0, None,
                            "Keep the current plan and monitor.")
        )
        return candidates

    def _candidate(
        self, action: str, source: DpcContext, target: DpcContext | None, qty: float, farmers: float,
        load: float, slot: SlotContext | None, explanation: str,
    ) -> dict:
        critical = load > self.CRITICAL_LOAD or source.operating_status == "overloaded"
        if action == "divert_to_dpc":
            target_name = target.name if target else source.name
            title = f"Divert arrivals from {source.name} to {target_name}"
        elif action == "redistribute_slots" and slot:
            target_name = f"{slot.start_time}-{slot.end_time} at {source.name}"
            title = f"Redistribute excess arrivals to {target_name}"
        elif action == "boost_resources":
            target_name = f"{source.name} (staffing)"
            title = f"Deploy additional staff and transport at {source.name}"
        elif action == "weather_reschedule":
            target_name = f"{source.name} (next-day window)"
            title = f"Reschedule arrivals at {source.name} due to weather"
        elif action == "prioritize_ready_farmers":
            target_name = f"{source.name} (first allotted batch)"
            title = f"Prioritize {int(round(farmers))} ready/overdue farmers at {source.name}"
        elif action == "open_underutilized_slots" and slot:
            target_name = f"{slot.start_time}-{slot.end_time} at {source.name}"
            title = f"Open underutilized slot at {source.name}"
        else:
            target_name = source.name
            title = "Maintain the current procurement plan"

        if action == "boost_resources":
            priority = "critical" if critical else "high"
        elif action == "weather_reschedule":
            priority = "critical" if source.weather_risk == "critical" else "high"
        elif action == "prioritize_ready_farmers":
            priority = "high" if load > self.HIGH_LOAD else "medium"
        elif action in ("open_underutilized_slots", "no_action"):
            priority = "low"
        else:
            priority = "critical" if critical else "high"

        return {
            "action": action,
            "title": title,
            "explanation": explanation,
            "expected_impact": "",
            "source": source.name,
            "source_dpc_id": source.dpc_id,
            "target": target_name,
            "target_dpc_id": target.dpc_id if target else None,
            "target_slot_id": slot.slot_id if slot else None,
            "priority": priority,
            "farmer_count": int(round(farmers)),
            "quantity": round(max(0.0, qty), 1),
            "feasible": False,
            "infeasible_reason": None,
            "scores": {},
            "overall_score": 0.0,
            "reasons": [],
            "expected_improvement": {},
        }

    def _apply_gates(self, candidate: dict, contexts: list[DpcContext], slots_by_dpc: dict[int, list[SlotContext]]) -> None:
        action = candidate["action"]
        by_id = {c.dpc_id: c for c in contexts}
        if action == "no_action":
            candidate["feasible"] = True
            candidate["reasons"] = [
                "Every active DPC is within the 85% tolerance; no diversion, rescheduling or boost is materially better."
            ]
            return
        if action in ("divert_to_dpc", "redistribute_slots"):
            self._gate_movement(candidate, by_id, slots_by_dpc)
        elif action == "prioritize_ready_farmers":
            candidate["feasible"] = True
        else:
            candidate["feasible"] = True

    def _gate_movement(self, candidate: dict, by_id: dict[int, DpcContext],
                       slots_by_dpc: dict[int, list[SlotContext]]) -> None:
        src = by_id.get(candidate["source_dpc_id"])
        if not src:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = "Source DPC is no longer active"
            return
        avg = self._avg_per_farmer(src)

        if candidate["action"] == "redistribute_slots":
            slot = next(
                (s for s in slots_by_dpc.get(src.dpc_id, []) if s.slot_id == candidate["target_slot_id"]), None
            )
            if slot is None:
                candidate["feasible"] = False
                candidate["infeasible_reason"] = "Target slot is no longer available"
                return
            candidate["quantity"] = min(candidate["quantity"], self._slot_headroom(src, slot, slots_by_dpc.get(src.dpc_id, [])))
            candidate["farmer_count"] = int(round(candidate["quantity"] / avg)) if avg else 0
            if candidate["quantity"] <= 0.0:
                candidate["feasible"] = False
                candidate["infeasible_reason"] = f"Slot {slot.start_time}-{slot.end_time} has no headroom under the 90% ceiling"
                return
            if src.labour_available <= 0:
                candidate["feasible"] = False
                candidate["infeasible_reason"] = f"{src.name} has no labour to handle the added lot"
                return
            needed = math.ceil(candidate["farmer_count"] / self.FARMERS_PER_LABOUR)
            if needed > src.labour_available:
                candidate["reasons"].append(
                    f"Labour short by {needed - src.labour_available} staff at {src.name} – schedule carefully"
                )
            candidate["reasons"].append(f"Reuses idle slot capacity within {src.name}'s 90% slot ceiling")
            candidate["feasible"] = True
            return

        dst = by_id.get(candidate["target_dpc_id"])
        if not dst or dst.operating_status != "active":
            candidate["feasible"] = False
            candidate["infeasible_reason"] = f"Target {candidate['target']} is not active"
            return

        capacity = dst.daily_capacity or 1.0
        after_load = (dst.predicted_quantity + candidate["quantity"]) / capacity
        if after_load > self.TARGET_MAX_LOAD:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = (
                f"Shifting {candidate['quantity']:.0f} q would put {dst.name} at {after_load * 100:.0f}% load "
                f"above the {self.TARGET_MAX_LOAD * 100:.0f}% ceiling"
            )
            return

        if dst.transport_available <= 0:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = f"{dst.name} has no transport available for the move"
            return
        needed_trucks = math.ceil(candidate["quantity"] / self.TRANSPORT_QTY_PER_TRIP)
        if needed_trucks > dst.transport_available:
            candidate["quantity"] = dst.transport_available * self.TRANSPORT_QTY_PER_TRIP
            candidate["farmer_count"] = int(round(candidate["quantity"] / avg)) if avg else 0
            candidate["reasons"].append(
                f"Transport capped: {dst.transport_available} truck(s) limit the move to "
                f"{dst.transport_available * self.TRANSPORT_QTY_PER_TRIP:.0f} q"
            )
            if candidate["quantity"] <= 0.0:
                candidate["feasible"] = False
                candidate["infeasible_reason"] = f"{dst.name} cannot carry any diverted quantity"
                return

        storage = dst.storage_available if dst.storage_available is not None else dst.storage_capacity
        slack = storage - dst.predicted_quantity
        if slack <= 0.2:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = f"Storage at {dst.name} is full ({max(0.0, storage):.0f} q total)"
            return
        if candidate["quantity"] > slack:
            candidate["quantity"] = slack
            candidate["farmer_count"] = int(round(candidate["quantity"] / avg)) if avg else 0
            candidate["reasons"].append(f"Storage capped: {dst.name} has {slack:.0f} q of free space")
        if candidate["quantity"] <= 0.2:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = f"Storage at {dst.name} cannot absorb the diversion"
            return

        needed_labour = math.ceil(candidate["farmer_count"] / self.FARMERS_PER_LABOUR)
        if dst.labour_available <= 0:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = f"{dst.name} has no labour to receive the diverted farmers"
            return
        if needed_labour > dst.labour_available:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = (
                f"{dst.name} has only {dst.labour_available} staff but {needed_labour} are required for "
                f"{candidate['farmer_count']} diverted farmers"
            )
            return

        final_load = (dst.predicted_quantity + candidate["quantity"]) / capacity
        if final_load > self.TARGET_MAX_LOAD:
            candidate["feasible"] = False
            candidate["infeasible_reason"] = f"Diversion would push {dst.name} past the 90% ceiling"
            return
        candidate["feasible"] = True

    def _simulate(self, candidate: dict, contexts: list[DpcContext],
                  slots_by_dpc: dict[int, list[SlotContext]]) -> dict:
        new_contexts = [dataclasses.replace(c) for c in contexts]
        new_slots = {dpc_id: [dataclasses.replace(s) for s in slots] for dpc_id, slots in slots_by_dpc.items()}
        by_id = {c.dpc_id: c for c in new_contexts}
        action = candidate["action"]
        qty = candidate["quantity"]
        src = by_id.get(candidate["source_dpc_id"])
        avg = self._avg_per_farmer(src) if src else self.DEFAULT_QUINTALS_PER_FARMER
        farmers = qty / avg if avg > 0 else 0.0

        if action in ("divert_to_dpc", "weather_reschedule", "prioritize_ready_farmers") and src:
            src.predicted_quantity = max(0.0, src.predicted_quantity - qty)
            src.predicted_arrivals = max(0.0, src.predicted_arrivals - farmers)
            if action == "divert_to_dpc" and candidate["target_dpc_id"] in by_id:
                dst = by_id[candidate["target_dpc_id"]]
                dst.predicted_quantity += qty
                dst.predicted_arrivals += farmers
        elif action == "redistribute_slots" and src:
            slot = next(
                (s for s in new_slots.get(src.dpc_id, []) if s.slot_id == candidate["target_slot_id"]), None
            )
            if slot:
                slot.booked_quantity += qty
                slot.booked_farmers += farmers
        elif action == "boost_resources" and src:
            needed = math.ceil(farmers / self.FARMERS_PER_LABOUR)
            src.labour_available += max(1, needed)
        elif action == "open_underutilized_slots" and src:
            slot = next(
                (s for s in new_slots.get(src.dpc_id, []) if s.slot_id == candidate["target_slot_id"]), None
            )
            if slot:
                slot.booked_quantity += qty
                slot.booked_farmers += farmers

        return self._snapshot(new_contexts, new_slots)

    def _score(self, candidate: dict, before: dict, after: dict) -> None:
        if candidate["action"] == "no_action":
            candidate["scores"] = {k: 0.0 for k in self.WEIGHTS}
            candidate["overall_score"] = 0.0
            candidate["expected_improvement"] = {
                "congestion_relief": 0.0,
                "delay_hours_saved": 0.0,
                "weather_exposure_reduction_units": 0.0,
                "capacity_utilization_gain": 0.0,
                "resource_slack_after": round(after["resource_slack"], 3),
                "balance_improvement": 0.0,
            }
            return

        def improvement(before_val: float, after_val: float) -> float:
            if before_val <= 1e-6:
                return 0.0
            return max(0.0, min(1.0, (before_val - after_val) / before_val))

        def gain(before_val: float, after_val: float) -> float:
            if before_val <= 1e-6:
                return 0.0
            return max(0.0, min(1.0, (after_val - before_val) / before_val))

        scores = {
            "congestion_reduction": round(improvement(before["congestion"], after["congestion"]), 3),
            "capacity_utilization": round(gain(before["utilization"], after["utilization"]), 3),
            "expected_delay_reduction": round(improvement(before["delay_hours"], after["delay_hours"]), 3),
            "weather_exposure_reduction": round(improvement(before["exposure"], after["exposure"]), 3),
            "resource_feasibility": round(min(1.0, after["resource_slack"]), 3),
            "operational_balance": round(improvement(before["balance"], after["balance"]), 3),
        }
        candidate["scores"] = scores
        candidate["overall_score"] = round(
            100.0 * sum(self.WEIGHTS[k] * v for k, v in scores.items()), 1
        )
        candidate["expected_improvement"] = {
            "congestion_relief": round(max(0.0, before["congestion"] - after["congestion"]), 2),
            "delay_hours_saved": round(max(0.0, before["delay_hours"] - after["delay_hours"]), 2),
            "weather_exposure_reduction_units": round(max(0.0, before["exposure"] - after["exposure"]), 2),
            "capacity_utilization_gain": round(max(0.0, after["utilization"] - before["utilization"]), 3),
            "resource_slack_after": round(after["resource_slack"], 3),
            "balance_improvement": round(max(0.0, before["balance"] - after["balance"]), 3),
        }
        steps = []
        if scores["congestion_reduction"] > 0:
            steps.append(f"cuts system congestion by {scores['congestion_reduction'] * 100:.0f}%")
        if scores["expected_delay_reduction"] > 0:
            steps.append(f"removes ~{candidate['expected_improvement']['delay_hours_saved']:.0f}h of queuing")
        if scores["weather_exposure_reduction"] > 0:
            steps.append(
                f"cuts weather-exposed harvest by {candidate['expected_improvement']['weather_exposure_reduction_units']:.0f} units"
            )
        if scores["capacity_utilization"] > 0:
            steps.append("improves slot/facility utilization toward the 75% target")
        if scores["operational_balance"] > 0:
            steps.append("evens out load across DPCs")
        if steps:
            candidate["reasons"].append(
                f"Best feasible {ACTION_LABELS[candidate['action']].lower()}: " + ", ".join(steps) + "."
            )
            candidate["expected_impact"] = (
                f"After execution: {', '.join(steps)}; overall decision score {candidate['overall_score']:.0f}/100."
            )

    def _quantity_load(self, c: DpcContext) -> float:
        capacity = c.daily_capacity if c.daily_capacity > 0 else 1.0
        return c.predicted_quantity / capacity

    def _avg_per_farmer(self, c: DpcContext) -> float:
        if c.predicted_arrivals > 0 and c.predicted_quantity > 0:
            return c.predicted_quantity / c.predicted_arrivals
        return SlotRecommender.DEFAULT_QUINTALS_PER_FARMER

    def _delay_hours(self, c: DpcContext) -> float:
        capacity = c.daily_capacity if c.daily_capacity > 0 else 1.0
        if c.predicted_quantity <= capacity:
            return 0.0
        rate_qty_per_h = (c.processing_rate or c.weighing_capacity or 10.0) * self._avg_per_farmer(c)
        needed_hours = c.predicted_quantity / max(1.0, rate_qty_per_h)
        return max(0.0, needed_hours - self.OPERATING_HOURS)

    def _mean_slot_util(self, c: DpcContext, slots: list[SlotContext]) -> float | None:
        if not slots:
            return None
        farmer_total = sum(s.max_farmers for s in slots)
        qty_total = sum(s.max_quantity for s in slots)
        utils = []
        for s in slots:
            share = c.predicted_quantity * s.max_quantity / qty_total if qty_total else 0.0
            utils.append(min(1.0, (share + s.booked_quantity) / s.max_quantity if s.max_quantity else 0.0))
        return sum(utils) / len(utils)

    def _slot_headroom(self, c: DpcContext, slot: SlotContext, slots: list[SlotContext]) -> float:
        qty_total = sum(s.max_quantity for s in slots)
        share = c.predicted_quantity * slot.max_quantity / qty_total if qty_total else 0.0
        farmer_total = sum(s.max_farmers for s in slots)
        farmer_share = c.predicted_arrivals * slot.max_farmers / farmer_total if farmer_total else 0.0
        qty_avail = min(
            max(0.0, slot.max_quantity - share - slot.booked_quantity),
            max(0.0, self.TARGET_MAX_LOAD * slot.max_quantity - share - slot.booked_quantity),
        )
        farmer_avail = min(
            max(0.0, slot.max_farmers - farmer_share - slot.booked_farmers),
            max(0.0, self.TARGET_MAX_LOAD * slot.max_farmers - farmer_share - slot.booked_farmers),
        )
        return min(qty_avail, farmer_avail * self._avg_per_farmer(c))

    def _resource_slack(self, c: DpcContext) -> float:
        labour_ratio = min(1.0, c.labour_available / max(1.0, c.predicted_arrivals / self.FARMERS_PER_LABOUR))
        transport_ratio = min(1.0, c.transport_available / max(1.0, c.predicted_quantity / self.TRANSPORT_QTY_PER_TRIP))
        storage = c.storage_available if c.storage_available is not None else c.storage_capacity
        storage_ratio = min(1.0, storage / max(1.0, c.predicted_quantity))
        return min(labour_ratio, transport_ratio, storage_ratio)

    def _util_health(self, load: float, slot_util: float | None) -> float:
        load_health = 1.0 - abs(load - self.TARGET_UTIL)
        slot_health = 1.0 - abs(slot_util - self.TARGET_UTIL) if slot_util is not None else load_health
        return 0.5 * load_health + 0.5 * slot_health

    def _stdev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)


class OptimizationService:
    def __init__(self, db: Session, slot_service: SlotRecommendationService | None = None) -> None:
        self.db = db
        self.slot_service = slot_service or SlotRecommendationService(db)
        self.recommendation_repo = RecommendationRepository(db)

    def optimize(self, target_date: date | None = None, persist: bool = True) -> dict:
        if target_date is None:
            target_date = date.today()
        contexts, slots_by_dpc = self.slot_service.build_contexts(target_date)
        result = OptimizationEngine().optimize(target_date, contexts, slots_by_dpc)

        selected = result["selected_recommendation"]
        if persist and selected and selected["action"] != "no_action":
            rec = self.recommendation_repo.create(
                dpc_id=selected["source_dpc_id"],
                date=target_date,
                recommendation_type=ACTION_TO_TYPE[selected["action"]],
                priority=RecommendationPriority(selected["priority"]),
                title=selected["title"],
                explanation=selected["explanation"] + "\n" + "; ".join(selected["reasons"]),
                expected_impact=selected["expected_impact"]
                or f"Best feasible action scoring {selected['overall_score']:.0f}/100.",
                source=selected["source"],
                target=selected["target"],
                farmer_count=selected["farmer_count"],
                quantity=selected["quantity"],
                feasibility_score=round(selected["overall_score"], 1),
            )
            selected["id"] = rec.id
            selected["reasons"] = [
                f"Persisted as recommendation #{rec.id} for the officer approve/reject workflow"
            ] + selected["reasons"]
            result["reasons"] = selected["reasons"]
            result["expected_improvement"] = selected["expected_improvement"]

        logger.info(
            "Optimization selected %s (score %.1f) for %s across %d DPCs",
            selected["action"], selected["overall_score"], target_date, len(contexts),
        )
        return result