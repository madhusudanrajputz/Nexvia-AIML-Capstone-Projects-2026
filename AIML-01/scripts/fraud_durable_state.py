
"""Durable PaySim account history with strict-hour semantics.

Atomic SQLite updates protect pending/committed state and
processed-event IDs. Strict increasing global hour policy.

Kafka acknowledgment and Feast online writes are NOT
atomic with this database. Further integration required.
"""

import math
import sqlite3


class LateEventError(ValueError):
    pass


class DurableAccountState:
    def __init__(self, database_path):
        self.db = sqlite3.connect(str(database_path), timeout=20)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=20000")

        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS accounts (
            role TEXT NOT NULL,
            account TEXT NOT NULL,
            count INTEGER NOT NULL,
            total REAL NOT NULL,
            last_step INTEGER,
            PRIMARY KEY(role, account)
        );

        CREATE TABLE IF NOT EXISTS pending (
            role TEXT NOT NULL,
            account TEXT NOT NULL,
            count INTEGER NOT NULL,
            total REAL NOT NULL,
            PRIMARY KEY(role, account)
        );

        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            transaction_id INTEGER NOT NULL,
            step INTEGER NOT NULL,
            amount REAL NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL
        );
        """)

    def initialize(self, step, account_rows):
        if not isinstance(step, int) or step < 1:
            raise ValueError("Invalid initial step")

        with self.db:
            existing = self.db.execute(
                "SELECT value FROM metadata WHERE key='step'"
            ).fetchone()

            if existing:
                raise RuntimeError("State already initialized")

            for role, account, count, total, age in account_rows:
                count = int(count)
                total = float(total)
                age = int(age)

                if role not in ("origin", "destination"):
                    raise ValueError("Invalid account role")
                if count < 0 or total < 0:
                    raise ValueError("Invalid historical state")
                if count == 0:
                    if age != -1 or total != 0:
                        raise ValueError("Invalid empty-account state")
                    last = None
                else:
                    if age < 1:
                        raise ValueError("Invalid account age")
                    last = step - age

                self.db.execute("""
                    INSERT INTO accounts
                    (role, account, count, total, last_step)
                    VALUES (?, ?, ?, ?, ?)
                """, (role, account, count, total, last))

            self.db.execute(
                "INSERT INTO metadata VALUES ('step', ?)",
                (step,)
            )

    def current_step(self):
        row = self.db.execute(
            "SELECT value FROM metadata WHERE key='step'"
        ).fetchone()
        if row is None:
            raise RuntimeError("State not initialized")
        return int(row[0])

    def _advance(self, step):
        old_step = self.current_step()

        if step < old_step:
            raise LateEventError(
                f"Late event: step {step} < finalized step {old_step}"
            )
        if step == old_step:
            return

        pending = self.db.execute("""
            SELECT role, account, count, total FROM pending
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
            """, (role, account, count, total, old_step))

        self.db.execute("DELETE FROM pending")
        self.db.execute(
            "UPDATE metadata SET value=? WHERE key='step'",
            (step,)
        )

    def advance_to(self, step):
        if not isinstance(step, int) or step < 1:
            raise ValueError("Invalid step")
        with self.db:
            self._advance(step)

    def snapshot(self, role, account, step=None):
        if step is None:
            step = self.current_step()

        if step != self.current_step():
            raise ValueError(
                "Snapshot requires current state step"
            )

        if role not in ("origin", "destination"):
            raise ValueError("Invalid role")

        row = self.db.execute("""
            SELECT count, total, last_step
            FROM accounts
            WHERE role=? AND account=?
        """, (role, account)).fetchone()

        if row is None:
            count, total, last = 0, 0.0, None
        else:
            count, total, last = row

        return {
            role + "_previous_count": int(count),
            role + "_previous_total": float(total),
            role + "_previous_mean": (
                float(total) / count if count else 0.0
            ),
            role + "_hours_since_previous": (
                -1 if last is None else int(step - last)
            )
        }

    def process(self, event):
        event_id = str(event["event_id"])
        txid = int(event["transaction_id"])
        step = int(event["step"])
        origin = str(event["nameOrig"])
        destination = str(event["nameDest"])
        amount = float(event["amount"])

        if (
            event_id != f"paysim:{txid}"
            or txid < 1 or step < 1
            or not origin or not destination
            or origin == destination
            or not math.isfinite(amount)
            or amount < 0
        ):
            raise ValueError("Invalid event")

        with self.db:
            previous = self.db.execute("""
                SELECT transaction_id, step, amount,
                       origin, destination
                FROM processed_events
                WHERE event_id=?
            """, (event_id,)).fetchone()

            if previous is not None:
                expected = (
                    txid, step, amount, origin, destination
                )
                if previous != expected:
                    raise ValueError(
                        "Conflicting duplicate event"
                    )
                return "DUPLICATE"

            self._advance(step)

            for role, account in (
                ("origin", origin),
                ("destination", destination)
            ):
                self.db.execute("""
                    INSERT INTO pending
                    (role, account, count, total)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(role, account) DO UPDATE SET
                        count = pending.count + 1,
                        total = pending.total + excluded.total
                """, (role, account, amount))

            self.db.execute("""
                INSERT INTO processed_events
                (event_id, transaction_id, step, amount,
                 origin, destination)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                event_id, txid, step, amount,
                origin, destination
            ))

        return "ACCEPTED"

    def count_events(self):
        return self.db.execute(
            "SELECT COUNT(*) FROM processed_events"
        ).fetchone()[0]

    def close(self):
        self.db.close()
