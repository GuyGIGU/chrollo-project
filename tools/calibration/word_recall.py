"""Word recall: his drawn event words against the words on the line (build step 5 of the final method).

For each of his box marks, the words the NEW reader's word rules (``engine_alpha.story``, copied
from the old engine at task 7 of the two-eyes-reader build) read on his read day, on the READER's own line
(``engine_alpha.line``, no scalar fallback) and in his box's own daily range (the range of the day his
second line was anchored: the unit the story measures a box's words in since task 12b), through the one assembly
the story runs (``line_words.assemble``; council review of Fri 09/10/2026, finding 13), against the words he drew. It CALLS the reader and never
re-types a rule (EC-18). Read-only: the marks DB is opened ``mode=ro&immutable=1``, so no pragma, no WAL write and
no commit can reach it. Not in pytest: CI has no marks DB.

The engine basis is the reader's own record of the chart on his fire day (``engine_alpha.gate.read_record``):
its parent box, its LPS and its mini, in the box's own daily range. The words and the line it reads on that
box are the same rules as on his rails. (Until 31/10/2026 this basis was the old engine's election; the old
engine is retired.)

Two bases, reported side by side:
  his rails  the reader on HIS rails, fed HIS drawn LPS windows: the word rule alone, without the election.
  engine     the words read on the reader's own box at his fire day (the record from the door, in the box's
             own daily range): scored only where the reader draws a box.

A hit is the same word within one trading day of the bar his drawing points at. Beside every hit rate: the exact
day, and CHANCE, the same score with his day moved three trading days either way (a word that fires on most days
scores as well there as on his day, and then the hit rate says nothing; for a word that names one day, like THE
SOS, it only asks whether the pick lands two to four days off, so it is near zero by construction):
  SOS          a thrust tops on his last day; "strict" also needs its launch on his first day
  THE SOS      per LPS window he drew with an SOS drawn since the one before it, the pick tops on that SOS
  last supper  a last supper tops on his highest high (his last LPS window is the later LPS it waits for)
  Phase C      the one Phase C sits on his tip
  spring test  the one spring test sits on his tip
  mini         the mini overlaps his span with both band edges inside the rail area of his (engine election
               only: on his rails the mini was the old engine's inner-box election, which the new reader does
               not carry — task 13 builds its own)
THE upthrust (one per box) is listed, never scored: the app cannot record one yet (its calibration event types are
phase_c, lps, spring_test, sos, mini_consolidation and last_supper), so his only drawn upthrusts are the UNF
picture of Tue 15/09/2026 (the push to Thu 11/06/2026) with the smaller breach to Fri 05/06/2026 crossed out on the
engine's own render a day later, and his VIK note of July (Thu 14/05/2026, named since the dip before it is no spring, his
word of Sat 19/09/2026).
Phase D opens at or before his first right-side event (his first SOS or his first LPS), and after the middle of the
box (a must, his ruling Mon 14/09/2026). It is scored as the reader emits it, and fed HIS drawn Phase C, first SOS
and first LPS (what the sixteenth sitting measured), so the rule and its inputs can be told apart; the report names
the marks with no Phase D (every opening at or before the middle) and those opening well after his first event.

usage: python -m tools.calibration.word_recall [--json PATH]
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
from engine_alpha import gate  # noqa: E402  (the door: the reader's own record)
from engine_alpha import story as line_words  # noqa: E402
from engine_alpha.line import build as build_line  # noqa: E402
from engine_alpha.chart import calculate_atr  # noqa: E402
from tools.calibration.calibration_harness import load_box_marks  # noqa: E402
from core.calibration.replay import session_pos  # noqa: E402
from webapp.backend import frame_store  # noqa: E402

WORDS = ("sos", "sos strict", "the_sos", "the_sos strict", "last_supper", "phase_c", "spring_test",
         "mini_consolidation")
SHIFT = 3


def _enriched(frame):
    """The columns the word rules expect, computed with the reader's daily range."""
    frame = frame.copy()
    frame["ATR_10"] = calculate_atr(frame, 10)
    frame["ATR_50"] = calculate_atr(frame, 50)
    frame["Vol_50"] = frame["Volume"].rolling(50).mean()
    frame["Spread"] = frame["High"] - frame["Low"]
    return frame


def _read_only_session():
    uri = "file:" + pathname2url(database._DB_PATH) + "?mode=ro&immutable=1"
    return sessionmaker(bind=create_engine("sqlite://", creator=lambda: sqlite3.connect(uri, uri=True)))()


def _line(frame):
    """The READER's own turn line on this frame (``line.build``: each day's own range, no scalar fallback), in
    the words' form."""
    return [(int(t.bar), t.kind, float(t.price), None if t.knowable_bar is None else int(t.knowable_bar))
            for t in build_line(frame).turns]


def _reader_box(idx, box, read_bar: int):
    """The reader's box (``engine_alpha.record.Box``) in the words' shape: bars of ``idx``."""
    start = session_pos(idx, box.opened_day.isoformat())
    R, S = float(box.resistance.price), float(box.support.price)
    return SimpleNamespace(start_bar=start, base_len=read_bar - start + 1, R=R, S=S, box_width=(R - S) / S,
                           r_anchor_bar=session_pos(idx, box.resistance.anchor_day.isoformat()),
                           s_anchor_bar=session_pos(idx, box.support.anchor_day.isoformat()))


def _box_unit(frame, box) -> float:
    """His box's own daily range, as the reader measures a pair's: the range of the day its second line was
    anchored."""
    return float(frame["ATR_10"].iloc[max(int(box.r_anchor_bar), int(box.s_anchor_bar))])


def _hit(bars, at, tol=1):
    return any(abs(int(b) - int(at)) <= tol for b in bars)


def _row(key, word, bars, at, a, b, day, strict=None):
    """One drawn word: the exact-day hit, the one-day hit and the chance hits with his day moved SHIFT days."""
    shifted = [at + s for s in (-SHIFT, SHIFT) if a <= at + s <= b]
    return {"mark": key, "word": word, "day": day, "hit": _hit(bars, at), "exact": _hit(bars, at, 0),
            "chance": mean(_hit(bars, s) for s in shifted) if shifted else None,
            **({"strict": bool(strict)} if strict is not None else {})}


def _score(key, rec, evs, span, tip, hi, lo, a, b, day, lps_windows, sos_windows, unit, *, line, box_start,
           read_bar):
    """The hit rows for one record against his drawn words. ``a`` .. ``b`` bound the chance shifts; ``line``,
    ``box_start`` and ``read_bar`` are the frame and box the record was read in (THE SOS is picked on them)."""
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
            pick = line_words.pick_the_sos(rec["thrusts"], low_bar, after=floor, line=line, highs=hi,
                                           start=box_start, read_bar=read_bar, unit=unit)
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
    raw = frame_store.load_frame(mk.ticker, mk.as_of_date, digest=mk.frame_digest)
    fr = _enriched(raw)
    idx = fr.index
    a = session_pos(idx, mk.box_start_date)
    b = session_pos(idx, mk.as_of_date, boundary="end")
    work = fr.iloc[:b + 1]
    hi, lo = work["High"].to_numpy(float), work["Low"].to_numpy(float)
    R, S = float(mk.resistance), float(mk.support)
    day = lambda bar: str(idx[int(bar)].date())
    line = _line(work)

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
    unit = _box_unit(work, box)
    rec = line_words.read_line_words(work, box, unit, lps=lps, line=line)
    rows = _score(key, rec, evs, span, tip, hi, lo, a, b, day, lps_windows, sos_windows, unit,
                  line=line, box_start=a, read_bar=b)

    # The engine basis reads on HIS fire day, the last day of his last LPS window: his read day is often the buy
    # day or later, where no LPS is live and the reader returns nothing. Only words he drew by then are scored.
    eng_rows, eng, eng_box = [], None, None
    if last:
        fire = last[1]
        wf = work.iloc[:fire + 1]
        record = gate.read_record(mk.ticker, raw.iloc[:fire + 1])
        box = None if record is None or record.failed else record.parent
        if box is not None:
            eng_box = _reader_box(idx, box, fire)
            uf = float(box.daily_range) if box.daily_range else _box_unit(wf, eng_box)
            eng_lps, eng_lps_ns = [], None
            if record.lps is not None:
                l0 = session_pos(idx, record.lps.start_day.isoformat())
                l1 = session_pos(idx, record.lps.end_day.isoformat(), boundary="end")
                low_bar = l0 + int(np.argmin(lo[l0:l1 + 1]))
                eng_lps = [(l0, l1, low_bar)]
                eng_lps_ns = SimpleNamespace(start_bar=l0, end_bar=l1, low_bar=low_bar, low=float(lo[low_bar]))
            inner = None if record.mini is None else _reader_box(idx, record.mini, fire)
            eng = line_words.read_line_words(wf, eng_box, uf, lps=eng_lps_ns, inner=inner, line=_line(wf))
            seen = [e for e in evs if span(e)[1] <= fire]
            eng_rows = _score(key, eng, seen, span, tip, hi, lo, min(a, int(eng_box.start_bar)), fire, day,
                              eng_lps, [w for w in sos_windows if w[1] <= fire], uf, line=_line(wf),
                              box_start=int(eng_box.start_bar), read_bar=fire)

    facts = {"mark": key, "days": b - a + 1, "thrusts": len(rec["thrusts"]),
             "last_suppers": len(rec["last_suppers"]), "spring_tests": len(rec["spring_tests"]),
             "phase_c_undrawn": rec["phase_c"] is not None and not any(e.event_type == "phase_c" for e in evs),
             "upthrust": (None if rec["the_upthrust"] is None else
                          f"{day(rec['the_upthrust']['swing_bar'])} -> {day(rec['the_upthrust']['top_bar'])} "
                          f"+{rec['the_upthrust']['poke_ranges']:.2f} over R"),
             "engine_box": (eng_box is not None) if last else None}
    if lps_windows:
        his_first = min([lps_windows[0][0]] + [s0 for (s0, _) in sos_windows])
        pcs = [e for e in evs if e.event_type == "phase_c"]
        his_pc = None
        if pcs:
            v = [t for t in line if t[1] == "valley" and abs(t[0] - tip(pcs[0])) <= 1]
            his_pc = {"tip_bar": int(v[0][0]), "tip_price": float(v[0][2])} if v else None
        his_sos = ({"launch_bar": sos_windows[0][0], "swing_bar": sos_windows[0][0], "in_progress": False}
                   if sos_windows else None)
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
    if any(f["engine_box"] is None for f in facts):
        print("ENGINE ELECTION: not read. It is the OLD reader's box read, and the new reader is switched on.")
    else:
        _report(f"ENGINE ELECTION at his read day (a box on {sum(f['engine_box'] for f in facts)} of "
                f"{len(facts)}):", eng_rows)
    per10 = lambda k: median(f[k] / f["days"] * 10 for f in facts)
    print(f"  per 10 trading days in his boxes: thrusts {per10('thrusts'):.2f}; last suppers named "
          f"{sum(f['last_suppers'] for f in facts)} on {sum(f['last_suppers'] > 0 for f in facts)} of his boxes; "
          f"spring tests per box {median(f['spring_tests'] for f in facts):.0f}")
    print(f"  a Phase C named on {sum(f['phase_c_undrawn'] for f in facts)} of his boxes where he drew none")
    uts = [f"{f['mark']} {f['upthrust']}" for f in facts if f["upthrust"]]
    print(f"  THE upthrust named on {len(uts)} of his boxes (one per box, never scored, the app cannot record "
          f"one): {uts}")
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
