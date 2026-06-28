"""Shared ``sys.path`` bootstrap for the ``tools/`` scripts.

Every tool is run as a standalone script (``python -m tools.foo`` or
``python tools/foo.py``) and needs the repository root on ``sys.path`` so the
``config`` / ``core`` / ``tools`` packages import. This collapses the bootstrap
block that was pasted verbatim across the tools into one call.
"""

import os
import sys

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def configure_path() -> str:
    """Prepend the repository root to ``sys.path`` (idempotent) and return it."""
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    return _PROJECT_ROOT
