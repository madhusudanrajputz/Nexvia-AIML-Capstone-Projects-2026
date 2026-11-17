
"""AIML-01 fraud scoring API.

Development mode is intentionally restricted to PaySim hour
377. Do not expose publicly until online feature freshness,
stream processing, authentication and durable recovery are
verified.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import xgboost as xgb

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROJECT = Path(os.environ["AIML01_PROJECT"])
FEAST_REPO = Path(os.environ["AIML01_FEAST_REPO"])
FEAST_PYTHON = Path(os.environ["AIML01_FEAST_PYTHON"])
STEP = 377
THRESHOLD = 0.48456997

sys.path.insert(0, str(PROJECT / "scripts"))
from fraud_serving_features import build_features

ORDER = json.loads(
    (PROJECT / "features/XGBoost_Feature_Contract.json")
    .read_text(encoding="utf-8")
)["feature_names_ordered"]

MODEL = xgb.Booster()
MODEL.load_model(str(
    PROJECT / "models/xgboost/XGBoost_Unweighted_Baseline.json"
))
assert MODEL.num_features() == 23
assert len(ORDER) == 23
if MODEL.feature_names is not None:
    assert MODEL.feature_names == ORDER

app = FastAPI(
    title="AIML-01 Fraud Detection API",
    version="0.1.0-dev"
)

class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    transaction_id: int = Field(gt=0)
    step: int = Field(gt=0)
    event_timestamp: str
    type: Literal[
        "CASH_IN", "CASH_OUT", "DEBIT",
        "PAYMENT", "TRANSFER"
    ]
    amount: float = Field(ge=0, allow_inf_nan=False)
    nameOrig: str = Field(min_length=1)
    nameDest: str = Field(min_length=1)
    oldbalanceOrg: float = Field(ge=0, allow_inf_nan=False)
    oldbalanceDest: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def verify_identity_and_time(self):
        expected = (
            datetime(2026, 1, 1, tzinfo=timezone.utc)
            + timedelta(hours=self.step)
        ).isoformat()
        if self.event_id != f"paysim:{self.transaction_id}":
            raise ValueError("Inconsistent event ID")
        if self.event_timestamp != expected:
            raise ValueError("Incorrect event timestamp")
        if self.nameOrig == self.nameDest:
            raise ValueError("Same-account transfer unsupported")
        return self

# The separate Feast virtualenv is required because Feast
# is not installed in Colab's main Python environment.
FEAST_WORKER = r"""
import json
import os
import sys
from feast import FeatureStore

store = FeatureStore(repo_path=os.environ["AIML01_FEAST_REPO"])
entity = json.loads(sys.stdin.read())

fields = [
    "origin_previous_count",
    "origin_previous_total",
    "origin_previous_mean",
    "origin_hours_since_previous",
    "destination_previous_count",
    "destination_previous_total",
    "destination_previous_mean",
    "destination_hours_since_previous"
]
refs = [
    ("origin_account_history:" if f.startswith("origin_")
     else "destination_account_history:") + f
    for f in fields
]

result = store.get_online_features(
    features=refs,
    entity_rows=[entity],
    full_feature_names=True
).to_dict()

values = {}
for name in fields:
    prefix = (
        "origin_account_history__"
        if name.startswith("origin_")
        else "destination_account_history__"
    )
    key = prefix + name
    if key not in result:
        raise RuntimeError("Missing Feast column: " + key)
    values[name] = result[key][0]

print("FEATURE_JSON_BEGIN")
print(json.dumps(values, allow_nan=False))
print("FEATURE_JSON_END")
"""

def fetch_history(event):
    environment = dict(os.environ)
    environment["AIML01_FEAST_REPO"] = str(FEAST_REPO)

    process = subprocess.run(
        [str(FEAST_PYTHON), "-c", FEAST_WORKER],
        input=json.dumps({
            "nameOrig": event.nameOrig,
            "nameDest": event.nameDest
        }),
        capture_output=True,
        text=True,
        env=environment,
        timeout=60
    )

    if process.returncode:
        raise RuntimeError(
            "Feast online retrieval process failed"
        )

    marker1 = "FEATURE_JSON_BEGIN"
    marker2 = "FEATURE_JSON_END"

    if marker1 not in process.stdout:
        raise RuntimeError("Feast response marker missing")

    payload = process.stdout.split(marker1, 1)[1].split(
        marker2, 1
    )[0].strip()

    values = json.loads(payload)

    if any(value is None for value in values.values()):
        raise LookupError("Account historical state unavailable")

    return values

@app.get("/health")
def health():
    return {
        "status": "development_ready",
        "model_loaded": True,
        "feature_count": 23,
        "fixed_hour": STEP,
        "live_streaming_ready": False
    }

@app.post("/predict")
def predict(event: Transaction):
    if event.step != STEP:
        raise HTTPException(
            status_code=409,
            detail="Online state not synchronized for this step"
        )

    started = time.perf_counter()

    try:
        history = fetch_history(event)
        frame = build_features(
            [{
                "type": event.type,
                "amount": event.amount,
                "oldbalanceOrg": event.oldbalanceOrg,
                "oldbalanceDest": event.oldbalanceDest
            }],
            [history]
        )
        assert list(frame.columns) == ORDER

        matrix = xgb.DMatrix(frame, feature_names=ORDER)
        probability = float(MODEL.predict(matrix)[0])

        if not np.isfinite(probability):
            raise ValueError("Nonfinite model output")

    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(
            status_code=503,
            detail="Historical feature service unavailable"
        )

    flagged = probability >= THRESHOLD

    return {
        "event_id": event.event_id,
        "transaction_id": event.transaction_id,
        "fraud_probability": probability,
        "decision_threshold": THRESHOLD,
        "fraud_alert": bool(flagged),
        "prediction_status": (
            "FLAGGED_FOR_REVIEW" if flagged
            else "NOT_FLAGGED"
        ),
        "feature_count": 23,
        "serving_mode": "fixed_hour_development",
        "latency_ms": round(
            (time.perf_counter() - started) * 1000, 3
        )
    }
