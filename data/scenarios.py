from __future__ import annotations

SCENARIO_CONFIGS = {
    "NORMAL_DAY": {
        "description": "Typical procurement day with moderate arrivals and normal operations",
        "parameters": {
            "arrival_multiplier": 1.0,
            "rain_mm": 0,
            "transport_multiplier": 1.0,
            "labour_multiplier": 1.0,
            "humidity": 60,
        },
    },
    "DPC_OVERLOAD": {
        "description": "High arrivals pushing DPC capacity limits",
        "parameters": {
            "arrival_multiplier": 1.5,
            "rain_mm": 0,
            "transport_multiplier": 1.0,
            "labour_multiplier": 1.0,
            "humidity": 55,
        },
    },
    "RAIN_RISK": {
        "description": "Heavy rain forecast threatening procurement and stored paddy",
        "parameters": {
            "arrival_multiplier": 0.7,
            "rain_mm": 25,
            "transport_multiplier": 0.7,
            "labour_multiplier": 0.9,
            "humidity": 85,
        },
    },
    "TRANSPORT_BOTTLENECK": {
        "description": "Limited transport preventing paddy movement from DPC to godown",
        "parameters": {
            "arrival_multiplier": 0.9,
            "rain_mm": 5,
            "transport_multiplier": 0.3,
            "labour_multiplier": 0.9,
            "humidity": 65,
        },
    },
    "COMBINED_CRISIS": {
        "description": "Multiple simultaneous crises: overload + rain + transport + labour constraints",
        "parameters": {
            "arrival_multiplier": 1.4,
            "rain_mm": 20,
            "transport_multiplier": 0.25,
            "labour_multiplier": 0.5,
            "humidity": 88,
        },
    },
}
