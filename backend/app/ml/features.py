from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.ml.errors import InsufficientDataError
from backend.app.ml.models import MLTarget, OVERLOAD_THRESHOLD
from backend.app.models.arrival_record import ArrivalRecord
from backend.app.models.dpc import DPC
from backend.app.models.dpc_capacity import DPCCapacity
from backend.app.models.procurement import ProcurementRecord
from backend.app.models.resource_availability import ResourceAvailability
from backend.app.models.weather_condition import WeatherCondition

WEATHER_LOCATIONS = ["Thanjavur", "Papanasam", "Kumbakonam", "Pattukkottai"]

FEATURE_COLUMNS = [
    "dpc_id",
    "day_of_week",
    "is_weekend",
    "day_of_season",
    "daily_capacity",
    "processing_rate",
    "storage_capacity",
    "rainfall_probability",
    "rainfall_mm",
    "humidity",
    "temperature_max",
    "labour_available",
    "transport_available",
    "weighing_capacity",
    "storage_available",
    "arrivals_prev_1d",
    "arrivals_mean_3d",
    "arrivals_mean_7d",
    "quantity_prev_1d",
    "quantity_mean_3d",
    "quantity_mean_7d",
    "utilization_pct_prev",
    "utilization_mean_3d",
]

LAG_COLUMNS = [
    "arrivals_prev_1d",
    "arrivals_mean_3d",
    "arrivals_mean_7d",
    "quantity_prev_1d",
    "quantity_mean_3d",
    "quantity_mean_7d",
    "utilization_pct_prev",
    "utilization_mean_3d",
]


def location_for_dpc(name: str | None) -> str | None:
    if not name:
        return None
    return next((loc for loc in WEATHER_LOCATIONS if loc in name), None)


class FeatureBuilder:
    """Builds a leak-free per-(dpc, date) feature frame directly from the DB.

    Calendar, DPC static, weather and resource columns describe the day itself.
    Lagged columns (arrivals/quantity utilization) are computed strictly from
    strictly-earlier dates so no target information leaks into the features.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def min_history_date(self) -> date:
        candidates: list[date] = []
        for column in (DPCCapacity.date, WeatherCondition.date, ArrivalRecord.date):
            value = self.db.execute(select(func.min(column))).scalar()
            if value is not None:
                candidates.append(value.date() if hasattr(value, "date") else value)
        if not candidates:
            raise InsufficientDataError("No historical records found in the database.")
        return min(candidates)

    def build(
        self,
        start: date,
        end: date,
        target: MLTarget | None = None,
        dpc_ids: Iterable[int] | None = None,
    ) -> pd.DataFrame:
        dpc_query = select(DPC).order_by(DPC.id)
        dpcs = list(self.db.execute(dpc_query).scalars().all())
        if dpc_ids is not None:
            keep = set(int(i) for i in dpc_ids)
            dpcs = [d for d in dpcs if d.id in keep]
        if not dpcs:
            return pd.DataFrame()

        date_index = pd.date_range(start, end, freq="D")
        dates = [dt.date() for dt in date_index]
        n_dates = len(dates)

        actual_start = date_index[0].date()
        actual_end = date_index[-1].date()

        arrival_counts = self._daily_counts(
            ArrivalRecord, ArrivalRecord.dpc_id, ArrivalRecord.date, actual_start, actual_end
        )
        quantity_sums = self._daily_sums(
            ProcurementRecord,
            ProcurementRecord.dpc_id,
            ProcurementRecord.date,
            ProcurementRecord.quantity_quintal,
            actual_start,
            actual_end,
        )

        resources = self._load_resources(actual_start, actual_end, {d.id for d in dpcs})
        utilization = self._load_utilization(actual_start, actual_end, {d.id for d in dpcs})

        frames: list[pd.DataFrame] = []
        for dpc in dpcs:
            loc = location_for_dpc(dpc.name)
            weather = self._load_weather(actual_start, actual_end, loc, dates)

            sub = pd.DataFrame({"date": dates, "dpc_id": dpc.id})
            sub["day_of_week"] = sub.apply(lambda r: r["date"].weekday(), axis=1)
            sub["is_weekend"] = (sub["day_of_week"] >= 5).astype(int)
            season_ref = dpc.open_date if dpc.open_date else date.today()
            sub["day_of_season"] = sub.apply(
                lambda r: max(0, (r["date"] - season_ref).days), axis=1
            )
            sub["daily_capacity"] = float(dpc.daily_capacity or 0)
            sub["processing_rate"] = float(dpc.processing_rate or 0)
            sub["storage_capacity"] = float(dpc.storage_capacity or 0)

            for col in ("rainfall_probability", "rainfall_mm", "humidity", "temperature_max"):
                sub[col] = weather[col].to_numpy().copy()

            sub["labour_available"] = [
                resources[(dpc.id, d)][0] if (dpc.id, d) in resources else 0 for d in dates
            ]
            sub["transport_available"] = [
                resources[(dpc.id, d)][1] if (dpc.id, d) in resources else 0 for d in dates
            ]
            sub["weighing_capacity"] = [
                resources[(dpc.id, d)][2] if (dpc.id, d) in resources else 0 for d in dates
            ]
            sub["storage_available"] = [
                resources[(dpc.id, d)][3] if (dpc.id, d) in resources else 0.0 for d in dates
            ]
            sub["utilization_pct"] = [
                utilization.get((dpc.id, d), 0.0) for d in dates
            ]

            sub["arrivals_count"] = [arrival_counts.get((dpc.id, d), 0) for d in dates]
            sub["quantity"] = [quantity_sums.get((dpc.id, d), 0.0) for d in dates]
            frames.append(sub)

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if frame.empty:
            raise InsufficientDataError("No feature rows could be built for the requested range.")

        frame = frame.sort_values(["dpc_id", "date"]).reset_index(drop=True)
        self._add_lag_features(frame)

        keep_mask = frame[LAG_COLUMNS].notna().all(axis=1)
        frame = frame[keep_mask].reset_index(drop=True)

        if target is None:
            return frame

        if target == MLTarget.arrival_count:
            frame["target"] = frame["arrivals_count"].astype(float)
        elif target == MLTarget.quantity:
            frame["target"] = frame["quantity"].astype(float)
        else:
            frame["target"] = (frame["utilization_pct"] > OVERLOAD_THRESHOLD).astype(int)
        return frame

    def row_for(self, dpc_id: int, target_date: date) -> dict:
        start = self.min_history_date()
        frame = self.build(start, target_date, target=None, dpc_ids=[dpc_id])
        if frame.empty:
            raise InsufficientDataError(f"No feature rows for DPC {dpc_id}.")
        dpc_rows = frame[frame["dpc_id"] == int(dpc_id)]
        if dpc_rows.empty:
            raise InsufficientDataError(f"No feature rows for DPC {dpc_id}.")
        last = dpc_rows.iloc[-1]
        return {col: last[col] for col in FEATURE_COLUMNS}

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _daily_counts(self, model, dpc_col, date_col, start: date, end: date) -> dict:
        result = self.db.execute(
            select(dpc_col, date_col, func.count(model.id))
            .where(date_col >= start, date_col <= end)
            .group_by(dpc_col, date_col)
        )
        return {(int(dpc), d): count for dpc, d, count in result.all()}

    def _daily_sums(self, model, dpc_col, date_col, value_col, start: date, end: date) -> dict:
        result = self.db.execute(
            select(dpc_col, date_col, func.sum(value_col))
            .where(date_col >= start, date_col <= end)
            .group_by(dpc_col, date_col)
        )
        return {(int(dpc), d): float(v or 0.0) for dpc, d, v in result.all()}

    def _load_resources(
        self, start: date, end: date, dpc_ids: set[int]
    ) -> dict[tuple[int, date], tuple]:
        rows = self.db.execute(
            select(ResourceAvailability)
            .where(
                ResourceAvailability.dpc_id.in_(dpc_ids),
                ResourceAvailability.date >= start,
                ResourceAvailability.date <= end,
            )
            .order_by(ResourceAvailability.dpc_id, ResourceAvailability.date)
        ).scalars().all()
        grouped: dict[int, list] = {}
        for r in rows:
            grouped.setdefault(r.dpc_id, []).append(r)

        out: dict[tuple[int, date], tuple] = {}
        interval = (end - start).days + 1
        for dpc_id, recs in grouped.items():
            rec_by_date = {r.date: r for r in recs}
            last = None
            for offset in range(interval):
                d = start + timedelta(days=offset)
                rec = rec_by_date.get(d)
                if rec is not None:
                    last = rec
                if last is not None:
                    out[(dpc_id, d)] = (
                        last.labour_available,
                        last.transport_available,
                        last.weighing_capacity,
                        float(last.storage_available),
                    )
        return out

    def _load_utilization(
        self, start: date, end: date, dpc_ids: set[int]
    ) -> dict[tuple[int, date], float]:
        rows = self.db.execute(
            select(DPCCapacity)
            .where(
                DPCCapacity.dpc_id.in_(dpc_ids),
                DPCCapacity.date >= start,
                DPCCapacity.date <= end,
            )
            .order_by(DPCCapacity.dpc_id, DPCCapacity.date)
        ).scalars().all()
        grouped: dict[int, list] = {}
        for r in rows:
            grouped.setdefault(r.dpc_id, []).append(r)

        out: dict[tuple[int, date], float] = {}
        interval = (end - start).days + 1
        for dpc_id, recs in grouped.items():
            rec_by_date = {r.date: r for r in recs}
            last = None
            for offset in range(interval):
                d = start + timedelta(days=offset)
                rec = rec_by_date.get(d)
                if rec is not None:
                    last = rec
                if last is not None:
                    out[(dpc_id, d)] = float(last.utilization_pct)
        return out

    def _load_weather(
        self, start: date, end: date, location: str | None, dates: list[date]
    ) -> pd.DataFrame:
        cols = ["rainfall_probability", "rainfall_mm", "humidity", "temperature_max"]
        frame = pd.DataFrame(
            {col: np.full(len(dates), np.nan) for col in cols}, index=dates
        )
        if not location:
            frame = frame.fillna(
                {"rainfall_probability": 0.0, "rainfall_mm": 0.0, "humidity": 50.0, "temperature_max": 30.0}
            )
            return frame

        rows = self.db.execute(
            select(WeatherCondition)
            .where(
                WeatherCondition.location == location,
                WeatherCondition.date >= start,
                WeatherCondition.date <= end,
            )
            .order_by(WeatherCondition.date)
        ).scalars().all()
        rec_by_date = {r.date: r for r in rows}
        last = None
        for d in dates:
            rec = rec_by_date.get(d)
            if rec is not None:
                last = rec
            if last is not None:
                frame.at[d, "rainfall_probability"] = last.rainfall_probability
                frame.at[d, "rainfall_mm"] = last.rainfall_mm
                frame.at[d, "humidity"] = last.humidity
                frame.at[d, "temperature_max"] = last.temperature_max if last.temperature_max is not None else 30.0
        frame = frame.fillna(
            {"rainfall_probability": 0.0, "rainfall_mm": 0.0, "humidity": 50.0, "temperature_max": 30.0}
        )
        return frame

    @staticmethod
    def _add_lag_features(frame: pd.DataFrame) -> None:
        grouped = frame.groupby("dpc_id", sort=False)

        def shift_mean(series, window: int):
            return series.rolling(window, min_periods=1).mean().shift(1)

        frame["arrivals_prev_1d"] = grouped["arrivals_count"].shift(1)
        frame["arrivals_mean_3d"] = grouped["arrivals_count"].transform(
            lambda s: shift_mean(s, 3)
        )
        frame["arrivals_mean_7d"] = grouped["arrivals_count"].transform(
            lambda s: shift_mean(s, 7)
        )
        frame["quantity_prev_1d"] = grouped["quantity"].shift(1)
        frame["quantity_mean_3d"] = grouped["quantity"].transform(
            lambda s: shift_mean(s, 3)
        )
        frame["quantity_mean_7d"] = grouped["quantity"].transform(
            lambda s: shift_mean(s, 7)
        )
        frame["utilization_pct_prev"] = grouped["utilization_pct"].shift(1)
        frame["utilization_mean_3d"] = grouped["utilization_pct"].transform(
            lambda s: shift_mean(s, 3)
        )