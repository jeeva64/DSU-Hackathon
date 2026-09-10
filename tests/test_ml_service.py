from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from backend.app.ml.errors import ModelNotTrainedError
from backend.app.ml.models import MLTarget
from backend.app.ml.registry import MAX_KEPT_VERSIONS, ModelRegistry
from backend.app.ml.service import MLService, severity_for_probability
from backend.app.ml.trainer import Trainer, chronological_split, classification_metrics, regression_metrics
from backend.app.models.risk_assessment import RiskSeverity
from mlfactories import seed_ml_dataset


def make_frame() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    rows = []
    for i, d in enumerate(dates):
        rows.append({"date": d.date(), "y": float(i)})
    return pd.DataFrame(rows)


class TestChronologicalSplit:
    def test_split_is_chronological(self):
        df = make_frame()
        train, valid = chronological_split(df, validation_days=3)
        assert len(train) == 7 and len(valid) == 3
        assert train["date"].max() < valid["date"].min()
        assert valid["date"].min() == date(2026, 1, 8)

    def test_validation_days_longer_than_history(self):
        df = make_frame()
        train, valid = chronological_split(df, validation_days=50)
        assert train.empty and len(valid) == 10


class TestMetrics:
    def test_regression_metrics_perfect(self):
        y = [1.0, 2.0, 3.0, 4.0]
        m = regression_metrics(y, y)
        assert m["mae"] == 0.0
        assert m["rmse"] == 0.0
        assert m["r2"] == 1.0
        assert m["mean_actual"] == 2.5

    def test_regression_metrics_zero_true_guard(self):
        y = [0.0, 0.0, 0.0]
        m = regression_metrics(y, [1.0, 0.5, 0.0])
        assert m["mape"] == 50.0
        assert m["rmse_scaled"] == pytest.approx(0.6455, abs=1e-3)

    def test_classification_metrics(self):
        m = classification_metrics([0, 0, 1, 1], [0, 0, 1, 0], [0.1, 0.2, 0.9, 0.3])
        assert m["tp"] == 1 and m["fn"] == 1 and m["tn"] == 2 and m["fp"] == 0
        assert m["precision"] == 1.0 and m["recall"] == 0.5
        assert m["roc_auc"] is not None


class TestSeverity:
    def test_severity_thresholds(self):
        assert severity_for_probability(0.9) == RiskSeverity.critical
        assert severity_for_probability(0.85) == RiskSeverity.critical
        assert severity_for_probability(0.7) == RiskSeverity.high
        assert severity_for_probability(0.5) == RiskSeverity.medium
        assert severity_for_probability(0.4) == RiskSeverity.medium
        assert severity_for_probability(0.39) == RiskSeverity.low
        assert severity_for_probability(0.2) == RiskSeverity.low


class TestModelRegistry:
    def test_empty_registry_not_trained(self, tmp_path):
        reg = ModelRegistry(tmp_path / "artifacts")
        assert reg.is_trained() is False
        assert reg.status()["trained"] is False
        with pytest.raises(ModelNotTrainedError):
            reg.load_current(MLTarget.arrival_count.value)

    def test_save_and_load_current(self, tmp_path):
        from sklearn.ensemble import RandomForestRegressor

        reg = ModelRegistry(tmp_path / "artifacts")
        model = RandomForestRegressor(n_estimators=5, random_state=0)
        entry = reg.save_run(
            target=MLTarget.arrival_count.value,
            model=model,
            feature_columns=["a", "b"],
            model_type="random_forest",
            metrics={"r2": 0.9},
            train_range=["2026-01-01", "2026-01-10"],
            valid_range=["2026-01-11", "2026-01-12"],
            n_train=10,
            n_valid=2,
            hyperparams={"n_estimators": 5},
        )
        assert reg.is_trained() is True
        loaded, loaded_entry = reg.load_current(MLTarget.arrival_count.value)
        assert loaded_entry["version"] == entry["version"]
        assert loaded_entry["features"] == ["a", "b"]
        assert isinstance(loaded, RandomForestRegressor)
        assert reg.metrics()[MLTarget.arrival_count.value]["metrics"]["r2"] == 0.9

    def test_keeps_only_max_versions(self, tmp_path):
        from sklearn.ensemble import RandomForestRegressor

        reg = ModelRegistry(tmp_path / "artifacts")
        versions = []
        for i in range(MAX_KEPT_VERSIONS + 2):
            entry = reg.save_run(
                target=MLTarget.quantity.value,
                model=RandomForestRegressor(n_estimators=5, random_state=i),
                feature_columns=["a"],
                model_type="random_forest",
                metrics={"r2": i},
                train_range=["2026-01-01", "2026-01-10"],
                valid_range=["2026-01-11", "2026-01-12"],
                n_train=10,
                n_valid=2,
                hyperparams={},
            )
            versions.append(entry["version"])
        kept = reg.get_entry(MLTarget.quantity.value)
        assert kept["version"] == versions[-1]
        files = list((tmp_path / "artifacts").glob("model_quantity_v-*.joblib"))
        assert len(files) == MAX_KEPT_VERSIONS


class TestMLServiceTrained:
    def _service(self, db_session, tmp_path):
        return MLService(db_session, artifacts_dir=tmp_path / "artifacts", validation_days=7)

    def test_untrained_predict_raises(self, db_session, tmp_path):
        seed_ml_dataset(db_session, n_days=24)
        svc = self._service(db_session, tmp_path)
        assert svc.is_trained() is False
        with pytest.raises(ModelNotTrainedError):
            svc.predict_congestion(1, date(2026, 1, 20))

    def test_train_and_predict_roundtrip(self, db_session, tmp_path):
        seed = seed_ml_dataset(db_session, n_days=24)
        svc = self._service(db_session, tmp_path)
        result = svc.train_models()
        assert result["status"] == "trained", result
        for target in (MLTarget.arrival_count, MLTarget.quantity, MLTarget.overload):
            assert result["targets"][target.value]["trained"] is True

        dpc_id = seed["dpcs"][0].id
        target_date = seed["dates"][-1] + timedelta(days=1)
        arrivals = svc.predict_arrivals(dpc_id, target_date)
        assert arrivals["predicted_value"] >= 0
        assert arrivals["persisted"] is True
        assert arrivals["model_version"]

        quantity = svc.predict_quantity(dpc_id, target_date)
        assert quantity["predicted_value"] >= 0
        assert quantity["persisted"] is True

        congestion = svc.predict_congestion(dpc_id, target_date)
        assert 0.0 <= congestion["probability"] <= 1.0
        assert congestion["severity"] in {s.value for s in RiskSeverity}
        assert 0.0 <= congestion["score"] <= 100.0
        assert congestion["persisted"] is True

    def test_predict_persists_to_db(self, db_session, tmp_path):
        seed = seed_ml_dataset(db_session, n_days=24)
        svc = self._service(db_session, tmp_path)
        svc.train_models()
        dpc_id = seed["dpcs"][0].id
        target_date = seed["dates"][-1]
        svc.predict_all(dpc_id, target_date)

        from backend.app.repositories.prediction_repo import PredictionRepository
        from backend.app.repositories.risk_assessment_repo import RiskAssessmentRepository

        preds = PredictionRepository(db_session).get_by_dpc(dpc_id, limit=30)
        assert {p.prediction_type.value for p in preds} >= {"arrival_count", "quantity"}
        risks = RiskAssessmentRepository(db_session).get_by_dpc_and_date(dpc_id, target_date)
        assert any(r.risk_type.value == "overload" for r in risks)

    def test_status_and_evaluate(self, db_session, tmp_path):
        seed_ml_dataset(db_session, n_days=24)
        svc = self._service(db_session, tmp_path)
        assert svc.status()["trained"] is False
        svc.train_models()
        status = svc.status()
        assert status["trained"] is True
        assert status["current_version"]
        assert set(status["targets"].keys()) == {"arrival_count", "quantity", "overload"}
        evaluate = svc.evaluate_models()
        assert set(evaluate["targets"].keys()) == {"arrival_count", "quantity", "overload"}


class TestTrainerDirect:
    def test_chronological_holdout_used(self, db_session, tmp_path):
        seed = seed_ml_dataset(db_session, n_days=24)
        reg = ModelRegistry(tmp_path / "artifacts")
        trainer = Trainer(db_session, reg, validation_days=7)
        entry = trainer.train(MLTarget.arrival_count)
        assert entry["valid_range"][0] == seed["dates"][-7].isoformat()
        assert entry["valid_range"][1] == seed["dates"][-1].isoformat()
        assert entry["n_valid"] == 2 * 7