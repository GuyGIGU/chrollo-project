"""The default-on half of the same-app posture rule.

`routers/calibration.require_same_app` states the first half: a custom header
no cross-origin page can send, declared per route. It has one structural blind
spot and one practical one.

*Structural:* `EventSource` cannot set a header, so the three scan/download SSE
streams — the app's single biggest side effect, a 12-17 minute subprocess that
writes the live archive and holds `SCAN_LOCK` — could never carry it.

*Practical:* a guard you opt into per route is only applied to the routes
someone remembered. Measured 2026-09-07: 15 of 85 routes carried it, and 28
mutating or streaming routes did not, including all four IBKR control routes.
The read-only broker rail is this project's loudest safety promise and it
rested on nobody having a stray browser page open.

This layer inverts the default. It runs for EVERY request, so a route added
tomorrow is covered without opting in, and there is no exemption list to grow
stale. It judges what the BROWSER attests, never what the page chooses to
send: `Sec-Fetch-Site` and `Origin` are forbidden header names that page JS
cannot set or override, and a browser attaches them to everything — an
`EventSource` GET, a body-less form POST, an `<img>` src. That is exactly the
class CORS does not stop, because the side effect lands server-side whether or
not the browser lets the attacking page read the answer.

A caller that sends NEITHER header is not a browser (curl on the operator's own
box, the TestClient, a local script) and is allowed through: the threat closed
here is a *page*, and localhost-only + `TrustedHostMiddleware` already bound
who can reach the port at all.

Three consequences worth knowing before you debug a 403 here (council review
2026-09-07 follow-up, findings 1-3):

*A cross-site LINK to the dashboard is refused.* Typing the URL, a bookmark and
`start_dashboard.bat` all report `Sec-Fetch-Site: none` and pass; clicking a
link to `http://localhost:8000` from a chat window, an IDE or a rendered README
reports `cross-site` and gets this JSON 403, not the dashboard. Deliberate:
this app has state-changing plain GETs (`/run-scan-stream/` starts a 12-17
minute subprocess that rewrites the live archive), so exempting top-level
navigations — `Sec-Fetch-Dest: document` — would hand a hostile page exactly
the attack this guard exists to stop. Reach the dashboard from the address bar.

*The dev carve-out keys on `Origin`, so it cannot cover a no-cors subresource.*
An `<img>`/`<link>`/`<video>` load sends no `Origin` at all, only
`Sec-Fetch-Site: same-site` across `:5173 -> :8000`, which is refused. So the
app must never hand the browser a cross-origin subresource URL: the journal
attachment URL is relative and `vite.config.js` proxies `/attachments` in dev
(`routers/journal._attachment_dict`). Do NOT fix a case like that by trusting
`same-site` — that reopens the guard to every other page on localhost, which is
most of what it buys.

*`OPTIONS` is the one carve-out, and it is keyed on the method, never a path.*
The CORS preflight is what makes the cross-origin dev flow work at all;
`CORSMiddleware` sits outside this guard and answers or rejects it first, and a
preflight that reaches a route gets a 405. There is no path exemption, and
adding one is the thing EC-56 forbids.
"""
from __future__ import annotations

import logging
from typing import Mapping

from starlette.responses import JSONResponse

log = logging.getLogger("chrollo.request")

# The ONE cross-origin caller Chrollo has: the Vite dev server, which serves the
# page on :5173 and calls the API on :8000. Shared with the CORS allowlist in
# main.py so the two can never disagree about who is us.
DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

# `same-origin` is the production app calling itself; `none` is the operator
# typing the URL or opening a bookmark (a user-initiated navigation has no
# initiator). Everything else a browser can report — `cross-site`, `same-site` —
# means another page initiated this, and only the dev server is allowed to.
_TRUSTED_SITES = ("same-origin", "none")


def refusal_class(method: str, headers: Mapping[str, str],
                  self_origin: str | None) -> str | None:
    """The whole decision, as a pure function. None means "let it through"."""
    if method == "OPTIONS":
        return None  # the CORS preflight the guard depends on; CORSMiddleware answers it
    origin = headers.get("origin")
    if origin in DEV_ORIGINS:
        return None
    site = headers.get("sec-fetch-site")
    if site is not None and site not in _TRUSTED_SITES:
        return "cross_site_request"
    if origin is not None and origin != self_origin:
        return "cross_origin_request"
    return None


def _self_origin(scope, headers: Mapping[str, str]) -> str | None:
    host = headers.get("host")
    return f"{scope.get('scheme', 'http')}://{host}" if host else None


class SameAppOriginGuard:
    """Pure-ASGI so it never buffers a streaming response (the SSE routes it
    exists to protect are the ones BaseHTTPMiddleware would break)."""

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
        reason = refusal_class(scope.get("method", ""), headers,
                               _self_origin(scope, headers))
        if reason is None:
            await self.app(scope, receive, send)
            return

        log.warning(
            "refused %s %s: %s (origin=%r sec-fetch-site=%r)",
            scope.get("method"), scope.get("path"), reason,
            headers.get("origin"), headers.get("sec-fetch-site"),
        )
        response = JSONResponse(
            status_code=403,
            content={
                "class": reason,
                "message": "this request did not come from the Chrollo app",
            },
        )
        await response(scope, receive, send)
