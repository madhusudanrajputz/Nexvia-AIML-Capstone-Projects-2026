"""
AIML-01 restricted deployment entrypoint.

Reuses the original FastAPI + XGBoost + persistent Feast
adapter without modifying prediction logic.

Prediction is disabled by default.

The explicit demo switch and API key are NOT substitutes
for production authentication, live-state freshness,
durable hosting, or operational recovery.

Use a server-side frontend proxy. Never place the
backend API key inside browser JavaScript.
"""

import hmac
import json
import os

from fraud_api_persistent import app as original_app


class RestrictedDeploymentApp:
    def __init__(self, downstream):
        self.downstream = downstream

    @staticmethod
    async def respond(send, status, message):
        payload = json.dumps({
            "detail": message
        }).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        })

        await send({
            "type": "http.response.body",
            "body": payload,
        })

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.downstream(
                scope, receive, send
            )

        path = scope.get("path", "").rstrip("/") or "/"
        method = scope.get("method", "").upper()

        # Explicit minimal public route surface.
        if path == "/health" and method == "GET":
            return await self.downstream(
                scope, receive, send
            )

        if path != "/predict" or method != "POST":
            return await self.respond(
                send, 404, "Not found"
            )

        enabled = (
            os.environ.get(
                "AIML01_ENABLE_DEMO_PREDICT", "0"
            ) == "1"
        )

        if not enabled:
            return await self.respond(
                send, 503,
                "Prediction disabled until demo readiness is verified"
            )

        expected_key = os.environ.get(
            "AIML01_DEPLOYMENT_API_KEY", ""
        )

        if len(expected_key) < 32:
            return await self.respond(
                send, 503,
                "Deployment authentication is not configured"
            )

        supplied_values = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"x-api-key"
        ]

        if len(supplied_values) != 1:
            return await self.respond(
                send, 401, "Unauthorized"
            )

        try:
            supplied_key = supplied_values[0].decode("ascii")
        except UnicodeDecodeError:
            return await self.respond(
                send, 401, "Unauthorized"
            )

        if not hmac.compare_digest(
            supplied_key, expected_key
        ):
            return await self.respond(
                send, 401, "Unauthorized"
            )

        # The original API still enforces its fixed-hour
        # input validation and uses persistent Feast history.
        return await self.downstream(
            scope, receive, send
        )


app = RestrictedDeploymentApp(original_app)
