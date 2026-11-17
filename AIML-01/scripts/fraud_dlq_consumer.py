import json

from fraud_kafka_events import validate_event


def process_raw_message(
    state,
    topic,
    partition,
    offset,
    raw_payload,
):
    """
    Process one Kafka message with durable DLQ protection.

    Preconditions:
    - state is an initialized DurableFraudDLQState
    - the partition is registered
    - Kafka auto-commit is disabled

    A successful return means the local SQLite transaction
    committed. It does not mean the Kafka broker offset
    was committed.

    The caller must commit offset + 1 to Kafka only after
    successful return, with recovery from the SQLite
    checkpoint on restart.
    """
    if not isinstance(raw_payload, bytes):
        raise TypeError("Kafka raw payload must be bytes")

    if len(raw_payload) > 1024 * 1024:
        raise ValueError(
            "Oversized payload requires an explicit "
            "oversize-message handling policy"
        )

    # Stage 1: Decode UTF-8.
    try:
        text = raw_payload.decode("utf-8")
    except UnicodeDecodeError as error:
        status = state.record_failure(
            topic,
            partition,
            offset,
            raw_payload,
            "INVALID_ENCODING",
            str(error),
        )
        return {
            "status": status,
            "route": "DLQ",
            "reason": "INVALID_ENCODING",
            "next_offset": state.checkpoint(topic, partition),
        }

    # Stage 2: Decode JSON.
    try:
        event = json.loads(text)
    except json.JSONDecodeError as error:
        status = state.record_failure(
            topic,
            partition,
            offset,
            raw_payload,
            "MALFORMED_JSON",
            str(error),
        )
        return {
            "status": status,
            "route": "DLQ",
            "reason": "MALFORMED_JSON",
            "next_offset": state.checkpoint(topic, partition),
        }

    # Stage 3: Validate the event before any state writes.
    if not isinstance(event, dict):
        reason = "INVALID_SCHEMA"
        detail = "JSON root must be an object"
    else:
        try:
            validate_event(event)
        except (ValueError, TypeError, KeyError) as error:
            reason = (
                "INVALID_SCHEMA"
                if set(event) != {
                    "event_id",
                    "transaction_id",
                    "step",
                    "event_timestamp",
                    "type",
                    "amount",
                    "nameOrig",
                    "nameDest",
                    "oldbalanceOrg",
                    "oldbalanceDest",
                }
                else "INVALID_EVENT"
            )
            detail = f"{type(error).__name__}: {error}"
        else:
            reason = None
            detail = None

    if reason is not None:
        status = state.record_failure(
            topic,
            partition,
            offset,
            raw_payload,
            reason,
            detail,
        )
        return {
            "status": status,
            "route": "DLQ",
            "reason": reason,
            "next_offset": state.checkpoint(topic, partition),
        }

    # Stage 4: Valid events use the existing atomic
    # Kafka checkpoint + account-state + Feast-outbox path.
    #
    # IMPORTANT: Do not catch processing exceptions here.
    # Infrastructure failures, offset conflicts and
    # late-event errors must propagate without DLQ routing.
    status = state.process(
        event,
        topic,
        partition,
        offset,
    )

    return {
        "status": status,
        "route": "PROCESSED",
        "reason": None,
        "event_id": event["event_id"],
        "next_offset": state.checkpoint(topic, partition),
    }
