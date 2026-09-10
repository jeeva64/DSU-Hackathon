from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api import deps
from backend.app.main import create_app
from backend.app.ml import MLService
from mlfactories import seed_ml_dataset


class TestMLAPI:
    def _app(self, db_session, tmp_path):
        artifacts_dir = tmp_path / "artifacts"

        def override_ml_service():
            return MLService(db_session, artifacts_dir=artifacts_dir, validation_days=7)

        app = create_app()
        app.dependency_overrides[deps.get_ml_service] = override_ml_service
        return TestClient(app), override_ml_service()

    def test_status_untrained(self, db_session, tmp_path):
        client, _ = self._app(db_session, tmp_path)
        res = client.get("/api/v1/ml/status")
        assert res.status_code == 200
        body = res.json()
        assert body["trained"] is False
        assert "not trained" in body["message"]

    def test_predict_untrained_is_graceful(self, db_session, tmp_path):
        seed_ml_dataset(db_session, n_days=24)
        client, _ = self._app(db_session, tmp_path)
        res = client.post(
            "/api/v1/ml/predict",
            json={"dpc_id": 1, "target_date": "2026-01-20"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "not_trained"
        assert body["results"]["arrivals"]["predicted_value"] is None

    def test_train_then_predict(self, db_session, tmp_path):
        seed = seed_ml_dataset(db_session, n_days=24)
        client, service = self._app(db_session, tmp_path)
        train_res = client.post("/api/v1/ml/train", json={"validation_days": 7})
        assert train_res.status_code == 200
        assert train_res.json()["status"] == "trained"

        status_res = client.get("/api/v1/ml/status")
        assert status_res.json()["trained"] is True

        dpc_id = seed["dpcs"][0].id
        target_date = seed["dates"][-1]
        res = client.post(
            "/api/v1/ml/predict",
            json={"dpc_id": dpc_id, "target_date": target_date.isoformat(), "target": "all"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        for key in ("arrivals", "quantity", "congestion"):
            assert body["results"][key]["confidence"] is not None

        get_res = client.get(f"/api/v1/ml/predict/{dpc_id}/{target_date.isoformat()}")
        assert get_res.status_code == 200
        assert get_res.json()["status"] == "ok"

    def test_single_target_predict(self, db_session, tmp_path):
        seed = seed_ml_dataset(db_session, n_days=24)
        client, service = self._app(db_session, tmp_path)
        client.post("/api/v1/ml/train", json={"validation_days": 7})
        dpc_id = seed["dpcs"][0].id
        res = client.post(
            "/api/v1/ml/predict",
            json={"dpc_id": dpc_id, "target_date": "2026-01-20", "target": "congestion", "persist": False},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["results"]["congestion"]["prediction_type"] == "overload_probability"
        assert body["results"]["congestion"]["persisted"] is False
        assert 0.0 <= body["results"]["congestion"]["score"] <= 100.0