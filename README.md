# NelSync AI

AI-assisted decision-support prototype for Tamil Nadu paddy procurement coordination.

> **Status:** MVP Prototype | **Data:** Synthetic Demo Data Only

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 14+

### 2. Setup

```bash
# Clone and enter project
cd "NelSync AI"

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# Edit .env with your PostgreSQL credentials
```

### 3. Database

```bash
# Create database (adjust user/password as needed)
psql -U postgres -c "CREATE DATABASE nelsync_ai;"
```

### 4. Run

```bash
# Start backend (auto-creates tables on first run)
python run_backend.py
```

The API is available at http://localhost:8000

### 5. Verify

```bash
# Health check
curl http://localhost:8000/api/v1/health
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/farmers` | GET/POST | List/create farmers |
| `/api/v1/farmers/{id}` | GET | Get farmer by ID |
| `/api/v1/dpcs` | GET/POST | List/create DPCs |
| `/api/v1/dpcs/{id}` | GET | Get DPC by ID |
| `/api/v1/dpcs/{id}/capacity` | GET | Get DPC capacity |
| `/api/v1/procurement` | GET/POST | List/create procurement |
| `/api/v1/procurement/summary` | GET | Procurement summary |
| `/api/v1/predictions/generate` | POST | Generate predictions |
| `/api/v1/predictions/{dpc_id}` | GET | Get predictions |
| `/api/v1/recommendations` | GET | List recommendations |
| `/api/v1/recommendations/{id}` | GET | Get recommendation by ID |
| `/api/v1/recommendations/pending` | GET | List pending recommendations |
| `/api/v1/recommendations/analysis` | POST | Run slot recommendation analysis (engine) |
| `/api/v1/recommendations/optimize` | POST | Optimize: rank feasible actions, select the best (engine) |
| `/api/v1/recommendations/{id}/approve` | POST | Approve (prototype workflow state change) |
| `/api/v1/recommendations/{id}/reject` | POST | Reject (prototype workflow state change) |
| `/api/v1/scenarios` | GET | List scenarios |
| `/api/v1/scenarios/run` | POST | Run scenario |

## Slot Recommendation Engine

`POST /api/v1/recommendations/analysis` runs a **deterministic, explainable engine**
(`SlotRecommender` in `backend/app/services/slot_recommendation_service.py`) — no LLM.

Inputs (from the seeded tables): predicted arrivals/quantity, current slot bookings,
DPC/slot capacity, processing rate, weather risk, farmer harvest readiness, transport,
labour, and storage availability.

Engine behaviour:
- Detects **overloaded** slots/DPCs (≥85% projected load; ≥95% critical)
- Detects **underutilized** slots (≤30%)
- Finds feasible alternative slots and nearby/alternative DPCs (same-district preferred,
  haversine distance otherwise)
- Recommends **redistribution** while never exceeding a 90% target-load ceiling
- Prioritizes **ready/overdue** farmers
- Computes **expected impact** (source/target utilization delta + queue relief)

Feasibility = weighted sum of six scores:
capacity (0.30), time (0.15), weather (0.15), resource (0.15), assignment (0.10),
processing (0.15) → 0–100.

Each recommendation carries `priority`, `action`, `source`, `target`, `farmer_count`,
`quantity`, `reason` (`explanation`), `expected_impact`, `feasibility_score`, and a
per-dimension `scores` breakdown. Results are persisted as `Recommendation` rows so the
officer can approve/reject them — a **prototype workflow state change only**; the system
never executes scheduling decisions automatically.

## Optimization Engine

`POST /api/v1/recommendations/optimize` runs a **deterministic, explainable engine**
(`OptimizationEngine` + `OptimizationService` in
`backend/app/services/optimization_service.py`) — no LLM. It composes the same context
builder as the slot engine and simulates candidate actions against the DPC states to
select the **single best feasible action**:

- Candidates: `no_action`, `divert_to_dpc`, `redistribute_slots`, `boost_resources`,
  `weather_reschedule`, `prioritize_ready_farmers`, `open_underutilized_slots`
- Hard gates (fail → infeasible, or clamp the quantity): target must be `active`;
  projected target load stays ≤ 90%; trucks needed = `ceil(qty/100)` (0 → infeasible,
  shortfall clamps qty); staff needed = `ceil(farmers/10)` (0 → infeasible); storage
  slack must absorb the moved quantity
- Selection: weighted before→after simulation across six dimensions — congestion
  reduction (0.30), capacity utilization (0.15), expected delay reduction (0.15),
  weather exposure reduction (0.15), resource feasibility (0.15), operational balance
  (0.10) → 0–100
- If nothing beats `no_action` by the selection threshold, the system honestly reports
  that no material action is needed

By default the winning action is persisted as a `Recommendation` row (id returned in
`selected_recommendation.id`) so it flows through the same officer approve/reject
workflow.

## Architecture

```
Streamlit → FastAPI → API Routers → Services → Repositories → PostgreSQL
                        ↓
              ML / Risk / Recommendation engines
```

## Important Notes

- All data is **synthetic and for demonstration only**
- This system does **not** make autonomous government decisions
- AI provides predictions and recommendations; officers decide
- The system works fully **offline** without LLM API keys
