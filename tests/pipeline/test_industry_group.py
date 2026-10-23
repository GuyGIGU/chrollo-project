"""The group facts (his yes, Fri 23/10/2026): the industry name and "N of M in
the group fired tonight / in the last 10 days", display only, resolved
engine-side, no sort and no gate. The industry is the vendor's word on the
fundamentals sheet; the group's size is the scanned universe through the
industry cache; the 10-day count reads the archive's own nights."""
import json
import sqlite3

import pandas as pd

from core.fundamentals import industry

HOTEL = "REIT - Hotel & Motel"


def test_the_industry_is_the_sheets_snapshot_word():
    assert industry.industry_of_sheet({"snapshot": {"industry": HOTEL}}) == HOTEL
    assert industry.industry_of_sheet({"snapshot": {"industry": None}}) is None
    assert industry.industry_of_sheet({"grade": {}}) is None
    assert industry.industry_of_sheet(None) is None


def test_group_counts_count_names_not_rows():
    tonight = {"APLE": HOTEL, "HST": HOTEL, "JPM": "Banks - Diversified"}
    recent = {"PK": HOTEL, "APLE": HOTEL, "RHP": HOTEL, "NOPE": None}
    members = {HOTEL: 9, "Banks - Diversified": 30}
    counts = industry.group_counts(tonight, recent, members)
    assert counts[HOTEL] == {"fired_tonight": 2, "fired_10d": 4, "members": 9}
    assert counts["Banks - Diversified"] == {"fired_tonight": 1, "fired_10d": 1, "members": 30}
    assert None not in counts


def test_a_group_the_cache_has_not_counted_yet_shows_the_names_it_can_see():
    # the cache knows no member of Steel yet: the group is at least the names that fired
    counts = industry.group_counts({"X": "Steel"}, {"Y": "Steel"}, {})
    assert counts["Steel"] == {"fired_tonight": 1, "fired_10d": 2, "members": 2}


def test_members_count_the_scanned_universe_through_the_cache():
    cache = {"APLE": {"industry": HOTEL}, "HST": {"industry": HOTEL}, "ZZZ": {"industry": None},
             "NOTSCANNED": {"industry": HOTEL}}
    assert industry.members_of(["APLE", "HST", "JPM", "ZZZ"], cache) == {HOTEL: 2}


def test_remember_writes_tonights_sheets_into_the_cache(tmp_path):
    path = str(tmp_path / "industry_cache.json")
    cache = industry.load_cache(path)
    assert cache == {}
    industry.remember(cache, "APLE", {"snapshot": {"sector": "Real Estate", "industry": HOTEL}}, "2026-10-22")
    industry.remember(cache, "XXX", None, "2026-10-22")
    industry.remember(cache, "YYY", {"snapshot": {"industry": None}}, "2026-10-22")
    industry.save_cache(cache, path)
    assert industry.load_cache(path) == {
        "APLE": {"sector": "Real Estate", "industry": HOTEL, "as_of": "2026-10-22"}}


def _archive(path, rows):
    con = sqlite3.connect(path)
    con.execute("create table setup_archive (ticker text, scan_date text, source text, "
                "universe_type text, fund_sheet_json text)")
    con.executemany("insert into setup_archive values (?,?,?,?,?)", rows)
    con.commit()
    con.close()


def test_recent_fires_read_the_window_the_source_and_the_universe(tmp_path):
    db = str(tmp_path / "a.db")
    sheet = json.dumps({"snapshot": {"industry": "Steel"}})
    _archive(db, [
        ("PK", "2026-10-13", "screener", "us_equities", None),         # inside, no sheet
        ("CLDT", "2026-10-14", "screener", "us_equities", sheet),      # inside, its own sheet
        ("CLDT", "2026-10-15", "screener", "us_equities", None),       # again, no sheet: its word stands
        ("OLD", "2026-10-02", "screener", "us_equities", sheet),       # before the window
        ("TONIGHT", "2026-10-22", "screener", "us_equities", sheet),   # tonight is not "before"
        ("SEED", "2026-10-14", "seed", "us_equities", sheet),          # not the screener's
        ("XLE", "2026-10-14", "screener", "us_sectors", sheet),        # another universe
    ])
    got = industry.recent_fires("2026-10-09", "2026-10-22", "us_equities", db_path=db)
    assert got == {"PK": None, "CLDT": "Steel"}


def test_recent_fires_tolerate_a_missing_archive(tmp_path):
    assert industry.recent_fires("2026-10-09", "2026-10-22", "us_equities",
                                 db_path=str(tmp_path / "none.db")) == {}


def test_the_payload_resolves_the_group_per_fired_name(monkeypatch, tmp_path):
    from core.pipeline.screening import dashboard

    path = str(tmp_path / "industry_cache.json")
    monkeypatch.setattr(dashboard, "_industry_cache_path", lambda: path)
    asked = {}

    def recent(since, before, universe_type, db_path=None):
        asked.update(since=since, before=before, universe_type=universe_type)
        return {"PK": None, "RHP": HOTEL}
    monkeypatch.setattr(industry, "recent_fires", recent)
    # an earlier night left PK's industry in the cache; RHP's rides its archived sheet
    industry.save_cache({"PK": {"industry": HOTEL, "sector": "Real Estate", "as_of": "2026-10-13"}}, path)
    hotel = {"snapshot": {"industry": HOTEL, "sector": "Real Estate"}}
    results = pd.DataFrame([{"Ticker": "APLE", "_fund_sheet": hotel}, {"Ticker": "HST", "_fund_sheet": hotel},
                            {"Ticker": "NOPE"}])
    frame = pd.DataFrame({"Close": range(12)}, index=pd.bdate_range("2026-10-07", periods=12))  # ends 22/10

    groups = dashboard._group_facts(results, ["APLE", "HST", "PK", "RHP", "NOPE", "ZZZ"], frame, "us_equities")

    assert asked == {"since": "2026-10-09", "before": "2026-10-22", "universe_type": "us_equities"}
    assert groups["APLE"] == {"industry": HOTEL, "fired_tonight": 2, "fired_10d": 4, "members": 4}
    assert groups["HST"] == groups["APLE"]
    assert groups["NOPE"] is None
    # tonight's sheets and the archived ones are remembered for the next night's count
    assert set(industry.load_cache(path)) == {"PK", "APLE", "HST", "RHP"}
