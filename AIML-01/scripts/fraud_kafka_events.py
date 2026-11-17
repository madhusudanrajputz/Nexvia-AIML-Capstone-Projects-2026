
"""AIML-01 transaction event contract for Kafka.

Contains only transaction-time attributes.
Fraud labels and post-event balances are excluded.
"""

from datetime import datetime, timezone, timedelta
import json
import math

TRANSACTION_FIELDS = (
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
)

VALID_TYPES = {
    "CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"
}

BASE_TIMESTAMP = datetime(
    2026, 1, 1, tzinfo=timezone.utc
)


def create_event(row):
    step = int(row["step"])
    transaction_id = int(row["transaction_id"])

    event = {
        "event_id": f"paysim:{transaction_id}",
        "transaction_id": transaction_id,
        "step": step,
        "event_timestamp": (
            BASE_TIMESTAMP + timedelta(hours=step)
        ).isoformat(),
        "type": str(row["type"]),
        "amount": float(row["amount"]),
        "nameOrig": str(row["nameOrig"]),
        "nameDest": str(row["nameDest"]),
        "oldbalanceOrg": float(row["oldbalanceOrg"]),
        "oldbalanceDest": float(row["oldbalanceDest"]),
    }

    return validate_event(event)


def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")

    if set(event) != set(TRANSACTION_FIELDS):
        raise ValueError(
            "Event schema mismatch or forbidden fields"
        )

    for name in ("transaction_id", "step"):
        if type(event[name]) is not int or event[name] < 1:
            raise ValueError("Invalid integer field: " + name)

    if event["event_id"] != (
        f"paysim:{event['transaction_id']}"
    ):
        raise ValueError("Inconsistent event ID")

    if event["type"] not in VALID_TYPES:
        raise ValueError("Invalid transaction type")

    for name in ("nameOrig", "nameDest"):
        if (
            not isinstance(event[name], str)
            or not event[name].strip()
        ):
            raise ValueError("Invalid account identifier")

    if event["nameOrig"] == event["nameDest"]:
        raise ValueError("Unsupported same-account transaction")

    for name in (
        "amount", "oldbalanceOrg", "oldbalanceDest"
    ):
        value = event[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("Invalid transaction field: " + name)

    expected_timestamp = (
        BASE_TIMESTAMP + timedelta(hours=event["step"])
    ).isoformat()

    if event["event_timestamp"] != expected_timestamp:
        raise ValueError("Incorrect transaction timestamp")

    return event


def encode_event(event):
    return json.dumps(
        validate_event(event),
        separators=(",", ":"),
        allow_nan=False
    ).encode("utf-8")


def decode_event(raw):
    return validate_event(json.loads(raw.decode("utf-8")))
