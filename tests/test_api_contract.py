"""Tests for the full REST API contract under /api/v1.

Uses FastAPI TestClient + sqlite (db_session fixture from conftest).
ML endpoints override the service to use a temporary artifacts directory.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.api import deps
from backend.app.main import create_app
from backend.app.ml import MLService
from backend.app.models.dpc import DPC, OperatingStatus
from backend.app.models.farmer import Farmer, HarvestReadiness
from backend.app.models.procurement import ProcurementRecord, ProcurementStatus
from backend.app.models.slot import Slot, SlotStatus
from backend.app.repositories.procurement_repo import ProcurementRepository
from backend.app.repositories.recommendation_repo import RecommendationRepository
from backend.app.repositories.slot_repo import SlotRepository
from backend.app.repositories.farmer_repo import FarmerRepository
from backend.app.repositories.dpc_repo import DPCRepository
from backend.app.schemas.farmer import FarmerCreate
from backend.app.schemas.dpc import DPCCreate
from backend.app.schemas.procurement import ProcurementCreate
from backend.app.schemas.slot import SlotCreate
from backend.app.services.scenario_service import ScenarioService
from mlfactories import seed_ml_dataset

from datetime import time as _time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DAY = date(2026, 9, 10)


def _seed_basics(db):
    """Insert minimal farmer + DPC + procurement + scenario rows for endpoint testing."""
    ScenarioService(db).seed_scenarios()

    f = Farmer(
        farmer_code="API-F01", name="Test Farmer", village="Papanasam",
        district="Thanjavur", cultivated_area=2.0, paddy_variety="CO-51",
        harvest_readiness=HarvestReadiness.ready,
    )
    dpc = DPC(
        dpc_code="API-D01", name="Thanjavur DPC", district="Thanjavur",
        daily_capacity=500, storage_capacity=200.0,
        operating_status=OperatingStatus.active, open_date=DAY - timedelta(days=30),
    )
    db.add_all([f, dpc])
    db.flush()
    for i in range(3):
        db.add(ProcurementRecord(
            farmer_id=f.id, dpc_id=dpc.id, date=DAY - timedelta(days=i),
            bags=100, quantity_quintal=25.0, moisture_pct=14.0,
            status=ProcurementStatus.accepted,
        ))
    for h in range(4):
        t0 = _time(9 + h, 0)
        t1 = _time(9 + h + 1, 0)
        db.add(Slot(
            dpc_id=dpc.id, date=DAY, start_time=t0, end_time=t1,
            max_farmers=50, max_quantity=200.0,
            status=SlotStatus.available if h < 3 else SlotStatus.full,
        ))
    db.commit()
    return f, dpc


def _make_client(db_session, tmp_path):
    """Build a TestClient with DI overrides for DB + ML."""
    app = create_app()

    def override_db():
        return db_session

    def override_ml():
        return MLService(db_session, artifacts_dir=str(tmp_path / "artifacts"), validation_days=7)

    app.dependency_overrides[deps.get_db] = override_db
    app.dependency_overrides[deps.get_ml_service] = override_ml
    return TestClient(app), override_ml()


# ===========================================================================
# Tests
# ===========================================================================


class TestHealth:
    def test_health_ok(self, db_session, tmp_path):
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] in ("ok", "healthy", "degraded")
        assert "version" in body


class TestDashboard:
    def test_dashboard_summary(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/dashboard/summary")
        assert res.status_code == 200
        body = res.json()
        assert body["total_farmers"] >= 1
        assert body["total_dpcs"] >= 1
        assert "ml_trained" in body
        assert isinstance(body["risk_by_severity"], dict)


class TestFarmers:
    def test_list_farmers(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/farmers", params={"skip": 0, "limit": 10})
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert body["total"] >= 1

    def test_get_farmer(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        list_res = client.get("/api/v1/farmers", params={"limit": 1})
        fid = list_res.json()["items"][0]["id"]
        res = client.get(f"/api/v1/farmers/{fid}")
        assert res.status_code == 200
        assert res.json()["farmer_code"] == "API-F01"

    def test_farmer_404(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/farmers/99999")
        assert res.status_code == 404

    def test_create_farmer(self, db_session, tmp_path):
        client, _ = _make_client(db_session, tmp_path)
        res = client.post("/api/v1/farmers", json={
            "farmer_code": "API-FNEW", "name": "New", "village": "V", "district": "Thanjavur",
            "cultivated_area": 1.0, "paddy_variety": "CO-43",
        })
        assert res.status_code == 201
        assert res.json()["farmer_code"] == "API-FNEW"


class TestDPCs:
    def test_list_dpcs(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/dpcs", params={"skip": 0, "limit": 10})
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_dpc_capacity(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        dpcs = client.get("/api/v1/dpcs", params={"limit": 1}).json()["items"]
        dpc_id = dpcs[0]["id"]
        res = client.get(f"/api/v1/dpcs/{dpc_id}/capacity")
        assert res.status_code == 200
        assert "current_utilization_pct" in res.json()


class TestProcurement:
    def test_list_procurement(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/procurement", params={"skip": 0, "limit": 10})
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_procurement_filters(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        dpcs = client.get("/api/v1/dpcs", params={"limit": 1}).json()["items"]
        dpc_id = dpcs[0]["id"]
        res = client.get("/api/v1/procurement", params={
            "dpc_id": dpc_id, "start_date": "2026-09-01", "end_date": "2026-09-10",
        })
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_procurement_summary(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/procurement/summary", params={"start_date": "2026-09-01", "end_date": "2026-09-10"})
        assert res.status_code == 200
        assert "total_bags" in res.json()


class TestSlots:
    def test_list_slots(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/slots", params={"skip": 0, "limit": 20})
        assert res.status_code == 200
        assert res.json()["total"] >= 4

    def test_slot_filters(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/slots", params={"date": "2026-09-10"})
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_available_slots(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/slots/available", params={"date": "2026-09-10"})
        assert res.status_code == 200
        items = res.json()
        assert isinstance(items, list)
        assert len(items) >= 1

    def test_create_slot(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        dpcs = client.get("/api/v1/dpcs", params={"limit": 1}).json()["items"]
        dpc_id = dpcs[0]["id"]
        res = client.post("/api/v1/slots", json={
            "dpc_id": dpc_id, "date": "2026-09-15",
            "start_time": "10:00:00", "end_time": "11:00:00",
            "max_farmers": 40, "max_quantity": 150.0,
        })
        assert res.status_code == 201
        assert res.json()["status"] == "available"


class TestPredictions:
    def test_predictions_status(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/predictions/status")
        assert res.status_code == 200
        body = res.json()
        assert body["trained"] is False
        assert body["active_engine"] == "ml"

    def test_forecast_arrivals_untrained(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/predictions/arrivals", params={"target_date": "2026-09-10"})
        assert res.status_code == 200
        items = res.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        assert items[0]["data_source"] == "statistical"
        assert items[0]["prediction_type"] == "arrival_count"

    def test_forecast_quantity_untrained(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/predictions/quantity", params={"target_date": "2026-09-10"})
        assert res.status_code == 200
        items = res.json()
        assert items[0]["data_source"] == "statistical"
        assert items[0]["prediction_type"] == "quantity"

    def test_forecast_congestion_untrained(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/predictions/congestion", params={"target_date": "2026-09-10"})
        assert res.status_code == 200
        items = res.json()
        assert items[0]["data_source"] == "statistical"
        assert items[0]["prediction_type"] == "overload_probability"

    def test_single_dpc_forecast(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        dpcs = client.get("/api/v1/dpcs", params={"limit": 1}).json()["items"]
        dpc_id = dpcs[0]["id"]
        res = client.get("/api/v1/predictions/arrivals", params={
            "target_date": "2026-09-10", "dpc_id": dpc_id,
        })
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["dpc_id"] == dpc_id

    def test_get_predictions_dpc_id(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        dpcs = client.get("/api/v1/dpcs", params={"limit": 1}).json()["items"]
        dpc_id = dpcs[0]["id"]
        res = client.get(f"/api/v1/predictions/{dpc_id}", params={"limit": 10})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_train_then_forecast(self, db_session, tmp_path):
        seed = seed_ml_dataset(db_session, n_days=24)
        client, _ = _make_client(db_session, tmp_path)
        train_res = client.post("/api/v1/predictions/train", params={"validation_days": 7})
        assert train_res.status_code == 200
        body = train_res.json()
        assert body["status"] in ("trained", "partial")

        dpc_id = seed["dpcs"][0].id
        res = client.get("/api/v1/predictions/arrivals", params={
            "target_date": "2026-01-20", "dpc_id": dpc_id,
        })
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["data_source"] in ("ml", "statistical")


class TestRisks:
    def test_risks_list(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/risks", params={"target_date": "2026-09-10"})
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_risks_filters(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/risks", params={"severity": "high", "target_date": "2026-09-10"})
        assert res.status_code == 200
        for item in res.json()["items"]:
            assert item["severity"] == "high"

    def test_risks_summary(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/risks/summary", params={"target_date": "2026-09-10"})
        assert res.status_code == 200
        body = res.json()
        assert "total_risks" in body
        assert "by_severity" in body
        assert "by_type" in body

    def test_risks_analyze(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.post("/api/v1/risks/analyze", json={"target_date": "2026-09-10"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestRecommendations:
    def test_list_recommendations(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/recommendations", params={"skip": 0, "limit": 20})
        assert res.status_code == 200
        assert "items" in res.json()

    def test_analyze_alias(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.post("/api/v1/recommendations/analyze", json={"target_date": "2026-09-10"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_pending_recommendations(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/recommendations/pending")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestSimulation:
    def test_simulation_scenarios(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/simulation/scenarios")
        assert res.status_code == 200
        scenarios = res.json()
        assert isinstance(scenarios, list)

    def test_simulation_run(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.post("/api/v1/simulation/run", json={"scenario_name": "NORMAL_DAY"})
        assert res.status_code == 200
        body = res.json()
        assert "risks" in body
        assert "recommendations" in body
        assert body["scenario_name"] == "NORMAL_DAY"

    def test_scenarios_still_work(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/scenarios")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestML:
    def test_ml_status(self, db_session, tmp_path):
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/ml/status")
        assert res.status_code == 200
        assert res.json()["trained"] is False

    def test_ml_train(self, db_session, tmp_path):
        seed_ml_dataset(db_session, n_days=24)
        client, _ = _make_client(db_session, tmp_path)
        res = client.post("/api/v1/ml/train", json={"validation_days": 7})
        assert res.status_code == 200
        assert res.json()["status"] in ("trained", "partial")


class TestOpenAPI:
    def test_openapi_schema_has_all_tags(self, db_session, tmp_path):
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/openapi.json")
        assert res.status_code == 200
        schema = res.json()
        tag_names = {t["name"] for t in schema.get("tags", [])}
        expected = {"health", "dashboard", "farmers", "dpcs", "procurement",
                    "slots", "predictions", "recommendations", "scenarios",
                    "simulation", "risks", "ml"}
        assert expected.issubset(tag_names), f"Missing tags: {expected - tag_names}"

    def test_new_paths_present(self, db_session, tmp_path):
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/openapi.json")
        assert res.status_code == 200
        paths = set(res.json()["paths"].keys())
        expected_paths = [
            "/api/v1/dashboard/summary",
            "/api/v1/slots",
            "/api/v1/slots/available",
            "/api/v1/simulation/scenarios",
            "/api/v1/simulation/run",
            "/api/v1/predictions/status",
            "/api/v1/predictions/train",
            "/api/v1/predictions/arrivals",
            "/api/v1/predictions/quantity",
            "/api/v1/predictions/congestion",
            "/api/v1/risks/summary",
            "/api/v1/risks/analyze",
            "/api/v1/recommendations/analyze",
        ]
        for p in expected_paths:
            assert p in paths, f"Path {p} not in OpenAPI schema"


class TestErrorFormat:
    def test_not_found_404_shape(self, db_session, tmp_path):
        _seed_basics(db_session)
        client, _ = _make_client(db_session, tmp_path)
        res = client.get("/api/v1/farmers/99999")
        assert res.status_code == 404
        body = res.json()
        assert "error" in body
        assert body["error"]["code"] == "NOT_FOUND"
        assert "99999" in body["error"]["message"]
