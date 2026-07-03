"""Request ID and timing middleware."""
from __future__ import annotations

import logging
import time
import uuid

_req_log = logging.getLogger("chrollo.request")

# The frontend polls these endpoints forever (Home price zones, the 60s
# scan-status/health tick, long-lived SSE streams). At INFO they dominate the
# service log and — with no rotation cap — grow it unboundedly, burying the
# lines that matter. Successful polls log at DEBUG; errors stay at INFO.
_NOISY_PATH_PREFIXES = ("/live-prices", "/scan-status", "/health", "/stream/")


class RequestIDMiddleware:
    """Pure-ASGI middleware that tags each HTTP request with a short ID."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        request_id = headers.get("x-request-id") or uuid.uuid4().hex[:8]
        scope.setdefault("state", {})["request_id"] = request_id

        start = time.perf_counter()
        status_code = {"value": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code["value"] = message["status"]
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _req_log.exception(
                "rid=%s %s %s -> 500 (%.1f ms)",
                request_id,
                scope.get("method"),
                scope.get("path"),
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        path = scope.get("path") or ""
        quiet = path.startswith(_NOISY_PATH_PREFIXES) and status_code["value"] < 400
        _req_log.log(
            logging.DEBUG if quiet else logging.INFO,
            "rid=%s %s %s -> %d (%.1f ms)",
            request_id,
            scope.get("method"),
            path,
            status_code["value"],
            elapsed_ms,
        )
