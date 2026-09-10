from __future__ import annotations

from datetime import date, datetime, timedelta

from frontend.config import (
    HARVEST_READINESS_LABELS,
    OPERATIONAL_STATUS_LABELS,
    SEVERITY_COLORS,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
)


def iso_today() -> str:
    return date.today().isoformat()


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def fmt_number(value, precision: int = 0) -> str:
    return f"{to_float(value):,.{precision}f}"


def fmt_qty(value, precision: int = 1) -> str:
    return f"{to_float(value):,.{precision}f}"


def fmt_pct(value, precision: int = 1) -> str:
    return f"{to_float(value):,.{precision}f}%"


def fmt_metric(value, precision: int = 2) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.{precision}f}"


def parse_iso_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def severity_rank(severity: str) -> int:
    try:
        return SEVERITY_ORDER.index((severity or "low").lower())
    except ValueError:
        return len(SEVERITY_ORDER) - 1


def severity_color(severity: str) -> str:
    key = (severity or "low").lower()
    return SEVERITY_COLORS.get(key, SEVERITY_COLORS["low"])


def severity_label(severity: str) -> str:
    key = (severity or "low").lower()
    return SEVERITY_LABELS.get(key, key.upper())


def capacity_status(utilization_pct: float) -> str:
    if utilization_pct >= 95:
        return "critical"
    if utilization_pct >= 85:
        return "high"
    if utilization_pct >= 70:
        return "medium"
    return "low"


def operational_status_label(status: str) -> str:
    return OPERATIONAL_STATUS_LABELS.get((status or "").lower(), str(status or "").title())


def readiness_label(status: str) -> str:
    return HARVEST_READINESS_LABELS.get((status or "").lower(), str(status or "").replace("_", " ").title())


def deterministic_hash(text: str) -> int:
    value = 0
    for ch in str(text):
        value = (value * 31 + ord(ch)) & 0xFFFFFFFF
    return value


def moisture_risk_from_code(farmer_code: str) -> str:
    """Prototype estimate: deterministic moisture risk level from a stable key."""
    bucket = deterministic_hash(farmer_code) % 100
    if bucket >= 90:
        return "high"
    if bucket >= 55:
        return "medium"
    return "low"


def expected_arrival_date(sowing_date_str: str | None, variety: str = "") -> str:
    """Prototype estimate: sowing date + fixed ~120 day crop window."""
    sowing = parse_iso_date(sowing_date_str)
    if sowing is None:
        return "-"
    return (sowing + timedelta(days=120)).isoformat()