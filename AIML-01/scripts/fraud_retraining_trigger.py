
"""Durable, guarded fraud-model retraining request trigger.

Automatically queues qualified retraining requests.
Does not train or promote a model.
"""

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def evaluate_drift(report, sampling_verified=False):
    if not isinstance(report, dict):
        raise ValueError("Drift report must be a dictionary")

    if not isinstance(sampling_verified, bool):
        raise ValueError("Sampling verification must be boolean")

    if report.get("status") != "PASS":
        return "BLOCKED", "DRIFT_REPORT_NOT_VERIFIED"

    if report.get("evaluation_scope") != "offline_train_vs_validation":
        return "BLOCKED", "UNSUPPORTED_EVALUATION_SCOPE"

    if report.get("features_analyzed") != 23:
        return "BLOCKED", "FEATURE_CONTRACT_MISMATCH"

    if not sampling_verified:
        return "BLOCKED", "TEMPORAL_SAMPLING_REVIEW_REQUIRED"

    if report.get("alert_status") != "REVIEW_REQUIRED":
        return "NO_TRIGGER", "NO_DRIFT_ALERT"

    critical = report.get("critical_drifted_features", [])

    if not isinstance(critical, list):
        raise ValueError("Invalid critical feature list")

    if not critical:
        return "NO_TRIGGER", "NO_CRITICAL_FEATURE_DRIFT"

    return "TRIGGER", "VERIFIED_CRITICAL_FEATURE_DRIFT"


def initialize_queue(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(path), timeout=10)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS retraining_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id TEXT NOT NULL UNIQUE,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.commit()
    finally:
        connection.close()


def queue_request(
    database_path,
    evaluation_id,
    report,
    sampling_verified=False
):
    if not isinstance(evaluation_id, str) or not (
        1 <= len(evaluation_id) <= 128
    ):
        raise ValueError("Invalid evaluation ID")

    decision, reason = evaluate_drift(
        report,
        sampling_verified=sampling_verified
    )

    if decision != "TRIGGER":
        return {
            "decision": decision,
            "reason": reason,
            "queued": False
        }

    initialize_queue(database_path)

    connection = sqlite3.connect(
        str(database_path), timeout=10
    )

    try:
        with connection:
            connection.execute("""
                INSERT OR IGNORE INTO retraining_requests (
                    evaluation_id, reason, status,
                    report_json, created_at
                )
                VALUES (?, ?, 'PENDING_APPROVAL', ?, ?)
            """, (
                evaluation_id,
                reason,
                json.dumps(report, sort_keys=True),
                utc_now()
            ))

        row = connection.execute("""
            SELECT id, status
            FROM retraining_requests
            WHERE evaluation_id = ?
        """, (evaluation_id,)).fetchone()

        return {
            "decision": "TRIGGER",
            "reason": reason,
            "queued": True,
            "request_id": row[0],
            "request_status": row[1]
        }

    finally:
        connection.close()
