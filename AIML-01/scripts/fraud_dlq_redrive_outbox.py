import hashlib
import json

from fraud_kafka_events import validate_event


def initialize_outbox(state):
    """Create an isolated durable redrive delivery queue."""
    state.db.execute("""
        CREATE TABLE IF NOT EXISTS dlq_redrive_outbox (
            source_topic TEXT NOT NULL,
            source_partition INTEGER NOT NULL,
            source_offset INTEGER NOT NULL,
            event_id TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN ('PENDING', 'CONFIRMED')),
            created_at TEXT NOT NULL DEFAULT
                (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            PRIMARY KEY (
                source_topic, source_partition, source_offset
            )
        )
    """)
    state.db.commit()


def enqueue_redrive(state, topic, partition, offset):
    """Atomically enqueue a staged correction without publishing."""
    if not isinstance(topic, str) or not topic:
        raise ValueError("Invalid source topic")
    if type(partition) is not int or partition < 0:
        raise ValueError("Invalid partition")
    if type(offset) is not int or offset < 0:
        raise ValueError("Invalid offset")

    state.db.execute("BEGIN IMMEDIATE")
    try:
        request = state.db.execute("""
            SELECT corrected_event_id, corrected_payload_json,
                   corrected_sha256, status,
                   source_payload_sha256
            FROM dlq_redrive_requests
            WHERE source_topic=? AND source_partition=?
              AND source_offset=?
        """, (topic, partition, offset)).fetchone()

        if request is None:
            raise ValueError("Approved staging request missing")

        event_id, payload, digest, status, original_digest = request

        if status != "APPROVED_PENDING":
            raise ValueError("Request not eligible for delivery")

        if hashlib.sha256(payload.encode()).hexdigest() != digest:
            raise ValueError("Corrected payload checksum mismatch")

        event = json.loads(payload)
        validate_event(event)

        if event["event_id"] != event_id:
            raise ValueError("Corrected event ID mismatch")

        original = state.db.execute("""
            SELECT payload_sha256, status
            FROM dead_letter_events
            WHERE topic=? AND partition_id=? AND offset_id=?
        """, (topic, partition, offset)).fetchone()

        if original != (original_digest, "QUARANTINED"):
            raise ValueError("Original DLQ record changed")

        current = state.db.execute("""
            SELECT value FROM metadata WHERE key='step'
        """).fetchone()

        if current is None or event["step"] < int(current[0]):
            raise ValueError("Correction is now chronologically late")

        processed = state.db.execute("""
            SELECT 1 FROM processed_events WHERE event_id=?
        """, (event_id,)).fetchone()

        if processed is not None:
            raise ValueError("Corrected event already processed")

        existing = state.db.execute("""
            SELECT event_id, payload_sha256
            FROM dlq_redrive_outbox
            WHERE source_topic=? AND source_partition=?
              AND source_offset=?
        """, (topic, partition, offset)).fetchone()

        if existing is not None:
            if existing != (event_id, digest):
                raise ValueError("Conflicting delivery request")
            state.db.commit()
            return "OUTBOX_REPLAY"

        state.db.execute("""
            INSERT INTO dlq_redrive_outbox (
                source_topic, source_partition, source_offset,
                event_id, payload_json, payload_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            topic, partition, offset, event_id, payload, digest
        ))

        state.db.commit()
        return "OUTBOX_ENQUEUED"

    except Exception:
        state.db.rollback()
        raise


def pending_redrives(state):
    """Read pending delivery metadata, never publish automatically."""
    return state.db.execute("""
        SELECT source_topic, source_partition, source_offset,
               event_id, payload_sha256
        FROM dlq_redrive_outbox
        WHERE status='PENDING'
        ORDER BY created_at, source_topic,
                 source_partition, source_offset
    """).fetchall()
