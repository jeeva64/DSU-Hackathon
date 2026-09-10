from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from backend.app.ml.errors import InsufficientDataError
from backend.app.ml.features import FEATURE_COLUMNS, LAG_COLUMNS, FeatureBuilder, location_for_dpc
from mlfactories import seed_ml_dataset


class TestLocationForDPC:
    def test_matches_substring(self):
        assert location_for_dpc("Thanjavur Central DPC") == "Thanjavur"
        assert location_for_dpc("Papanasam SPC") == "Papanasam"
        assert location_for_dpc("Kumbakonam DPC") == "Kumbakonam"
        assert location_for_dpc("Pattukkottai DPC") == "Pattukkottai"

    def test_no_match(self):
        assert location_for_dpc("Some Other DPC") is None
        assert location_for_dpc(None) is None
        assert location_for_dpc("") is None


class TestFeatureBuilder:
    def test_build_columns_and_drop_first_day(self, db_session):
        seed_ml_dataset(db_session, n_days=5)
        fb = FeatureBuilder(db_session)
        frame = fb.build(fb.min_history_date(), fb.min_history_date() + timedelta(days=4))
        assert not frame.empty
        for col in FEATURE_COLUMNS:
            assert col in frame.columns
        # First per-DPC row has NaN lags and is dropped entirely.
        assert len(frame) == 2 * 4
        assert frame[LAG_COLUMNS].notna().all().all()

    def test_weather_values_populated(self, db_session):
        seed = seed_ml_dataset(db_session, n_days=5)
        fb = FeatureBuilder(db_session)
        frame = fb.build(seed["start"], seed["start"] + timedelta(days=4), dpc_ids=[seed["dpcs"][0].id])
        assert not frame["rainfall_probability"].isna().any()
        assert frame["temperature_max"].between(28, 36).all()

    def test_no_weather_location_uses_defaults(self, db_session):
        from backend.app.models.dpc import DPC, OperatingStatus

        dpc = DPC(
            dpc_code="DPC-ND",
            name="No Weather DPC",
            district="X",
            daily_capacity=1000,
            processing_rate=50.0,
            storage_capacity=250.0,
            operating_status=OperatingStatus.active,
        )
        db_session.add(dpc)
        db_session.commit()
        fb = FeatureBuilder(db_session)
        day = date(2026, 3, 1)
        frame = fb.build(day, day + timedelta(days=3), dpc_ids=[dpc.id])
        assert not frame.empty
        assert (frame["temperature_max"] == 30.0).all()
        assert (frame["humidity"] == 50.0).all()

    def test_lag_features_do_not_leak(self):
        from backend.app.ml.features import FeatureBuilder
        from backend.app.ml.models import build_regressor

        counts = [10, 20, 30, 40, 50]
        frame = pd.DataFrame(
            {
                "dpc_id": [1] * len(counts),
                "date": [date(2026, 2, i) for i in range(1, len(counts) + 1)],
                "arrivals_count": counts,
                "quantity": [q * 3.0 for q in counts],
                "utilization_pct": [30.0, 40.0, 50.0, 60.0, 70.0],
            }
        )
        FeatureBuilder._add_lag_features(frame)
        # First row has no history to lag against.
        assert frame.loc[0, "arrivals_prev_1d"] != frame.loc[0, "arrivals_prev_1d"]
        # Each lag uses only strictly-earlier rows.
        assert frame.loc[1, "arrivals_prev_1d"] == 10
        assert frame.loc[4, "arrivals_prev_1d"] == 40
        assert frame.loc[2, "arrivals_mean_3d"] == 15.0   # mean(10, 20)
        assert frame.loc[3, "arrivals_mean_3d"] == 20.0   # mean(10, 20, 30)
        assert frame.loc[4, "arrivals_mean_3d"] == 30.0   # mean(20, 30, 40)
        assert frame.loc[4, "quantity_prev_1d"] == 120.0
        assert frame.loc[4, "utilization_pct_prev"] == 60.0
        # Nothing is pulled from the future.
        assert frame.loc[4, "arrivals_mean_3d"] == (frame.loc[1]["arrivals_count"] + frame.loc[2]["arrivals_count"] + frame.loc[3]["arrivals_count"]) / 3

    def test_target_columns(self, db_session):
        from backend.app.ml.models import MLTarget, OVERLOAD_THRESHOLD

        seed_ml_dataset(db_session, n_days=6)
        fb = FeatureBuilder(db_session)
        start = fb.min_history_date()
        for target in (MLTarget.arrival_count, MLTarget.quantity, MLTarget.overload):
            frame = fb.build(start, start + timedelta(days=5), target=target)
            assert "target" in frame.columns
            assert frame["target"].notna().all()
            if target != MLTarget.overload:
                assert frame["target"].ge(0).all()

    def test_empty_database_raises(self, db_session):
        fb = FeatureBuilder(db_session)
        with pytest.raises(InsufficientDataError):
            fb.min_history_date()

    def test_row_for_returns_feature_dict(self, db_session):
        seed = seed_ml_dataset(db_session, n_days=6)
        fb = FeatureBuilder(db_session)
        row = fb.row_for(seed["dpcs"][0].id, seed["dates"][-1] + timedelta(days=1))
        assert set(row.keys()) == set(FEATURE_COLUMNS)
        assert all(pd.notna(v) for v in row.values())