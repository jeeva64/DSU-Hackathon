# NelSync AI - demo frontend

Streamlit frontend for the NelSync AI hackathon MVP. AI assists, officers decide.

## What this is

A lightweight, offline-capable presentation layer over the FastAPI backend.
It calls the REST API under `/api/v1` and never touches Postgres directly.
Demo Mode ships with built-in synthetic data so the showcase works even when
the backend is not running - fallback values are always labeled
"Demo fallback data" / "Prototype / Synthetic Data".

## Setup

Requires Python 3.11.

```powershell
pip install -r frontend/requirements.txt
```

`pandas` and `numpy` are usually already installed (backend). The install step
needs internet once; runtime does not (no CDN assets, no remote calls except
the optional backend).

## Run

Start the backend first (optional; dashboard falls back to demo data otherwise):

```powershell
python run_backend.py
```

Then in a second shell:

```powershell
$env:BACKEND_URL="http://localhost:8000"
streamlit run frontend/streamlit_app.py
```

`BACKEND_URL` is optional and defaults to `http://localhost:8000`. You can also
create `frontend/.env` with `BACKEND_URL=http://localhost:8000` (see
`.env.example`) - the frontend reads it with a tiny built-in parser (no extra
dependency). Never commit real credentials; backend `.env` is separate and
gitignored.

## Pages

| Page | Backend source | Demo fallback |
| --- | --- | --- |
| Dashboard | `/health`, `/dpcs`, `/dpcs/{id}/capacity`, `/risks` | built-in snapshot |
| Procurement | `/farmers`, `/procurement`, `/procurement/summary` | built-in roster |
| DPC Monitoring | `/dpcs`, `/dpcs/{id}/capacity`, `/predictions/{dpc_id}` | built-in capacity |
| AI Predictions | `/ml/status`, `/ml/predict`, `/predictions/generate` | synthetic registry |
| Risk Center | `/risks` (risk engine) | built-in risk set |
| Scenario Simulation | `/scenarios`, `/scenarios/run` | deterministic engine mirror |

The sidebar **Demo Mode** toggle switches between synthetic data and live
backend queries. Default: ON (COMBINED_CRISIS scenario preselected).

## Risk Center endpoint

`GET /api/v1/risks?target_date=YYYY-MM-DD` was added to the backend to expose
the existing `RiskService.detect_risks()`. It returns a flat list of
`{risk_type, severity, dpc_id, dpc_name, description, metric}` items and
persists the detected assessments (existing service behavior).

## Notes / limitations

- Backend development is complete through the operational risk engine; no
  optimization/slot-scheduling endpoints exist yet.
- Farmer "Expected Arrival" is a prototype estimate (sowing date + ~120 days)
  and "Moisture Risk" is a deterministic prototype estimate - labeled as such.
- ML metrics show only real keys (`mae/rmse/mape/r2/rmse_scaled`,
  `accuracy/precision/recall/f1/roc_auc`). When models are not trained the UI
  says so and falls back to the statistical predictor or labeled synthetic
  values.
- Simulation "Recommended Actions" come from the real
  `POST /api/v1/scenarios/run` result (or the deterministic mirror offline).