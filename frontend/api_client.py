"""Thin REST client for the NelSync AI backend.

Never raises on network/HTTP failures: every call returns
(ok: bool, payload, error: dict | None) and high-level getters return
(Data, "backend" | "demo", error) so pages can fall back to clearly-labeled
synthetic demo data without crashing.

The backend error format is {"error": {"code", "message", "details"}}.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from frontend.config import API_BASE_URL

logger = logging.getLogger("frontend.api")

DEFAULT_TIMEOUT = 10

_PAGINATION_KEYS = ("items", "total", "skip", "limit")


class ApiClient:
    def __init__(self, base_url: str = API_BASE_URL, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Low-level request
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        body: dict | None = None,
        timeout: int | None = None,
    ) -> tuple[bool, Any, dict | None]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.request(
                method,
                url,
                params=params,
                json=body,
                timeout=timeout or self.timeout,
            )
        except requests.exceptions.Timeout:
            return False, None, {"type": "timeout", "message": f"Backend timed out at {url}"}
        except requests.exceptions.ConnectionError:
            return False, None, {"type": "connection", "message": f"Backend unreachable at {url}"}
        except requests.exceptions.RequestException as exc:
            return False, None, {"type": "request", "message": str(exc)}

        if response.status_code >= 400:
            message = f"HTTP {response.status_code} from {url}"
            detail = None
            try:
                payload = response.json()
                if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                    message = payload["error"].get("message") or message
                    detail = payload["error"].get("details")
            except ValueError:
                payload = None
            return False, payload, {"type": "http", "status": response.status_code,
                                    "message": message, "details": detail}

        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return True, payload, None

    # ------------------------------------------------------------------
    # Response unwrapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def unwrap(items_or_page: Any) -> Any:
        if isinstance(items_or_page, dict) and isinstance(items_or_page.get("items"), list):
            return items_or_page["items"]
        if isinstance(items_or_page, dict) and "total" in items_or_page:
            return items_or_page.get("items", [])
        return items_or_page

    def _safe(
        self,
        method: str,
        path: str,
        fallback: Any = None,
        params: dict | None = None,
        body: dict | None = None,
        unwrap: bool = False,
        timeout: int | None = None,
    ) -> tuple[Any, str, dict | None]:
        ok, payload, error = self._request(method, path, params=params, body=body, timeout=timeout)
        if not ok:
            if fallback is not None:
                return fallback, "demo", error
            return None, "backend", error
        if unwrap:
            payload = self.unwrap(payload)
        return payload, "backend", None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def get_health(self) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/health")

    # ------------------------------------------------------------------
    # Farmers
    # ------------------------------------------------------------------

    def get_farmers(self, limit: int = 500, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/farmers", fallback=fallback,
                          params={"skip": 0, "limit": limit}, unwrap=True)

    # ------------------------------------------------------------------
    # DPCs + capacities
    # ------------------------------------------------------------------

    def get_dpcs(self, limit: int = 500, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/dpcs", fallback=fallback,
                          params={"skip": 0, "limit": limit}, unwrap=True)

    def get_dpc_capacity(self, dpc_id: int) -> tuple[Any, str, dict | None]:
        return self._safe("GET", f"/dpcs/{dpc_id}/capacity")

    def get_dpc_overview(self, dpcs: list[dict], fallback: Any = None) -> tuple[Any, str, dict | None]:
        rows = []
        source = "backend"
        error = None
        for dpc in dpcs:
            cap, src, err = self.get_dpc_capacity(dpc["id"])
            if cap is None:
                source = "demo"
                error = error or err
            row = dict(dpc)
            if cap is not None:
                row.update({
                    "daily_capacity": cap.get("daily_capacity", dpc.get("daily_capacity")),
                    "current_utilization_pct": cap.get("current_utilization_pct", 0),
                    "bags_received_today": cap.get("bags_received_today", 0),
                    "remaining_capacity_bags": cap.get("remaining_capacity_bags", 0),
                })
            rows.append(row)
        if source == "demo":
            if fallback is not None:
                return fallback, source, error
            return rows, source, error
        return rows, source, None

    # ------------------------------------------------------------------
    # Procurement
    # ------------------------------------------------------------------

    def get_procurement(self, limit: int = 500, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/procurement", fallback=fallback,
                          params={"skip": 0, "limit": limit}, unwrap=True)

    def get_procurement_summary(self, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/procurement/summary", fallback=fallback)

    # ------------------------------------------------------------------
    # Statistical predictions
    # ------------------------------------------------------------------

    def get_predictions_for_dpc(self, dpc_id: int, limit: int = 30,
                                fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", f"/predictions/{dpc_id}", fallback=fallback,
                          params={"limit": limit})

    def generate_prediction(
        self, dpc_id: int, target_date: str, prediction_type: str = "arrival_count"
    ) -> tuple[Any, str, dict | None]:
        return self._safe(
            "POST",
            "/predictions/generate",
            body={"dpc_id": dpc_id, "target_date": target_date,
                  "prediction_type": prediction_type, "history_days": 30},
        )

    # ------------------------------------------------------------------
    # ML endpoints
    # ------------------------------------------------------------------

    def get_ml_status(self, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/ml/status", fallback=fallback)

    def ml_predict(self, dpc_id: int, target_date: str, target: str = "all",
                   persist: bool = False) -> tuple[Any, str, dict | None]:
        return self._safe(
            "POST",
            "/ml/predict",
            body={"dpc_id": dpc_id, "target_date": target_date, "target": target,
                  "persist": persist},
            timeout=20,
        )

    # ------------------------------------------------------------------
    # Risks, scenarios, recommendations
    # ------------------------------------------------------------------

    def get_risks(self, target_date: str | None = None, fallback: Any = None) -> tuple[Any, str, dict | None]:
        params = {"target_date": target_date} if target_date else None
        return self._safe("GET", "/risks", fallback=fallback, params=params)

    def get_scenarios(self, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/scenarios", fallback=fallback)

    def run_scenario(self, scenario_name: str, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("POST", "/scenarios/run", fallback=fallback,
                          body={"scenario_name": scenario_name}, timeout=20)

    def get_recommendations(self, limit: int = 100, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/recommendations", fallback=fallback,
                          params={"skip": 0, "limit": limit}, unwrap=True)

    def get_pending_recommendations(self, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("GET", "/recommendations/pending", fallback=fallback)

    def generate_recommendations(self, fallback: Any = None) -> tuple[Any, str, dict | None]:
        return self._safe("POST", "/recommendations/generate", fallback=fallback)


def error_summary(error: dict | None) -> str:
    if not error:
        return ""
    message = error.get("message") or ""
    error_type = error.get("type") or ""
    if error_type == "connection":
        return "Data unavailable from backend (connection failed)."
    if error_type == "timeout":
        return "Data unavailable from backend (request timed out)."
    if message:
        return f"Data unavailable from backend: {message}"
    return "Data unavailable from backend."