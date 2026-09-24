"""Two-form LPS guard net (Event Map Task 9) — Beck × Leach.

The holding-shelf completion form (Task 8, dark behind LPS_HOLDING_SHELF_ENABLED)
widens ACCEPTANCE; these guards pin what must NEVER move when it does:

1. **Attribution stability at panel scale** — flag-on, every previously-firing
   shadow-fixture ticker fires byte-identically on the canonical fields AND
   stays pullback-attributed (the shelf never steals an election).
2. **The conversions are real and flag-owned** — the operator's marked WTS/PBT
   corpus shelves fire flag-ON ONLY, carrying the queryable form provenance
   (``_lps_swing_type == "holding_shelf"`` — the value the archive writer maps
   to the ``lps_swing_type`` column, the zone-type/swing-type precedent).

Fully OFFLINE: reads only the committed shadow + marks-corpus fixtures. The
flag-ON negative-corpus replay lives in test_negative_corpus.py (its home);
the engineered both-forms precedence pins live in test_lps.py.
"""
from __future__ import annotations

import json
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from core.pipeline.screening.screener import _evaluate_ticker
from tools import shadow_diff
from tools.marks_corpus import _FROZEN_BREADTH
from tools.marks_corpus import _load_fixture as _load_marks_fixture
from tools.replay import fixture_frame

pytestmark = pytest.mark.regression


# The Task-8 acceptance battery's proven conversion points, re-grounded on the
# Guided List fixture (2026-07-24 graduation: frames keyed by full setup key,
# frozen as-drawn basis). The sessions are unchanged — both conversions replay
# at the same first-fire sessions on the new basis (freeze log 2026-07-24).
_CONVERSIONS = {
    "WTS:2026-06-12": "2026-06-08",
    "PBT:2026-05-11": "2026-04-30",
}


def test_flag_on_shadow_panel_is_identical_and_pullback_attributed(monkeypatch):
    """Flag-on, the WHOLE shadow fixture must (a) match the committed flag-off
    baseline on every canonical field and the ranking, and (b) attribute every
    fire to a pullback-form swing_type — the shelf form may only ADD fires,
    never move or re-attribute an existing one."""
    monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)

    frames, scalars = shadow_diff._load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    fields, scored = {}, []
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if result is None or not isinstance(result, dict):
            continue
        assert result.get("_lps_swing_type") != "holding_shelf", (
            f"{ticker}: a previously-firing ticker re-attributed to the shelf "
            "form flag-on - the election precedence has broken"
        )
        fields[ticker] = shadow_diff.canonical_fields(result)
        scored.append((ticker, float(result["Score"])))

    ranking = [t for t, _ in sorted(scored, key=lambda x: (-x[1], x[0]))]
    with open(shadow_diff._BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    ok, lines = shadow_diff.diff_against_baseline(
        {"fields": fields, "ranking": ranking}, baseline)
    assert ok, "flag-on canonical drift vs committed baseline:\n" + "\n".join(lines)


def test_marked_corpus_shelves_convert_flag_on_only(monkeypatch):
    """The WTS/PBT conversions are owned by the flag: the same frozen frame at
    the same session is a MISS flag-off and a holding-shelf-attributed FIRE
    flag-on — no pullback-form gate moved. The provenance key the archive
    writer maps (``_lps_swing_type``) carries the form."""
    frames, baseline = _load_marks_fixture()
    spy_by_key = {s["key"]: float(s["spy_6m_return"])
                  for s in baseline["setups"]}

    for key, session in _CONVERSIONS.items():
        ticker = key.split(":")[0]
        sliced = fixture_frame(frames, key, ticker).loc[:pd.Timestamp(session)]
        spy = spy_by_key[key]

        monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", False)
        off = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
        assert off is None or not isinstance(off, dict), (
            f"{ticker}@{session}: fires flag-OFF - the conversion is no longer "
            "owned by the shelf flag; re-ground the guard"
        )

        monkeypatch.setattr(settings, "LPS_HOLDING_SHELF_ENABLED", True)
        on = _evaluate_ticker(ticker, sliced, spy, _FROZEN_BREADTH)
        assert isinstance(on, dict), f"{ticker}@{session}: no fire flag-ON"
        assert on["_lps_swing_type"] == "holding_shelf", (
            f"{ticker}@{session}: fired flag-ON but attributed "
            f"{on['_lps_swing_type']!r} - form provenance is wrong"
        )
        assert on["Setup"] == "LPS"
        assert on["Score"] > 0
