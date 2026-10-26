"""Leading groups and sectors, and each stock's place in its group (his ask, 26/10/2026)."""
import sys

import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

import core.regime.scan_context as scan_context  # noqa: E402
from core.regime.leadership import read_leadership  # noqa: E402


def _cache(**groups):
    """industry -> (sector, [tickers]) as an industry cache."""
    return {ticker: {"sector": sector, "industry": industry}
            for industry, (sector, tickers) in groups.items() for ticker in tickers}


CACHE = _cache(Semis=("Technology", ["N1", "N2", "N3"]),
               Software=("Technology", ["W1", "W2", "W3", "W4"]),
               Banks=("Financial Services", ["B1", "B2", "B3"]),
               Shells=("Financial Services", ["X1", "X2"]))
RATINGS = {"N1": 99.0, "N2": 90.0, "N3": 80.0,           # Semis median 90
           "W1": 70.0, "W2": 60.0, "W3": 50.0, "W4": 95.0,  # Software median 65
           "B1": 20.0, "B2": 30.0, "B3": 10.0,           # Banks median 20
           "X1": 100.0, "X2": 100.0,                     # two names: never ranked
           "LOST": 50.0}                                 # the cache does not know it


def test_groups_rank_by_the_median_rs_of_their_stocks():
    groups = read_leadership(RATINGS, CACHE)["groups"]
    assert {name: (g["rank"], g["of"], g["rs"], g["members"], g["sector"]) for name, g in groups.items()} == {
        "Semis": (1, 3, 90.0, 3, "Technology"),
        "Software": (2, 3, 65.0, 4, "Technology"),
        "Banks": (3, 3, 20.0, 3, "Financial Services"),
    }
    # The top quarter leads: one of three groups.
    assert [name for name, g in groups.items() if g["leading"]] == ["Semis"]


def test_a_stock_knows_its_place_in_its_group():
    stocks = read_leadership(RATINGS, CACHE)["stocks"]
    assert stocks["W4"] == {"group": "Software", "rs": 95.0, "place": 1, "of": 4}  # the group's leader
    assert stocks["W2"] == {"group": "Software", "rs": 60.0, "place": 3, "of": 4}
    assert "X1" not in stocks and "LOST" not in stocks  # an unranked group, an unknown name


def test_sectors_rank_by_the_median_rs_of_all_their_stocks():
    sectors = read_leadership(RATINGS, CACHE)["sectors"]
    # Technology: 7 names, median 80; Financial Services: 5 names (the shells count), median 30.
    assert {name: (s["rank"], s["rs"], s["members"], s["leading"]) for name, s in sectors.items()} == {
        "Technology": (1, 80.0, 7, True), "Financial Services": (2, 30.0, 5, False)}


def test_nothing_to_group_reads_as_nothing():
    assert read_leadership(RATINGS, {}) == {}
    assert read_leadership({}, CACHE) == {}


def test_the_rs_pass_returns_the_whole_population_even_on_a_night_with_no_fires():
    days = 253
    frames = {f"S{i}": pd.DataFrame({"Close": [10.0 + i * k / (days - 1) for k in range(days)]},
                                    index=pd.date_range("2025-01-01", periods=days, freq="B"))
              for i in range(4)}
    ratings = scan_context.attach_rs_ratings([], frames)
    assert ratings["S3"] == pytest.approx(87.5) and ratings["S0"] == pytest.approx(12.5)
