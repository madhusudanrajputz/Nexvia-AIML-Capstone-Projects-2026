
"""PaySim hour-buffered origin/destination account state.

Historical snapshots use only events from strictly earlier
PaySim steps. No event from the same step is visible.

Requires a globally nondecreasing transaction-step stream.
For Kafka, partition ordering and watermark/late-event policy
must be implemented and tested separately.
"""

from collections import defaultdict
from pathlib import Path
import json
import math
import os


class HourBufferedAccountState:
    def __init__(self):
        self.current_step = None
        self.committed = {}
        self.pending = {}

    @staticmethod
    def _key(role, account):
        if role not in ("origin", "destination"):
            raise ValueError("Role must be origin or destination")
        if not isinstance(account, str) or not account:
            raise ValueError("Account ID must be a nonempty string")
        return role + "|" + account

    @staticmethod
    def _validate_step(step):
        if isinstance(step, bool) or not isinstance(step, int):
            raise ValueError("Step must be an integer")
        if step < 1:
            raise ValueError("Step must be >= 1")

    def advance_to(self, step):
        self._validate_step(step)
        if self.current_step is None:
            self.current_step = step
            return

        if step < self.current_step:
            raise ValueError("Out-of-order historical step")

        if step == self.current_step:
            return

        # Only when the hour changes are buffered events
        # added to the history visible to later hours.
        for key, pending in self.pending.items():
            existing = self.committed.get(
                key, {"count": 0, "total": 0.0, "last_step": None}
            )
            self.committed[key] = {
                "count": existing["count"] + pending["count"],
                "total": existing["total"] + pending["total"],
                "last_step": self.current_step,
            }
        self.pending.clear()
        self.current_step = step

    def snapshot(self, role, account, step):
        self.advance_to(step)
        key = self._key(role, account)
        state = self.committed.get(
            key, {"count": 0, "total": 0.0, "last_step": None}
        )

        count = int(state["count"])
        total = float(state["total"])
        last_step = state["last_step"]

        hours = -1 if last_step is None else step - last_step

        return {
            role + "_previous_count": count,
            role + "_previous_total": total,
            role + "_previous_mean": total / count if count else 0.0,
            role + "_hours_since_previous": hours,
        }

    def observe(self, role, account, step, amount):
        self._validate_step(step)
        key = self._key(role, account)

        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("Amount must be numeric")
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Amount must be finite and nonnegative")

        self.advance_to(step)
        existing = self.pending.get(
            key, {"count": 0, "total": 0.0}
        )
        existing["count"] += 1
        existing["total"] += float(amount)
        self.pending[key] = existing

    def observe_transaction(self, origin, destination, step, amount):
        if origin == destination:
            raise ValueError("Self-transfer is unsupported")
        # Advance and validate both updates before writing.
        self.advance_to(step)
        self._key("origin", origin)
        self._key("destination", destination)
        if isinstance(amount, bool) or not isinstance(
            amount, (int, float)
        ) or not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid transaction amount")

        self.observe("origin", origin, step, amount)
        self.observe("destination", destination, step, amount)

    def save_json(self, path):
        path = Path(path)
        if path.exists():
            raise FileExistsError("State checkpoint already exists")

        payload = {
            "version": 1,
            "current_step": self.current_step,
            "committed": self.committed,
            "pending": self.pending,
        }
        temporary = path.with_name(path.name + ".partial")
        if temporary.exists():
            raise FileExistsError("Partial checkpoint already exists")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temporary, path)

    @classmethod
    def load_json(cls, path):
        payload = json.loads(
            Path(path).read_text(encoding="utf-8")
        )
        if payload.get("version") != 1:
            raise ValueError("Unsupported state checkpoint version")

        state = cls()
        state.current_step = payload["current_step"]
        state.committed = payload["committed"]
        state.pending = payload["pending"]
        return state
