from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any

DEMO_PATIENT_ID = "DEMO-001"


def validate_request(patient_id: str, delay_seconds: float) -> None:
    if patient_id != DEMO_PATIENT_ID:
        raise ValueError("Only the synthetic patient DEMO-001 is available.")
    if not math.isfinite(delay_seconds) or not 0 <= delay_seconds <= 30:
        raise ValueError("delay_seconds must be finite and between 0 and 30.")


async def fetch_electrolyte_panel(
    patient_id: str, delay_seconds: float = 2.5
) -> dict[str, Any]:
    validate_request(patient_id, delay_seconds)
    await asyncio.sleep(delay_seconds)
    return {
        "patient_id": patient_id,
        "synthetic": True,
        "panel": "electrolytes",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "potassium": {
            "value": 3.1,
            "unit": "mEq/L",
            "flag": "CRITICAL LOW",
        },
        "sodium": {"value": 138, "unit": "mEq/L", "flag": "NORMAL"},
        "critical": True,
        "flag_policy": "Hackathon fixture; not a validated laboratory threshold.",
    }


async def fetch_arterial_blood_gas(
    patient_id: str, delay_seconds: float = 0.5
) -> dict[str, Any]:
    validate_request(patient_id, delay_seconds)
    await asyncio.sleep(delay_seconds)
    return {
        "patient_id": patient_id,
        "synthetic": True,
        "panel": "abg",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "ph": {"value": 7.26, "unit": "", "flag": "ACIDOSIS"},
        "pco2": {"value": 48, "unit": "mmHg", "flag": "HIGH"},
        "critical": True,
        "flag_policy": "Hackathon fixture; clinician interpretation required.",
    }