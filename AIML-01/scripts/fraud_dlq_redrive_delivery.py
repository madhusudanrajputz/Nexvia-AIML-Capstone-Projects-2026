import hashlib
import json

from fraud_kafka_events import validate_event


def prepare_redrive_delivery(
    state,
    source_topic,
    source_partition,
    source_offset,
    destination_topic,
):
    """
    Validate one approved, queued correction for delivery.

    Returns bytes and an event ID, but NEVER publishes,
    commits Kafka offsets or changes SQLite state.

    This function does not authenticate the operator.
    Production dispatch must remain disabled until
    authorization and delivery reconciliation exist.
    """
    if not isinstance(source_topic, str) or not source_topic:
        raise ValueError("Invalid source topic")
    if type(source_partition) is not int or source_partition < 0:
        raise ValueError("Invalid source partition")
    if type(source_offset) is not int or source_offset < 0:
        raise ValueError("Invalid source offset")
    if not isinstance(destination_topic, str):
        raise ValueError("Invalid destination topic")
    if not destination_topic.strip():
        raise ValueError("Empty destination topic")
    if destination_topic == source_topic:
        raise ValueError("Redrive must use a separate topic")

    outbox = state.db.execute("""
        SELECT event_id, payload_json,
               payload_sha256, status
        FROM dlq_redrive_outbox
        WHERE source_topic=? AND source_partition=?
          AND source_offset=?
    """, (
        source_topic, source_partition, source_offset
    )).fetchone()

    if outbox is None:
        raise ValueError("Delivery outbox entry not found")

    event_id, payload, digest, status = outbox

    if status != "PENDING":
        raise ValueError("Delivery is not pending")

    request = state.db.execute("""
        SELECT corrected_event_id, corrected_sha256,
               source_payload_sha256, approved_by,
               approval_reference, status
        FROM dlq_redrive_requests
        WHERE source_topic=? AND source_partition=?
          AND source_offset=?
    """, (
        source_topic, source_partition, source_offset
    )).fetchone()

    if request is None:
        raise ValueError("Approval record missing")

    (
        approved_event_id,
        approved_hash,
        original_hash,
        approved_by,
        approval_reference,
        request_status,
    ) = request

    if request_status != "APPROVED_PENDING":
        raise ValueError("Approval request not pending")
    if not approved_by or not approval_reference:
        raise ValueError("Approval metadata missing")

    original = state.db.execute("""
        SELECT payload_sha256, status
        FROM dead_letter_events
        WHERE topic=? AND partition_id=? AND offset_id=?
    """, (
        source_topic, source_partition, source_offset
    )).fetchone()

    if original != (original_hash, "QUARANTINED"):
        raise ValueError("Original quarantine integrity mismatch")

    encoded = payload.encode("utf-8")
    actual_digest = hashlib.sha256(encoded).hexdigest()

    if actual_digest != digest or digest != approved_hash:
        raise ValueError("Corrected payload checksum mismatch")

    event = json.loads(payload)
    validate_event(event)

    if event["event_id"] != event_id:
        raise ValueError("Outbox event ID mismatch")
    if event_id != approved_event_id:
        raise ValueError("Approved event ID mismatch")

    current = state.db.execute("""
        SELECT value FROM metadata WHERE key='step'
    """).fetchone()

    if current is None:
        raise RuntimeError("State not initialized")

    if event["step"] < int(current[0]):
        raise ValueError(
            "Redrive blocked: correction became chronologically late"
        )

    processed = state.db.execute("""
        SELECT 1 FROM processed_events WHERE event_id=?
    """, (event_id,)).fetchone()

    if processed is not None:
        raise ValueError("Correction already processed")

    return {
        "destination_topic": destination_topic,
        "event_id": event_id,
        "payload": encoded,
        "payload_sha256": digest,
        "source_topic": source_topic,
        "source_partition": source_partition,
        "source_offset": source_offset,
        "status": "READY_FOR_TEST_DELIVERY",
    }
