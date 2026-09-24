"""Compatibility alias; implementation lives in app.startup."""
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("app.startup")
