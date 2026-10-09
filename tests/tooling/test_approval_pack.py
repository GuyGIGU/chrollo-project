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
from types import SimpleNamespace

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
        "rescues": [
            {"key": "BWAY", "day": "2026-08-13", "fired": True, "state": "fired", "against": "mini", "how": "near",
             "trigger": 17.29, "grade": "S", "score": 100.0, "page": "pages/rescue_BWAY.png"},
            {"key": "FRBA", "day": "2026-07-30", "fired": False, "state": "crossed", "against": None, "how": None,
             "trigger": None, "grade": None, "score": None, "page": "pages/rescue_FRBA.png"},
        ],
    }


def _night() -> dict:
    return {
        "night": "2026-10-08",
        "panel": {"source": "C:/live/market_data_cache_5y.parquet", "sha256": "f" * 64, "tickers": 3712},
        "readers": {
            "old": {"read": 3701, "fires": [{"ticker": "AAA", "tier": "A", "score": 61.0, "trigger": 10.0}],
                    "silent": 3699, "failed": 1, "wall_clock_s": 610.0, "slowest": [["AAA", 2.0]]},
            "new": {"read": 3701, "fires": [{"ticker": "BBB", "tier": "S", "score": 92.3, "trigger": 20.0}],
                    "silent": 3699, "failed": 1, "wall_clock_s": 240.0, "slowest": [["BBB", 0.9]],
                    "tiers": {"S": 1},
                    "failures": [["HOLE", "a trading day is missing from the middle: 1 session(s) between ..."]],
                    "failure_reasons": {"a trading day is missing from the middle": 1},
                    "states": {"no lines": 2800, "not scanned": 700, "lines, no LPS yet": 199, "fired": 1}},
        },
        "both": [], "old_only": ["AAA"], "new_only": ["BBB"],
        # The scan that served this night: another engine, which took AAA out after its read.
        "scan": {"scan_date": "2026-10-08", "engine_config_version": "a2252c6c" + "0" * 56, "same_night": True,
                 "read": 3690, "fires": 0, "removed_after_the_read": ["AAA"], "replay_only": ["AAA"],
                 "scan_only": []},
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
    assert [h.split(" ")[0] for h in headings[1:]] == ["Your", "The", "Three", "The", "One"]
    summary = html[html.index("In short"):html.index(headings[1])]
    for fact in ("35 of 40", "S 39", "both readers", "Thu 08/10/2026", "the scan you saw that night showed 0"):
        assert fact in summary, fact


def test_his_rows_link_their_pictures_misses_first(tmp_path):
    html = _write(tmp_path, _record(), _night())
    pages = re.findall(r'src="(pages/his_[^"]+)"', html)
    assert pages[:2] == ["pages/his_DOOR.png", "pages/his_LINES.png"]
    assert pages[-1] == "pages/his_NKE.png"


def test_each_drawing_says_whether_it_fires_on_his_day_whatever_differs_before():
    """A box read from another opening day can still fire on his day at his trigger: the caption must say so, and
    the frame is amber, not the red of a drawing with no fire."""
    differs_but_fires = dict(_his("OPEN", "opening day"), strict=True)
    silent = _his("FIRE", "no fire")
    matched = _his("NKE", None, strict=True)
    assert 'class="chance"' in pack._his_figure(differs_but_fires)
    assert "fires on your day at your trigger" in pack._his_figure(differs_but_fires)
    assert 'class="miss"' in pack._his_figure(silent)
    assert "no fire on your day at your trigger" in pack._his_figure(silent)
    assert 'class="hit"' in pack._his_figure(matched) and "read as you drew it" in pack._his_figure(matched)


def test_the_junk_he_rules_and_the_junk_for_his_eye_are_named_apart(tmp_path):
    html = _write(tmp_path, _record(), _night())
    rule = html[html.index('id="junk-rule"'):html.index('id="junk-eye"')]
    eye = html[html.index('id="junk-eye"'):html.index('id="junk-rest"')]
    rest = html[html.index('id="junk-rest"'):]
    assert re.findall(r"<b>([^<]+)</b>", rule) == ["ABEV", "ENIC", "DGII", "DBD"]
    assert re.findall(r"<b>([^<]+)</b>", eye) == ["SPCB", "BBVA@2026-06-05", "KWR", "COLM"]
    assert "<b>FRPH</b>" in rest and "<b>BMRN</b>" in rest


def test_the_three_charts_named_for_this_sheet_are_the_records():
    """The task-13 blind check named three charts he never drew that fire ONLY by the small box's "near" while the big
    box refuses (docs/decisions.md, 2026-10-03): "named for task 15's sheet before any go-live"."""
    assert pack.MINI_RESCUES == (("BWAY", "2026-08-13"), ("FRBA", "2026-07-30"), ("TEVA", "2026-09-25"))


def test_the_charts_he_never_drew_that_fire_by_the_small_boxs_near_are_shown(tmp_path):
    html = _write(tmp_path, _record(), _night())
    section = html[html.index('id="rescues"'):html.index('id="grade"')]
    assert 'src="pages/rescue_BWAY.png"' in section
    assert "fires on Thu 13/08/2026 at 17.29, read against the small box (near it)" in section
    assert "grade S 100" in section
    # What the reader says today, never the record's word: a chart that no longer fires says so.
    assert "no fire on Thu 30/07/2026 (crossed)" in section


def test_a_pack_made_before_its_night_says_where_the_three_charts_come_from(tmp_path):
    record = dict(_record(), rescues=None)
    html = _write(tmp_path, record, None)
    section = html[html.index('id="rescues"'):html.index('id="grade"')]
    assert "run the night first" in section
    assert pack.rescue_rows(str(tmp_path)) is None, "no copied panel, no read"


def test_the_night_shows_both_readers_side_by_side(tmp_path):
    html = _write(tmp_path, _record(), _night())
    night = html[html.index('id="night"'):]
    for fact in ("3701", "610", "240", "no lines", "2800", "not scanned", "AAA", "BBB",
                 "a trading day is missing from the middle 1", "HOLE", "S 1"):
        assert fact in night, fact


def test_the_night_says_what_the_scan_showed_that_night(tmp_path):
    """The night's "today's engine" is this tree's; the scan he saw ran the deployed engine and cut after its read.
    The page says what that scan showed and which fires differ, never the replay as the night he saw (the task-15
    blind check's P2: 121 on the page, 116 on his screen)."""
    html = _write(tmp_path, _record(), _night())
    night = html[html.index('id="night"'):]
    for fact in ("The scan you saw that night", "a2252c6c", "3690", "only in this replay: AAA",
                 "its market-cap floor took out after the read: AAA", "only in the scan: none"):
        assert fact in night, fact


def test_the_night_says_why_the_replay_reads_more_charts_than_the_scan(tmp_path):
    """The replay reads every chart of the copied panel its ledgers admit; the scan read the names of its ticker list
    it admitted that night, a set it does not keep (verify-15c: the list itself is on disk). The page says so whenever
    the two counts differ (verify-15b: 5,520 here, 5,502 in the scan), and only then."""
    night = _night()
    html = _write(tmp_path, _record(), night)
    assert ("This replay reads every chart of the copied panel its ledgers admit (3701); the scan read the names of "
            "its ticker list it admitted that night (3690), a set it does not keep on disk."
            ) in html[html.index('id="night"'):]
    night["scan"]["read"] = 3701
    (tmp_path / "night" / "night.json").write_text(json.dumps(night), encoding="utf-8")
    with open(pack.write_index(str(tmp_path)), encoding="utf-8") as f:
        assert "every chart of the copied panel" not in f.read()


def test_the_page_states_the_grade_he_approves(tmp_path):
    """verify-15d: the sheet showed every chart's grade and letter, never the rule that makes them, and he is asked to
    approve that rule. The page states it beside the sheet, from the reader's own numbers."""
    html = _write(tmp_path, _record(), _night())
    grade = html[html.index('id="grade"'):html.index('id="night"')]
    for fact in ("misses the box by more than half its daily range", "100 when no day of the base is empty",
                 "0 when half the base is empty", "0 when the base did not hold", "S from 75, A from 50, B from 25",
                 "yours to approve"):
        assert fact in grade, fact


def test_the_stamp_says_when_the_pack_was_built_from_a_changed_tree(monkeypatch):
    """The page stamps the commit it was built at; a tracked file changed since that commit is said, never hidden
    (the task-15 blind check: a page stamped with a commit, written by a tool not yet committed)."""
    said = {"rev-parse": "abc1234\n", "status": " M tools/calibration/approval_pack.py\n"}
    monkeypatch.setattr(pack.subprocess, "run", lambda args, **kwargs: SimpleNamespace(
        stdout=said["rev-parse" if "rev-parse" in args else "status"]))
    assert pack._head() == "abc1234+dirty"
    said["status"] = ""
    assert pack._head() == "abc1234"


def test_a_pack_without_its_night_says_how_to_make_it(tmp_path):
    html = _write(tmp_path, _record(), None)
    night = html[html.index('id="night"'):]
    assert "python -m tools.calibration.parallel_night" in night
