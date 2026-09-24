"""Compatibility alias; the implementation lives in core.calibration.agreement.

The agreement taxonomy moved to ``core/calibration/`` on 2026-09-24 so the
backend's calibration chips import it without reaching into ``tools/``. This
name stays importable because engine code cites it
(``engine_alpha/election_identity.py``) and branches written before the move
import it. The alias swaps itself in ``sys.modules`` for the real module, so
both names are ONE module object. New code imports ``core.calibration.agreement``.
"""
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("core.calibration.agreement")
