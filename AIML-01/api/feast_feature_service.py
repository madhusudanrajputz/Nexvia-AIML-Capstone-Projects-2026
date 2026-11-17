
"""Persistent local Feast lookup service for AIML-01.

Internal development service, bound to 127.0.0.1 only.
The feature store is loaded once per service process.

Production deployment requires authentication, access
controls, operational monitoring and secure networking.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from feast import FeatureStore
import json
import os
import sys

STORE = FeatureStore(repo_path=os.environ["AIML_FEAST_REPO"])

FIELDS = [
    "origin_previous_count",
    "origin_previous_total",
    "origin_previous_mean",
    "origin_hours_since_previous",
    "destination_previous_count",
    "destination_previous_total",
    "destination_previous_mean",
    "destination_hours_since_previous",
]

REFS = [
    ("origin_account_history:" if f.startswith("origin_")
     else "destination_account_history:") + f
    for f in FIELDS
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def reply(self, status, payload):
        raw = json.dumps(
            payload,
            allow_nan=False
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {
                "status": "ready",
                "feast_loaded": True,
                "historical_fields": len(FIELDS)
            })
        self.reply(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/features":
            return self.reply(404, {"error": "not_found"})

        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                return self.reply(413, {"error": "invalid_size"})

            data = json.loads(self.rfile.read(size))
            if (
                not isinstance(data, dict)
                or set(data) != {"nameOrig", "nameDest"}
                or any(
                    not isinstance(data[k], str) or not data[k]
                    for k in ("nameOrig", "nameDest")
                )
            ):
                return self.reply(422, {"error": "invalid_entities"})

            response = STORE.get_online_features(
                features=REFS,
                entity_rows=[data],
                full_feature_names=True
            ).to_dict()

            output = {}
            for field in FIELDS:
                prefix = (
                    "origin_account_history__"
                    if field.startswith("origin_")
                    else "destination_account_history__"
                )
                key = prefix + field
                values = response.get(key)

                if values is None or len(values) != 1:
                    raise RuntimeError("Missing feature field")

                value = values[0]
                if hasattr(value, "item"):
                    value = value.item()

                output[field] = value

            if any(v is None for v in output.values()):
                return self.reply(404, {
                    "error": "historical_features_unavailable"
                })

            return self.reply(200, output)

        except (ValueError, TypeError, json.JSONDecodeError):
            return self.reply(422, {"error": "invalid_request"})
        except Exception:
            return self.reply(503, {
                "error": "feast_lookup_failed"
            })


if __name__ == "__main__":
    port = int(os.environ["AIML_FEAST_PORT"])
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("FEAST_SERVICE_READY", flush=True)
    server.serve_forever()
