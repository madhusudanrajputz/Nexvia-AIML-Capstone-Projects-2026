import hashlib
import sqlite3
import time
from pathlib import Path


def confirm_test_redrive(
    state,
    source_topic,
    source_partition,
    source_offset,
    destination_topic,
    destination_partition,
    destination_offset,
    downstream_db_path,
    broker,
    consumer_group,
    *,
    isolated_test=False,
):
    """
    Confirm an isolated redrive only after matching:
      - source approval and outbox
      - original quarantined record
      - broker-stored corrected payload
      - downstream offset ledger and processed event
      - downstream SQLite and broker group checkpoints

    Not a production confirmation API.
    """
    if isolated_test is not True:
        raise PermissionError(
            "Production confirmation disabled"
        )

    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            source_topic,
            destination_topic,
            broker,
            consumer_group,
        )
    ):
        raise ValueError("Invalid Kafka configuration")

    if not all(
        type(value) is int and value >= 0
        for value in (
            source_partition,
            source_offset,
            destination_partition,
            destination_offset,
        )
    ):
        raise ValueError("Invalid partition or offset")

    if (
        source_topic == destination_topic
        or not source_topic.startswith("aiml01_13nk_")
        or not destination_topic.startswith("aiml01_13nk_")
        or not consumer_group.startswith("aiml01_13nk_")
        or broker != "127.0.0.1:19092"
    ):
        raise PermissionError(
            "Only the isolated 13N-K Kafka test is allowed"
        )

    downstream_path = Path(downstream_db_path).resolve()

    if (
        not downstream_path.is_file()
        or not str(downstream_path).startswith(
            "/content/aiml01_13nk_"
        )
    ):
        raise ValueError(
            "Isolated downstream database not found"
        )

    key = (source_topic, source_partition, source_offset)

    def source_snapshot():
        outbox = state.db.execute("""
            SELECT event_id, payload_json,
                   payload_sha256, status
            FROM dlq_redrive_outbox
            WHERE source_topic=?
              AND source_partition=?
              AND source_offset=?
        """, key).fetchone()

        request = state.db.execute("""
            SELECT corrected_event_id, corrected_sha256,
                   source_payload_sha256, approved_by,
                   approval_reference, status
            FROM dlq_redrive_requests
            WHERE source_topic=?
              AND source_partition=?
              AND source_offset=?
        """, key).fetchone()

        original = state.db.execute("""
            SELECT payload_sha256, status
            FROM dead_letter_events
            WHERE topic=? AND partition_id=?
              AND offset_id=?
        """, key).fetchone()

        return outbox, request, original

    snapshot = source_snapshot()
    outbox, request, original = snapshot

    if outbox is None or request is None or original is None:
        raise ValueError("Missing source evidence")

    event_id, payload_json, digest, status = outbox

    if status not in ("PENDING", "CONFIRMED"):
        raise ValueError("Invalid outbox status")

    if (
        request[0] != event_id
        or request[1] != digest
        or not request[3]
        or not request[4]
        or request[5] != "APPROVED_PENDING"
        or original != (request[2], "QUARANTINED")
    ):
        raise ValueError("Approval or quarantine mismatch")

    payload = payload_json.encode("utf-8")

    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("Corrected payload integrity failure")

    # Downstream DB is opened read-only.
    downstream = sqlite3.connect(
        downstream_path.as_uri() + "?mode=ro",
        uri=True
    )

    try:
        if downstream.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] != "ok":
            raise ValueError("Downstream SQLite integrity failure")

        processed = downstream.execute("""
            SELECT COUNT(*) FROM processed_events
            WHERE event_id=?
        """, (event_id,)).fetchone()[0]

        ledger = downstream.execute("""
            SELECT event_id FROM kafka_offset_events
            WHERE topic=? AND partition_id=?
              AND offset_id=?
        """, (
            destination_topic,
            destination_partition,
            destination_offset,
        )).fetchone()

        checkpoint_row = downstream.execute("""
            SELECT next_offset FROM kafka_checkpoints
            WHERE topic=? AND partition_id=?
        """, (
            destination_topic,
            destination_partition,
        )).fetchone()

        if processed != 1 or ledger != (event_id,):
            raise ValueError(
                "Downstream processing evidence missing"
            )

        if (
            checkpoint_row is None
            or checkpoint_row[0] < destination_offset + 1
        ):
            raise ValueError(
                "Downstream SQLite checkpoint incomplete"
            )

        downstream_checkpoint = checkpoint_row[0]

    finally:
        downstream.close()

    # Check the broker and committed consumer-group offset.
    from kafka import KafkaConsumer, TopicPartition

    tp = TopicPartition(
        destination_topic, destination_partition
    )

    consumer = KafkaConsumer(
        bootstrap_servers=[broker],
        group_id=consumer_group,
        enable_auto_commit=False,
        request_timeout_ms=20000,
        api_version_auto_timeout_ms=10000,
    )

    try:
        consumer.assign([tp])

        beginning = consumer.beginning_offsets([tp])[tp]
        ending = consumer.end_offsets([tp])[tp]
        committed = consumer.committed(tp)

        if not (
            beginning <= destination_offset < ending
            and committed is not None
            and committed >= destination_offset + 1
        ):
            raise ValueError(
                "Kafka record or committed offset missing"
            )

        if downstream_checkpoint < destination_offset + 1:
            raise ValueError("SQLite checkpoint mismatch")

        consumer.seek(tp, destination_offset)
        received = None
        deadline = time.monotonic() + 20

        while time.monotonic() < deadline:
            batch = consumer.poll(
                timeout_ms=1000,
                max_records=1,
            ).get(tp, [])

            if batch:
                received = batch[0]
                break

        if (
            received is None
            or received.offset != destination_offset
            or received.value != payload
            or received.key != event_id.encode("utf-8")
        ):
            raise ValueError(
                "Kafka delivery payload mismatch"
            )

    finally:
        consumer.close()

    # All external evidence has passed. Atomically
    # recheck the source before updating its status.
    state.db.execute("BEGIN IMMEDIATE")

    try:
        if source_snapshot() != snapshot:
            raise ValueError(
                "Source evidence changed during verification"
            )

        if status == "CONFIRMED":
            state.db.commit()
            return "CONFIRMATION_REPLAY"

        cursor = state.db.execute("""
            UPDATE dlq_redrive_outbox
            SET status='CONFIRMED'
            WHERE source_topic=?
              AND source_partition=?
              AND source_offset=?
              AND status='PENDING'
        """, key)

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Outbox confirmation transition failed"
            )

        state.db.commit()
        return "DELIVERY_CONFIRMED"

    except Exception:
        state.db.rollback()
        raise
