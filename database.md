# NelSync AI — Database Documentation

> **Status:** MVP Prototype | **Data:** Synthetic Demo Data Only
> **ORM:** SQLAlchemy 2.0 (Mapped + mapped_column style)
> **Database:** PostgreSQL | **Tables:** 13

---

## Table of Contents

1. [ER Diagram](#er-diagram)
2. [Tables](#tables)
3. [Enums](#enums)
4. [Relationships](#relationships)
5. [Indexes & Constraints](#indexes--constraints)
6. [Seeding](#seeding)

---

## ER Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          NelSync AI — Entity Relationship Diagram               │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────┐
                                    │   farmers     │
                                    ├──────────────┤
                                    │ PK id         │
                                    │    farmer_code│ UNIQUE
                                    │    name       │
                                    │    village    │
                                    │    district   │ INDEX
                                    │    location_area
                                    │    cultivated_area
                                    │    paddy_variety
                                    │    expected_quantity
                                    │    harvest_readiness  FK→enum
                                    │    mobile      │
                                    │    sowing_date │
                                    │    created_at  │
                                    └──────┬───────┘
                                           │
                          ┌────────────────┼────────────────┐
                          │                │                │
                          │ 1:N            │ 1:N            │ 1:N
                          ▼                ▼                │
              ┌───────────────────┐  ┌──────────────────┐   │
              │ procurement_records│  │ arrival_records  │   │
              ├───────────────────┤  ├──────────────────┤   │
              │ PK id             │  │ PK id            │   │
              │ FK farmer_id      │  │ FK farmer_id     │───┘
              │ FK dpc_id         │  │ FK dpc_id        │
              │    date           │  │ FK slot_id       │ NULLABLE
              │    bags           │  │    date          │
              │    quantity_quintal│  │    arrival_time  │
              │    moisture_pct   │  │    bags_brought  │
              │    grade          │  │    quantity_brought
              │    status         │  │    wait_time_min │
              │    created_at     │  │    status        │
              └────────┬──────────┘  │    created_at    │
                       │             └────────┬─────────┘
                       │                      │
                       │ N:1                  │ N:1
                       ▼                      ▼
              ┌────────────────────────────────────────────┐
              │                   dpcs                      │
              ├────────────────────────────────────────────┤
              │ PK id                                       │
              │    dpc_code              UNIQUE              │
              │    name                                     │
              │    district               INDEX              │
              │    daily_capacity                           │
              │    processing_rate                          │
              │    storage_capacity                         │
              │    operating_status     FK→enum              │
              │    lat, lon                                │
              │    open_date, close_date                    │
              │    created_at                              │
              └──┬──────┬──────┬──────┬──────┬──────┬──────┘
                 │      │      │      │      │      │
                 │      │      │      │      │      │
        ┌────────┘   ┌──┘   ┌──┘   ┌──┘   ┌──┘   └────────┐
        │ 1:N        │1:N   │1:N   │1:N   │1:N          │1:N
        ▼            ▼      ▼      ▼      ▼              ▼
 ┌────────────┐ ┌───────┐ ┌────┐ ┌────┐ ┌──────────┐ ┌────────────┐
 │dpc_capacit.│ │ slots │ │res.│ │pre-│ │risk_asses│ │recommendat.│
 ├────────────┤ ├───────┤ ├────┤ ├────┤ ├──────────┤ ├────────────┤
 │PK id       │ │PK id  │ │PK  │ │PK  │ │PK id     │ │PK id       │
 │FK dpc_id   │ │FK dpc │ │id  │ │id  │ │FK dpc_id │ │FK dpc_id   │ NULLABLE
 │   date     │ │  _id  │ │    │ │    │ │   date   │ │   date     │
 │   planned  │ │  date │ │FK  │ │FK  │ │risk_type │ │rec_type    │
 │   _capacity│ │start  │ │dpc │ │dpc │ │severity  │ │priority    │
 │   used     │ │ _time │ │ _id│ │ _id│ │score     │ │title       │
 │   _capacity│ │end    │ │    │ │    │ │explanation│ │explanation │
 │   remaining│ │ _time │ │date│ │    │ │mitigation│ │expected    │
 │   _capacity│ │max    │ │    │ │pred│ │created_at│ │ _impact    │
 │   utilizat.│ │ _farm.│ │lab.│ │_val│ └──────────┘ │status      │
 │   _pct     │ │max    │ │_av.│ │    │              │officer     │
 │   created  │ │ _qty  │ │    │ │conf│              │ _notes     │
 │   _at      │ │booked │ │trn │ │    │              │created_at  │
 │UNIQUE(dpc, │ │ _farm.│ │_av.│ │pred│              │updated_at  │
 │  date)     │ │booked │ │    │ │_dat│              └──────┬─────┘
 └────────────┘ │ _qty  │ │wgh.│ │e   │                     │ 1:N
                │status │ │_cap│ │targ│                     │
                │created│ │    │ │_dat│                     ▼
                │ _at    │ │stor│ │    │          ┌──────────────────┐
                └────────┘ │_av.│ │pred│          │recommendation_   │
                           │    │ │_typ│          │    actions       │
                           │creat│ │e   │          ├──────────────────┤
                           │ _at │ │mode│          │PK id             │
                           └─────┘ │l_ver│         │FK recommendation │
                                   │created│        │   _id            │
                                   │ _at   │        │action            │
                                   └───────┘        │FK source_dpc_id  │ NULLABLE
                                                    │FK target_dpc_id  │ NULLABLE
                      ┌──────────────┐              │FK source_slot_id │ NULLABLE
                      │   weather    │              │FK target_slot_id │ NULLABLE
                      │  _conditions │              │quantity          │
                      ├──────────────┤              │rationale         │
                      │PK id         │              │created_at        │
                      │  date        │              └──────────────────┘
                      │  location    │
                      │  rainfall_   │
                      │   probability│
                      │  rainfall_mm │
                      │  humidity    │
                      │  temperature │
                      │   _max       │
                      │  weather_risk│
                      │  created_at  │
                      │UNIQUE(date,  │
                      │  location)   │
                      └──────────────┘

                      ┌──────────────────┐
                      │simulation_       │
                      │   scenarios      │
                      ├──────────────────┤
                      │PK id             │
                      │  name            │ UNIQUE
                      │  description     │
                      │  parameters      │ JSON
                      │  results_json    │ JSON
                      │  status          │ FK→enum
                      │  created_at      │
                      └──────────────────┘
```

---

## Tables

### 1. farmers

Stores registered farmer information.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `farmer_code` | String(50) | No | — | **Unique**. e.g. `FRM-001` |
| `name` | String(255) | No | — | Full name |
| `village` | String(255) | No | — | Village name |
| `district` | String(255) | No | — | **Indexed** |
| `location_area` | String(255) | Yes | NULL | Lat/lon or area description |
| `cultivated_area` | Float | No | — | Acres under cultivation |
| `paddy_variety` | String(100) | No | `'paddy'` | e.g. `CO-51`, `CR-1009` |
| `expected_quantity` | Float | Yes | NULL | Expected yield in quintals |
| `harvest_readiness` | Enum | Yes | NULL | `not_ready`, `partially_ready`, `ready`, `overdue` |
| `mobile` | String(15) | Yes | NULL | Contact number |
| `sowing_date` | Date | Yes | NULL | Date of sowing |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

---

### 2. dpcs

Distribution and Procurement Centers.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_code` | String(50) | No | — | **Unique**. e.g. `DPC-001` |
| `name` | String(255) | No | — | Center name |
| `district` | String(255) | No | — | **Indexed** |
| `daily_capacity` | Integer | No | 1000 | Max bags per day |
| `processing_rate` | Float | Yes | NULL | Bags processed per hour |
| `storage_capacity` | Float | No | 250.0 | Storage in metric tonnes |
| `operating_status` | Enum | No | `'active'` | `active`, `maintenance`, `closed`, `overloaded` |
| `lat` | Float | Yes | NULL | Latitude |
| `lon` | Float | Yes | NULL | Longitude |
| `open_date` | Date | Yes | NULL | Season opening date |
| `close_date` | Date | Yes | NULL | Season closing date |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

---

### 3. procurement_records

Individual procurement transactions (Farmer → DPC).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `farmer_id` | Integer | No | — | **FK → farmers.id**, indexed |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `date` | Date | No | — | **Indexed**. Procurement date |
| `bags` | Integer | No | — | Number of bags |
| `quantity_quintal` | Float | No | — | Total weight in quintals |
| `moisture_pct` | Float | No | — | Moisture content % |
| `grade` | String(10) | Yes | NULL | Quality grade (A, B, C) |
| `status` | Enum | No | `'pending'` | `accepted`, `rejected`, `pending` |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Composite index:** `(dpc_id, date)`

---

### 4. dpc_capacities

Daily capacity tracking per DPC.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `date` | Date | No | — | Capacity date |
| `planned_capacity` | Integer | No | — | Bags planned for the day |
| `used_capacity` | Integer | No | 0 | Bags processed so far |
| `remaining_capacity` | Integer | No | — | Bags remaining |
| `utilization_pct` | Float | No | 0.0 | `used / planned * 100` |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Unique constraint:** `(dpc_id, date)`

---

### 5. slots

Time-based booking slots at DPCs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `date` | Date | No | — | Slot date |
| `start_time` | Time | No | — | Slot start time |
| `end_time` | Time | No | — | Slot end time |
| `max_farmers` | Integer | No | 50 | Max farmers in slot |
| `max_quantity` | Float | No | 200.0 | Max quantity (quintals) |
| `booked_farmers` | Integer | No | 0 | Farmers booked |
| `booked_quantity` | Float | No | 0.0 | Quantity booked |
| `status` | Enum | No | `'available'` | `available`, `partially_booked`, `full`, `closed` |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Composite index:** `(dpc_id, date, start_time)`

---

### 6. arrival_records

Tracks farmer arrivals at DPCs.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `farmer_id` | Integer | No | — | **FK → farmers.id**, indexed |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `slot_id` | Integer | Yes | NULL | **FK → slots.id**, indexed. NULL for walk-ins |
| `date` | Date | No | — | **Indexed**. Arrival date |
| `arrival_time` | DateTime | No | — | Exact arrival timestamp |
| `bags_brought` | Integer | No | — | Bags brought by farmer |
| `quantity_brought` | Float | No | — | Quantity in quintals |
| `wait_time_minutes` | Integer | Yes | NULL | Measured after processing |
| `status` | Enum | No | `'pending'` | `accepted`, `rejected`, `pending` |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Composite index:** `(dpc_id, date)`

---

### 7. resource_availability

Daily resource availability per DPC.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `date` | Date | No | — | Resource date |
| `labour_available` | Integer | No | 0 | Number of workers |
| `transport_available` | Integer | No | 0 | Number of vehicles |
| `weighing_capacity` | Integer | No | 0 | Weighments per hour |
| `storage_available` | Float | No | 0.0 | Available storage in MT |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Unique constraint:** `(dpc_id, date)`

---

### 8. weather_conditions

Weather data per location per date.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `date` | Date | No | — | Weather date |
| `location` | String(255) | No | — | District or DPC name |
| `rainfall_probability` | Float | No | 0.0 | 0–100% |
| `rainfall_mm` | Float | No | 0.0 | Actual/forecast rainfall in mm |
| `humidity` | Float | No | 50.0 | 0–100% |
| `temperature_max` | Float | Yes | NULL | Max temperature in °C |
| `weather_risk` | Enum | No | `'none'` | `none`, `low`, `medium`, `high`, `critical` |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Unique constraint:** `(date, location)`

---

### 9. predictions

ML prediction results per DPC per target date.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `prediction_date` | Date | No | — | **Indexed**. When prediction was made |
| `target_date` | Date | No | — | **Indexed**. What date is being predicted |
| `prediction_type` | Enum | No | — | `arrival_count`, `quantity`, `queue_length`, `processing_time` |
| `predicted_value` | Float | No | — | Predicted numeric value |
| `confidence` | Float | No | — | Confidence score 0–1 |
| `model_version` | String(50) | No | `'v0.1'` | Model version used |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Composite index:** `(dpc_id, target_date, prediction_type)`

---

### 10. risk_assessments

Detected operational risks per DPC.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_id` | Integer | No | — | **FK → dpcs.id**, indexed |
| `date` | Date | No | — | Risk assessment date |
| `risk_type` | Enum | No | — | `overload`, `congestion`, `rain`, `transport`, `labour`, `storage`, `moisture`, `combined` |
| `severity` | Enum | No | — | `low`, `medium`, `high`, `critical` |
| `score` | Float | No | — | Risk score 0–100 (higher = worse) |
| `explanation` | Text | No | — | Human-readable explanation |
| `mitigation` | Text | Yes | NULL | Suggested mitigation action |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

**Composite index:** `(dpc_id, date, risk_type)`

---

### 11. recommendations

AI-generated recommendations.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `dpc_id` | Integer | Yes | NULL | **FK → dpcs.id**, indexed. NULL for system-wide recs |
| `date` | Date | No | — | **Indexed**. Recommendation date |
| `recommendation_type` | Enum | No | — | `slot`, `resource`, `risk`, `weather` |
| `priority` | Enum | No | — | `low`, `medium`, `high`, `critical` |
| `title` | String(500) | No | — | Short title |
| `explanation` | Text | No | — | Detailed reasoning |
| `expected_impact` | Text | No | — | Expected effect if implemented |
| `status` | Enum | No | `'pending'` | `pending`, `approved`, `rejected` |
| `officer_notes` | Text | Yes | NULL | Officer's notes on decision |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |
| `updated_at` | DateTime(tz) | Yes | NULL | Auto-updated on change |

---

### 12. recommendation_actions

Specific actions for approved recommendations.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `recommendation_id` | Integer | No | — | **FK → recommendations.id**, indexed |
| `action` | String(255) | No | — | e.g. `divert_farmers`, `add_staff`, `cover_paddy` |
| `source_dpc_id` | Integer | Yes | NULL | **FK → dpcs.id**. DPC to divert FROM |
| `target_dpc_id` | Integer | Yes | NULL | **FK → dpcs.id**. DPC to divert TO |
| `source_slot_id` | Integer | Yes | NULL | **FK → slots.id**. Source slot |
| `target_slot_id` | Integer | Yes | NULL | **FK → slots.id**. Target slot |
| `quantity` | Float | Yes | NULL | Quintals affected |
| `rationale` | Text | No | — | Why this action is recommended |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

---

### 13. simulation_scenarios

What-if scenario configurations and results.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | Integer | No | auto PK | Primary key |
| `name` | String(255) | No | — | **Unique**. Scenario identifier |
| `description` | Text | No | — | Human-readable description |
| `parameters` | JSON | No | — | Input parameters (arrival_multiplier, rain_mm, etc.) |
| `results_json` | JSON | Yes | NULL | Computed results |
| `status` | Enum | No | `'draft'` | `draft`, `running`, `completed`, `failed` |
| `created_at` | DateTime(tz) | No | `now()` | Record creation timestamp |

---

## Enums

| Enum | Values | Used By |
|------|--------|---------|
| `ProcurementStatus` | `accepted`, `rejected`, `pending` | procurement_records, arrival_records |
| `OperatingStatus` | `active`, `maintenance`, `closed`, `overloaded` | dpcs |
| `HarvestReadiness` | `not_ready`, `partially_ready`, `ready`, `overdue` | farmers |
| `SlotStatus` | `available`, `partially_booked`, `full`, `closed` | slots |
| `WeatherRisk` | `none`, `low`, `medium`, `high`, `critical` | weather_conditions |
| `PredictionType` | `arrival_count`, `quantity`, `queue_length`, `processing_time` | predictions |
| `RiskType` | `overload`, `congestion`, `rain`, `transport`, `labour`, `storage`, `moisture`, `combined` | risk_assessments |
| `RiskSeverity` | `low`, `medium`, `high`, `critical` | risk_assessments |
| `RecommendationType` | `slot`, `resource`, `risk`, `weather` | recommendations |
| `RecommendationPriority` | `low`, `medium`, `high`, `critical` | recommendations |
| `RecommendationStatus` | `pending`, `approved`, `rejected` | recommendations |
| `SimulationStatus` | `draft`, `running`, `completed`, `failed` | simulation_scenarios |

---

## Relationships

```
farmers (1) ────── (N) procurement_records     via farmer_id
farmers (1) ────── (N) arrival_records          via farmer_id
dpcs (1)    ────── (N) procurement_records     via dpc_id
dpcs (1)    ────── (N) dpc_capacities          via dpc_id
dpcs (1)    ────── (N) slots                   via dpc_id
dpcs (1)    ────── (N) arrival_records         via dpc_id
dpcs (1)    ────── (N) resource_availability   via dpc_id
dpcs (1)    ────── (N) predictions             via dpc_id
dpcs (1)    ────── (N) risk_assessments        via dpc_id
dpcs (1)    ────── (N) recommendations         via dpc_id (nullable)
dpcs (1)    ────── (N) recommendation_actions  via source_dpc_id (nullable)
dpcs (1)    ────── (N) recommendation_actions  via target_dpc_id (nullable)
slots (1)   ────── (N) arrival_records         via slot_id (nullable)
slots (1)   ────── (N) recommendation_actions  via source_slot_id (nullable)
slots (1)   ────── (N) recommendation_actions  via target_slot_id (nullable)
recommendations (1) ── (N) recommendation_actions via recommendation_id
```

**No ORM `relationship()` calls** — all joins are performed at query time in repositories.

---

## Indexes & Constraints

### Primary Keys
All 13 tables have an auto-incrementing `id` primary key.

### Unique Constraints
| Table | Column(s) | Purpose |
|-------|-----------|---------|
| `farmers` | `farmer_code` | Unique farmer identifier |
| `dpcs` | `dpc_code` | Unique DPC identifier |
| `dpc_capacities` | `(dpc_id, date)` | One capacity record per DPC per day |
| `resource_availability` | `(dpc_id, date)` | One resource record per DPC per day |
| `weather_conditions` | `(date, location)` | One weather record per location per day |
| `simulation_scenarios` | `name` | Unique scenario name |

### Single-Column Indexes
| Table | Column | Purpose |
|-------|--------|---------|
| `farmers` | `district` | Filter by district |
| `dpcs` | `district` | Filter by district |
| `procurement_records` | `farmer_id` | Farmer lookup |
| `procurement_records` | `dpc_id` | DPC lookup |
| `procurement_records` | `date` | Date range queries |
| `arrival_records` | `farmer_id` | Farmer lookup |
| `arrival_records` | `dpc_id` | DPC lookup |
| `arrival_records` | `date` | Date range queries |
| `arrival_records` | `slot_id` | Slot lookup |
| `dpc_capacities` | `dpc_id` | DPC lookup |
| `slots` | `dpc_id` | DPC lookup |
| `resource_availability` | `dpc_id` | DPC lookup |
| `predictions` | `dpc_id` | DPC lookup |
| `predictions` | `prediction_date` | When prediction was made |
| `predictions` | `target_date` | What date is predicted |
| `risk_assessments` | `dpc_id` | DPC lookup |
| `recommendations` | `dpc_id` | DPC lookup |
| `recommendations` | `date` | Date range queries |
| `recommendation_actions` | `recommendation_id` | Recommendation lookup |

### Composite Indexes
| Table | Columns | Purpose |
|-------|---------|---------|
| `procurement_records` | `(dpc_id, date)` | Daily DPC procurement queries |
| `arrival_records` | `(dpc_id, date)` | Daily DPC arrival queries |
| `slots` | `(dpc_id, date, start_time)` | Slot availability lookups |
| `predictions` | `(dpc_id, target_date, prediction_type)` | Prediction lookups |
| `risk_assessments` | `(dpc_id, date, risk_type)` | Risk lookups |

### Foreign Keys
| Table | Column | References | On Delete |
|-------|--------|-----------|-----------|
| `procurement_records` | `farmer_id` | `farmers.id` | RESTRICT |
| `procurement_records` | `dpc_id` | `dpcs.id` | RESTRICT |
| `arrival_records` | `farmer_id` | `farmers.id` | RESTRICT |
| `arrival_records` | `dpc_id` | `dpcs.id` | RESTRICT |
| `arrival_records` | `slot_id` | `slots.id` | SET NULL |
| `dpc_capacities` | `dpc_id` | `dpcs.id` | RESTRICT |
| `slots` | `dpc_id` | `dpcs.id` | RESTRICT |
| `resource_availability` | `dpc_id` | `dpcs.id` | RESTRICT |
| `predictions` | `dpc_id` | `dpcs.id` | RESTRICT |
| `risk_assessments` | `dpc_id` | `dpcs.id` | RESTRICT |
| `recommendations` | `dpc_id` | `dpcs.id` | SET NULL |
| `recommendation_actions` | `recommendation_id` | `recommendations.id` | RESTRICT |
| `recommendation_actions` | `source_dpc_id` | `dpcs.id` | SET NULL |
| `recommendation_actions` | `target_dpc_id` | `dpcs.id` | SET NULL |
| `recommendation_actions` | `source_slot_id` | `slots.id` | SET NULL |
| `recommendation_actions` | `target_slot_id` | `slots.id` | SET NULL |

---

## Seeding

The `data/seed.py` module creates realistic demo data:

- **5 villages** in Thanjavur district
- **20 farmers** across villages with varied paddy varieties
- **4 DPCs** with realistic Tamil Nadu names
- **60 days** of procurement history with weather-driven patterns
- **Daily capacity records** for each DPC
- **Time slots** per DPC per day (morning, afternoon, evening)
- **Resource availability** per DPC per day
- **Weather conditions** matching NE monsoon patterns
- **Arrival records** linked to farmers and slots
- **Pre-seeded scenarios**: NORMAL_DAY, DPC_OVERLOAD, RAIN_RISK, TRANSPORT_BOTTLENECK, COMBINED_CRISIS

### Run Seeding

```bash
python -c "from data.seed import seed_all; seed_all()"
```

---

## File Reference

| Layer | Files |
|-------|-------|
| Models | `backend/app/models/*.py` (13 files) |
| Schemas | `backend/app/schemas/*.py` (14 files) |
| Repositories | `backend/app/repositories/*.py` (13 files) |
| Services | `backend/app/services/*.py` (6 files) |
| API Endpoints | `backend/app/api/v1/endpoints/*.py` (7 files) |
| Seeding | `data/seed.py` |
| Tests | `tests/test_models.py`, `tests/conftest.py` |
