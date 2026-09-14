"""Word recall: his drawn event words against the words on the line (build step 5 of the final method).

For each of his box marks, the words ``engine_alpha.structure.line_words`` reads on his read day, in his unit (the
day's range six trading days back, the unit his numbers were placed in), against the words he drew. It CALLS the
reader and never re-types a rule (EC-18). Read-only: the marks DB is opened ``mode=ro&immutable=1``, so no pragma,
no WAL write and no commit can reach it. Not in pytest: CI has no marks DB.

Two bases, reported side by side:
  his rails  the reader on HIS rails, fed HIS drawn LPS windows: the word rule alone, without the election.
  engine     the reader on the engine's own election at his read day (``read_structure`` on the same frame): the
             words a fire would carry, scored only where the engine draws a box.

A hit is the same word within one trading day of the bar his drawing points at. Beside every hit rate: the exact
day, and CHANCE, the same score with his day moved three trading days either way (a word that fires on most days
scores as well there as on his day, and then the hit rate says nothing):
  SOS          a thrust tops on his last day; "strict" also needs its launch on his first day
  THE SOS      per LPS window he drew with an SOS drawn since the one before it, the pick tops on that SOS
  last supper  a last supper tops on his highest high (his last LPS window is the later LPS it waits for)
  Phase C      the one Phase C sits on his tip
  spring test  the one spring test sits on his tip
  mini         the mini overlaps his span with both band edges inside the rail area of his
Phase D opens at or before his first right-side event (his first SOS or his first LPS), and after the middle of the
box (a must, his ruling Mon 14/09/2026). It is scored as the reader emits it, and fed HIS drawn Phase C, first SOS
and first LPS (what the sixteenth sitting measured), so the rule and its inputs can be told apart; the report names
the marks with no Phase D (every opening at or before the middle) and those opening well after his first event.

usage: python -m tools.word_recall [--json PATH]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from statistics import mean, median
from types import SimpleNamespace
from urllib.request import pathname2url

from tools._bootstrap import configure_path

configure_path(backend=True)

import numpy as np  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import database  # noqa: E402
from engine_alpha.structure import line_words  # noqa: E402
from engine_alpha.structure.bricks import find_inner_box  # noqa: E402
from engine_alpha.structure.narrative import read_structure  # noqa: E402
from engine_alpha.structure.pivots import turn_line, turn_line_floors  # noqa: E402
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.replay import MARK_ATR_OFFSET, enrich_marked_frame, session_pos  # noqa: E402
from webapp.backend import frame_store  # noqa: E402

WORDS = ("sos", "sos strict", "the_sos", "the_sos strict", "last_supper", "phase_c", "spring_test",
         "mini_consolidation")
SHIFT = 3


def _read_only_session():
    uri = "file:" + pathname2url(database._DB_PATH) + "?mode=ro&immutable=1"
    return sessionmaker(bind=create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True)))()


def _hit(bars, at, tol=1):
    return any(abs(int(b) - int(at)) <= tol for b in bars)


def _row(key, word, bars, at, a, b, day, strict=None):
    """One drawn word: the exact-day hit, the one-day hit and the chance hits with his day moved SHIFT days."""
    shifted = [at + s for s in (-SHIFT, SHIFT) if a <= at + s <= b]
    return {"mark": key, "word": word, "day": day, "hit": _hit(bars, at), "exact": _hit(bars, at, 0),
            "chance": mean(_hit(bars, s) for s in shifted) if shifted else None,
            **({"strict": bool(strict)} if strict is not None else {})}


def _score(key, rec, evs, span, tip, hi, lo, a, b, day, lps_windows, sos_windows, unit):
    """The hit rows for one record against his drawn words."""
    rows = []
    for e in evs:
        t = e.event_type
        s0, s1 = span(e)
        if t == "sos":
            tops = [x["top_bar"] for x in rec["thrusts"]]
            rows.append(_row(key, "sos", tops, s1, a, b, day(s1)))
            both = [x["top_bar"] for x in rec["thrusts"] if abs(x["launch_bar"] - s0) <= 1]
            rows.append(_row(key, "sos strict", both, s1, a, b, day(s1)))
        elif t == "last_supper":
            at = s0 + int(np.argmax(hi[s0:s1 + 1]))
            rows.append(_row(key, "last_supper", [x["top_bar"] for x in rec["last_suppers"]], at, a, b, day(at)))
        elif t == "phase_c":
            pc = rec["phase_c"]
            rows.append(_row(key, "phase_c", [pc["tip_bar"]] if pc else [], tip(e), a, b, day(tip(e))))
        elif t == "spring_test":
            rows.append(_row(key, "spring_test", [x["tip_bar"] for x in rec["spring_tests"]], tip(e), a, b,
                             day(tip(e))))
        elif t == "mini_consolidation":
            bh = float(e.band_high) if e.band_high is not None else float(hi[s0:s1 + 1].max())
            bl = float(e.band_low) if e.band_low is not None else float(lo[s0:s1 + 1].min())
            m = rec["mini"]
            ok = (m is not None and m["start_bar"] <= s1 and abs(m["R"] - bh) <= 0.5 * unit
                  and abs(m["S"] - bl) <= 0.5 * unit)
            rows.append({"mark": key, "word": "mini_consolidation", "day": day(s0), "hit": bool(ok),
                         "exact": bool(ok), "chance": None})
    pc = rec["phase_c"]
    prev_low = None
    for (l0, l1, low_bar) in lps_windows:
        mine = [(s0, s1) for (s0, s1) in sos_windows if (prev_low is None or s1 > prev_low) and s1 <= low_bar]
        if mine:
            floor = max([v for v in (prev_low, pc["tip_bar"] if pc else None) if v is not None], default=None)
            pick = line_words.pick_the_sos(rec["thrusts"], low_bar, after=floor)
            tops = [pick["top_bar"]] if pick else []
            s0, s1 = mine[-1]
            strict = bool(pick) and _hit([pick["launch_bar"]], s0)
            rows.append(_row(key, "the_sos", tops, s1, a, b, day(s1)))
            rows.append(_row(key, "the_sos strict", tops if strict else [], s1, a, b, day(s1)))
        prev_low = low_bar
    return rows


def read_mark(mk):
    """(his-rails rows, engine rows, facts) for one mark."""
    key = f"{mk.ticker}:{mk.as_of_date}"
    fr = enrich_marked_frame(frame_store.load_frame(mk.ticker, mk.as_of_date, digest=mk.frame_digest))
    idx = fr.index
    a = session_pos(idx, mk.box_start_date)
    b = session_pos(idx, mk.as_of_date, boundary="end")
    work = fr.iloc[:b + 1]
    hi, lo = work["High"].to_numpy(float), work["Low"].to_numpy(float)
    unit = float(work["ATR_10"].iloc[-MARK_ATR_OFFSET])
    R, S = float(mk.resistance), float(mk.support)
    day = lambda bar: str(idx[int(bar)].date())

    def span(e):
        return session_pos(idx, e.start_date), session_pos(idx, e.end_date, boundary="end")

    def tip(e):
        s0, s1 = span(e)
        return session_pos(idx, e.tip_date) if e.tip_date else s0 + int(np.argmin(lo[s0:s1 + 1]))

    evs = sorted(mk.events, key=lambda e: str(e.start_date))
    lps_windows = [(s0, s1, s0 + int(np.argmin(lo[s0:s1 + 1])))
                   for (s0, s1) in (span(e) for e in evs if e.event_type == "lps")]
    sos_windows = [span(e) for e in evs if e.event_type == "sos"]
    last = lps_windows[-1] if lps_windows else None
    lps = (SimpleNamespace(start_bar=last[0], low_bar=last[2], low=float(lo[last[2]])) if last else None)
    box = SimpleNamespace(start_bar=a, base_len=b - a + 1, R=R, S=S, box_width=(R - S) / S,
                          r_anchor_bar=session_pos(idx, mk.r_anchor_date) if mk.r_anchor_date else a,
                          s_anchor_bar=session_pos(idx, mk.s_anchor_date) if mk.s_anchor_date else a)
    rec = line_words.read_line_words(work, box, unit, lps=lps, inner=find_inner_box(work, box, unit))
    rows = _score(key, rec, evs, span, tip, hi, lo,a, b, day, lps_windows, sos_windows, unit)

    # The engine basis reads on HIS fire day, the last day of his last LPS window: his read day is often the buy
    # day or later, where no LPS is live and the engine returns nothing. Only words he drew by then are scored.
    eng_rows, eng, structure = [], None, None
    if last:
        fire = last[1]
        wf = fr.iloc[:fire + 1]
        uf = float(wf["ATR_10"].iloc[-MARK_ATR_OFFSET])
        structure = read_structure(wf, uf)
        if structure is not None:
            eng = line_words.read_line_words(wf, structure.box, uf, lps=structure.lps, inner=structure.inner)
            eng_lps = [(int(structure.lps.start_bar), int(structure.lps.end_bar), int(structure.lps.low_bar))]
            seen = [e for e in evs if span(e)[1] <= fire]
            eng_rows = _score(key, eng, seen, span, tip, hi, lo, min(a, int(structure.box.start_bar)), fire, day,
                              eng_lps, [w for w in sos_windows if w[1] <= fire], uf)

    facts = {"mark": key, "days": b - a + 1, "thrusts": len(rec["thrusts"]),
             "last_suppers": len(rec["last_suppers"]), "spring_tests": len(rec["spring_tests"]),
             "phase_c_undrawn": rec["phase_c"] is not None and not any(e.event_type == "phase_c" for e in evs),
             "engine_box": structure is not None}
    if lps_windows:
        his_first = min([lps_windows[0][0]] + [s0 for (s0, _) in sos_windows])
        line = turn_line(hi, lo, turn_line_floors(work, unit))
        pcs = [e for e in evs if e.event_type == "phase_c"]
        his_pc = None
        if pcs:
            v = [t for t in line if t[1] == "valley" and abs(t[0] - tip(pcs[0])) <= 1]
            his_pc = {"tip_bar": int(v[0][0]), "tip_price": float(v[0][2])} if v else None
        his_sos = {"launch_bar": sos_windows[0][0], "in_progress": False} if sos_windows else None
        fed = line_words.phase_d(line, a, R, S, unit, his_pc, his_sos, lps_windows[0][0], b)
        variants = {"as emitted": rec["phase_d"], "fed his words": fed}
        if eng is not None:
            variants["engine election"] = eng["phase_d"]
        facts["phase_d"] = {name: {"open": day(p["open_bar"]), "opener": p["opener"],
                                   "position": p["position"], "lead_days": his_first - p["open_bar"]}
                            for name, p in variants.items() if p is not None}
        facts["phase_d_none"] = [name for name, p in variants.items() if p is None]
    return rows, eng_rows, facts


def _report(title, rows):
    by = defaultdict(list)
    for r in rows:
        by[r["word"]].append(r)
    print(title)
    for w in WORDS:
        rs = by.get(w, [])
        if not rs:
            continue
        ch = [r["chance"] for r in rs if r["chance"] is not None]
        chance = f"{sum(ch) / len(ch) * len(rs):4.1f}" if ch else "   -"
        misses = [f"{r['mark']} {r['day']}" for r in rs if not r["hit"]]
        print(f"  {w:20s} {sum(r['hit'] for r in rs):2d} of {len(rs):2d}   exact day {sum(r['exact'] for r in rs):2d}"
              f"   chance {chance}   misses {misses}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", help="also write every hit row and fact to this path")
    args = ap.parse_args(argv)
    session = _read_only_session()
    try:
        marks, fp = load_box_marks(session, None)
        out = [read_mark(mk) for mk in marks]
    finally:
        session.close()
    rows = [r for rs, _, _ in out for r in rs]
    eng_rows = [r for _, rs, _ in out for r in rs]
    facts = [f for _, _, f in out]
    print(f"WORD RECALL on his {len(marks)} marks, his read day (fingerprint {fp[:12]})")
    _report("HIS RAILS, fed his drawn LPS windows:", rows)
    _report(f"ENGINE ELECTION at his read day (a box on {sum(f['engine_box'] for f in facts)} of {len(facts)}):",
            eng_rows)
    per10 = lambda k: median(f[k] / f["days"] * 10 for f in facts)
    print(f"  per 10 trading days in his boxes: thrusts {per10('thrusts'):.2f}, last suppers "
          f"{per10('last_suppers'):.2f}; spring tests per box {median(f['spring_tests'] for f in facts):.0f}")
    print(f"  a Phase C named on {sum(f['phase_c_undrawn'] for f in facts)} of his boxes where he drew none")
    pd_rows = [f for f in facts if "phase_d" in f]
    for name in ("as emitted", "fed his words", "engine election"):
        got = [f["phase_d"][name] for f in pd_rows if name in f["phase_d"]]
        if not got:
            continue
        pos = [g["position"] for g in got]
        early = [f"{f['mark']} {f['phase_d'][name]['lead_days']}" for f in pd_rows
                 if name in f["phase_d"] and f["phase_d"][name]["lead_days"] > 15]
        late = [f"{f['mark']} {-f['phase_d'][name]['lead_days']}" for f in pd_rows
                if name in f["phase_d"] and f["phase_d"][name]["lead_days"] < -15]
        none = [f["mark"] for f in pd_rows if name in f.get("phase_d_none", [])]
        print(f"  Phase D {name:16s}: {len(got)} marks, position median {median(pos):.2f}, after the middle "
              f"{sum(p > 0.5 for p in pos)}, earliest {min(pos):.2f}, more than 15 trading days before his first "
              f"right-side event {early}, more than 15 after it {late}, none (every opening at or before the "
              f"middle) {none}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"fingerprint": fp, "his_rails": rows, "engine": eng_rows, "facts": facts}, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
