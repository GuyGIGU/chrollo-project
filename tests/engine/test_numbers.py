"""The reader's own numbers (engine_alpha/numbers.py): every one moves the version stamp, and the
reader reads none of them from config.settings.

Moved out of tests/engine/test_two_eyes_copies_equal_originals.py when the old engine retired (Sat 31/10/2026):
the copies have no originals left to equal, but these two pins are about the numbers, not the copies.
"""
from __future__ import annotations

import ast
import os

from _paths import REPO_ROOT


def test_a_changed_number_moves_the_version_stamp(monkeypatch):
    """The reader reads its numbers from `two_eyes_numbers`, not from settings, and the version stamp hashes
    settings: without the TWO_EYES_METHOD_NUMBERS block a tuned number would change the reading and keep the
    stamp, so the archived rows before and after could not be told apart. Each number, moved alone, must move
    the stamp."""
    from engine_alpha import stamp as manifest
    from engine_alpha import numbers as method_numbers

    names = sorted(n for n in vars(method_numbers) if n.isupper())
    assert len(names) == 49, names    # + the three CLARITY_* trait scales and the four STAGE_* numbers moved out of config (Fri 30/10/2026) + the election by respect (two switches, three numbers, Fri 30/10/2026) + the wrap switch and the seven TRAIT_* numbers of Thu 29/10/2026           # six from the copies (task 7; R15's margin left with the box-end copy at task 11), two from stage 1 (task 8), three from stages 2 and 3 (task 10), five from stage 6 (task 12a), the last supper's naming floor (Sat 03/10/2026), four from the grade (task 14), three from his HCA (Sat 24/10/2026), the walk's four switches (Wed 28/10/2026)
    before = manifest.manifest_hash()
    for name in names:
        value = getattr(method_numbers, name)
        moved = (value + "x" if isinstance(value, str) else (not value) if isinstance(value, bool)
                 else {**value, "moved": 1} if isinstance(value, dict) else value + 1)
        monkeypatch.setattr(method_numbers, name, moved)
        assert manifest.manifest_hash() != before, f"moving {name} left the version stamp where it was"
        monkeypatch.undo()
    assert manifest.manifest_hash() == before


def test_the_reader_reads_no_shared_setting():
    """The reader's numbers are its own (engine_alpha/numbers.py). Were a stage to read `config.settings`, a knob
    tuned for the reader would be a setting the manifest may not list, and the version stamp would miss the move.
    The stages: every module of the engine but the gate, the result row, the archive family, the stamp and the
    stock facts, which read settings on purpose."""
    root = str(REPO_ROOT)
    engine = os.path.join(root, "engine_alpha")
    not_a_stage = {"gate", "result", "archive", "stamp", "stock", "__init__"}
    names = sorted(f[:-3] for f in os.listdir(engine) if f.endswith(".py") and f[:-3] not in not_a_stage)
    assert {"chart", "line", "lps", "story", "grade", "state", "record", "reader", "numbers"} <= set(names)
    paths = [os.path.join(engine, f"{name}.py") for name in names]
    paths += [os.path.join(engine, "box", f) for f in sorted(os.listdir(os.path.join(engine, "box")))
              if f.endswith(".py") and f != "__init__.py"]
    for path in paths:
        name = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        named = [a.name for n in imports if isinstance(n, ast.Import) for a in n.names] + \
                [n.module or "" for n in imports if isinstance(n, ast.ImportFrom)]
        assert not any(m == "config" or m.startswith("config.") for m in named), f"{name} imports config"
        assert not any(isinstance(n, ast.Name) and n.id == "settings" for n in ast.walk(tree)), \
            f"{name} reads `settings`"
