"""Access-log volume guards for the request middleware.

The NSSM service writes its log with no rotation cap, so one forever-polled
endpoint logging at INFO is not cosmetic. ``/ibkr/status`` was missing from the
quiet list and wrote 16,698 of the last 16,850 lines (99.1%) of a 167 MB
error log: the shell polls it every 3s while DISCONNECTED, and disconnected is
the permanent steady state because boot stays broker-free by house rule.

Two contracts are pinned here — a successful poll is DEBUG while anything that
failed stays visible, and the two streams are split so the *error* log means
errors. The middleware is driven straight against its ASGI callable: no server
boot, no lifespan, no broker touch.
"""
import asyncio
import logging
import subprocess
import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))

from webapp.backend.middleware.request_id import (  # noqa: E402
    _NOISY_PATH_PREFIXES,
    RequestIDMiddleware,
)

_LOGGER = "chrollo.request"


def _drive(path: str, status: int = 200) -> None:
    """Run one request through the middleware wrapped around a stub app."""
    async def app(scope, receive, send):
        await send({"type": "http.response.start",
                    "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message):
        return None

    scope = {"type": "http", "method": "GET", "path": path, "headers": []}
    asyncio.run(RequestIDMiddleware(app)(scope, None, send))


def _sole_record(caplog):
    records = [r for r in caplog.records if r.name == _LOGGER]
    assert len(records) == 1, f"expected one access line, got {len(records)}"
    return records[0]


@pytest.mark.parametrize("prefix", _NOISY_PATH_PREFIXES)
def test_a_successful_poll_of_a_noisy_path_is_quiet(prefix, caplog):
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        _drive(prefix)
    assert _sole_record(caplog).levelno == logging.DEBUG, (
        f"{prefix} is polled forever — a 200 there must not log at INFO"
    )


def test_the_broker_status_poll_is_quieted():
    """The 167 MB regression: this exact path was absent from the list."""
    assert "/ibkr/status" in _NOISY_PATH_PREFIXES, (
        "the shell polls /ibkr/status every 3s while disconnected, which is "
        "the steady state — removing it from the quiet list regrows the log"
    )


def test_a_failed_poll_stays_visible(caplog):
    """Quieting is for successful noise only — a broken poll must still speak."""
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        _drive("/ibkr/status", status=503)
    assert _sole_record(caplog).levelno == logging.INFO


def test_an_ordinary_route_is_not_quieted(caplog):
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        _drive("/screener-data/")
    assert _sole_record(caplog).levelno == logging.INFO


def test_info_goes_to_stdout_and_warnings_to_stderr():
    """Plain basicConfig() puts every level on stderr, which is how routine
    access lines filled the *error* log while the stdout log stayed tiny.
    Imported the way the service imports it; import does not run lifespan."""
    code = (
        "import logging, sys\n"
        "import main  # noqa: F401\n"
        "root = logging.getLogger()\n"
        "out = [h for h in root.handlers"
        " if getattr(h, 'stream', None) is sys.stdout]\n"
        "err = [h for h in root.handlers"
        " if getattr(h, 'stream', None) is sys.stderr]\n"
        "assert len(out) == 1, f'stdout handlers: {len(out)}'\n"
        "assert len(err) == 1, f'stderr handlers: {len(err)}'\n"
        "def rec(level):\n"
        "    return logging.LogRecord('chrollo.t', level, 'probe', 1,"
        " 'x', None, None)\n"
        "assert out[0].filter(rec(logging.INFO)), 'INFO must reach stdout'\n"
        "assert not out[0].filter(rec(logging.WARNING)),"
        " 'WARNING must not double-log to stdout'\n"
        "assert err[0].level == logging.WARNING, err[0].level\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"log-stream split broken (exit {proc.returncode}):\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_uvicorns_access_log_stays_silenced():
    """One access log, and it is ours.

    uvicorn's access logger records the same event as chrollo.request with less
    information (no request id, no duration) and no quiet list, so it wrote
    every request twice and kept logging the 3-second /ibkr/status poll after
    the middleware stopped. Measured right after the 2026-08-25 redeploy: 2,296
    of the next 3,000 stdout lines were uvicorn logging GET /ibkr/status.

    Errors are untouched — chrollo.request logs every non-2xx at INFO and every
    exception with a traceback, and uvicorn.access can still report at WARNING.
    """
    code = (
        "import logging, sys\n"
        "import main  # noqa: F401\n"
        "access = logging.getLogger('uvicorn.access')\n"
        "assert not access.isEnabledFor(logging.INFO),"
        " 'uvicorn.access logs at INFO again - the access-log twin is back'\n"
        "assert access.isEnabledFor(logging.WARNING),"
        " 'uvicorn.access must still be able to report problems'\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"uvicorn access-log twin returned (exit {proc.returncode}):\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
