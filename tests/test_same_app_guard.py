"""The default-on browser-origin guard (council 2026-09-07, finding 3).

The opt-in header guard (``routers.calibration.require_same_app``) reached 15
of 85 routes and structurally could never reach the three scan/download SSE
streams, because ``EventSource`` cannot send a header. Left unguarded: all four
IBKR control routes, every archive write, the journal writes — reachable by any
page open in the operator's browser as a CORS *simple request*, whose side
effect lands server-side whether or not the browser lets that page read the
answer.

These pin the replacement: a guard that runs for EVERY request and reads what
the BROWSER attests (``Sec-Fetch-Site`` / ``Origin`` — forbidden header names
page JS cannot set), so a route added tomorrow inherits it. The middleware is
driven straight against its ASGI callable: no server boot, no lifespan, no
broker touch. The wiring into the real app is pinned in test_service_boot.py,
which already imports main.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webapp.backend.middleware.same_app import (  # noqa: E402
    DEV_ORIGINS,
    SameAppOriginGuard,
    refusal_class,
)

_APP_ORIGIN = "http://localhost:8000"
_APP_HOST = "localhost:8000"


def _drive(method: str, path: str, headers: dict[str, str]) -> tuple[int, bool]:
    """One request through the guard wrapped around a stub app.

    Returns ``(status, reached_inner_app)`` — the second half is the point:
    a refusal that still ran the handler is not a refusal.
    """
    reached = {"value": False}

    async def inner(scope, receive, send):
        reached["value"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    status = {"value": 0}

    async def send(message):
        if message["type"] == "http.response.start":
            status["value"] = message["status"]

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "scheme": "http",
        "headers": [(k.lower().encode(), v.encode())
                    for k, v in {"host": _APP_HOST, **headers}.items()],
    }
    asyncio.run(SameAppOriginGuard(inner)(scope, receive, send))
    return status["value"], reached["value"]


# ── what a hostile page looks like on the wire ────────────────────────────

# A page on the internet firing a body-less POST at 127.0.0.1. No preflight
# stops it; CORS only hides the response, which the attacker does not need.
_CROSS_SITE = {"sec-fetch-site": "cross-site", "origin": "https://evil.example"}
# The same page firing an <img>/EventSource GET, which sends no Origin at all.
_CROSS_SITE_NO_ORIGIN = {"sec-fetch-site": "cross-site"}
# An older browser that reports no Sec-Fetch-Site but still sends Origin.
_FOREIGN_ORIGIN_ONLY = {"origin": "https://evil.example"}


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_a_cross_site_mutation_is_refused_before_the_handler(method):
    status, reached = _drive(method, "/ibkr/disconnect", _CROSS_SITE)
    assert status == 403
    assert not reached, "the guard answered 403 but the handler still ran"


def test_a_cross_site_stream_get_is_refused():
    """The hole the header guard could never close: EventSource sends no
    custom header, but the browser stamps Sec-Fetch-Site on it regardless."""
    status, reached = _drive("GET", "/run-scan-stream/", _CROSS_SITE_NO_ORIGIN)
    assert (status, reached) == (403, False)


def test_a_foreign_origin_without_sec_fetch_site_is_refused():
    status, reached = _drive("POST", "/ibkr/reconnect", _FOREIGN_ORIGIN_ONLY)
    assert (status, reached) == (403, False)


# ── what the app itself looks like, which must keep working ───────────────

def test_the_production_app_calling_itself_passes():
    status, reached = _drive("POST", "/ibkr/reconnect",
                             {"sec-fetch-site": "same-origin",
                              "origin": _APP_ORIGIN})
    assert (status, reached) == (200, True)


def test_a_same_origin_get_with_no_origin_header_passes():
    status, reached = _drive("GET", "/stream/portfolio",
                             {"sec-fetch-site": "same-origin"})
    assert (status, reached) == (200, True)


def test_the_operator_typing_the_url_passes():
    """A user-initiated navigation has no initiator: Sec-Fetch-Site: none."""
    status, reached = _drive("GET", "/", {"sec-fetch-site": "none"})
    assert (status, reached) == (200, True)


@pytest.mark.parametrize("origin", DEV_ORIGINS)
def test_the_vite_dev_server_passes(origin):
    """`npm run dev` serves the page on :5173 and calls the API on :8000 —
    cross-origin by construction, and the one caller that is still us."""
    status, reached = _drive("POST", "/calibration/marks",
                             {"sec-fetch-site": "same-site", "origin": origin})
    assert (status, reached) == (200, True)


def test_a_non_browser_caller_passes():
    """curl on the operator's own box sends neither header. The threat closed
    here is a PAGE; who can reach the port at all is TrustedHost's job."""
    status, reached = _drive("POST", "/update-returns", {})
    assert (status, reached) == (200, True)


def test_the_cors_preflight_is_never_refused():
    """The preflight is what makes the header guard work — refusing it would
    break the very cross-origin dev flow both layers deliberately allow."""
    status, reached = _drive("OPTIONS", "/calibration/marks", _CROSS_SITE)
    assert status == 200


# ── the policy as a pure function (no exemption may be keyed on method) ───

def test_no_method_is_exempt_from_the_policy():
    for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"):
        assert refusal_class(method, _CROSS_SITE, _APP_ORIGIN) is not None, method
