"""Global configuration for the NelSync AI demo frontend.

All backend endpoints default to http://localhost:8000 and can be overridden
with the BACKEND_URL environment variable or a local frontend/.env file.
"""

from __future__ import annotations

import os
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent
DOT_ENV = FRONTEND_DIR / ".env"

DEFAULT_BACKEND_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

APP_TITLE = "NelSync AI"
APP_TAGLINE = "AI-assisted decision support for Tamil Nadu paddy procurement"

SEVERITY_COLORS = {
    "critical": "#b00020",
    "high": "#d1495b",
    "medium": "#e07c24",
    "low": "#2e7d32",
    "none": "#2e7d32",
}
SEVERITY_LABELS = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "none": "NONE",
}
SEVERITY_ORDER = ("critical", "high", "medium", "low", "none")

OPERATIONAL_STATUS_LABELS = {
    "active": "Active",
    "maintenance": "Maintenance",
    "closed": "Closed",
    "overloaded": "Overloaded",
}

HARVEST_READINESS_LABELS = {
    "not_ready": "Not ready",
    "partially_ready": "Partially ready",
    "ready": "Ready",
    "overdue": "Overdue",
}

PLANTING_TO_HARVEST_DAYS = 120  # prototype estimate for "expected arrival"

CAPACITY_THRESHOLDS = {"watch": 70, "high": 85, "critical": 95}

PAGE_LABELS = [
    "Dashboard",
    "Procurement",
    "DPC Monitoring",
    "AI Predictions",
    "Risk Center",
    "Scenario Simulation",
]

# ---------------------------------------------------------------------------
# Demo (synthetic) fallback data - mirrors the backend seed, never shown as
# live backend data. Labeled "Demo fallback data" in the UI.
# ---------------------------------------------------------------------------

DEMO_DPCS = [
    {"id": 1, "dpc_code": "DPC-001", "name": "Thanjavur Central DPC", "district": "Thanjavur",
     "daily_capacity": 1000, "processing_rate": 60.0, "storage_capacity": 300.0,
     "operating_status": "active", "utilization_pct": 88.0, "bags_received_today": 880,
     "remaining_capacity_bags": 120},
    {"id": 2, "dpc_code": "DPC-002", "name": "Papanasam Procurement Center", "district": "Thanjavur",
     "daily_capacity": 800, "processing_rate": 50.0, "storage_capacity": 250.0,
     "operating_status": "active", "utilization_pct": 74.0, "bags_received_today": 592,
     "remaining_capacity_bags": 208},
    {"id": 3, "dpc_code": "DPC-003", "name": "Kumbakonam DPC", "district": "Thanjavur",
     "daily_capacity": 1200, "processing_rate": 70.0, "storage_capacity": 400.0,
     "operating_status": "active", "utilization_pct": 91.0, "bags_received_today": 1092,
     "remaining_capacity_bags": 108},
    {"id": 4, "dpc_code": "DPC-004", "name": "Pattukkottai DPC", "district": "Thanjavur",
     "daily_capacity": 900, "processing_rate": 55.0, "storage_capacity": 280.0,
     "operating_status": "overloaded", "utilization_pct": 97.0, "bags_received_today": 873,
     "remaining_capacity_bags": 27},
]

DEMO_VARIETIES = {"CO-51": 120, "CR-1009": 125, "CO-43": 115, "BPT-5204": 130, "ADT-37": 110}

DEMO_FARMERS = [
    {"farmer_code": "FRM-001", "name": "Ramasamy P", "village": "Thanjavur", "variety": "CO-51",
     "expected_quantity": 18.5, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-002", "name": "Lakshmi Devi", "village": "Thanjavur", "variety": "CR-1009",
     "expected_quantity": 12.0, "harvest_readiness": "partially_ready"},
    {"farmer_code": "FRM-003", "name": "Murugan K", "village": "Papanasam", "variety": "ADT-37",
     "expected_quantity": 8.2, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-004", "name": "Priya S", "village": "Papanasam", "variety": "CO-51",
     "expected_quantity": 15.4, "harvest_readiness": "overdue"},
    {"farmer_code": "FRM-005", "name": "Selvaraj M", "village": "Kumbakonam", "variety": "CO-43",
     "expected_quantity": 22.1, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-006", "name": "Meena K", "village": "Kumbakonam", "variety": "BPT-5204",
     "expected_quantity": 6.8, "harvest_readiness": "not_ready"},
    {"farmer_code": "FRM-007", "name": "Karuppu R", "village": "Pattukkottai", "variety": "CR-1009",
     "expected_quantity": 19.3, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-008", "name": "Anandhi V", "village": "Pattukkottai", "variety": "CO-51",
     "expected_quantity": 11.7, "harvest_readiness": "partially_ready"},
    {"farmer_code": "FRM-009", "name": "Ganesan T", "village": "Orathanadu", "variety": "ADT-37",
     "expected_quantity": 14.9, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-010", "name": "Kavitha R", "village": "Orathanadu", "variety": "CO-43",
     "expected_quantity": 7.6, "harvest_readiness": "overdue"},
    {"farmer_code": "FRM-011", "name": "Sundaram P", "village": "Thanjavur", "variety": "BPT-5204",
     "expected_quantity": 13.5, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-012", "name": "Parvathi S", "village": "Papanasam", "variety": "CO-51",
     "expected_quantity": 9.4, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-013", "name": "Veerapandi M", "village": "Kumbakonam", "variety": "CR-1009",
     "expected_quantity": 20.8, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-014", "name": "Sakthi K", "village": "Pattukkottai", "variety": "ADT-37",
     "expected_quantity": 5.9, "harvest_readiness": "not_ready"},
    {"farmer_code": "FRM-015", "name": "Palaniappan R", "village": "Orathanadu", "variety": "CO-51",
     "expected_quantity": 17.2, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-016", "name": "Revathi T", "village": "Thanjavur", "variety": "CO-43",
     "expected_quantity": 10.1, "harvest_readiness": "partially_ready"},
    {"farmer_code": "FRM-017", "name": "Balu N", "village": "Papanasam", "variety": "BPT-5204",
     "expected_quantity": 16.6, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-018", "name": "Jeyalakshmi V", "village": "Kumbakonam", "variety": "CO-51",
     "expected_quantity": 12.3, "harvest_readiness": "ready"},
    {"farmer_code": "FRM-019", "name": "Thirunavukkarasu", "village": "Pattukkottai", "variety": "CR-1009",
     "expected_quantity": 23.9, "harvest_readiness": "overdue"},
    {"farmer_code": "FRM-020", "name": "Poongodi M", "village": "Orathanadu", "variety": "ADT-37",
     "expected_quantity": 7.1, "harvest_readiness": "ready"},
]

DEMO_PROCUREMENT_SUMMARY = {
    "total_records": 184,
    "total_bags": 3450,
    "total_quantity_quintal": 1180.5,
    "accepted_count": 168,
    "rejected_count": 16,
    "pending_count": 12,
    "avg_moisture_pct": 16.4,
}

DEMO_RISKS = [
    {"risk_type": "overload", "severity": "critical", "dpc_id": 4, "dpc_name": "Pattukkottai DPC",
     "description": "DPC Pattukkottai at 97% predicted capacity", "metric": 97.0},
    {"risk_type": "overload", "severity": "high", "dpc_id": 3, "dpc_name": "Kumbakonam DPC",
     "description": "DPC Kumbakonam at 91% predicted capacity", "metric": 91.0},
    {"risk_type": "congestion", "severity": "high", "dpc_id": 1, "dpc_name": "Thanjavur Central DPC",
     "description": "Queue of 64 farmers expected", "metric": 64.0},
    {"risk_type": "moisture", "severity": "medium", "dpc_id": None, "dpc_name": "System-wide",
     "description": "High humidity (88%) increases moisture rejection risk", "metric": 88.0},
]

DEMO_SCENARIOS = [
    {"name": "NORMAL_DAY", "description": "Typical procurement day with moderate arrivals and normal operations"},
    {"name": "DPC_OVERLOAD", "description": "High arrivals pushing DPC capacity limits"},
    {"name": "RAIN_RISK", "description": "Heavy rain forecast threatening procurement and stored paddy"},
    {"name": "TRANSPORT_BOTTLENECK", "description": "Limited transport preventing paddy movement from DPC to godown"},
    {"name": "COMBINED_CRISIS", "description": "Multiple simultaneous crises: overload + rain + transport + labour constraints"},
]

DEMO_SCENARIO_PARAMS = {
    "NORMAL_DAY": {"arrival_multiplier": 0.6, "capacity_utilization": 0.4, "rain_mm": 0,
                   "transport_availability_pct": 100, "labour_availability_pct": 100,
                   "storage_utilization_pct": 40, "humidity_pct": 60},
    "DPC_OVERLOAD": {"arrival_multiplier": 1.2, "capacity_utilization": 0.85, "rain_mm": 0,
                     "transport_availability_pct": 100, "labour_availability_pct": 100,
                     "storage_utilization_pct": 80, "humidity_pct": 55},
    "RAIN_RISK": {"arrival_multiplier": 0.8, "capacity_utilization": 0.6, "rain_mm": 25,
                  "transport_availability_pct": 70, "labour_availability_pct": 90,
                  "storage_utilization_pct": 60, "humidity_pct": 85},
    "TRANSPORT_BOTTLENECK": {"arrival_multiplier": 0.9, "capacity_utilization": 0.7, "rain_mm": 5,
                             "transport_availability_pct": 30, "labour_availability_pct": 90,
                             "storage_utilization_pct": 75, "humidity_pct": 65},
    "COMBINED_CRISIS": {"arrival_multiplier": 1.3, "capacity_utilization": 0.92, "rain_mm": 20,
                        "transport_availability_pct": 25, "labour_availability_pct": 50,
                        "storage_utilization_pct": 90, "humidity_pct": 88},
}

DEFAULT_SCENARIO = "COMBINED_CRISIS"

# Deterministic demo ML predictions for a DPC (arrivals, quantity, overload %).
DEMO_ML_PREDICTIONS = {
    "Thanjavur Central DPC": {"arrivals": 123, "quantity": 369, "overload_pct": 78.0, "severity": "high"},
    "Papanasam Procurement Center": {"arrivals": 87, "quantity": 261, "overload_pct": 46.0, "severity": "low"},
    "Kumbakonam DPC": {"arrivals": 140, "quantity": 420, "overload_pct": 82.0, "severity": "high"},
    "Pattukkottai DPC": {"arrivals": 111, "quantity": 333, "overload_pct": 91.0, "severity": "critical"},
}

DEMO_ML_STATUS = {
    "trained": True,
    "current_version": "v-demo-000000000000",
    "trained_at": None,
    "message": "Demo mode: showing synthetic model registry.",
    "targets": {
        "arrival_count": {"trained": True, "version": "v-demo", "model_type": "GradientBoosting",
                          "metrics": {"mae": 0.77, "rmse": 1.05, "mape": 8.5, "r2": 0.52, "rmse_scaled": 0.11}},
        "quantity": {"trained": True, "version": "v-demo", "model_type": "GradientBoosting",
                     "metrics": {"mae": 18.08, "rmse": 26.4, "mape": 6.4, "r2": 0.24, "rmse_scaled": 0.09}},
        "overload": {"trained": True, "version": "v-demo", "model_type": "RandomForestClassifier",
                     "metrics": {"accuracy": 0.82, "precision": 0.67, "recall": 0.12, "f1": 0.20,
                                 "roc_auc": 0.61, "positives": 17, "negatives": 39}},
    },
}
DEMO_ML_STATUS["targets"]["arrival_count"]["n_train"] = 320
DEMO_ML_STATUS["targets"]["arrival_count"]["n_valid"] = 56
DEMO_ML_STATUS["targets"]["quantity"]["n_train"] = 320
DEMO_ML_STATUS["targets"]["quantity"]["n_valid"] = 56
DEMO_ML_STATUS["targets"]["overload"]["n_train"] = 320
DEMO_ML_STATUS["targets"]["overload"]["n_valid"] = 56


def get_backend_url() -> str:
    """Resolve the backend URL: BACKEND_URL env var, then frontend/.env, then default."""
    env_value = os.environ.get("BACKEND_URL")
    if env_value:
        return env_value.strip().rstrip("/")
    if DOT_ENV.exists():
        for line in DOT_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
    return DEFAULT_BACKEND_URL


BACKEND_URL = get_backend_url()
API_BASE_URL = f"{BACKEND_URL}{API_PREFIX}"