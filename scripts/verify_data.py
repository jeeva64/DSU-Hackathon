from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.db.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("=== BUSINESS LOGIC CHECK ===")
print("  Avg rain by risk level:")
for row in db.execute(
    text(
        "SELECT weather_risk, avg(rainfall_mm)::numeric(6,1) as avg_rain, count(*) "
        "FROM weather_conditions GROUP BY weather_risk ORDER BY avg_rain DESC"
    )
):
    print(f"    {row[0]:<10s} avg_rain={row[1]:>6}  n={row[2]}")

print("  Moisture stats:")
for row in db.execute(
    text(
        "SELECT grade, avg(moisture_pct)::numeric(5,1) as avg_m, count(*) "
        "FROM procurement_records GROUP BY grade ORDER BY grade"
    )
):
    print(f"    grade={row[0]}  avg_moisture={row[1]}  n={row[2]}")

print("  Avg moisture by status:")
for row in db.execute(
    text(
        "SELECT status, avg(moisture_pct)::numeric(5,1) as avg_m "
        "FROM procurement_records GROUP BY status"
    )
):
    print(f"    {row[0]:<10s} avg_moisture={row[1]}")

print("  Arrival counts by DPC (per day avg):")
for row in db.execute(
    text(
        "SELECT dpc_id, count(*)::numeric(6,1) / " + str(14) + " as per_day " + " "
        "FROM arrival_records GROUP BY dpc_id ORDER BY per_day DESC"
    )
):
    print(f"    dpc={row[0]}  per_day={row[1]:.2f}")

print("  Weekend vs weekday arrival rate:")
for row in db.execute(
    text(
        "SELECT CASE WHEN EXTRACT(DOW FROM date) >= 5 THEN 'weekend' ELSE 'weekday' END as day_type, "
        "count(*) as total, round(count(*)/14.0, 2) as per_day "
        "FROM arrival_records GROUP BY day_type"
    )
):
    print(f"    {row[0]:<8s} total={row[1]:>4d}  per_day={row[2]}")

db.close()
print("\nDONE")