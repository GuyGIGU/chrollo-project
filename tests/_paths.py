"""Where the suite lives, anchored once.

Test modules sit one folder below ``tests/`` (``tests/engine/``,
``tests/backend/``, ...), so a module that rebuilt the repo root from its own
``__file__`` would silently point at the wrong place the day it moved. They
import these constants instead: ``from _paths import REPO_ROOT``. That import
resolves from any category folder because ``tests/conftest.py`` puts ``tests/``
on ``sys.path`` before any test module loads.
"""
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
BACKEND_DIR = REPO_ROOT / "webapp" / "backend"
BASELINES_DIR = TESTS_DIR / "baselines"
FIXTURES_DIR = TESTS_DIR / "fixtures"
