"""UTF-8 for the service's OWN log streams.

Under the NSSM service, ``sys.stdout``/``sys.stderr`` are the two files named in
``docs/deploy.md`` §2, opened with the Windows locale codec (cp1252). A log
record carrying a character cp1252 cannot encode is therefore not written at
all: ``StreamHandler.emit()`` raises ``UnicodeEncodeError``, ``handleError()``
prints a traceback to stderr, and the record is DROPPED. Measured on the live
box: 15 ``--- Logging error ---`` blocks in ``output/chrollo-service-error.log``,
every one a 'charmap' failure on the arrow U+2192 — the character the scan child
prints and the relay repeats into our logger (``services/scan_runner.py:76``).

``services/scan_runner.py:45-52`` already forces ``PYTHONUTF8``/
``PYTHONIOENCODING`` on the scan CHILD and decodes the pipe as UTF-8 at
``:62-63``. This closes the last hop of that same path: the child encodes UTF-8,
the parent decodes UTF-8, and then the parent re-encoded to cp1252 on the way to
disk. There is no implementation to fold with (EC-3) — that side is a subprocess
environment handed to a process we spawn, this side is our own already-open
streams; what the two share is the choice of codec and ``errors="replace"``,
not code.
"""
from __future__ import annotations


def force_utf8(stream) -> bool:
    """Switch one already-open text stream to UTF-8 in place.

    Returns True when the stream is UTF-8 afterwards, False when it could not be
    reconfigured (and the locale codec stays in force).

    ``reconfigure()`` mutates the existing ``TextIOWrapper``, so the single call
    also fixes every reference already taken — uvicorn's handlers, APScheduler's,
    ours — and leaves ``line_buffering``/``write_through`` alone, which wrapping
    the raw buffer in a fresh wrapper would silently reset.

    ``errors="replace"`` matches ``scan_runner.py:63``: a stray character must
    degrade to a placeholder, because losing the whole line is the bug. It also
    covers the one thing UTF-8 cannot encode — a lone surrogate, e.g. a
    ``surrogateescape``-decoded Windows path quoted in an exception message.

    Never raises. This runs at import time in a service whose boot must not die
    for a logging preference, and there is no recovery beyond keeping the locale
    codec. A ``hasattr`` guard alone is NOT enough: ``reconfigure`` also exists on
    a detached wrapper and on a closed one and raises ``ValueError`` in both —
    hence the getattr check AND the try/except.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return False
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return True
