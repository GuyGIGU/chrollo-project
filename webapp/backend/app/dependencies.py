"""Shared HTTP dependencies for same-app request admission."""
from fastapi import Header, HTTPException

_CLIENT_HEADER_VALUE = "chrollo-dashboard"


def require_same_app(x_chrollo_client: str = Header(default="")):
    """Only our own frontend passes. THE POSTURE RULE (stated once, here) has
    TWO layers, and this is the opt-in one: a route declares this dependency
    and gains a header no cross-origin page can send. It is declared on every
    mutating route in this router, on the expensive GETs, and on any route
    BUILT with it from day one (the candle reads) — but retrofitting it onto a
    pre-existing open GET is a breaking change for that route's callers and is
    done deliberately, not by drift.

    The second layer is the DEFAULT one and needs no declaration:
    ``middleware/same_app.SameAppOriginGuard`` refuses every request a browser
    attests came from another page, using ``Sec-Fetch-Site`` / ``Origin``,
    which page JS cannot forge. It covers routes nobody remembered to decorate
    and the SSE streams this header can never reach (``EventSource`` cannot
    set one). A new route is therefore guarded whether or not its author read
    this docstring; declaring the header on top is the stricter belt for
    routes whose callers already send it.

    The DNS-rebinding vector neither header can stop — a rebound page IS
    same-origin — is closed by the TrustedHost allowlist in main.py."""
    if x_chrollo_client != _CLIENT_HEADER_VALUE:
        raise HTTPException(status_code=403, detail={
            "class": "cross_app_write",
            "message": "calibration writes require the X-Chrollo-Client header",
        })

