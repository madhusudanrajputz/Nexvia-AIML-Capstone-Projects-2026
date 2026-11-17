
"""Atomic Kafka state and Feast outbox integration.

Creates an outbox snapshot whenever a new event hour
finalizes the previous hour.

Account-state finalization, outbox insertion, event
processing and Kafka checkpoint update use the SAME
SQLite transaction.

Feast delivery itself happens asynchronously through
fraud_feast_delivery.py. There is no cross-database
distributed transaction.
"""

import hashlib
import json

from fraud_offset_recovery import AtomicFraudConsumerState


class AtomicFeastConsumerState(AtomicFraudConsumerState):

    def __init__(self, database_path):
        super().__init__(database_path)

        self.db.execute("""
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
        self.db.commit()

        # Used only for isolated failure-injection tests.
        self._inject_outbox_failure = False

    def _advance(self, step):
        row = self.db.execute("""
            SELECT value FROM metadata WHERE key='step'
        """).fetchone()

        if row is None:
            raise RuntimeError("State not initialized")

        previous_step = int(row[0])
        step = int(step)

        # Preserve original late-event and same-hour behavior.
        if step <= previous_step:
            return super()._advance(step)

        # Parent finalizes pending transactions into accounts.
        # Parent does not commit the transaction.
        super()._advance(step)

        # We are still inside process() BEGIN IMMEDIATE.
        assert self.db.in_transaction

        # After the boundary, all prior-hour transactions
        # are finalized, while the incoming event has not
        # yet been added to pending.
        pending_count = self.db.execute("""
            SELECT COUNT(*) FROM pending
        """).fetchone()[0]

        if pending_count:
            raise RuntimeError(
                "Unexpected pending rows after finalization"
            )

        accounts = self.db.execute("""
            SELECT role, account, count, total, last_step
            FROM accounts
            ORDER BY role, account
        """).fetchall()

        rows = []

        for role, account, count, total, last_step in accounts:
            if role not in ("origin", "destination"):
                raise ValueError("Invalid account role")

            count = int(count)
            total = float(total)

            if count < 0:
                raise ValueError("Invalid account count")

            age = (
                -1 if last_step is None
                else step - int(last_step)
            )

            if age < -1:
                raise ValueError("Invalid account history age")

            rows.append({
                "role": role,
                "account": str(account),
                "count": count,
                "total": total,
                "mean": total / count if count else 0.0,
                "age": age
            })

        payload = json.dumps(
            {
                "target_step": step,
                "accounts": rows
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False
        )

        digest = hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

        task_id = f"account_history_hour_{step}"

        existing = self.db.execute("""
            SELECT payload_sha256
            FROM feast_sync_outbox
            WHERE task_id=?
        """, (task_id,)).fetchone()

        if existing is not None:
            if existing[0] != digest:
                raise ValueError(
                    "Conflicting hour-boundary snapshot"
                )
        else:
            self.db.execute("""
                INSERT INTO feast_sync_outbox (
                    task_id, target_step,
                    payload_json, payload_sha256
                )
                VALUES (?, ?, ?, ?)
            """, (task_id, step, payload, digest))

        # Failure injection BEFORE parent process() commits.
        if self._inject_outbox_failure:
            raise RuntimeError(
                "INJECTED_FAILURE_BEFORE_ATOMIC_COMMIT"
            )
