
"""AIML-01 Kafka message -> FastAPI score -> durable SQLite sink.

This module processes real Kafka messages through the API.
It does not use saved prediction CSVs as scoring inputs.

Production needs a network-hosted API, authentication,
Feast event-time synchronization, late-event handling
and durable event/state atomicity.
"""


def process_message(client, db, message, storage):
    event = message.value

    # No fraud label is included in the API payload.
    response = client.post("/predict", json=event)

    # Failure must prevent successful persistence/offset
    # acknowledgment, enabling retry or dead-letter routing.
    if response.status_code != 200:
        raise RuntimeError(
            "Scoring API returned HTTP "
            + str(response.status_code)
            + ": "
            + response.text[:500]
        )

    scored = response.json()

    if scored["event_id"] != event["event_id"]:
        raise ValueError("API event ID mismatch")

    if scored["transaction_id"] != event["transaction_id"]:
        raise ValueError("API transaction ID mismatch")

    probability = float(scored["fraud_probability"])
    threshold = float(scored["decision_threshold"])

    duplicate = storage.persist(
        db=db,
        event=event,
        probability=probability,
        threshold=threshold,
        topic=message.topic,
        partition=message.partition,
        offset=message.offset
    )

    return {
        "event_id": event["event_id"],
        "transaction_id": event["transaction_id"],
        "offset": int(message.offset),
        "fraud_probability": probability,
        "fraud_alert": bool(scored["fraud_alert"]),
        "api_latency_ms": float(scored["latency_ms"]),
        "duplicate": bool(duplicate)
    }
