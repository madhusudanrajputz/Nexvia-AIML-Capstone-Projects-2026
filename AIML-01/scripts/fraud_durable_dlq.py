import hashlib
import sqlite3

from fraud_atomic_feast_state import AtomicFeastConsumerState
from fraud_offset_recovery import (
    OffsetConflictError,
    OffsetSequenceError,
)


PERMANENT_REASONS = frozenset({
    "MALFORMED_JSON",
    "INVALID_ENCODING",
    "INVALID_SCHEMA",
    "INVALID_EVENT",
})

MAX_RAW_BYTES = 1024 * 1024


class DurableFraudDLQState(AtomicFeastConsumerState):
    """Atomically record poison messages and advance local offsets."""

    def __init__(self, database_path):
        super().__init__(database_path)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_events (
                topic TEXT NOT NULL,
                partition_id INTEGER NOT NULL,
                offset_id INTEGER NOT NULL,
                raw_payload BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                error_detail TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'QUARANTINED'
                    CHECK(status IN (
                        'QUARANTINED', 'RESOLVED'
                    )),
                created_at TEXT NOT NULL DEFAULT
                    (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                PRIMARY KEY(topic, partition_id, offset_id)
            )
        """)
        self.db.commit()

    def record_failure(
        self,
        topic,
        partition,
        offset,
        raw_payload,
        reason_code,
        error_detail="",
    ):
        """
        Quarantine a permanently invalid message.

        Kafka broker commits are the caller's responsibility
        and must occur only after this method returns.

        Never use this method for transient infrastructure
        or model-serving failures.
        """
        if not isinstance(topic, str) or not topic:
            raise ValueError("Invalid topic")
        if type(partition) is not int or partition < 0:
            raise ValueError("Invalid partition")
        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid offset")
        if type(raw_payload) is not bytes:
            raise TypeError("raw_payload must be bytes")
        if len(raw_payload) > MAX_RAW_BYTES:
            raise ValueError("Payload exceeds DLQ size limit")
        if reason_code not in PERMANENT_REASONS:
            raise ValueError("Reason is not permanently invalid")
        if not isinstance(error_detail, str):
            raise TypeError("error_detail must be text")

        detail = error_detail[:1000]
        digest = hashlib.sha256(raw_payload).hexdigest()

        event_id = f"dlq:{topic}:{partition}:{offset}"
        fingerprint = f"DLQ_SHA256:{digest}"

        self.db.execute("BEGIN IMMEDIATE")

        try:
            checkpoint = self.db.execute("""
                SELECT next_offset
                FROM kafka_checkpoints
                WHERE topic=? AND partition_id=?
            """, (topic, partition)).fetchone()

            if checkpoint is None:
                raise RuntimeError(
                    "Register partition before DLQ processing"
                )

            expected = int(checkpoint[0])

            if offset > expected:
                raise OffsetSequenceError(
                    f"Expected offset {expected}, got {offset}"
                )

            previous = self.db.execute("""
                SELECT payload_sha256, reason_code
                FROM dead_letter_events
                WHERE topic=? AND partition_id=?
                  AND offset_id=?
            """, (topic, partition, offset)).fetchone()

            previous_checkpoint = self.db.execute("""
                SELECT event_id, fingerprint
                FROM kafka_offset_events
                WHERE topic=? AND partition_id=?
                  AND offset_id=?
            """, (topic, partition, offset)).fetchone()

            if offset < expected:
                if (
                    previous != (digest, reason_code)
                    or previous_checkpoint != (
                        event_id, fingerprint
                    )
                ):
                    raise OffsetConflictError(
                        "Conflicting or missing DLQ replay record"
                    )

                self.db.commit()
                return "DLQ_OFFSET_REPLAY"

            if previous is not None:
                raise OffsetConflictError(
                    "Current offset already has a DLQ record"
                )

            if previous_checkpoint is not None:
                raise OffsetConflictError(
                    "Current offset already has an event record"
                )

            self.db.execute("""
                INSERT INTO dead_letter_events (
                    topic, partition_id, offset_id,
                    raw_payload, payload_sha256,
                    reason_code, error_detail
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                topic, partition, offset,
                sqlite3.Binary(raw_payload), digest,
                reason_code, detail
            ))

            self.db.execute("""
                INSERT INTO kafka_offset_events (
                    topic, partition_id, offset_id,
                    event_id, fingerprint
                )
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
            return "DLQ_QUARANTINED"

        except Exception:
            self.db.rollback()
            raise

    def dlq_records(self, topic=None):
        """Read quarantine metadata without exposing raw payloads."""
        if topic is None:
            return self.db.execute("""
                SELECT topic, partition_id, offset_id,
                       payload_sha256, reason_code, status
                FROM dead_letter_events
                ORDER BY topic, partition_id, offset_id
            """).fetchall()

        return self.db.execute("""
            SELECT topic, partition_id, offset_id,
                   payload_sha256, reason_code, status
            FROM dead_letter_events
            WHERE topic=?
            ORDER BY partition_id, offset_id
        """, (topic,)).fetchall()
