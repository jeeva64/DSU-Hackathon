from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.ml.errors import InsufficientDataError
from backend.app.ml.features import FEATURE_COLUMNS, FeatureBuilder
from backend.app.ml.models import (
    MIN_POSITIVES_PER_SPLIT,
    MIN_TRAIN_SAMPLES_GBR,
    MLTarget,
    REGRESSION_TARGETS,
    build_classifier,
    build_regressor,
)
from backend.app.ml.registry import ModelRegistry
from backend.app.models.dpc_capacity import DPCCapacity


def chronological_split(
    df: pd.DataFrame, validation_days: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(df["date"].unique())
    if validation_days >= len(dates) or validation_days <= 0:
        cutoff = dates[0]
    else:
        cutoff = dates[-validation_days]
    train = df[df["date"] < cutoff]
    valid = df[df["date"] >= cutoff]
    return train, valid


def _as_range(dates: list[date]) -> list[str]:
    if not dates:
        return []
    return [min(dates).isoformat(), max(dates).isoformat()]


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(math.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))
    mean_actual = float(y_true.mean())
    denom = max(mean_actual, 1.0)
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mae / denom * 100, 3),
        "r2": round(r2, 4),
        "mean_actual": round(mean_actual, 4),
        "rmse_scaled": round(rmse / denom, 4),
    }


def classification_metrics(y_true, y_pred, y_prob) -> dict[str, Any]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    support = confusion_matrix(y_true, y_pred, labels=[0, 1])
    metrics = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "positives": int(np.sum(y_true == 1)),
        "negatives": int(np.sum(y_true == 0)),
        "tn": int(support[0, 0]),
        "fp": int(support[0, 1]),
        "fn": int(support[1, 0]),
        "tp": int(support[1, 1]),
        "mean_actual": round(float(np.mean(y_true)), 4),
    }
    if (metrics["positives"] > 0) and (metrics["negatives"] > 0):
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)
        except ValueError:
            metrics["roc_auc"] = None
    else:
        metrics["roc_auc"] = None
    return metrics


class Trainer:
    """Trains the three prediction models with a chronological split.

    The split is date-based (never random): earlier dates are training,
    the most recent `validation_days` form the holdout. All reported metrics
    are computed exclusively on that holdout.
    """

    def __init__(self, db: Session, registry: ModelRegistry, validation_days: int = 14) -> None:
        self.db = db
        self.registry = registry
        self.validation_days = validation_days
        self.features = FeatureBuilder(db)

    def _history_bounds(self) -> tuple[date, date]:
        first = self.features.min_history_date()
        last_value = self.db.execute(select(func.max(DPCCapacity.date))).scalar()
        last = last_value if last_value is not None else first
        return first, last

    def _prepare(self, target: MLTarget) -> tuple[pd.DataFrame, pd.DataFrame]:
        start, end = self._history_bounds()
        df = self.features.build(start, end, target=target)
        df = df.dropna(subset=["target"])
        if df.empty:
            raise InsufficientDataError(f"Not enough labelled rows to train '{target.value}'.")
        train, valid = chronological_split(df, self.validation_days)
        if train.empty or valid.empty:
            raise InsufficientDataError(
                f"Chronological split produced empty train/valid subsets for '{target.value}'."
            )
        return train, valid

    def train(self, target: MLTarget) -> dict[str, Any]:
        train, valid = self._prepare(target)
        X_train = train[FEATURE_COLUMNS]
        y_train = train["target"].astype(int if target == MLTarget.overload else float)
        X_valid = valid[FEATURE_COLUMNS]
        y_valid = valid["target"].astype(int if target == MLTarget.overload else float)

        train_range = _as_range([d for d in sorted(train["date"].unique())])
        valid_range = _as_range([d for d in sorted(valid["date"].unique())])
        n_train = int(len(train))
        n_valid = int(len(valid))

        if target in REGRESSION_TARGETS:
            return self._train_regression(
                target, X_train, y_train, X_valid, y_valid, train_range, valid_range, n_train, n_valid
            )
        return self._train_classifier(
            target, X_train, y_train, X_valid, y_valid, train_range, valid_range, n_train, n_valid
        )

    def _train_regression(
        self,
        target: MLTarget,
        X_tr,
        y_tr,
        X_val,
        y_val,
        train_range: list[str],
        valid_range: list[str],
        n_train: int,
        n_valid: int,
    ) -> dict[str, Any]:
        candidate_metrics = {}
        candidates = [("random_forest", build_regressor("random_forest"))]
        if len(X_tr) >= MIN_TRAIN_SAMPLES_GBR:
            candidates.append(("gradient_boosting", build_regressor("gradient_boosting")))

        hyperparams: dict[str, Any] = {}
        best_name, best_model, best_metrics = None, None, None
        for name, model in candidates:
            model.fit(X_tr, y_tr)
            y_pred = model.predict(X_val)
            metrics = regression_metrics(y_val, y_pred)
            candidate_metrics[name] = metrics
            hyperparams[name] = {
                "estimator": model.__class__.__name__,
                "n_estimators": getattr(model, "n_estimators", None),
                "max_depth": getattr(model, "max_depth", None),
            }
            if best_metrics is None or metrics["r2"] > best_metrics["r2"]:
                best_name, best_model, best_metrics = name, model, metrics

        return self.registry.save_run(
            target=target.value,
            model=best_model,
            feature_columns=FEATURE_COLUMNS,
            model_type=best_name,
            metrics=best_metrics,
            train_range=train_range,
            valid_range=valid_range,
            n_train=n_train,
            n_valid=n_valid,
            hyperparams=hyperparams,
        )

    def _train_classifier(
        self,
        target: MLTarget,
        X_tr,
        y_tr,
        X_val,
        y_val,
        train_range: list[str],
        valid_range: list[str],
        n_train: int,
        n_valid: int,
    ) -> dict[str, Any]:
        if len(np.unique(y_tr)) < 2:
            raise InsufficientDataError(
                f"Training set for '{target.value}' has a single class; cannot train a classifier."
            )
        if min(np.sum(y_tr == 1), np.sum(y_val == 1)) < MIN_POSITIVES_PER_SPLIT:
            raise InsufficientDataError(
                f"Too few positive examples for '{target.value}' to evaluate reliably."
            )

        model = build_classifier()
        model.fit(X_tr, y_tr)
        y_prob = model.predict_proba(X_val)[:, 1]
        y_pred = model.predict(X_val)
        metrics = classification_metrics(y_val, y_pred, y_prob)
        hyperparams = {"estimator": model.__class__.__name__, "class_weight": "balanced"}

        return self.registry.save_run(
            target=target.value,
            model=model,
            feature_columns=FEATURE_COLUMNS,
            model_type="random_forest_classifier",
            metrics=metrics,
            train_range=train_range,
            valid_range=valid_range,
            n_train=n_train,
            n_valid=n_valid,
            hyperparams=hyperparams,
        )