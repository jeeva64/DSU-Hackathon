from __future__ import annotations

from datetime import date, datetime, time

import pytest

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
from backend.app.models.recommendation import Recommendation, RecommendationType, RecommendationPriority, RecommendationStatus
from backend.app.models.recommendation_action import RecommendationAction
from backend.app.models.scenario import SimulationScenario, SimulationStatus


class TestFarmerModel:
    def test_create_farmer(self, db_session):
        farmer = Farmer(
            farmer_code="FRM-001",
            name="Test Farmer",
            village="Thanjavur",
            district="Thanjavur",
            cultivated_area=5.0,
            paddy_variety="CO-51",
            expected_quantity=75.0,
            harvest_readiness=HarvestReadiness.ready,
        )
        db_session.add(farmer)
        db_session.commit()
        assert farmer.id is not None
        assert farmer.farmer_code == "FRM-001"
        assert farmer.harvest_readiness == HarvestReadiness.ready

    def test_farmer_code_unique(self, db_session):
        f1 = Farmer(farmer_code="FRM-100", name="F1", village="V", district="D", cultivated_area=2.0)
        f2 = Farmer(farmer_code="FRM-100", name="F2", village="V", district="D", cultivated_area=3.0)
        db_session.add(f1)
        db_session.commit()
        db_session.add(f2)
        with pytest.raises(Exception):
            db_session.commit()


class TestDPCModel:
    def test_create_dpc(self, db_session):
        dpc = DPC(
            dpc_code="DPC-001",
            name="Test DPC",
            district="Thanjavur",
            daily_capacity=1000,
            processing_rate=60.0,
            storage_capacity=300.0,
            operating_status=OperatingStatus.active,
        )
        db_session.add(dpc)
        db_session.commit()
        assert dpc.id is not None
        assert dpc.dpc_code == "DPC-001"
        assert dpc.operating_status == OperatingStatus.active

    def test_dpc_code_unique(self, db_session):
        d1 = DPC(dpc_code="DPC-200", name="D1", district="D", daily_capacity=1000, storage_capacity=250)
        d2 = DPC(dpc_code="DPC-200", name="D2", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(d1)
        db_session.commit()
        db_session.add(d2)
        with pytest.raises(Exception):
            db_session.commit()


class TestProcurementRecordModel:
    def _create_farmer_and_dpc(self, db_session):
        farmer = Farmer(farmer_code="FRM-PR1", name="PF1", village="V", district="D", cultivated_area=3.0)
        dpc = DPC(dpc_code="DPC-PR1", name="PD1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add_all([farmer, dpc])
        db_session.commit()
        return farmer, dpc

    def test_create_procurement(self, db_session):
        farmer, dpc = self._create_farmer_and_dpc(db_session)
        proc = ProcurementRecord(
            farmer_id=farmer.id, dpc_id=dpc.id, date=date.today(),
            bags=20, quantity_quintal=60.0, moisture_pct=14.0, grade="A",
            status=ProcurementStatus.accepted,
        )
        db_session.add(proc)
        db_session.commit()
        assert proc.id is not None
        assert proc.status == ProcurementStatus.accepted


class TestDPCCapacityModel:
    def test_create_capacity(self, db_session):
        dpc = DPC(dpc_code="DPC-CA1", name="CA1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        cap = DPCCapacity(
            dpc_id=dpc.id, date=date.today(),
            planned_capacity=1000, used_capacity=600, remaining_capacity=400, utilization_pct=60.0,
        )
        db_session.add(cap)
        db_session.commit()
        assert cap.id is not None
        assert cap.utilization_pct == 60.0

    def test_unique_dpc_date(self, db_session):
        dpc = DPC(dpc_code="DPC-CA2", name="CA2", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        c1 = DPCCapacity(dpc_id=dpc.id, date=date.today(), planned_capacity=1000, used_capacity=500, remaining_capacity=500, utilization_pct=50.0)
        c2 = DPCCapacity(dpc_id=dpc.id, date=date.today(), planned_capacity=1000, used_capacity=600, remaining_capacity=400, utilization_pct=60.0)
        db_session.add(c1)
        db_session.commit()
        db_session.add(c2)
        with pytest.raises(Exception):
            db_session.commit()


class TestSlotModel:
    def test_create_slot(self, db_session):
        dpc = DPC(dpc_code="DPC-SL1", name="SL1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        slot = Slot(
            dpc_id=dpc.id, date=date.today(),
            start_time=time(8, 0), end_time=time(11, 0),
            max_farmers=50, max_quantity=200.0,
            booked_farmers=20, booked_quantity=60.0,
            status=SlotStatus.partially_booked,
        )
        db_session.add(slot)
        db_session.commit()
        assert slot.id is not None
        assert slot.status == SlotStatus.partially_booked


class TestArrivalRecordModel:
    def test_create_arrival(self, db_session):
        farmer = Farmer(farmer_code="FRM-AR1", name="AR1", village="V", district="D", cultivated_area=3.0)
        dpc = DPC(dpc_code="DPC-AR1", name="AR1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add_all([farmer, dpc])
        db_session.commit()
        arrival = ArrivalRecord(
            farmer_id=farmer.id, dpc_id=dpc.id, date=date.today(),
            arrival_time=datetime.now(), bags_brought=15, quantity_brought=45.0,
            wait_time_minutes=30, status="accepted",
        )
        db_session.add(arrival)
        db_session.commit()
        assert arrival.id is not None


class TestResourceAvailabilityModel:
    def test_create_resource(self, db_session):
        dpc = DPC(dpc_code="DPC-RA1", name="RA1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        res = ResourceAvailability(
            dpc_id=dpc.id, date=date.today(),
            labour_available=20, transport_available=5,
            weighing_capacity=40, storage_available=200.0,
        )
        db_session.add(res)
        db_session.commit()
        assert res.id is not None


class TestWeatherConditionModel:
    def test_create_weather(self, db_session):
        weather = WeatherCondition(
            date=date.today(), location="Thanjavur",
            rainfall_probability=60.0, rainfall_mm=15.0,
            humidity=80.0, temperature_max=32.0,
            weather_risk=WeatherRisk.high,
        )
        db_session.add(weather)
        db_session.commit()
        assert weather.id is not None
        assert weather.weather_risk == WeatherRisk.high


class TestPredictionModel:
    def test_create_prediction(self, db_session):
        dpc = DPC(dpc_code="DPC-PR2", name="PR2", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        pred = Prediction(
            dpc_id=dpc.id, prediction_date=date.today(), target_date=date.today(),
            prediction_type=PredictionType.arrival_count,
            predicted_value=85.0, confidence=0.82, model_version="v0.1",
        )
        db_session.add(pred)
        db_session.commit()
        assert pred.id is not None
        assert pred.prediction_type == PredictionType.arrival_count


class TestRiskAssessmentModel:
    def test_create_risk(self, db_session):
        dpc = DPC(dpc_code="DPC-RA2", name="RA2", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        risk = RiskAssessment(
            dpc_id=dpc.id, date=date.today(),
            risk_type=RiskType.overload, severity=RiskSeverity.high,
            score=85.0, explanation="DPC at 85% capacity",
            mitigation="Divert farmers to adjacent DPC",
        )
        db_session.add(risk)
        db_session.commit()
        assert risk.id is not None
        assert risk.severity == RiskSeverity.high


class TestRecommendationModel:
    def test_create_recommendation(self, db_session):
        dpc = DPC(dpc_code="DPC-RC1", name="RC1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        rec = Recommendation(
            dpc_id=dpc.id, date=date.today(),
            recommendation_type=RecommendationType.slot,
            priority=RecommendationPriority.high,
            title="Reduce load",
            explanation="Capacity at 85%",
            expected_impact="Reduce wait by 30%",
            status=RecommendationStatus.pending,
        )
        db_session.add(rec)
        db_session.commit()
        assert rec.id is not None
        assert rec.status == RecommendationStatus.pending


class TestRecommendationActionModel:
    def test_create_action(self, db_session):
        dpc = DPC(dpc_code="DPC-AC1", name="AC1", district="D", daily_capacity=1000, storage_capacity=250)
        db_session.add(dpc)
        db_session.commit()
        rec = Recommendation(
            dpc_id=dpc.id, date=date.today(),
            recommendation_type=RecommendationType.resource,
            priority=RecommendationPriority.critical,
            title="Add staff", explanation="Queue too long", expected_impact="Faster processing",
        )
        db_session.add(rec)
        db_session.commit()
        action = RecommendationAction(
            recommendation_id=rec.id, action="add_staff",
            rationale="Need more workers for morning shift",
        )
        db_session.add(action)
        db_session.commit()
        assert action.id is not None


class TestSimulationScenarioModel:
    def test_create_scenario(self, db_session):
        scenario = SimulationScenario(
            name="TEST_SCENARIO",
            description="Test scenario for unit tests",
            parameters={"rain_mm": 15, "transport_availability_pct": 50},
            status=SimulationStatus.draft,
        )
        db_session.add(scenario)
        db_session.commit()
        assert scenario.id is not None
        assert scenario.parameters["rain_mm"] == 15

    def test_scenario_name_unique(self, db_session):
        s1 = SimulationScenario(name="DUP", description="D1", parameters={})
        s2 = SimulationScenario(name="DUP", description="D2", parameters={})
        db_session.add(s1)
        db_session.commit()
        db_session.add(s2)
        with pytest.raises(Exception):
            db_session.commit()
