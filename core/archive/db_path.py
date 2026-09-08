"""The ONE home for the archive database's location.

The archive had ten front doors and one lock. ``CHROLLO_DB_PATH`` was added
2026-09-07 so a plain ``pytest`` run would stop migrating the operator's live
archive (``import main`` runs the whole migration battery at import scope, and
its orphan reconcile rewrites an in-flight ``scan_runs`` row to 'failed' — that
string is in his archive). But it was read at exactly ONE site,
``webapp/backend/database.py``; nine other modules rebuilt the same literal from
their own ``__file__`` anchor and ignored the override entirely. Measured latent,
not live — no test reached them against the live file — but the guards written
for it were PATH-specific, so a future test calling ``archive_scan_results()``
would have written to the live archive with every guard green.

This module is that one home (register row 11, EC-3). It lives in ``core`` on
purpose: the backend already imports ``core`` freely, so ``database.py`` can read
it without inverting the layering, and ``config`` is not safe here — the backend's
own working directory shadows the repo-root ``config`` package.

``archive_db_path()`` reads the environment at CALL time. A module-level constant
captured at import time is the defect one level down: a module imported before
the override is set would bind the live path and never see it.
"""
from __future__ import annotations

import os

# Anchored to THIS file, never to the working directory — the screener, the
# backend and the tools all run from different places.
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)

#: Where the archive lives when nothing overrides it. This is the path the test
#: suite's refuser is keyed on, and the one production always uses — nothing in
#: the service sets ``CHROLLO_DB_PATH`` (``docs/deploy.md`` §2).
DEFAULT_DB_PATH = os.path.join(_REPO_ROOT, "webapp", "backend", "trading_journal.db")

#: The override's env var. Named here so a caller can refer to it without
#: retyping the string (the same twin defect, one size smaller).
DB_PATH_ENV_VAR = "CHROLLO_DB_PATH"


def archive_db_path() -> str:
    """The archive file this process must use.

    ``CHROLLO_DB_PATH`` wins when set and non-empty; otherwise the anchored
    default. Read fresh on every call so a test session that sets the variable
    after some module was imported is still honoured.
    """
    return os.environ.get(DB_PATH_ENV_VAR) or DEFAULT_DB_PATH
