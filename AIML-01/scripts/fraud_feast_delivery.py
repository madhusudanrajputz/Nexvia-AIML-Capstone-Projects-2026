
"""Deliver pending durable outbox tasks to Feast.

Usage:
    python fraud_feast_delivery.py DB_PATH FEAST_REPO

The caller must ensure:
- a single writer for a given outbox,
- finalized event-hour snapshots,
- no concurrent older Feast snapshot overwrites.

Uses at-least-once delivery and verified idempotent retry.
SQLite and Feast are NOT a distributed atomic transaction.
"""

from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys
import numpy as np
import pandas as pd
from feast import FeatureStore

if len(sys.argv) < 3:
    raise SystemExit(
        "Usage: python fraud_feast_delivery.py "
        "DB_PATH FEAST_REPO [--crash-before-ack]"
    )

DB_PATH = Path(sys.argv[1]).resolve()
REPO = Path(sys.argv[2]).resolve()

CRASH = "--crash-before-ack" in sys.argv[3:]

if not DB_PATH.is_file():
    raise FileNotFoundError(DB_PATH)

if not (REPO / "feature_store.yaml").is_file():
    raise FileNotFoundError("Feast configuration missing")

# Import the permanent project outbox module.
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fraud_feast_outbox import (
    connect,
    pending_tasks,
    mark_completed
)

db = connect(DB_PATH)

try:
    tasks = pending_tasks(db)

    if not tasks:
        print("NO_PENDING_TASKS", flush=True)
        raise SystemExit(0)

    store = FeatureStore(repo_path=str(REPO))

    total_checks = 0
    total_completed = 0

    for task in tasks:
        payload = task["payload"]
        step = int(task["target_step"])

        assert payload["target_step"] == step

        timestamp = (
            datetime(2026, 1, 1, tzinfo=timezone.utc)
            + timedelta(hours=step)
        )

        for role, entity in (
            ("origin", "nameOrig"),
            ("destination", "nameDest")
        ):
            rows = []

            for item in payload["accounts"]:
                if item["role"] != role:
                    continue

                rows.append({
                    entity: str(item["account"]),
                    role + "_previous_count": int(
                        item["count"]
                    ),
                    role + "_previous_total": float(
                        item["total"]
                    ),
                    role + "_previous_mean": float(
                        item["mean"]
                    ),
                    role + "_hours_since_previous": int(
                        item["age"]
                    ),
                    "event_timestamp": timestamp
                })

            if not rows:
                raise ValueError(
                    "Empty account snapshot: " + role
                )

            frame = pd.DataFrame(rows)
            assert frame[entity].is_unique

            view = role + "_account_history"

            store.write_to_online_store(
                feature_view_name=view,
                df=frame
            )

            fields = [
                role + "_previous_count",
                role + "_previous_total",
                role + "_previous_mean",
                role + "_hours_since_previous"
            ]

            result = store.get_online_features(
                features=[
                    view + ":" + f for f in fields
                ],
                entity_rows=[
                    {entity: name}
                    for name in frame[entity].tolist()
                ]
            ).to_dict()

            for field in fields:
                key = (
                    field if field in result
                    else view + "__" + field
                )

                if key not in result:
                    raise KeyError(
                        "Missing online feature: " + field
                    )

                expected = frame[
                    field
                ].to_numpy(dtype=float)

                actual = np.array([
                    np.nan if value is None
                    else float(value)
                    for value in result[key]
                ])

                if not np.isclose(
                    expected,
                    actual,
                    rtol=1e-8,
                    atol=0.01,
                    equal_nan=False
                ).all():
                    raise AssertionError(
                        "Feast readback mismatch: " + field
                    )

                total_checks += len(expected)

        print(
            "FEAST_READBACK_PASS:",
            task["task_id"],
            total_checks,
            flush=True
        )

        # Test interruption: Feast succeeded, but SQLite
        # acknowledgment has not yet been written.
        if CRASH:
            print(
                "SIMULATED_CRASH_BEFORE_ACK",
                flush=True
            )
            raise SystemExit(73)

        # Mark completed only after all readback checks.
        result = mark_completed(
            db,
            task["task_id"],
            task["sha256"]
        )

        assert result in (
            "COMPLETED",
            "ALREADY_COMPLETED"
        )

        total_completed += 1

        print(
            "OUTBOX_ACK_PASS:",
            task["task_id"],
            flush=True
        )

    print("COMPLETED_TASKS:", total_completed)
    print("TOTAL_FEATURE_CHECKS:", total_checks)

finally:
    db.close()
