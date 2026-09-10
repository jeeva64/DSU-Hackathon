from __future__ import annotations


def format_bags(bags: int) -> str:
    """Format bag count for display."""
    if bags >= 1000:
        return f"{bags / 1000:.1f}K bags"
    return f"{bags} bags"


def format_quintal(quintal: float) -> str:
    """Format quintal amount for display."""
    if quintal >= 100:
        return f"{quintal / 100:.1f}Q"
    return f"{quintal:.1f} Qtl"


def severity_color(severity: str) -> str:
    """Return hex color for risk severity."""
    colors = {
        "critical": "#dc3545",
        "high": "#fd7e14",
        "medium": "#ffc107",
        "low": "#28a745",
    }
    return colors.get(severity, "#6c757d")
