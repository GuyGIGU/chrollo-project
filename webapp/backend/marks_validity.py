"""Compatibility alias; implementation lives in domains.calibration.validation.

Root-safe, like the module it names: imported as ``marks_validity`` (backend cwd on
sys.path) it aliases ``domains.calibration.validation``; imported as ``webapp.backend.marks_validity``
(repo root only, as tools do) it aliases ``webapp.backend.domains.calibration.validation``.
"""
import importlib as _importlib
import sys as _sys

_PARENT = __name__.rpartition(".")[0]
_sys.modules[__name__] = _importlib.import_module(
    (_PARENT + "." if _PARENT else "") + "domains.calibration.validation")
