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


# Directories no tool-written report may ever land in: the sealed marks
# corpus (EC-7 — immutable operator ground truth / acceptance specs) and the
# sealed ratchet baselines. ONE guard for every tool write (EC-3): a mistyped
# --out/--json path must fail loudly here, never silently clobber a spec.
_SEALED_DIRS = (
    os.path.join(_PROJECT_ROOT, "docs", "marks"),
    os.path.join(_PROJECT_ROOT, "tests", "baselines"),
)


def refuse_sealed_output(path: str) -> str:
    """Raise if ``path`` sits under a sealed directory; return it otherwise."""
    target = os.path.abspath(path)
    for sealed in _SEALED_DIRS:
        if target == sealed or target.startswith(sealed + os.sep):
            raise ValueError(
                f"refusing to write under the sealed directory ({sealed}) — "
                "tool reports belong under output/ or a scratch area")
    return path
