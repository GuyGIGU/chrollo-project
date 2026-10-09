"""The approval pack's index (task 15 of the two-eyes-reader build): one page he approves from, summary first.

The plan's Done-when: *"the APPROVAL PACK is the last yardstick run: your 35 (misses first, sorted by the first step
that differs), the junk sheet (ABEV, ENIC, DGII, DBD for you to rule; SPCB, the June BBVA, KWR and COLM for your
eye), the grade sheet, and a real scan night replayed by BOTH readers ... with fires, the tally of state words and
the wall clock; you approve, or point at the charts that are wrong"*. His 35 are 40 since Fri 02/10/2026.

The index is written from the pack's own record (``pack.json``, the one run's numbers) and the night's side file, so
it is tested here on a record built by hand: what comes first, what order the misses take, which junk is his to rule.
"""
from __future__ import annotations

import json
import re

from tools.calibration import approval_pack as pack


def _his(key, first, strict=False):
    return {"key": key, "first_difference": first, "strict": strict, "box": "OTHER" if first == "lines" else "HIS",
            "why": None if strict else "a reason", "page": f"pages/his_{key}.png", "grade": "S", "score": 90.0}


def _record() -> dict:
    return {
        "made": "Fri 09/10/2026", "head": "abc1234", "ruleset": "two-eyes-0.9.0-grade",
        "marks": {"drawings": 40, "events": 98},
        "yardstick": {"arms": [
            {"arm": "today", "strict": 15, "chance": 20, "lines_close": 9, "opened_on_his_day": 3, "total": 40,
             "wall_clock": 120.0},
            {"arm": "method", "strict": 30, "chance": 33, "lines_close": 14, "opened_on_his_day": 7, "total": 40,
             "wall_clock": 140.0},
            {"arm": "two-eyes", "strict": 35, "chance": 37, "lines_close": 36, "opened_on_his_day": 25, "total": 40,
             "wall_clock": 60.0},
        ]},
        "his": [_his("NKE", None, strict=True), _his("TRIG", "trigger"), _his("LINES", "lines"),
                _his("FIRE", "no fire"), _his("OPEN", "opening day"), _his("DOOR", "no frame"),
                _his("ALB", None, strict=True)],
        "junk": [
            {"key": key, "label": "junk", "fires": ["2026-06-05"], "grades": ["A"], "page": f"pages/junk_{key}.png"}
            for key in ("FRPH", "COLM", "KWR", "DBD", "SPCB", "ENIC", "DGII", "ABEV", "BBVA@2026-06-05", "BMRN")
        ],
        "grade": {"his": {"S": 39, "C": 1}, "junk": {"S": 17, "A": 8, "B": 6, "C": 12}, "sheet": "grade/index.html"},
    }


def _night() -> dict:
    return {
        "night": "2026-10-08",
        "panel": {"source": "C:/live/market_data_cache_5y.parquet", "sha256": "f" * 64, "tickers": 3712},
        "readers": {
            "old": {"read": 3701, "fires": [{"ticker": "AAA", "tier": "A", "score": 61.0, "trigger": 10.0}],
                    "silent": 3699, "failed": 1, "wall_clock_s": 610.0, "slowest": [["AAA", 2.0]]},
            "new": {"read": 3701, "fires": [{"ticker": "BBB", "tier": "S", "score": 92.3, "trigger": 20.0}],
                    "silent": 3700, "failed": 0, "wall_clock_s": 240.0, "slowest": [["BBB", 0.9]],
                    "states": {"no lines": 2800, "not scanned": 700, "lines, no LPS yet": 200, "fired": 1}},
        },
        "both": [], "old_only": ["AAA"], "new_only": ["BBB"],
    }


def _write(tmp_path, record: dict, night: dict | None) -> str:
    (tmp_path / "pack.json").write_text(json.dumps(record), encoding="utf-8")
    if night is not None:
        (tmp_path / "night").mkdir()
        (tmp_path / "night" / "night.json").write_text(json.dumps(night), encoding="utf-8")
    with open(pack.write_index(str(tmp_path)), encoding="utf-8") as f:
        return f.read()


def test_his_drawings_come_misses_first_in_the_order_of_the_first_step_that_differs():
    ordered = [row["key"] for row in pack.misses_first_by_step(_record()["his"])]
    assert ordered == ["DOOR", "LINES", "OPEN", "FIRE", "TRIG", "ALB", "NKE"]


def test_the_summary_comes_before_the_detail(tmp_path):
    html = _write(tmp_path, _record(), _night())
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
    assert headings[0].startswith("In short")
    assert [h.split(" ")[0] for h in headings[1:]] == ["Your", "The", "The", "One"]
    summary = html[html.index("In short"):html.index(headings[1])]
    for fact in ("35 of 40", "S 39", "both readers", "Thu 08/10/2026"):
        assert fact in summary, fact


def test_his_rows_link_their_pictures_misses_first(tmp_path):
    html = _write(tmp_path, _record(), _night())
    pages = re.findall(r'src="(pages/his_[^"]+)"', html)
    assert pages[:2] == ["pages/his_DOOR.png", "pages/his_LINES.png"]
    assert pages[-1] == "pages/his_NKE.png"


def test_the_junk_he_rules_and_the_junk_for_his_eye_are_named_apart(tmp_path):
    html = _write(tmp_path, _record(), _night())
    rule = html[html.index('id="junk-rule"'):html.index('id="junk-eye"')]
    eye = html[html.index('id="junk-eye"'):html.index('id="junk-rest"')]
    rest = html[html.index('id="junk-rest"'):]
    assert re.findall(r"<b>([^<]+)</b>", rule) == ["ABEV", "ENIC", "DGII", "DBD"]
    assert re.findall(r"<b>([^<]+)</b>", eye) == ["SPCB", "BBVA@2026-06-05", "KWR", "COLM"]
    assert "<b>FRPH</b>" in rest and "<b>BMRN</b>" in rest


def test_the_night_shows_both_readers_side_by_side(tmp_path):
    html = _write(tmp_path, _record(), _night())
    night = html[html.index('id="night"'):]
    for fact in ("3701", "610", "240", "no lines", "2800", "not scanned", "AAA", "BBB"):
        assert fact in night, fact


def test_a_pack_without_its_night_says_how_to_make_it(tmp_path):
    html = _write(tmp_path, _record(), None)
    night = html[html.index('id="night"'):]
    assert "python -m tools.calibration.parallel_night" in night
