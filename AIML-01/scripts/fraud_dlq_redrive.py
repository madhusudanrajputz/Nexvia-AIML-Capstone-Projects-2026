import hashlib
import json

from fraud_kafka_events import validate_event


def initialize_redrive(state):
    """Create durable staging schema in the supplied test database."""
    state.db.execute("""
        CREATE TABLE IF NOT EXISTS dlq_redrive_requests (
            source_topic TEXT NOT NULL,
            source_partition INTEGER NOT NULL,
            source_offset INTEGER NOT NULL,
            source_payload_sha256 TEXT NOT NULL,
            corrected_event_id TEXT NOT NULL,
            corrected_payload_json TEXT NOT NULL,
            corrected_sha256 TEXT NOT NULL,
            approved_by TEXT NOT NULL,
            approval_reference TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'APPROVED_PENDING'
                CHECK(status IN (
                    'APPROVED_PENDING',
                    'BLOCKED_LATE',
                    'CANCELLED'
                )),
            created_at TEXT NOT NULL DEFAULT
                (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            PRIMARY KEY (
                source_topic,
                source_partition,
                source_offset
            ),
            UNIQUE(corrected_event_id),
            UNIQUE(approval_reference)
        )
    """)
    state.db.commit()


def stage_redrive(
    state,
    topic,
    partition,
    offset,
    corrected_event,
    approved_by,
    approval_reference,
):
    """
    Stage an operator-approved correction without Kafka publishing.

    Only transactions at or after the current state step
    are eligible for staging.

    This is NOT a producer, dispatcher or production redrive.
    """
    if not isinstance(topic, str) or not topic:
        raise ValueError("Invalid source topic")
    if type(partition) is not int or partition < 0:
        raise ValueError("Invalid source partition")
    if type(offset) is not int or offset < 0:
        raise ValueError("Invalid source offset")

    for name, value in (
        ("approved_by", approved_by),
        ("approval_reference", approval_reference),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing {name}")
        if len(value) > 200:
            raise ValueError(f"{name} exceeds size limit")

    if not isinstance(corrected_event, dict):
        raise ValueError("Corrected event must be a dictionary")

    validate_event(corrected_event)

    payload = json.dumps(
        corrected_event,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    corrected_hash = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

    event_id = corrected_event["event_id"]
    target_step = corrected_event["step"]

    state.db.execute("BEGIN IMMEDIATE")

    try:
        original = state.db.execute("""
            SELECT payload_sha256, status
            FROM dead_letter_events
            WHERE topic=? AND partition_id=? AND offset_id=?
        """, (topic, partition, offset)).fetchone()

        if original is None:
            raise ValueError("Original DLQ entry not found")

        original_hash, original_status = original

        if original_status != "QUARANTINED":
            raise ValueError("Original entry is not quarantined")

        existing = state.db.execute("""
            SELECT source_payload_sha256,
                   corrected_event_id,
                   corrected_sha256,
                   approved_by,
                   approval_reference,
                   status
            FROM dlq_redrive_requests
            WHERE source_topic=?
              AND source_partition=?
              AND source_offset=?
        """, (topic, partition, offset)).fetchone()

        expected = (
            original_hash,
            event_id,
            corrected_hash,
            approved_by.strip(),
            approval_reference.strip(),
            "APPROVED_PENDING",
        )

        if existing is not None:
            if existing != expected:
                raise ValueError("Conflicting redrive request")
            state.db.commit()
            return "REDRIVE_REQUEST_REPLAY"

        processed = state.db.execute("""
            SELECT 1 FROM processed_events WHERE event_id=?
        """, (event_id,)).fetchone()

        if processed is not None:
            raise ValueError("Transaction already processed")

        current = state.db.execute("""
            SELECT value FROM metadata WHERE key='step'
        """).fetchone()

        if current is None:
            raise RuntimeError("State not initialized")

        if target_step < int(current[0]):
            raise ValueError(
                "Late correction blocked: would violate "
                "account-history chronology"
            )

        state.db.execute("""
            INSERT INTO dlq_redrive_requests (
                source_topic,
                source_partition,
                source_offset,
                source_payload_sha256,
                corrected_event_id,
                corrected_payload_json,
                corrected_sha256,
                approved_by,
                approval_reference
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            topic,
            partition,
            offset,
            original_hash,
            event_id,
            payload,
            corrected_hash,
            approved_by.strip(),
            approval_reference.strip(),
        ))

        state.db.commit()
        return "REDRIVE_STAGED"

    except Exception:
        state.db.rollback()
        raise


def list_staged_redrives(state):
    """Return redrive metadata without raw corrected payloads."""
    return state.db.execute("""
        SELECT source_topic, source_partition, source_offset,
               corrected_event_id, approved_by,
               approval_reference, status
        FROM dlq_redrive_requests
        ORDER BY source_topic, source_partition, source_offset
    """).fetchall()
