"""Doc-sync guard: the generated Settings Quick-Reference cannot rot.

docs/strategy_v2.md's quick-reference was hand-maintained and had already
drifted (stale values, newer constants missing). It is now a GENERATED block
(``tools.settings_reference``) built from the frozen engine-identity allow-list
(``core.freeze.manifest.ENGINE_SETTINGS_KEYS``) + live ``config/settings.py``
values. This test asserts the committed doc matches the generator, so any
settings or manifest change that skips regenerating the doc fails the suite -
"update strategy_v2.md in the same change", enforced.
"""
from __future__ import annotations

import os

from tools import settings_reference


def test_quick_reference_markers_present():
    """The generated block's markers must exist in the committed doc - if they
    vanish, --write has nowhere to land and the sync guard guards nothing."""
    assert os.path.exists(settings_reference._DOC_PATH)
    with open(settings_reference._DOC_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    # split_doc raises ValueError when markers are missing/misordered.
    settings_reference.split_doc(text)


def test_quick_reference_matches_live_settings():
    """The committed block must equal the generator's output byte-for-byte.

    Fails whenever a manifest constant's value, the allow-list membership, or
    the manifest hash moved without `python -m tools.settings_reference --write`
    being run and committed in the same change.
    """
    assert settings_reference.check_doc() is True, (
        "docs/strategy_v2.md's Settings Quick-Reference drifted from "
        "config/settings.py - run `python -m tools.settings_reference --write` "
        "and commit the doc in the SAME change as the settings/manifest edit."
    )
