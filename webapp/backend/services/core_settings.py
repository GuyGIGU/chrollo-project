"""Read root config/settings.py without colliding with backend config.py."""
from __future__ import annotations

import importlib.util
import os
from types import ModuleType

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SETTINGS_PATH = os.path.join(ROOT_DIR, "config", "settings.py")


def load_core_settings() -> ModuleType:
    spec = importlib.util.spec_from_file_location("chrollo_core_settings", SETTINGS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load settings from {SETTINGS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
