from __future__ import annotations

import types
from datetime import date

from backend.app.models.recommendation import Recommendation
from backend.app.services.optimization_service import OptimizationEngine, OptimizationService
from backend.app.services.slot_recommendation_service import DpcContext, SlotContext

TODAY = date.today()


def dpc(**over):
    base = dict(
        dpc_id=1,
        code="DPC-1",
        name="Alpha DPC",
        district="Thanjavur",
        daily_capacity=1000.0,
        processing_rate=80.0,
        storage_capacity=250.0,
        operating_status="active",
        lat=10.8,
        lon=79.1,
    )
    base.update(over)
    return DpcContext(**base)


def slot(**over):
    base = dict(
        slot_id=1,
        dpc_id=1,
        start_time="09:00",
        end_time="12:00",
        max_farmers=50,
        max_quantity=125.0,
        booked_farmers=0,
        booked_quantity=0.0,
    )
    base.update(over)
    return SlotContext(**base)


def well_resourced():
    return dict(labour_available=100, transport_available=30, weighing_capacity=40, storage_available=600.0)


def optimize(engine, contexts, slots=None, target_date=TODAY):
    return engine.optimize(
        target_date,
        contexts,
        slots if slots is not None else {c.dpc_id: [] for c in contexts},
    )


def by_action(result, action):
    return [c for c in result["candidate_actions"] if c["action"] == action]


class TestOverloadDiversion:
    def test_overloaded_dpc_diverts_to_best_feasible_target(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        beta = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
                   **well_resourced())
        gamma = dpc(dpc_id=3, name="Gamma DPC", code="DPC-C", predicted_arrivals=100, predicted_quantity=100.0,
                    **well_resourced())
        result = optimize(OptimizationEngine(), [source, beta, gamma])

        assert result["target_date"] == TODAY
        assert len(result["current_state"]) == 3
        for cand in by_action(result, "divert_to_dpc"):
            assert cand["feasible"] and cand["infeasible_reason"] is None
        selected = result["selected_recommendation"]
        assert selected["action"] == "divert_to_dpc"
        assert selected["target"] == "Gamma DPC"
        assert selected["farmer_count"] > 0
        assert selected["overall_score"] > 0
        assert selected["scores"]
        assert selected["expected_improvement"]

    def test_every_movement_respects_ceiling(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        beta = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=700, predicted_quantity=700.0,
                   **well_resourced())
        gamma = dpc(dpc_id=3, name="Gamma DPC", code="DPC-C", predicted_arrivals=200, predicted_quantity=200.0,
                    **well_resourced())
        result = optimize(OptimizationEngine(), [source, beta, gamma])
        by_id = {c["dpc_id"]: c for c in result["current_state"]}
        for cand in by_action(result, "divert_to_dpc"):
            if not cand["feasible"]:
                continue
            target = by_id[cand["target_dpc_id"]]
            load_after = (target["predicted_quantity"] + cand["quantity"]) / 1000.0
            assert load_after <= OptimizationEngine.TARGET_MAX_LOAD


class TestHardConstraints:
    def test_insufficient_transport_target_is_infeasible(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        no_trucks = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
                        labour_available=100, transport_available=0, weighing_capacity=40, storage_available=600.0)
        result = optimize(OptimizationEngine(), [source, no_trucks])
        diverts = by_action(result, "divert_to_dpc")
        assert len(diverts) == 1
        assert diverts[0]["feasible"] is False
        assert "transport" in diverts[0]["infeasible_reason"]
        assert result["selected_recommendation"]["target"] != "Beta DPC"

    def test_insufficient_labour_target_is_infeasible(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        no_staff = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
                       labour_available=0, transport_available=30, weighing_capacity=40, storage_available=600.0)
        result = optimize(OptimizationEngine(), [source, no_staff])
        diverts = by_action(result, "divert_to_dpc")
        assert len(diverts) == 1
        assert diverts[0]["feasible"] is False
        assert "labour" in diverts[0]["infeasible_reason"]
        assert result["selected_recommendation"]["target"] != "Beta DPC"

    def test_storage_shortage_clamps_quantity(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        tight = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=800, predicted_quantity=800.0,
                    labour_available=100, transport_available=30, weighing_capacity=40, storage_available=880.0)
        roomy = dpc(dpc_id=3, name="Gamma DPC", code="DPC-C", predicted_arrivals=100, predicted_quantity=100.0,
                    **well_resourced())
        result = optimize(OptimizationEngine(), [source, tight, roomy])
        diverts = {c["target"]: c for c in by_action(result, "divert_to_dpc")}

        capped = diverts["Beta DPC"]
        assert capped["feasible"] is True
        assert capped["quantity"] == 80.0
        assert (800.0 + capped["quantity"]) / 1000.0 <= OptimizationEngine.TARGET_MAX_LOAD

        full = diverts["Gamma DPC"]
        assert full["feasible"] is True
        assert full["quantity"] == 130.0
        assert result["selected_recommendation"]["target"] == "Gamma DPC"

    def test_zero_storage_slack_is_infeasible(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        packed = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=750, predicted_quantity=750.0,
                     labour_available=100, transport_available=30, weighing_capacity=40, storage_available=750.0)
        result = optimize(OptimizationEngine(), [source, packed])
        diverts = by_action(result, "divert_to_dpc")
        assert len(diverts) == 1
        assert diverts[0]["feasible"] is False
        assert "storage" in diverts[0]["infeasible_reason"].lower()


class TestMultipleAlternativeSlots:
    def test_redistribution_targets_best_slot_within_bounds(self):
        slots = [
            slot(slot_id=1, dpc_id=1, start_time="09:00", max_farmers=600, max_quantity=600.0),
            slot(slot_id=2, dpc_id=1, start_time="10:00", max_farmers=500, max_quantity=500.0),
            slot(slot_id=3, dpc_id=1, start_time="11:00", max_farmers=300, max_quantity=300.0),
        ]
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=950, predicted_quantity=950.0,
                     **well_resourced())
        result = optimize(OptimizationEngine(), [source], {1: slots})
        redistributes = by_action(result, "redistribute_slots")
        assert len(redistributes) == 3
        for cand in redistributes:
            assert cand["feasible"] is True
            slot_max = next(s.max_quantity for s in slots if s.slot_id == cand["target_slot_id"])
            assert cand["quantity"] <= slot_max

        selected = result["selected_recommendation"]
        assert selected["action"] == "redistribute_slots"
        assert 0 < selected["quantity"] <= 100.0
        assert selected["farmer_count"] > 0
        assert selected["overall_score"] > 0


class TestCombinedCrisis:
    def test_combined_crisis_selects_feasible_action(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0,
                     weather_risk="high", labour_available=2, transport_available=1, weighing_capacity=40,
                     storage_available=200.0)
        rainy = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
                    weather_risk="medium", labour_available=50, transport_available=3, weighing_capacity=40,
                    storage_available=200.0)
        calm = dpc(dpc_id=3, name="Gamma DPC", code="DPC-C", predicted_arrivals=100, predicted_quantity=100.0,
                   weather_risk="none", **well_resourced())
        slots = {3: [slot(slot_id=1, dpc_id=3, max_farmers=80, max_quantity=200.0)]}
        result = optimize(OptimizationEngine(), [source, rainy, calm], slots)

        rainy_diverts = [c for c in by_action(result, "divert_to_dpc") if c["target"] == "Beta DPC"]
        assert len(rainy_diverts) == 1
        assert rainy_diverts[0]["feasible"] is False
        assert "storage" in rainy_diverts[0]["infeasible_reason"].lower()

        selected = result["selected_recommendation"]
        assert selected["feasible"] is True
        assert selected["action"] in ("divert_to_dpc", "weather_reschedule", "boost_resources")
        assert selected["overall_score"] > 0
        if selected["action"] == "divert_to_dpc":
            target = next(s for s in result["current_state"] if s["dpc_id"] == selected["target_dpc_id"])
            load_after = (target["predicted_quantity"] + selected["quantity"]) / 1000.0
            assert load_after <= OptimizationEngine.TARGET_MAX_LOAD


class TestNoAction:
    def test_healthy_day_selects_no_action(self):
        a = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=400, predicted_quantity=400.0,
                **well_resourced())
        b = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=350, predicted_quantity=350.0,
                **well_resourced())
        result = optimize(OptimizationEngine(), [a, b])
        assert len(result["candidate_actions"]) == 1
        selected = result["selected_recommendation"]
        assert selected["action"] == "no_action"
        assert selected["feasible"] is True
        assert selected["overall_score"] == 0.0
        assert selected["reasons"]
        assert result["reasons"] == selected["reasons"]

    def test_result_shape_is_complete(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        beta = dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
                   **well_resourced())
        result = optimize(OptimizationEngine(), [source, beta])
        assert {"target_date", "current_state", "baseline", "candidate_actions", "selected_recommendation",
                "reasons", "expected_improvement"} <= set(result)
        state0 = result["current_state"][0]
        for field in ("load_pct", "congestion_pct", "weather_risk", "labour_available", "transport_available",
                      "storage_available", "free_slots", "urgent_farmers"):
            assert field in state0
        for cand in result["candidate_actions"]:
            for field in ("action", "title", "source", "target", "priority", "farmer_count", "quantity",
                          "feasible", "scores", "overall_score", "reasons", "expected_improvement"):
                assert field in cand


def _persist_fixture():
    contexts = [
        dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0),
        dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
            **well_resourced()),
        dpc(dpc_id=3, name="Gamma DPC", code="DPC-C", predicted_arrivals=100, predicted_quantity=100.0,
            **well_resourced()),
    ]
    return contexts, {c.dpc_id: [] for c in contexts}


class TestServiceIntegration:
    def _stub(self, contexts, slots_dict):
        return types.SimpleNamespace(build_contexts=lambda d: (contexts, slots_dict))

    def test_optimize_persists_selected_recommendation(self, db_session):
        contexts, slots_dict = _persist_fixture()
        service = OptimizationService(db_session, slot_service=self._stub(contexts, slots_dict))
        result = service.optimize(TODAY, persist=True)

        selected = result["selected_recommendation"]
        assert selected["action"] == "divert_to_dpc"
        assert selected["id"] is not None
        assert "Persisted" in selected["reasons"][0]

        rec = db_session.get(Recommendation, selected["id"])
        assert rec is not None
        assert rec.date == TODAY
        assert rec.source == "Alpha DPC"
        assert rec.feasibility_score == selected["overall_score"]
        assert rec.farmer_count == selected["farmer_count"]

    def test_optimize_persists_nothing_when_no_action(self, db_session):
        contexts = [
            dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=400, predicted_quantity=400.0,
                **well_resourced()),
            dpc(dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=350, predicted_quantity=350.0,
                **well_resourced()),
        ]
        slots_dict = {c.dpc_id: [] for c in contexts}
        service = OptimizationService(db_session, slot_service=self._stub(contexts, slots_dict))
        result = service.optimize(TODAY, persist=True)
        assert result["selected_recommendation"]["action"] == "no_action"
        assert service.recommendation_repo.count() == 0