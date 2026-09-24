"""seed --force preserves operator curation (council review 2026-08-22, Leach F6).

The --force overwrite branch builds a FULL column dict (quality_label is
unconditionally 'perfect' from overrides; notes auto-fills to None via the
mapper) and used to setattr every key onto the existing row — silently wiping
a hand-edited note or a re-graded label on re-seed. The overwrite now
refreshes MEASUREMENTS only: the operator-curation columns (quality_label,
notes) are never writer-refreshable (EC-7 spirit).
"""
import sys

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
from core.archive import seed  # noqa: E402


def test_overwrite_refreshes_measurements_but_preserves_curation():
    existing = archive_models.SetupArchive(
        ticker="EGBN", scan_date="2026-01-08", setup_type="LPS",
        tier="A", score=61.0,
        quality_label="good_not_perfect",     # operator re-graded it
        notes="operator: shelf LPS, watch the dwell",
    )
    values = {
        "score": 72.5,                        # fresh measurement — refresh
        "tier": "S",
        "quality_label": "perfect",           # the writer's auto-fill — ignore
        "notes": None,                        # the mapper's auto-None — ignore
    }
    seed._overwrite_existing(existing, values)

    assert existing.score == 72.5 and existing.tier == "S"
    assert existing.quality_label == "good_not_perfect"
    assert existing.notes == "operator: shelf LPS, watch the dwell"


def test_curation_columns_are_real_model_columns():
    """The exclusion list must name live columns — a model rename would
    otherwise silently turn the guard into a no-op."""
    model_cols = {c.name for c in archive_models.SetupArchive.__table__.columns}
    assert set(seed._CURATION_COLUMNS) <= model_cols
