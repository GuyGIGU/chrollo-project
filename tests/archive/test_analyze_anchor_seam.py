"""The Phase-A anchor family may not be pooled across an engine seam.

``docs/flag_ledger.md`` names this partition as ``AR_FIRST_REACTION_ENABLED``'s
blocking precondition: flipping it re-anchors the drawn automatic reaction (19
of 140 overlays), which shifts the archived ``bin_a_*`` columns — and
``analyze.py`` pooled those columns over every epoch in the archive, so the
blend read as a measurement instead of as an artifact of when each row was
written. The always-on climax-terminality repair moves the same anchor, so the
seam is not hypothetical and not only about the dark flag.

These pin the partition, not the prose.
"""
import pandas as pd
import pytest

from core.archive import analyze


def _rows(specs, **overrides):
    """A frame of archive-shaped rows from [(engine_config_version, scan_date, n)].

    Values vary per row so the correlation path sees variance — a constant
    column correlates to NaN and would be skipped for the wrong reason.
    """
    out = []
    for version, date, count in specs:
        for i in range(count):
            row = {
                "engine_config_version": version,
                "scan_date": date,
                "setup_type": "LPS",
                "tier": "S",
                "bin_a_bars": 4 + (i % 7),
                "bin_a_range_pct": 0.08 + 0.01 * (i % 5),
                "bin_a_volume_ratio": 1.1 + 0.05 * (i % 4),
                "bars_since_bc": 25 + (i % 11),
                "descent_length": 6 + (i % 3),
                "box_width": 0.04 + 0.002 * (i % 9),
                "base_length": 30 + (i % 13),
                "fwd_return_20d": -0.05 + 0.01 * (i % 17),
            }
            row.update(overrides)
            out.append(row)
    return pd.DataFrame(out)


def _report(section, df):
    analyze._LINES.clear()
    section(df)
    return "\n".join(analyze._LINES)


def test_unversioned_rows_count_as_their_own_epoch():
    # The pre-versioning archive (2,664 rows) was written by an engine too — one
    # that did not stamp itself. Folding it into a versioned pool is the same
    # blend by a quieter route.
    df = _rows([("vA", "2026-08-01", 3), (None, "2026-01-01", 2)])
    assert analyze.engine_epochs(df) == ["?", "vA"]
    assert analyze.anchor_seam(df) is True


def test_a_single_epoch_is_not_a_seam():
    df = _rows([("vA", "2026-08-01", 5)])
    assert analyze.engine_epochs(df) == ["vA"]
    assert analyze.anchor_seam(df) is False


def test_an_archive_without_the_column_reports_no_epochs():
    df = _rows([("vA", "2026-08-01", 3)]).drop(columns=["engine_config_version"])
    assert analyze.engine_epochs(df) == []
    assert analyze.anchor_seam(df) is False
    assert analyze.current_epoch(df) is None


def test_current_epoch_is_the_LATEST_not_the_largest():
    """Config hashes carry no ordering, so recency has to come from the data.
    Picking the largest epoch would scope this archive's read to its oldest
    engine — the pre-versioning bulk is the biggest cohort in it."""
    df = _rows([("vOLD", "2026-01-05", 100), ("vNEW", "2026-08-12", 3)])
    assert analyze.current_epoch(df) == "vNEW"


def test_current_epoch_ignores_unversioned_rows():
    # "?" is an epoch for the purpose of DETECTING a seam, never a scope to
    # report inside — an unstamped row cannot be "today's reader".
    df = _rows([(None, "2026-08-12", 50), ("vA", "2026-08-01", 3)])
    assert analyze.current_epoch(df) == "vA"


def test_the_family_is_reported_ONCE_and_scoped_across_a_seam():
    df = _rows([("vOLD", "2026-01-05", 20), ("vNEW", "2026-08-12", 20)])
    report = _report(analyze.section_fingerprint, df)
    assert "Phase-A anchor family - NOT pooled" in report
    # Exactly once = it left the pooled table and appears only in the scoped
    # one. Family members the frame does not carry (the dark pp_* names) can
    # appear in neither — the report only speaks about columns it was given.
    for feature in analyze.PHASE_A_ANCHOR_FEATURES:
        if feature.startswith("pp_"):
            assert report.count(feature) == 0
            continue
        assert report.count(feature) == 1, f"{feature} appears in two tables"
    assert "CURRENT epoch vNEW" in report
    # A feature that does NOT move with the anchor stays pooled.
    assert "box_width" in report


def test_the_family_stays_pooled_on_a_single_epoch():
    df = _rows([("vNEW", "2026-08-12", 20)])
    report = _report(analyze.section_fingerprint, df)
    assert "NOT pooled" not in report
    for feature in analyze.PHASE_A_ANCHOR_FEATURES:
        if feature.startswith("pp_"):
            continue                 # dark columns: absent from the fixture
        assert feature in report


def test_correlations_withhold_the_family_across_a_seam():
    """Correlating a two-population blend against outcomes reports the seam —
    and reports it as a predictor, which is the failure that matters."""
    df = _rows([("vOLD", "2026-01-05", 20), ("vNEW", "2026-08-12", 20)])
    report = _report(lambda d: analyze.section_correlations(d, True), df)
    assert "Withheld across an engine seam" in report
    # Split at the first correlation TABLE — the notice above it names the
    # withheld features on purpose (a silent withholding is its own defect).
    table = report.split("vs fwd_return_20d")[1]
    for feature in analyze.PHASE_A_ANCHOR_FEATURES:
        assert feature not in table, f"{feature} correlated across the seam"
    assert "box_width" in table          # an anchor-independent feature survives


def test_correlations_keep_the_family_on_a_single_epoch():
    df = _rows([("vNEW", "2026-08-12", 40)])
    report = _report(lambda d: analyze.section_correlations(d, True), df)
    assert "Withheld across an engine seam" not in report


def test_the_family_is_exactly_the_documented_seam():
    """strategy_alpha.md names the partitioned columns as
    bin_a_*/bars_since_bc/descent_length. If a new Phase-A measurement lands in
    STRUCTURAL_FEATURES without joining this family, it will be pooled across
    the seam silently — which is the whole defect."""
    assert set(analyze.PHASE_A_ANCHOR_FEATURES) == {
        "bin_a_bars", "bin_a_range_pct", "bin_a_volume_ratio",
        "bars_since_bc", "descent_length",
        # Power-Play species numerics — anchor-family from birth (species
        # program Task 7); dark columns, partition-declared before any row.
        "pp_clock", "pp_pole_gain"}
    bin_a = {f for f in analyze.STRUCTURAL_FEATURES if f.startswith("bin_a_")}
    assert bin_a <= set(analyze.PHASE_A_ANCHOR_FEATURES), (
        "a new bin_a_* feature registered without joining PHASE_A_ANCHOR_FEATURES")


@pytest.mark.parametrize("epochs", [
    [("vA", "2026-08-01", 4)],
    [("vA", "2026-08-01", 4), ("vB", "2026-08-12", 4)],
    [(None, "2026-08-01", 4)],
])
def test_the_fingerprint_never_raises_whatever_the_epoch_shape(epochs):
    _report(analyze.section_fingerprint, _rows(epochs))
