"""Archive-feed completeness under the NEW reader (the flip; verify-3 of the go-live build).

The old reader's gate (``test_archive_feed_completeness.py``) pins its own floor of
measurement columns and, since the flip, asks for the old reader by name. The new
reader feeds a different set: the setup and its tier, the trend template the scan
adds to every fire, the stock's ADR (from Tue 13/10/2026; empty on every new-reader
row before), and its own family (``engine_alpha/archive.py``). The
old engine's measurement columns (the bins, the equilibrium, the traversal, the old
LPS's geometry) are that engine's facts and stay NULL on a new-reader row by design
(``docs/flag_ledger.md``, the reader's Retired row); the studies read the new stamp
apart. This gate makes a silent NULL in what the new reader DOES feed go red.

The floor is every writer-mapped key non-null on all 31 fired shadow-fixture
tickers under the new reader at capture (Sat 10/10/2026); ``_adr_pct`` joined it on
Tue 13/10/2026, non-null on the same 31.
"""
import re

import pytest

from _paths import REPO_ROOT
from engine_alpha import gate
from engine_alpha.archive import ALPHA_COLUMN_SQL
from tools.regression.shadow_diff import _load_fixture

_WRITER = REPO_ROOT / "core" / "archive" / "writer.py"

NEW_READER_FEED_FLOOR = (
    "Setup", "Tier",
    "_adr_pct",
    "_phase_b_start_date",
    "_stage2_52w_low_pct", "_stage2_ma200_slope_1m_pct", "_stage2_trend_pass_count",
    "_cycle_stage",                        # the stage read (Fri 16/10/2026), on every frame of 44 weeks or more
    "_two_eyes_has_mini", "_two_eyes_lps_read_against",
    "_two_eyes_parent_daily_range", "_two_eyes_parent_opened_date",
    "_two_eyes_parent_r_anchor_date", "_two_eyes_parent_r_price",
    "_two_eyes_parent_s_anchor_date", "_two_eyes_parent_s_price",
    # His word Mon 12/10/2026 (option A): the LPS pullback's volume, the one setup
    # fact that separated the archive's big winners, keeps being archived.
    "_two_eyes_lps_volume_ratio",
)


def test_writer_still_maps_every_new_reader_floor_key():
    src = _WRITER.read_text(encoding="utf-8")
    sources = {m.group(2) for m in re.finditer(r'(\w+)=(?:r|row)\.get\("([^"]+)"', src)}
    family = {"_" + column for column in ALPHA_COLUMN_SQL}   # written through alpha_archive_values
    missing = [k for k in NEW_READER_FEED_FLOOR if k not in sources | family]
    assert not missing, f"the writer no longer maps these new-reader keys: {missing}"


@pytest.mark.slow
def test_a_new_reader_fire_feeds_every_floor_key():
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None
    result = None
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        r = gate.scan_read(ticker, df, spy_6m, breadth)
        if isinstance(r, dict):
            result = r
            break
    assert result is not None, "no fixture ticker fires under the new reader"
    bad = [k for k in NEW_READER_FEED_FLOOR
           if result.get(k) is None
           or (isinstance(result.get(k), float) and result[k] != result[k])]
    assert not bad, f"a new-reader fire no longer feeds these archive keys non-null: {bad}"
