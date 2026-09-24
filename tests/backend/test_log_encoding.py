"""The service's log streams must be able to write the characters it logs.

Under NSSM, sys.stdout/sys.stderr are the two files from docs/deploy.md §2,
opened with the Windows locale codec. A record carrying a char cp1252 lacks was
not written at all: StreamHandler.emit() raised UnicodeEncodeError, handleError()
printed a traceback, and the record was DROPPED. Measured on the live box: 15
"--- Logging error ---" blocks in output/chrollo-service-error.log, every one a
'charmap' failure on the arrow U+2192 that the scan relay repeats into our
logger (services/scan_runner.py:76). Losing the line is the bug, so the contract
pinned here is *written*, not *pretty*.
"""
import io
import os
import subprocess
import sys

import pytest

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))

from app.log_encoding import force_utf8  # noqa: E402

_ARROW = "→"
_ARROW_UTF8 = _ARROW.encode("utf-8")

# Log one record on each side of the WARNING split, so this also proves the fix
# did not cost the stdout/stderr routing. Imported the way the service imports
# it; import does not run lifespan.
_PROBE = (
    "import logging\n"
    "import main  # noqa: F401  (configures the handlers the service runs on)\n"
    "log = logging.getLogger('chrollo.encoding_probe')\n"
    f"log.info('scan relay {_ARROW} info')\n"
    f"log.warning('scan relay {_ARROW} warning')\n"
    "logging.shutdown()\n"
)


def _run_probe(tmp_path):
    """Import main with cp1252 stdio redirected to files — the service's shape."""
    out_path = tmp_path / "chrollo-service.log"
    err_path = tmp_path / "chrollo-service-error.log"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        proc = subprocess.run(
            [sys.executable, "-c", _PROBE],
            cwd=str(BACKEND_DIR),
            stdout=out,
            stderr=err,
            env=env,
            timeout=300,
        )
    return proc, out_path.read_bytes(), err_path.read_bytes()


@pytest.mark.slow
def test_a_non_ascii_record_survives_to_the_log_file(tmp_path):
    proc, out, err = _run_probe(tmp_path)
    assert proc.returncode == 0, (
        f"probe exited {proc.returncode}\n"
        f"{out.decode('utf-8', 'replace')}\n{err.decode('utf-8', 'replace')}"
    )
    assert b"--- Logging error ---" not in err, (
        "logging dropped a record and reported it instead of writing it:\n"
        + err.decode("utf-8", "replace")
    )
    assert b"scan relay " + _ARROW_UTF8 + b" info" in out, (
        "the INFO line with an arrow never reached the stdout log:\n"
        + out.decode("utf-8", "replace")
    )
    assert b"scan relay " + _ARROW_UTF8 + b" warning" in err, (
        "the WARNING line with an arrow never reached the stderr log:\n"
        + err.decode("utf-8", "replace")
    )


def test_force_utf8_reconfigures_a_locale_codec_stream():
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    assert force_utf8(stream) is True
    assert stream.encoding == "utf-8"
    stream.write(_ARROW)
    stream.flush()
    assert _ARROW_UTF8 in buffer.getvalue()


def test_force_utf8_replaces_what_utf8_cannot_encode():
    """A lone surrogate (a surrogateescape-decoded Windows path in a traceback)
    is the one thing UTF-8 still cannot encode. It must cost a placeholder, not
    the line."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    assert force_utf8(stream) is True
    stream.write("path \udcff end")
    stream.flush()
    assert b"path " in buffer.getvalue() and b" end" in buffer.getvalue()


def _detached_wrapper():
    stream = io.TextIOWrapper(io.BytesIO())
    stream.detach()
    return stream


def _closed_wrapper():
    stream = io.TextIOWrapper(io.BytesIO())
    stream.close()
    return stream


@pytest.mark.parametrize("stream", [
    None,                       # pythonw / no console: sys.stdout is None
    io.StringIO(),              # captured stdio: no reconfigure attribute
    _detached_wrapper(),        # HAS reconfigure, raises ValueError
    _closed_wrapper(),          # HAS reconfigure, raises ValueError
])
def test_force_utf8_falls_back_instead_of_killing_boot(stream):
    """This runs at import time in the service. A hasattr() guard alone sails
    straight into the last two cases and takes the boot down for a logging
    preference — far worse than the defect being fixed."""
    assert force_utf8(stream) is False
