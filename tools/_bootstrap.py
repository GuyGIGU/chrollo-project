"""Shared ``sys.path`` bootstrap for the ``tools/`` scripts.

Every tool is run as a standalone script (``python -m tools.foo`` or
``python tools/foo.py``) and needs the repository root on ``sys.path`` so the
``config`` / ``core`` / ``tools`` packages import. This collapses the bootstrap
block that was pasted verbatim across the tools into one call.
"""

import os
import sys

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def configure_path(*, backend: bool = False) -> str:
    """Prepend the repository root to ``sys.path`` (idempotent) and return it.

    ``backend=True`` additionally puts ``webapp/backend`` on the path for
    tools that read the calibration DB / frame store / marks validity. The
    insertion sits at position 1 — AFTER the repo root — so the repo-root
    ``config`` package keeps precedence over the backend's own ``config.py``
    (the known cwd-shadowing trap lives in exactly this ordering)."""
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    if backend:
        backend_dir = os.path.join(_PROJECT_ROOT, "webapp", "backend")
        if backend_dir not in sys.path:
            sys.path.insert(1, backend_dir)
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
    """Raise if ``path`` sits under a sealed directory; return it otherwise.

    Both sides are case-normalized AND symlink-resolved: Chrollo deploys on
    NTFS, where paths are case-insensitive — a case-sensitive prefix check
    let ``docs/Marks/…`` sail into the real sealed directory (2026-08-08
    review, finding 15)."""
    target = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    for sealed in _SEALED_DIRS:
        s = os.path.normcase(os.path.realpath(sealed))
        if target == s or target.startswith(s + os.sep):
            raise ValueError(
                f"refusing to write under the sealed directory ({sealed}) — "
                "tool reports belong under output/ or a scratch area")
    return path
