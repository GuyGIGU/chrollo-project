"""Battery for tools/power_play_sheets.py — the ruling-sheet selection.

Pure-selection tests only (no matplotlib, no cache): membership per section,
the informativeness ranks on both sides of the form (boundary-first for
admissions, textbook-first for refusals), cross-section dedup, the
no-silent-caps accounting, verbatim census identity on every card, the VOID
tripwire refusal, and the sealed-output guard.
"""
import json
import sys

import pytest

from _paths import BASELINES_DIR, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from tools.power_play_sheets import (  # noqa: E402
    _NAMED_ANCHORS,
    boundary_key,
    fold_episodes,
    load_sidecar,
    select_cards,
    textbook_key,
    write_sheet,
)


def _row(ticker, climax, ar, clock, verdict, *, breakout=None, pole=1.5,
         depth=0.2, fll="2026-06-01", **extra):
    row = {"ticker": ticker, "climax": climax, "ar": ar, "clock": clock,
           "verdict": verdict, "breakout": breakout, "pole_gain": pole,
           "depth": depth, "first_legal_look": fll}
    row.update(extra)
    return row


def _ladder(ticker, climax, ar, verdicts, **kw):
    """One episode's rows across the 4 swept clocks."""
    return [_row(ticker, climax, ar, clock, verdict, **kw)
            for clock, verdict in zip((8, 10, 15, 20), verdicts)]


def _doc(rows, clocks=(20, 15, 10, 8)):
    per_clock = {str(c): {v: 0 for v in (
        "elected_episode", "elected_other", "no_election",
        "refused_universe", "not_watched_clock", "pending")} for c in clocks}
    return {"tool": "power_play_census", "tripwire": "OK",
            "params": {"clocks": list(clocks), "pole_min_gain": 0.9,
                       "pole_window_bars": 40},
            "engine_config_version": "m" * 64, "marks_fingerprint": "f" * 64,
            "cache_state": {"tickers": 1, "last_session": "2026-08-17"},
            "per_clock": per_clock, "rows": rows}


def test_a_void_census_is_refused_outright(tmp_path):
    doc = _doc([])
    doc["tripwire"] = "VOID: lookahead — X@2026-01-01"
    path = tmp_path / "census.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="VOID"):
        load_sidecar(str(path))


def test_fold_builds_the_per_episode_clock_ladder():
    rows = _ladder("AAA", "2026-01-05", "2026-01-12",
                   ("no_election", "not_watched_clock", "pending", "pending"))
    episodes = fold_episodes(rows)
    ladder = episodes[("AAA", "2026-01-05", "2026-01-12")]
    assert set(ladder) == {8, 10, 15, 20}
    assert ladder[8]["verdict"] == "no_election"
    assert ladder[10]["verdict"] == "not_watched_clock"


def test_s2_marginal_is_watched_short_and_walled_next_up():
    rows = (
        # IN: cascaded at 8, walled at 10.
        _ladder("MRG", "2026-01-05", "2026-01-12",
                ("no_election", "not_watched_clock", "pending", "pending"))
        # OUT: watched at both 8 and 10 — no marginal information.
        + _ladder("BOTH", "2026-02-02", "2026-02-09",
                  ("no_election", "no_election", "no_election", "no_election"))
        # OUT: refused_universe at 8 never reaches a ruling sheet.
        + _ladder("REF", "2026-03-02", "2026-03-09",
                  ("refused_universe", "not_watched_clock", "pending",
                   "pending"))
    )
    sel = select_cards(_doc(rows), budget=40)
    s2 = [c["ticker"] for c in sel["cards"] if c["section"] == "S2"]
    assert s2 == ["MRG"]
    assert sel["sections"]["S2"]["population"] == 1


def test_s1_misfiles_are_fast_resolutions_or_named_anchors():
    rows = (
        # IN: census breakout 5 calendar days after the AR (the MAN signature).
        _ladder("FAST", "2026-01-05", "2026-01-12",
                ("not_watched_clock",) * 4, breakout="2026-01-16")
        # OUT: breakout 30 days out — the wall did its normal job.
        + _ladder("SLOW", "2026-02-02", "2026-02-09",
                  ("not_watched_clock",) * 4, breakout="2026-03-11")
        # IN regardless of timing: a named anchor (the operator's own name).
        + _ladder("MAN", "2026-07-17", "2026-07-24",
                  ("not_watched_clock",) * 4, breakout="2026-08-25")
    )
    assert "MAN" in _NAMED_ANCHORS
    sel = select_cards(_doc(rows), budget=40)
    s1 = [c["ticker"] for c in sel["cards"] if c["section"] == "S1"]
    assert set(s1) == {"FAST", "MAN"}
    anchor_card = next(c for c in sel["cards"] if c["ticker"] == "MAN")
    assert "anchor" in anchor_card["chips"]
    assert s1[0] == "MAN"          # named anchors lead the section


def test_refusals_rank_textbook_first_and_admissions_boundary_first():
    # Two refusals: the textbook pole must outrank the weak one.
    strong = _row("STRN", "2026-01-05", "2026-01-12", 8, "no_election",
                  pole=3.0, depth=0.10)
    weak = _row("WEAK", "2026-02-02", "2026-02-09", 8, "no_election",
                pole=0.95, depth=0.20)
    assert textbook_key(strong) < textbook_key(weak)
    # Two admissions: the boundary case must outrank the obvious archetype.
    edge = _row("EDGE", "2026-03-02", "2026-03-09", 8, "elected_episode",
                pole=0.92, depth=0.22, elected={"open": "2026-03-09",
                                                "R": 10.0, "S": 9.0,
                                                "base_len": 9})
    arch = _row("ARCH", "2026-04-06", "2026-04-13", 8, "elected_episode",
                pole=2.5, depth=0.12, elected={"open": "2026-04-13",
                                               "R": 10.0, "S": 9.0,
                                               "base_len": 9})
    assert boundary_key(edge) < boundary_key(arch)
    rows = []
    for r in (strong, weak, edge, arch):
        ladder = _ladder(r["ticker"], r["climax"], r["ar"],
                         (r["verdict"],) * 4, pole=r["pole_gain"],
                         depth=r["depth"])
        for lr in ladder:
            if r.get("elected") and lr["clock"] == 8:
                lr["elected"] = r["elected"]
        rows.extend(ladder)
    sel = select_cards(_doc(rows), budget=40)
    s4 = [c["ticker"] for c in sel["cards"] if c["section"] == "S4"]
    s3 = [c["ticker"] for c in sel["cards"] if c["section"] == "S3"]
    assert s4 == ["STRN", "WEAK"]
    assert s3 == ["EDGE", "ARCH"]


def test_book_valid_rows_lead_and_degenerates_sink():
    # A reverse-split-artifact "pole" (+30000%, 90% "flag") must never outrank
    # a book-valid refusal, and must carry the depth chip when charted.
    rows = (_ladder("JUNK", "2025-01-06", "2025-01-13",
                    ("no_election",) * 4, pole=300.0, depth=0.9)
            + _ladder("BOOK", "2025-02-03", "2025-02-10",
                      ("no_election",) * 4, pole=1.2, depth=0.15))
    sel = select_cards(_doc(rows), budget=40)
    s4 = [c for c in sel["cards"] if c["section"] == "S4"]
    assert [c["ticker"] for c in s4] == ["BOOK", "JUNK"]
    junk = next(c for c in s4 if c["ticker"] == "JUNK")
    assert any(ch.startswith("depth>") for ch in junk["chips"])
    assert sel["sections"]["S4"]["book_valid"] == 1


def test_live_chip_means_recent_and_unresolved():
    # Unresolved + recent look = LIVE; unresolved + stale look = "unresolved".
    rows = (_ladder("NOW", "2026-07-20", "2026-07-27",
                    ("elected_episode",) * 4, fll="2026-08-10")
            + _ladder("OLD", "2024-03-04", "2024-03-11",
                      ("elected_episode",) * 4, fll="2024-03-25"))
    sel = select_cards(_doc(rows), budget=40)   # cache last_session 2026-08-17
    now = next(c for c in sel["cards"] if c["ticker"] == "NOW")
    old = next(c for c in sel["cards"] if c["ticker"] == "OLD")
    assert "LIVE" in now["chips"] and "unresolved" not in now["chips"]
    assert "unresolved" in old["chips"] and "LIVE" not in old["chips"]
    s3 = [c["ticker"] for c in sel["cards"] if c["section"] == "S3"]
    assert s3[0] == "NOW"               # live rows lead the admissions


def test_budget_caps_and_cross_section_dedup_are_accounted():
    # 30 marginal episodes (also all no_election at 8) — S2 takes them first;
    # S4 must NOT re-chart the same episodes, and the accounting must show
    # population vs charted honestly on both sections.
    rows = []
    for i in range(30):
        rows.extend(_ladder(
            f"T{i:02d}", f"2026-01-{(i % 27) + 1:02d}", f"2026-02-{(i % 27) + 1:02d}",
            ("no_election", "not_watched_clock", "pending", "pending"),
            pole=1.0 + i * 0.05))
    sel = select_cards(_doc(rows), budget=12)
    by_section = {}
    seen = set()
    for c in sel["cards"]:
        by_section.setdefault(c["section"], []).append(c)
        key = (c["ticker"], c["climax"])
        assert key not in seen          # an episode is charted at most once
        seen.add(key)
    assert len(sel["cards"]) <= 12 + len(sel["sections"])  # quota rounding only
    assert sel["sections"]["S2"]["population"] == 30
    assert sel["sections"]["S4"]["population"] == 30
    assert (sel["sections"]["S2"]["charted"]
            + sel["sections"]["S4"]["charted"] < 30)  # capped, not silently


def test_cards_carry_the_census_identity_verbatim():
    rows = _ladder("IDN", "2026-05-04", "2026-05-11",
                   ("no_election", "not_watched_clock", "pending", "pending"),
                   fll="2026-05-22", pole=1.23, depth=0.19)
    sel = select_cards(_doc(rows), budget=10)
    card = next(c for c in sel["cards"] if c["ticker"] == "IDN")
    src = rows[0]                       # the clock-8 census row
    for field in ("ticker", "climax", "ar", "breakout", "pole_gain", "depth",
                  "clock", "first_legal_look"):
        assert card[field] == src[field]
    assert card["census_verdict"] == src["verdict"]
    assert card["ladder"]["10"] == "not_watched_clock"


def test_the_page_embeds_identity_and_stamp(tmp_path):
    rows = _ladder("PGE", "2026-05-04", "2026-05-11",
                   ("no_election", "not_watched_clock", "pending", "pending"))
    doc = _doc(rows)
    sel = select_cards(doc, budget=10)
    for card in sel["cards"]:
        card["img"] = None
    md_path, html_path = write_sheet(doc, sel, str(tmp_path / "sheets"),
                                     "census.json", "48 min")
    html = open(html_path, encoding="utf-8").read()
    assert '"ticker": "PGE"' in html
    assert '"climax": "2026-05-04"' in html
    assert ("m" * 64) in html           # the manifest stamp rides the export
    md = open(md_path, encoding="utf-8").read()
    assert "shadow-clock counterfactual" in md
    assert "48 min" in md               # the measured wall clock is quoted


def test_sheet_output_refuses_sealed_dirs():
    rows = _ladder("SEA", "2026-05-04", "2026-05-11",
                   ("no_election", "not_watched_clock", "pending", "pending"))
    doc = _doc(rows)
    sel = select_cards(doc, budget=10)
    sealed = str(BASELINES_DIR)
    with pytest.raises(ValueError, match="sealed"):
        write_sheet(doc, sel, sealed, "census.json", None)
