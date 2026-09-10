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
| `/api/v1/recommendations/{id}/approve` | POST | Approve |
| `/api/v1/recommendations/{id}/reject` | POST | Reject |
| `/api/v1/scenarios` | GET | List scenarios |
| `/api/v1/scenarios/run` | POST | Run scenario |

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
