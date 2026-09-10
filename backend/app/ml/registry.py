from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from backend.app.ml.errors import ModelNotTrainedError

MAX_KEPT_VERSIONS = 3


class ModelRegistry:
    """Persists trained models as joblib artifacts plus a JSON registry.

    One model file per target per version. The registry keeps the latest
    `MAX_KEPT_VERSIONS` versions per target and tracks train/valid ranges,
    feature list, hyperparameters and holdout metrics for every run.
    """

    def __init__(self, artifacts_dir: str | Path) -> None:
        self.dir = Path(artifacts_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.dir / "model_registry.json"

    # ------------------------------------------------------------------
    # Reading / writing
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"current_version": None, "models": {}}
        with open(self.registry_path, encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, data: dict[str, Any]) -> None:
        fd, tmp_path = tempfile.mkstemp(dir=str(self.dir), suffix=".json")
        with open(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        shutil.move(tmp_path, str(self.registry_path))

    # ------------------------------------------------------------------
    # Training API
    # ------------------------------------------------------------------

    @staticmethod
    def _next_version(data: dict[str, Any]) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        used: set[str] = set()
        for state in data.get("models", {}).values():
            used.update(v["version"] for v in state.get("versions", []))
        version = f"v-{stamp}"
        counter = 1
        while version in used:
            version = f"v-{stamp}-{counter}"
            counter += 1
        return version

    def save_run(
        self,
        target: str,
        model: Any,
        feature_columns: list[str],
        model_type: str,
        metrics: dict[str, Any],
        train_range: list[str],
        valid_range: list[str],
        n_train: int,
        n_valid: int,
        hyperparams: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._load()
        version = self._next_version(data)
        filename = f"model_{target}_{version}.joblib"
        model_path = self.dir / filename
        joblib.dump(model, model_path)

        entry = {
            "version": version,
            "filename": filename,
            "model_type": model_type,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "features": feature_columns,
            "metrics": metrics,
            "train_range": train_range,
            "valid_range": valid_range,
            "n_train": n_train,
            "n_valid": n_valid,
            "hyperparams": hyperparams,
        }

        target_state = data["models"].setdefault(target, {"current": None, "versions": []})
        target_state["versions"].insert(0, entry)
        target_state["versions"] = target_state["versions"][:MAX_KEPT_VERSIONS]
        target_state["current"] = entry
        data["current_version"] = version
        self._save(data)
        self._prune(target, entry)
        return entry

    def load_current(self, target: str):
        data = self._load()
        target_state = data.get("models", {}).get(target)
        if not target_state or not target_state.get("current"):
            raise ModelNotTrainedError(f"No trained model available for target '{target}'.")
        entry = target_state["current"]
        model_path = self.dir / entry["filename"]
        if not model_path.exists():
            raise ModelNotTrainedError(
                f"Artifact for '{target}' ({entry['version']}) is missing."
            )
        return joblib.load(model_path), entry

    def _prune(self, target: str, keep_entry: dict[str, Any]) -> None:
        data = self._load()
        target_state = data.get("models", {}).get(target)
        if not target_state:
            return
        kept_versions = {v["version"] for v in target_state["versions"]}
        for filename in self.dir.glob(f"model_{target}_*.joblib"):
            if filename.name != keep_entry["filename"]:
                version_hint = filename.stem.split("_")[-1]
                if version_hint not in kept_versions:
                    filename.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def is_trained(self) -> bool:
        data = self._load()
        models = data.get("models", {})
        return bool(models and any(m.get("current") for m in models.values()))

    def get_entry(self, target: str) -> dict[str, Any] | None:
        data = self._load()
        target_state = data.get("models", {}).get(target)
        if not target_state:
            return None
        return target_state.get("current")

    def status(self) -> dict[str, Any]:
        data = self._load()
        models = data.get("models", {})
        trained = bool(models and any(m.get("current") for m in models.values()))
        targets = {}
        for target, state in sorted(models.items()):
            current = state.get("current")
            if not current:
                targets[target] = {"trained": False}
                continue
            targets[target] = {
                "trained": True,
                "version": current["version"],
                "model_type": current["model_type"],
                "trained_at": current["trained_at"],
                "metrics": current["metrics"],
                "train_range": current["train_range"],
                "valid_range": current["valid_range"],
                "n_train": current["n_train"],
                "n_valid": current["n_valid"],
            }
        return {
            "trained": trained,
            "current_version": data.get("current_version"),
            "artifacts_dir": str(self.dir),
            "targets": targets,
        }

    def metrics(self) -> dict[str, Any]:
        data = self._load()
        out = {}
        for target, state in sorted(data.get("models", {}).items()):
            current = state.get("current")
            if current:
                out[target] = {
                    "version": current["version"],
                    "trained_at": current["trained_at"],
                    "metrics": current["metrics"],
                    "n_train": current["n_train"],
                    "n_valid": current["n_valid"],
                    "train_range": current["train_range"],
                    "valid_range": current["valid_range"],
                }
        return out