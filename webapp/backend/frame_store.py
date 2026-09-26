"""Compatibility alias; implementation lives in domains.calibration.frame_store.

Root-safe, like the module it names: imported as ``frame_store`` (backend cwd on
sys.path) it aliases ``domains.calibration.frame_store``; imported as ``webapp.backend.frame_store``
(repo root only, as tools do) it aliases ``webapp.backend.domains.calibration.frame_store``.
"""
import importlib as _importlib
import sys as _sys

_PARENT = __name__.rpartition(".")[0]
_sys.modules[__name__] = _importlib.import_module(
    (_PARENT + "." if _PARENT else "") + "domains.calibration.frame_store")
