
"""AIML-01 development FastAPI adapter with persistent Feast.

Local-only, fixed-hour 377 compatibility mode.
Not production-ready until event-time state updates,
authentication and operational recovery are integrated.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fraud_api as original

FEAST_URL = os.environ["AIML01_FEAST_SERVICE_URL"].rstrip("/")


def persistent_fetch_history(event):
    data = json.dumps({
        "nameOrig": event.nameOrig,
        "nameDest": event.nameDest
    }).encode("utf-8")

    req = urllib.request.Request(
        FEAST_URL + "/features",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            req, timeout=8
        ) as response:
            values = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise LookupError("Account historical state unavailable")
        raise RuntimeError("Persistent Feast service HTTP failure")
    except (OSError, ValueError) as error:
        raise RuntimeError("Persistent Feast service unavailable") from error

    required = (
        "origin_previous_count",
        "origin_previous_total",
        "origin_previous_mean",
        "origin_hours_since_previous",
        "destination_previous_count",
        "destination_previous_total",
        "destination_previous_mean",
        "destination_hours_since_previous"
    )

    if set(values) != set(required):
        raise RuntimeError("Incorrect Feast feature schema")

    if any(values[field] is None for field in required):
        raise LookupError("Missing historical account features")

    return values


original.fetch_history = persistent_fetch_history
app = original.app
