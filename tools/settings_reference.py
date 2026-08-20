"""
Generated Settings Quick-Reference for docs/engine_reference.md.

The doc's quick-reference used to be a hand-maintained copy of
``config/settings.py`` values - a guaranteed-rot surface (it had already
drifted: stale values, dozens of newer constants missing). This tool replaces
it with a GENERATED block: the frozen engine-identity allow-list
(``engine_alpha.freeze.manifest.ENGINE_SETTINGS_KEYS`` - every constant that can move
a detector decision) rendered with its live settings value, in manifest order,
stamped with the manifest hash. ``tests/test_docs_sync.py`` asserts the
committed block matches this generator, so any settings/manifest change that
skips the doc fails the suite - the read-before-engine-work house rule,
enforced.

Ops/data-fetch knobs are deliberately absent - they are not engine identity
(see the DELIBERATELY EXCLUDED block in engine_alpha/freeze/manifest.py).

Usage:
    python -m tools.settings_reference --write   # regenerate the doc block in place
    python -m tools.settings_reference --check   # fail (exit 1) if the doc drifted
"""
from __future__ import annotations

import os
import sys

try:  # works under both `python -m tools.settings_reference` and direct run
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

_DOC_PATH = os.path.join(_PROJECT_ROOT, "docs", "engine_reference.md")
_BEGIN = "<!-- BEGIN GENERATED: settings-quick-reference -->"
_END = "<!-- END GENERATED: settings-quick-reference -->"


def render_block() -> str:
    """The full generated block (markers included), built from live settings."""
    from config import settings
    from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS, manifest_hash

    lines = [f"{key} = {getattr(settings, key)!r}" for key in ENGINE_SETTINGS_KEYS]
    body = "\n".join(lines)
    return (
        f"{_BEGIN}\n"
        "_Generated from the frozen engine-identity allow-list\n"
        "(`engine_alpha/freeze/manifest.ENGINE_SETTINGS_KEYS`) — every constant that can move a\n"
        "detector decision, in manifest order, with its live `config/settings.py` value.\n"
        "Regenerate with `python -m tools.settings_reference --write`;\n"
        "`tests/test_docs_sync.py` fails the suite when this block drifts._\n"
        "\n"
        f"_engine_config_version: `{manifest_hash()}`_\n"
        "\n"
        "```text\n"
        f"{body}\n"
        "```\n"
        "\n"
        "_Ops / data-fetch knobs (cache TTLs, Yahoo rate limits, admission/quarantine,\n"
        "scheduler, dashboard) are deliberately NOT part of the engine identity — see\n"
        "the \"DELIBERATELY EXCLUDED\" block in\n"
        "[engine_alpha/freeze/manifest.py](../engine_alpha/freeze/manifest.py)._\n"
        f"{_END}"
    )


def split_doc(text: str) -> tuple[str, str, str]:
    """Split the doc into (before, committed_block, after) around the markers.

    Raises ValueError when the markers are missing/misordered - the test
    surfaces that as a loud failure, never a silent skip.
    """
    start = text.find(_BEGIN)
    end = text.find(_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            f"generated-block markers missing/misordered in {_DOC_PATH} - "
            f"expected '{_BEGIN}' ... '{_END}'"
        )
    end += len(_END)
    return text[:start], text[start:end], text[end:]


def write_doc(doc_path: str = _DOC_PATH) -> None:
    with open(doc_path, "r", encoding="utf-8") as f:
        text = f.read()
    before, _old, after = split_doc(text)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(before + render_block() + after)
    print(f"Regenerated settings quick-reference block -> {doc_path}")


def check_doc(doc_path: str = _DOC_PATH) -> bool:
    with open(doc_path, "r", encoding="utf-8") as f:
        text = f.read()
    _before, committed, _after = split_doc(text)
    expected = render_block()
    if committed == expected:
        print("settings quick-reference block matches config/settings.py.")
        return True
    print("settings quick-reference block DRIFTED from config/settings.py - "
          "run `python -m tools.settings_reference --write` and commit the doc.")
    return False


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Generated settings quick-reference for engine_reference.md.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="regenerate the doc block in place")
    group.add_argument("--check", action="store_true", help="fail (exit 1) if the doc block drifted")
    args = ap.parse_args()

    try:
        if args.write:
            write_doc()
        elif args.check:
            sys.exit(0 if check_doc() else 1)
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
