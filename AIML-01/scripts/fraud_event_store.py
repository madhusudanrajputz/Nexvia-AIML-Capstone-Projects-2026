
"""Durable SQLite sink for fraud prediction events.

A database transaction saves prediction, optional alert
and Kafka progress together. Kafka commits happen AFTER
successful persistence.

At-least-once consumer delivery with idempotent writes;
not an exactly-once Kafka transaction.
"""

import json
import math
import sqlite3
from datetime import datetime, timezone


def connect(path):
    db = sqlite3.connect(str(path), timeout=15)
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")

    db.executescript("""
    CREATE TABLE IF NOT EXISTS predictions (
        event_id TEXT PRIMARY KEY,
        transaction_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        partition_id INTEGER NOT NULL,
        first_offset INTEGER NOT NULL,
        fraud_probability REAL NOT NULL,
        threshold REAL NOT NULL,
        fraud_alert INTEGER NOT NULL,
        scored_at_utc TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS alerts (
        event_id TEXT PRIMARY KEY,
        transaction_id INTEGER NOT NULL,
        fraud_probability REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        FOREIGN KEY(event_id) REFERENCES predictions(event_id)
    );
    CREATE TABLE IF NOT EXISTS consumer_progress (
        topic TEXT NOT NULL,
        partition_id INTEGER NOT NULL,
        next_offset INTEGER NOT NULL,
        PRIMARY KEY(topic, partition_id)
    );
    """)
    return db


def persist(db, event, probability, threshold, topic, partition, offset):
    if not isinstance(event, dict):
        raise ValueError("Invalid event")
    if not event["event_id"] or int(event["transaction_id"]) <= 0:
        raise ValueError("Invalid event identity")
    if not math.isfinite(float(probability)) or not 0 <= probability <= 1:
        raise ValueError("Invalid probability")
    if not 0 < threshold < 1 or offset < 0:
        raise ValueError("Invalid threshold or offset")

    flagged = int(probability >= threshold)
    duplicate = False

    with db:
        previous = db.execute(
            "SELECT transaction_id, fraud_probability, threshold "
            "FROM predictions WHERE event_id=?",
            (event["event_id"],)
        ).fetchone()

        if previous is None:
            db.execute("""
                INSERT INTO predictions VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                event["event_id"], int(event["transaction_id"]),
                topic, int(partition), int(offset),
                float(probability), float(threshold), flagged,
                datetime.now(timezone.utc).isoformat()
            ))

            if flagged:
                db.execute("""
                    INSERT INTO alerts
                    (event_id, transaction_id, fraud_probability, status)
                    VALUES (?,?,?,?)
                """, (
                    event["event_id"], int(event["transaction_id"]),
                    float(probability), "OPEN"
                ))
        else:
            duplicate = True
            if (
                int(previous[0]) != int(event["transaction_id"])
                or not math.isclose(
                    float(previous[1]), float(probability),
                    rel_tol=1e-7, abs_tol=1e-8
                )
                or not math.isclose(
                    float(previous[2]), float(threshold),
                    rel_tol=0, abs_tol=1e-10
                )
            ):
                raise ValueError("Conflicting duplicate event")

        current = db.execute("""
            SELECT next_offset FROM consumer_progress
            WHERE topic=? AND partition_id=?
        """, (topic, partition)).fetchone()

        next_offset = max(
            int(offset) + 1,
            int(current[0]) if current else 0
        )

        db.execute("""
            INSERT INTO consumer_progress
            (topic, partition_id, next_offset)
            VALUES (?,?,?)
            ON CONFLICT(topic, partition_id)
            DO UPDATE SET next_offset=excluded.next_offset
        """, (topic, partition, next_offset))

    return duplicate


def checkpoint(db, topic, partition):
    row = db.execute("""
        SELECT next_offset FROM consumer_progress
        WHERE topic=? AND partition_id=?
    """, (topic, partition)).fetchone()
    return None if row is None else int(row[0])
