"""The industry backfill (2026-10-23): asks the vendor once per name the cache
lacks, keeps an empty answer so funds are not re-asked, stops on the throttle."""
from tools.maintenance import industry_backfill as tool


def test_backfill_asks_only_what_the_cache_lacks_and_keeps_empty_answers():
    cache = {"APLE": {"sector": "Real Estate", "industry": "REIT - Hotel & Motel", "as_of": "2026-10-22"}}
    asked = []

    def info(ticker):
        asked.append(ticker)
        return {"HST": {"sector": "Real Estate", "industry": "REIT - Hotel & Motel"},
                "BMEZ": {"sector": None, "industry": None}}.get(ticker, {})

    saves = []
    counts = tool.backfill(["APLE", "HST", "BMEZ"], cache, info, as_of="2026-10-23",
                           save=lambda: saves.append(len(cache)), log=lambda *_: None)
    assert asked == ["HST", "BMEZ"]
    assert cache["HST"] == {"sector": "Real Estate", "industry": "REIT - Hotel & Motel", "as_of": "2026-10-23"}
    assert cache["BMEZ"] == {"sector": None, "industry": None, "as_of": "2026-10-23"}
    assert counts == {"todo": 2, "asked": 2, "named": 1, "empty": 1, "stopped": None}
    assert saves == [3]


def test_backfill_stops_when_the_probe_comes_back_empty_and_a_miss_costs_itself():
    calls = {"n": 0}

    def info(ticker):
        calls["n"] += 1
        if ticker == "BAD":
            raise RuntimeError("vendor down")
        if ticker == "AAPL":
            return {} if calls["n"] > 3 else {"industry": "Consumer Electronics"}
        return {"industry": "Steel"}

    cache = {}
    counts = tool.backfill(["A", "BAD", "C", "D", "E"], cache, info, as_of="2026-10-23",
                           log=lambda *_: None, probe_every=2, save_every=100)
    # A, BAD -> probe ok (3rd call); C, D -> probe empty (6th call): stop before E
    assert counts["asked"] == 4 and counts["stopped"].startswith("throttled")
    assert cache["BAD"]["industry"] is None and "E" not in cache


def test_seed_merges_a_measuring_sessions_map_without_touching_the_caches_own_words():
    cache = {"APLE": {"sector": "Real Estate", "industry": "REIT - Hotel & Motel", "as_of": "2026-10-22"}}
    added = tool.seed(cache, {"APLE": {"industry": "wrong"}, "X": {"sector": "S", "industry": "Steel", "from": "vendor"},
                              "Y": "junk"}, "2026-10-23")
    assert added == 1
    assert cache["APLE"]["industry"] == "REIT - Hotel & Motel"
    assert cache["X"] == {"sector": "S", "industry": "Steel", "as_of": "2026-10-23"}
