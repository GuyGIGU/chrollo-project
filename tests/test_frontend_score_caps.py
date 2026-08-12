"""The frontend's point-cap mirror must equal the engine's caps.

`webapp/frontend/src/components/setupScoreMath.js` holds the one sanctioned
copy of the engine's `SCORE_*` caps (AGENTS.md: "Tag-chip / score-pill caps
mirror `config/settings.py` and live in one place"). A copy can rot, and this
one did: `uptrend_bonus` and `rs_bonus` sat at 15 for three weeks after the
2026-07-25 demotion set both to 0, leaving 30 points of phantom capacity in the
legacy Market pill's denominator (found by the 2026-08-12 review, not by any
gate). The mirror now also feeds the lens's LPS grade, so a silent drift there
would print a wrong percentage on the panel the operator reads first.

decisions.md: "Prefer a machine-checked invariant to a paragraph."
"""

import re
from pathlib import Path

import pytest

from engine_alpha.scoring import taxonomy

MIRROR = (Path(__file__).resolve().parents[1] / "webapp" / "frontend" / "src"
          / "components" / "setupScoreMath.js")


def _mirrored_caps() -> dict[str, float]:
    """Parse the SUB_SCORE_CAPS object literal out of the JS module."""
    text = MIRROR.read_text(encoding="utf-8")
    block = re.search(r"export const SUB_SCORE_CAPS = \{(.*?)\n\};", text, re.S)
    assert block, f"SUB_SCORE_CAPS object literal not found in {MIRROR}"
    pairs = re.findall(r"^\s*(\w+):\s*([0-9]+(?:\.[0-9]+)?)\s*,", block.group(1),
                       re.M)
    assert pairs, "SUB_SCORE_CAPS parsed as empty — the literal's shape changed"
    return {key: float(value) for key, value in pairs}


def test_mirror_file_exists():
    assert MIRROR.is_file(), f"the cap mirror moved: {MIRROR} is gone"


@pytest.mark.parametrize("key,cap", sorted(_mirrored_caps().items()))
def test_every_mirrored_cap_equals_the_engine(key, cap):
    engine = taxonomy.caps()
    assert key in engine, (
        f"{key} is mirrored in setupScoreMath.js but is not a registered term — "
        "a renamed or retired term must be removed from the mirror")
    assert cap == pytest.approx(engine[key]), (
        f"cap drift on {key}: the frontend says {cap}, settings.py says "
        f"{engine[key]}. Update SUB_SCORE_CAPS in setupScoreMath.js.")


def test_the_lps_grade_has_a_live_cap_to_divide_by():
    """The lens's LPS row grades `lps_tightness` as a fraction of this cap.

    A zero cap is not a crash (lpsGrade returns null, and the row honestly
    shows no grade) but it IS a silent feature loss, so it gets its own
    assertion rather than hiding inside the parametrised sweep.
    """
    assert _mirrored_caps()["lps_tightness"] == pytest.approx(
        taxonomy.caps()["lps_tightness"])
    assert taxonomy.caps()["lps_tightness"] > 0
