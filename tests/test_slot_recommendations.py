from __future__ import annotations

from datetime import date, time

from backend.app.models.dpc import DPC
from backend.app.models.farmer import Farmer, HarvestReadiness
from backend.app.models.prediction import Prediction, PredictionType
from backend.app.models.recommendation import Recommendation, RecommendationStatus
from backend.app.models.resource_availability import ResourceAvailability
from backend.app.models.slot import Slot, SlotStatus
from backend.app.models.weather_condition import WeatherCondition, WeatherRisk
from backend.app.schemas.recommendation import RecommendationRead
from backend.app.services.slot_recommendation_service import (
    DpcContext,
    SlotContext,
    SlotRecommender,
    SlotRecommendationService,
)

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


def run(collector, contexts, slots=None):
    recs = collector.analyze(TODAY, contexts, slots if slots is not None else {c.dpc_id: [] for c in contexts})
    return recs


def by_action(recs, action):
    return [r for r in recs if r.get("action") == action]


class TestOverloadRedistribution:
    def test_overload_triggers_divert_to_neighbouring_dpc(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        target = dpc(
            dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, target])
        diverts = by_action(recs, "divert_to_dpc")
        assert len(diverts) == 1
        divert = diverts[0]
        assert divert["source"] == "Alpha DPC"
        assert divert["target"] == "Beta DPC"
        assert divert["priority"] == "critical"
        assert divert["farmer_count"] == 130
        assert divert["quantity"] == 130.0
        assert 0 <= divert["feasibility_score"] <= 100
        assert divert["scores"]  # explainable breakdown present

    def test_moved_quantity_respects_target_headroom(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        target = dpc(
            dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=850, predicted_quantity=850.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, target])
        diverts = by_action(recs, "divert_to_dpc")
        assert len(diverts) == 1
        divert = diverts[0]
        headroom = SlotRecommender.TARGET_MAX_LOAD * target.daily_capacity - target.predicted_quantity
        assert divert["quantity"] == round(headroom, 1)
        assert target.predicted_quantity + divert["quantity"] <= SlotRecommender.TARGET_MAX_LOAD * target.daily_capacity

    def test_no_redistribution_to_an_already_overloaded_dpc(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        busy = dpc(
            dpc_id=2, name="Busy DPC", code="DPC-B", predicted_arrivals=880, predicted_quantity=880.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, busy])
        assert by_action(recs, "divert_to_dpc") == []


class TestCapacityConstraints:
    def test_never_exceeds_target_cap(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        target = dpc(
            dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=850, predicted_quantity=850.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, target])
        diverts = by_action(recs, "divert_to_dpc")
        for divert in diverts:
            target_load_after = (target.predicted_quantity + divert["quantity"]) / target.daily_capacity
            assert target_load_after <= SlotRecommender.TARGET_MAX_LOAD

    def test_multi_source_allocation_stays_within_capacity(self):
        source_a = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        source_b = dpc(
            dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=960, predicted_quantity=960.0,
            **well_resourced(),
        )
        target = dpc(
            dpc_id=3, name="Gamma DPC", code="DPC-C", predicted_arrivals=200, predicted_quantity=200.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source_a, source_b, target])
        total_moved = sum(r["quantity"] for r in recs if r.get("action") == "divert_to_dpc" and r["target"] == "Gamma DPC")
        target_load_after = (target.predicted_quantity + total_moved) / target.daily_capacity
        assert target_load_after <= SlotRecommender.TARGET_MAX_LOAD + 1e-6

    def test_redistribute_to_same_dpc_slot_within_bounds(self):
        big_slots = [
            slot(slot_id=i, dpc_id=1, start_time=f"{9 + i}:00", max_farmers=400, max_quantity=400.0)
            for i in range(1, 4)
        ]
        source = dpc(
            dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source], {1: big_slots})
        redistributes = by_action(recs, "redistribute_slots")
        assert len(redistributes) >= 1
        for redist in redistributes:
            assert redist["quantity"] <= 400.0
            assert redist["farmer_count"] <= 400
            assert redist["feasibility_score"] > 0


class TestUnderutilized:
    def test_underutilized_slot_triggers_open_recommendation(self):
        quiet = dpc(
            dpc_id=1, name="Quiet DPC", code="DPC-Q", daily_capacity=2000.0, predicted_arrivals=100,
            predicted_quantity=100.0, **well_resourced(),
        )
        slots = {1: [slot(slot_id=1, dpc_id=1, max_farmers=50, max_quantity=125.0)]}
        recs = run(SlotRecommender(), [quiet], slots)
        opened = by_action(recs, "open_underutilized_slots")
        assert len(opened) == 1
        assert opened[0]["feasibility_score"] > 0

    def test_utilized_dpc_gets_no_open_recommendation(self):
        busy = dpc(dpc_id=1, name="Busy DPC", code="DPC-B", predicted_arrivals=700, predicted_quantity=700.0)
        slots = {1: [slot(slot_id=1, dpc_id=1, max_farmers=50, max_quantity=125.0)]}
        recs = run(SlotRecommender(), [busy], slots)
        assert by_action(recs, "open_underutilized_slots") == []


class TestFeasibilityFilters:
    def test_weather_critical_target_is_excluded(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        rainy = dpc(
            dpc_id=2, name="Rainy DPC", code="DPC-R", predicted_arrivals=300, predicted_quantity=300.0,
            weather_risk="critical", **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, rainy])
        assert by_action(recs, "divert_to_dpc") == []
        weather_recs = by_action(recs, "weather_reschedule")
        assert any(r["dpc_id"] == 2 for r in weather_recs)

    def test_resource_starved_target_is_excluded(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        starved = dpc(
            dpc_id=2, name="Starved DPC", code="DPC-S", predicted_arrivals=300, predicted_quantity=300.0,
            labour_available=0, transport_available=0, weighing_capacity=0, storage_available=0.0,
        )
        recs = run(SlotRecommender(), [source, starved])
        assert by_action(recs, "divert_to_dpc") == []

    def test_feasibility_score_ranks_according_to_headroom(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        far = dpc(
            dpc_id=2, name="Far DPC", code="DPC-F", district="Madurai", predicted_arrivals=300,
            predicted_quantity=300.0, lat=9.9, lon=78.1, **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, far])
        diverts = by_action(recs, "divert_to_dpc")
        assert len(diverts) == 1
        assert diverts[0]["scores"]["assignment"] < 1.0


class TestUrgentFarmerPrioritization:
    def test_ready_and_overdue_farmers_prioritized(self):
        overloaded = dpc(
            dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0,
            ready_farmers=12, overdue_farmers=2,
        )
        recs = run(SlotRecommender(), [overloaded])
        priorities = by_action(recs, "prioritize_ready_farmers")
        assert len(priorities) == 1
        assert priorities[0]["farmer_count"] == 14
        assert priorities[0]["priority"] == "high"


class TestSortingAndShape:
    def test_recommendations_sorted_by_priority(self):
        overloaded = dpc(
            dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0,
            ready_farmers=10, weather_risk="high",
        )
        target = dpc(
            dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [overloaded, target])
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ranks = [order[r["priority"]] for r in recs]
        assert ranks == sorted(ranks)

    def test_required_fields_present(self):
        source = dpc(dpc_id=1, name="Alpha DPC", code="DPC-A", predicted_arrivals=980, predicted_quantity=980.0)
        target = dpc(
            dpc_id=2, name="Beta DPC", code="DPC-B", predicted_arrivals=300, predicted_quantity=300.0,
            **well_resourced(),
        )
        recs = run(SlotRecommender(), [source, target])
        required = {
            "priority", "title", "source", "target", "farmer_count", "quantity",
            "explanation", "expected_impact", "feasibility_score",
        }
        for r in recs:
            assert required.issubset(r)


class TestServiceIntegration:
    def _seed(self, session):
        today = TODAY
        dpc_a = DPC(dpc_code="DPC-A1", name="Thanjavur Central DPC", district="Thanjavur",
                    daily_capacity=1000, processing_rate=80.0, storage_capacity=300.0)
        dpc_b = DPC(dpc_code="DPC-B1", name="Kumbakonam DPC", district="Thanjavur",
                    daily_capacity=1000, processing_rate=80.0, storage_capacity=600.0)
        session.add_all([dpc_a, dpc_b])
        session.commit()

        session.add_all([
            Prediction(dpc_id=dpc_a.id, prediction_date=today, target_date=today,
                       prediction_type=PredictionType.arrival_count, predicted_value=980.0, confidence=0.9, model_version="v0.1"),
            Prediction(dpc_id=dpc_a.id, prediction_date=today, target_date=today,
                       prediction_type=PredictionType.quantity, predicted_value=980.0, confidence=0.9, model_version="v0.1"),
            Prediction(dpc_id=dpc_b.id, prediction_date=today, target_date=today,
                       prediction_type=PredictionType.arrival_count, predicted_value=300.0, confidence=0.9, model_version="v0.1"),
            Prediction(dpc_id=dpc_b.id, prediction_date=today, target_date=today,
                       prediction_type=PredictionType.quantity, predicted_value=300.0, confidence=0.9, model_version="v0.1"),
            ResourceAvailability(dpc_id=dpc_b.id, date=today, labour_available=100, transport_available=30,
                                 weighing_capacity=40, storage_available=600.0),
            WeatherCondition(date=today, location="Thanjavur", weather_risk=WeatherRisk.none),
            WeatherCondition(date=today, location="Kumbakonam", weather_risk=WeatherRisk.none),
            Slot(dpc_id=dpc_a.id, date=today, start_time=time(9, 0), end_time=time(12, 0),
                 max_farmers=50, max_quantity=125.0, booked_farmers=5, booked_quantity=15.0,
                 status=SlotStatus.partially_booked),
            Farmer(farmer_code="FRM-Z1", name="F1", village="Thanjavur", district="Thanjavur",
                   cultivated_area=2.0, harvest_readiness=HarvestReadiness.ready),
            Farmer(farmer_code="FRM-Z2", name="F2", village="Thanjavur", district="Thanjavur",
                   cultivated_area=2.0, harvest_readiness=HarvestReadiness.overdue),
        ])
        session.commit()
        return dpc_a, dpc_b

    def test_analyze_persists_recommendations(self, db_session):
        dpc_a, dpc_b = self._seed(db_session)
        service = SlotRecommendationService(db_session)
        results = service.analyze(TODAY, persist=True)
        assert len(results) > 0
        assert any(r.get("action") == "divert_to_dpc" for r in results)

        persisted = service.recommendation_repo.get_all(limit=100)
        assert len(persisted) == len(results)
        for rec in persisted:
            read = RecommendationRead.model_validate(rec)
            assert read.source is not None or read.target is not None or read.feasibility_score is not None

    def test_persisted_rows_feed_the_officer_workflow(self, db_session):
        self._seed(db_session)
        service = SlotRecommendationService(db_session)
        results = service.analyze(TODAY, persist=True)
        first = next(r for r in results if r.get("action") == "divert_to_dpc")
        rec_id = first["id"]
        rec = db_session.get(Recommendation, rec_id)
        assert rec is not None
        assert rec.status == RecommendationStatus.pending
        assert rec.source == first["source"]
        assert rec.feasibility_score == first["feasibility_score"]