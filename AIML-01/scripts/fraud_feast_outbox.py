
"""Durable Feast synchronization intent for AIML-01.

This module manages SQLite outbox tasks. Feast delivery
will be handled by a separate worker.

Important: enqueue_snapshot must run after the SQLite
account state has reached a finalized hour. The current
API does not make account-state processing and outbox
insertion one atomic transaction.
"""

import hashlib
import json
import sqlite3


def connect(path):
    db = sqlite3.connect(str(path), timeout=15)
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")

    db.execute("""
        CREATE TABLE IF NOT EXISTS feast_sync_outbox (
            task_id TEXT PRIMARY KEY,
            target_step INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN ('PENDING', 'COMPLETED')),
            attempts INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT
        )
    """)
    db.commit()
    return db


def _payload_hash(payload_text):
    return hashlib.sha256(
        payload_text.encode("utf-8")
    ).hexdigest()


def enqueue_snapshot(db, target_step):
    """Create an idempotent, deterministic snapshot task."""

    target_step = int(target_step)

    # Snapshot must represent a finalized state.
    db.execute("BEGIN IMMEDIATE")

    try:
        row = db.execute("""
            SELECT value FROM metadata
            WHERE key='step'
        """).fetchone()

        if row is None:
            raise ValueError("Missing state hour")

        current_step = int(row[0])

        if target_step < current_step:
            raise ValueError(
                "Cannot enqueue a past-hour snapshot"
            )

        pending_count = db.execute("""
            SELECT COUNT(*) FROM pending
        """).fetchone()[0]

        if pending_count:
            raise ValueError(
                "Unfinalized account updates remain pending"
            )

        accounts = db.execute("""
            SELECT role, account, count, total, last_step
            FROM accounts
            ORDER BY role, account
        """).fetchall()

        rows = []

        for role, account, count, total, last_step in accounts:
            count = int(count)
            total = float(total)

            if count < 0:
                raise ValueError("Negative account count")

            if role not in ("origin", "destination"):
                raise ValueError("Unexpected account role")

            age = (
                -1 if last_step is None
                else target_step - int(last_step)
            )

            if age < -1:
                raise ValueError("Invalid account history age")

            rows.append({
                "role": role,
                "account": str(account),
                "count": count,
                "total": total,
                "mean": total / count if count else 0.0,
                "age": age,
            })

        payload = json.dumps(
            {
                "target_step": target_step,
                "accounts": rows,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False
        )

        digest = _payload_hash(payload)
        task_id = f"account_history_hour_{target_step}"

        existing = db.execute("""
            SELECT payload_sha256, status
            FROM feast_sync_outbox
            WHERE task_id=?
        """, (task_id,)).fetchone()

        if existing is not None:
            if existing[0] != digest:
                raise ValueError(
                    "Outbox task exists with different content"
                )
            result = existing[1]
        else:
            db.execute("""
                INSERT INTO feast_sync_outbox (
                    task_id, target_step,
                    payload_json, payload_sha256
                ) VALUES (?, ?, ?, ?)
            """, (
                task_id, target_step, payload, digest
            ))
            result = "PENDING"

        db.commit()

        return {
            "task_id": task_id,
            "status": result,
            "target_step": target_step,
            "accounts": len(rows),
            "sha256": digest,
        }

    except Exception:
        db.rollback()
        raise


def pending_tasks(db):
    rows = db.execute("""
        SELECT task_id, target_step,
               payload_json, payload_sha256
        FROM feast_sync_outbox
        WHERE status='PENDING'
        ORDER BY target_step, task_id
    """).fetchall()

    tasks = []

    for task_id, step, payload, digest in rows:
        if _payload_hash(payload) != digest:
            raise ValueError(
                "Outbox payload integrity failure"
            )

        tasks.append({
            "task_id": task_id,
            "target_step": step,
            "payload": json.loads(payload),
            "sha256": digest,
        })

    return tasks


def mark_completed(db, task_id, expected_sha256):
    """Acknowledge only after verified Feast readback."""

    with db:
        row = db.execute("""
            SELECT payload_sha256, status
            FROM feast_sync_outbox
            WHERE task_id=?
        """, (task_id,)).fetchone()

        if row is None:
            raise KeyError(task_id)

        if row[0] != expected_sha256:
            raise ValueError("Payload checksum mismatch")

        if row[1] == "COMPLETED":
            return "ALREADY_COMPLETED"

        updated = db.execute("""
            UPDATE feast_sync_outbox
            SET status='COMPLETED',
                attempts=attempts+1,
                completed_at=CURRENT_TIMESTAMP
            WHERE task_id=?
              AND status='PENDING'
        """, (task_id,))

        if updated.rowcount != 1:
            raise RuntimeError("Outbox acknowledgment failed")

    return "COMPLETED"
