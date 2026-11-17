
import json
import math
import sqlite3
from pathlib import Path


class OffsetSequenceError(Exception):
    pass


class OffsetConflictError(Exception):
    pass


class AtomicFraudConsumerState:

    def __init__(self, database_path):
        path = Path(database_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        self.db = sqlite3.connect(
            str(path),
            timeout=20,
            isolation_level=None
        )

        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=20000")

        required = {
            "metadata", "accounts",
            "pending", "processed_events"
        }

        existing = {
            row[0] for row in self.db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table'"
            )
        }

        if not required.issubset(existing):
            self.db.close()
            raise RuntimeError(
                "DurableAccountState schema missing"
            )

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS kafka_checkpoints (
                topic TEXT NOT NULL,
                partition_id INTEGER NOT NULL,
                next_offset INTEGER NOT NULL,
                PRIMARY KEY(topic, partition_id)
            )
        """)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS kafka_offset_events (
                topic TEXT NOT NULL,
                partition_id INTEGER NOT NULL,
                offset_id INTEGER NOT NULL,
                event_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                PRIMARY KEY(topic, partition_id, offset_id)
            )
        """)

    def register_partition(
        self, topic, partition, starting_offset
    ):
        if (
            not isinstance(topic, str)
            or not topic
            or type(partition) is not int
            or partition < 0
            or type(starting_offset) is not int
            or starting_offset < 0
        ):
            raise ValueError("Invalid partition checkpoint")

        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("""
                SELECT next_offset
                FROM kafka_checkpoints
                WHERE topic=? AND partition_id=?
            """, (topic, partition)).fetchone()

            if row is None:
                self.db.execute("""
                    INSERT INTO kafka_checkpoints
                    VALUES (?, ?, ?)
                """, (topic, partition, starting_offset))

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return self.checkpoint(topic, partition)

    def checkpoint(self, topic, partition):
        row = self.db.execute("""
            SELECT next_offset
            FROM kafka_checkpoints
            WHERE topic=? AND partition_id=?
        """, (topic, partition)).fetchone()

        return None if row is None else int(row[0])

    def _advance(self, step):
        row = self.db.execute("""
            SELECT value FROM metadata WHERE key='step'
        """).fetchone()

        if row is None:
            raise RuntimeError("State not initialized")

        current = int(row[0])

        if step < current:
            raise ValueError("Late event")

        if step == current:
            return

        pending = self.db.execute("""
            SELECT role, account, count, total
            FROM pending
        """).fetchall()

        for role, account, count, total in pending:
            self.db.execute("""
                INSERT INTO accounts
                    (role, account, count, total, last_step)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(role, account) DO UPDATE SET
                    count = accounts.count + excluded.count,
                    total = accounts.total + excluded.total,
                    last_step = excluded.last_step
            """, (role, account, count, total, current))

        self.db.execute("DELETE FROM pending")
        self.db.execute("""
            UPDATE metadata SET value=?
            WHERE key='step'
        """, (step,))

    def process(self, event, topic, partition, offset):
        if not isinstance(event, dict):
            raise ValueError("Invalid event")

        txid = int(event["transaction_id"])
        event_id = str(event["event_id"])
        step = int(event["step"])
        origin = str(event["nameOrig"])
        destination = str(event["nameDest"])
        amount = float(event["amount"])

        if (
            event_id != f"paysim:{txid}"
            or txid < 1
            or step < 1
            or not origin
            or not destination
            or origin == destination
            or not math.isfinite(amount)
            or amount < 0
        ):
            raise ValueError("Invalid transaction")

        if (
            not isinstance(topic, str)
            or not topic
            or type(partition) is not int
            or partition < 0
            or type(offset) is not int
            or offset < 0
        ):
            raise ValueError("Invalid Kafka coordinates")

        fingerprint = json.dumps(
            {
                "transaction_id": txid,
                "step": step,
                "amount": amount,
                "nameOrig": origin,
                "nameDest": destination
            },
            sort_keys=True,
            separators=(",", ":")
        )

        self.db.execute("BEGIN IMMEDIATE")

        try:
            row = self.db.execute("""
                SELECT next_offset
                FROM kafka_checkpoints
                WHERE topic=? AND partition_id=?
            """, (topic, partition)).fetchone()

            if row is None:
                raise RuntimeError(
                    "Partition must be registered first"
                )

            expected_offset = int(row[0])

            if offset > expected_offset:
                raise OffsetSequenceError(
                    f"Expected offset {expected_offset}, "
                    f"received {offset}"
                )

            if offset < expected_offset:
                old = self.db.execute("""
                    SELECT event_id, fingerprint
                    FROM kafka_offset_events
                    WHERE topic=?
                      AND partition_id=?
                      AND offset_id=?
                """, (topic, partition, offset)).fetchone()

                if old != (event_id, fingerprint):
                    raise OffsetConflictError(
                        "Old offset does not match "
                        "durably recorded event"
                    )

                self.db.commit()
                return "OFFSET_REPLAY"

            previous = self.db.execute("""
                SELECT transaction_id, step, amount,
                       origin, destination
                FROM processed_events
                WHERE event_id=?
            """, (event_id,)).fetchone()

            if previous is not None:
                if previous != (
                    txid, step, amount, origin, destination
                ):
                    raise ValueError(
                        "Conflicting duplicate event"
                    )
                status = "DUPLICATE"

            else:
                self._advance(step)

                for role, account in (
                    ("origin", origin),
                    ("destination", destination)
                ):
                    self.db.execute("""
                        INSERT INTO pending
                            (role, account, count, total)
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(role, account)
                        DO UPDATE SET
                            count = pending.count + 1,
                            total = pending.total +
                                    excluded.total
                    """, (role, account, amount))

                self.db.execute("""
                    INSERT INTO processed_events
                    (event_id, transaction_id, step,
                     amount, origin, destination)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event_id, txid, step,
                    amount, origin, destination
                ))

                status = "ACCEPTED"

            self.db.execute("""
                INSERT INTO kafka_offset_events
                (topic, partition_id, offset_id,
                 event_id, fingerprint)
                VALUES (?, ?, ?, ?, ?)
            """, (
                topic, partition, offset,
                event_id, fingerprint
            ))

            self.db.execute("""
                UPDATE kafka_checkpoints
                SET next_offset=?
                WHERE topic=? AND partition_id=?
            """, (offset + 1, topic, partition))

            self.db.commit()
            return status

        except Exception:
            self.db.rollback()
            raise

    def close(self):
        self.db.close()
