from __future__ import annotations

import enum

from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)

OVERLOAD_THRESHOLD = 85.0
MIN_TRAIN_SAMPLES_GBR = 80
MIN_POSITIVES_PER_SPLIT = 3
DEFAULT_RANDOM_STATE = 42


class MLTarget(str, enum.Enum):
    arrival_count = "arrival_count"
    quantity = "quantity"
    overload = "overload"


REGRESSION_TARGETS = (MLTarget.arrival_count, MLTarget.quantity)


def build_regressor(model_type: str = "random_forest", random_state: int = DEFAULT_RANDOM_STATE):
    if model_type == "gradient_boosting":
        return GradientBoostingRegressor(
            n_estimators=160,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            loss="huber",
            random_state=random_state,
        )
    return RandomForestRegressor(
        n_estimators=220,
        max_depth=6,
        min_samples_leaf=3,
        random_state=random_state,
    )


def build_classifier(random_state: int = DEFAULT_RANDOM_STATE):
    return RandomForestClassifier(
        n_estimators=220,
        max_depth=6,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=random_state,
    )