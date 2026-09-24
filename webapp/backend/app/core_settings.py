"""Read root config/settings.py without colliding with backend config.py.

Every call executes the settings fresh from disk, as an isolated module that never
sees the running process's ``config.settings`` overrides. settings.py re-exports its
defaults from the domain files beside it (``from .engine import ...``), so it is loaded
as a submodule of a private, throwaway package whose path is the root config/ folder.
"""
from __future__ import annotations

import importlib
import itertools
import os
import sys
from types import ModuleType

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.py")

_load_ids = itertools.count()


def load_core_settings() -> ModuleType:
    package_name = f"_chrollo_core_config_{next(_load_ids)}"
    package = ModuleType(package_name)
    package.__path__ = [CONFIG_DIR]
    sys.modules[package_name] = package
    try:
        return importlib.import_module(f"{package_name}.settings")
    finally:
        for name in [n for n in sys.modules if n == package_name or n.startswith(package_name + ".")]:
            del sys.modules[name]
