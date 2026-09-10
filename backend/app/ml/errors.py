from __future__ import annotations


class MLError(Exception):
    """Base error for the ML layer."""


class ModelNotTrainedError(MLError):
    """Raised when a prediction is requested before any model is trained."""


class InsufficientDataError(MLError):
    """Raised when the available training data is too small or degenerate."""