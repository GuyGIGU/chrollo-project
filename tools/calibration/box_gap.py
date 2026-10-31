"""The box gap: his drawn pair against the reader's, by cause (his "fix the box", Tue 13/10 and Fri 17/10/2026:
*"if we can get the engine to draw like me ... that would truly be a breakthrough"*; *"build something to close
the gap"*).

Two populations, one reading: his sealed drawings (the standard, as `walk_board` reads them) and his LENS FIXES
(the `box_fixes` table: the two lines he drew over the reader's box on a scan night, read-only here), each read by
the reader on its own bars cut at his day. Per drawing: the box the reader shows against his two lines (HIS, CLOSE,
OTHER, NONE: `walk_board.verdict`), and when they differ, the CAUSE in words:

  * his pair is not a pair the rule lists (his two anchors are not two swing ends a swing connects);
  * his pair can never be a box (not a daily range tall, or the counter move took it all back);
  * his pair is no box by his day (the bars never came back to a rail, or under fifteen days);
  * his pair is a box, another is shown: born first, or shown by a hand-over (the reader's reason, in its words);
  * no box shown at all.

The board counts them; `--pages` draws one OHLC page per differing drawing (the walk board's own renderer: red his
lines, blue the reader's) and a contact sheet. Nothing here chooses: the chooser is learned only once thirty to
fifty fixes differ, and proven on fixes it never saw (the graveyard in decisions.md says why).

HIS EVENTS on a fix (Sat 18/10/2026, *"lets widen it by letting me put events (spring, upthrust, sos, lps/former
lps, span, mini consolidation.)"*): each event he placed is read against the reader's words on the same bars, and
the board says per fix whether they agree (the reader names the same kind on the same day, or on a day inside his
span; his LPS and the reader's LPS share a day; his mini and the reader's mini share their lines within half a
range) and prints every disagreement with its bars, so a tuning session can read them. A FORMER LPS is the pattern
he named (*"the screener shows stock that already had clear prior entry points and todays 'lps' are simply some
one bar correction post break out"*): the line says how many trading days after his former LPS the reader's LPS
began — the entry was earlier. A span is his word alone and is listed, never counted.

Offline, read-only, sidecars only.

    python -m tools.calibration.box_gap                  # the board, his 40 and every fix
    python -m tools.calibration.box_gap --pages OUT      # the board AND one OHLC page per differing drawing
    python -m tools.calibration.box_gap --fixes-only     # the fixes alone
    python -m tools.calibration.box_gap --fixes-only --db PATH   # a worktree reading the live journal
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
from collections import Counter
from urllib.request import pathname2url

import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha.box import handover, walk  # noqa: E402
from tools.calibration import walk_board  # noqa: E402
from tools.regression.marks_corpus import load_corpus, setup_key  # noqa: E402
from core.calibration.replay import fixture_frame, load_sealed_fixture  # noqa: E402
from core.pipeline.universe.descriptor import default_universe  # noqa: E402

#: The charts he named when he asked for the loop (13/10 and 17/10/2026), when they are in a population.
NAMED = ("MTLS", "ANET", "DDI", "BWA", "NET", "MATX", "BODI")
AGREE = ("his box", "close (both lines within half a range)")
_OHLCV = ("Open", "High", "Low", "Close", "Volume")


# --------------------------------------------------------------------------- #
# The cause: why the reader's box is not his, in words                        #
# --------------------------------------------------------------------------- #
def cause(row: dict) -> str:
    """ONE sentence per drawing. Agreement is a cause too (so every drawing has one); the rest name the step of
    the rule of the pair where his pair fell out, or the hand-over that shows another."""
    if row["verdict"] == "HIS":
        return AGREE[0]
    if row["verdict"] == "CLOSE":
        return AGREE[1]
    hp = row["his_pair"]
    if hp is None:
        return "his pair is not a pair the rule lists"
    if hp.unfit:
        return f"his pair can never be a box: {hp.unfit}"
    if hp.birth_bar is None:
        missing = [n for n, got in (("resistance", hp.r_back), ("support", hp.s_back)) if got is None]
        return ("his pair is no box by his day: the bars not back at " + " and ".join(missing)) if missing \
            else "his pair is no box by his day: under fifteen days"
    box = row["box"]
    if box is None:
        return "no box shown"
    why = row["why"]
    if why == handover.FIRST_BOX:
        return "his pair is a box, another was a box first"
    return f"his pair is a box, another is shown by a hand-over: {why}"


def _born_first(row: dict) -> str:
    """When his pair and the shown box are both boxes: which was born first, in words for the line."""
    hp, box, days = row["his_pair"], row["box"], row["days"]
    if hp is None or hp.birth_bar is None or box is None:
        return ""
    if hp.birth_bar < box.birth_bar:
        return f"his a box {days[hp.birth_bar]:%d/%m}, the shown one {days[box.birth_bar]:%d/%m}"
    if hp.birth_bar > box.birth_bar:
        return f"the shown one a box {days[box.birth_bar]:%d/%m}, his {days[hp.birth_bar]:%d/%m}"
    return f"both boxes on {days[box.birth_bar]:%d/%m}"


# --------------------------------------------------------------------------- #
# His fixes, read-only, as drawings the walk board can read                   #
# --------------------------------------------------------------------------- #
def load_fixes(db_path: str | None = None) -> list:
    """Every lens fix, oldest first, as dicts; an empty list when the table has not been born yet."""
    if db_path is None:
        import database  # noqa: PLC0415 — the backend's one DB path, on the path since configure_path(backend=True)
        db_path = database._DB_PATH
    # Read-only, WITH the write-ahead log: the service runs the journal in WAL mode, so the newest fixes and
    # every event sit in the -wal file until a checkpoint; `immutable=1` skips that file and read a state hours
    # old (Sat 18/10/2026: his DSGX fix at revision 2 and no events table at all). `immutable` only as the
    # fallback when a plain read-only open is refused (a path with no -shm to touch).
    base = "file:" + pathname2url(os.path.abspath(db_path))
    con = None
    for query in ("?mode=ro", "?mode=ro&immutable=1"):
        try:
            con = sqlite3.connect(base + query, uri=True)
            con.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            break
        except sqlite3.OperationalError:
            if con is not None:
                con.close()
            con = None
    if con is None:
        return []
    try:
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("SELECT id, ticker, scan_day, resistance, r_day, support, s_day, reader_resistance, "
                               "reader_r_day, reader_support, reader_s_day, reader_opened_day, ruleset, note, "
                               "revision FROM box_fixes ORDER BY ticker, scan_day").fetchall()
        except sqlite3.OperationalError:          # no such table: no fix saved yet
            return []
        fixes = [dict(r) for r in rows]
        events = {}
        try:
            for e in con.execute("SELECT fix_id, kind, first_day, last_day, price, band_high, band_low, label "
                                 "FROM box_fix_events ORDER BY fix_id, first_day").fetchall():
                events.setdefault(e["fix_id"], []).append(dict(e))
        except sqlite3.OperationalError:          # the events table is younger than the fixes: none placed yet
            pass
        for fix in fixes:
            fix["events"] = events.get(fix.get("id"), [])
        return fixes
    finally:
        con.close()


def fix_setup(fix: dict) -> dict:
    """A fix in the drawing's shape the walk board reads: his two lines and their days are his anchors, the scan
    day is his day (no LPS window, no buy: the box is read on the chart he fixed)."""
    first = min(fix["r_day"], fix["s_day"])
    return {"ticker": fix["ticker"], "as_of": fix["scan_day"], "setup": f"fix {fix['scan_day']}",
            "rails_drawn": {"R": float(fix["resistance"]), "S": float(fix["support"])},
            "anchors": {"R": fix["r_day"], "S": fix["s_day"]}, "box": [first, fix["scan_day"]],
            "lps": [fix["scan_day"], fix["scan_day"]], "lps2": None, "trigger": None,
            "reader_then": {"R": fix.get("reader_resistance"), "S": fix.get("reader_support")},
            "revision": fix.get("revision", 1), "events": list(fix.get("events") or [])}


# --------------------------------------------------------------------------- #
# His events against the reader's words                                       #
# --------------------------------------------------------------------------- #
#: His kind -> the reader's word for it (record.EVENT_KINDS); the LPS, the mini and the former LPS are read apart.
_READER_WORD = {"spring": "spring", "upthrust": "upthrust", "sos": "SOS"}
_HIS_NAME = {"spring": "spring", "upthrust": "upthrust", "sos": "SOS", "lps": "LPS", "former_lps": "former LPS",
             "span": "span", "mini": "mini"}
COUNTED = ("spring", "upthrust", "sos", "lps", "mini")


def _iso(day) -> str:
    return day.isoformat() if hasattr(day, "isoformat") else str(day)


def _trading_days_between(days: list, a: str, b: str) -> int:
    """Trading days from day a to day b on the frame (b after a: positive)."""
    iso = [_iso(d) for d in days]
    try:
        return iso.index(b) - iso.index(a)
    except ValueError:
        return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def event_agreement(row: dict) -> list:
    """One line per event he placed on this fix, read against the reader's words on the same bars: ``verdict`` is
    'agree', 'differ' or 'noted' (a span, and a former LPS, are his words: listed, never counted), ``words`` says
    what the reader named instead, ``days`` the stretch to print the bars of when they differ."""
    read = row.get("read")
    his_events = (row.get("setup") or {}).get("events") or []
    if not his_events:
        return []
    days = row["days"]
    unit = float(row["unit"])
    reader_events = list(getattr(read, "events", ()) or ())
    lps = getattr(read, "lps", None)
    minis = [b for b in (getattr(read, "boxes", ()) or ()) if getattr(b, "role", "") == "mini"]
    out = []
    for his in his_events:
        kind, first, last = his["kind"], str(his["first_day"]), str(his["last_day"])
        name = _HIS_NAME.get(kind, kind)
        line = {"kind": kind, "name": name, "his": his, "days": [first, last], "verdict": "noted", "words": ""}
        if kind in _READER_WORD:
            same = [e for e in reader_events if e.kind == _READER_WORD[kind]]
            hit = [e for e in same if first <= _iso(e.day) <= last]
            if hit:
                line.update(verdict="agree", words=f"the reader's {name} on {dt.date.fromisoformat(_iso(hit[0].day)):%d/%m} too")
            elif same:
                named = ", ".join(f"{dt.date.fromisoformat(_iso(e.day)):%d/%m} at {e.price:.2f}" for e in same)
                line.update(verdict="differ", words=f"the reader's {name} is on {named}")
            else:
                line.update(verdict="differ", words=f"the reader names no {name} on this box")
        elif kind == "lps":
            if lps is not None and _iso(lps.start_day) <= last and _iso(lps.end_day) >= first:
                line.update(verdict="agree", words=f"the reader's LPS {dt.date.fromisoformat(_iso(lps.start_day)):%d/%m} to "
                                                   f"{dt.date.fromisoformat(_iso(lps.end_day)):%d/%m} shares a day")
            elif lps is not None:
                line.update(verdict="differ", words=f"the reader's LPS is {dt.date.fromisoformat(_iso(lps.start_day)):%d/%m} to "
                                                    f"{dt.date.fromisoformat(_iso(lps.end_day)):%d/%m}")
            else:
                line.update(verdict="differ", words="the reader reads no LPS on this box")
        elif kind == "former_lps":
            if lps is None:
                line.update(words="the reader reads no LPS tonight")
            elif _iso(lps.start_day) > last:
                gap = _trading_days_between(days, last, _iso(lps.start_day))
                line.update(words=f"the entry was earlier: the reader's LPS begins {gap} trading days after your former LPS "
                                  f"ended ({dt.date.fromisoformat(_iso(lps.start_day)):%d/%m})", earlier_by=gap)
            else:
                line.update(words="the reader's LPS sits on your former LPS: it reads the earlier entry as tonight's")
        elif kind == "mini":
            hit = [b for b in minis if _iso(b.opened_day) <= last and (b.end_day is None or _iso(b.end_day) >= first)
                   and abs(float(b.resistance.price) - float(his["band_high"])) <= 0.5 * unit
                   and abs(float(b.support.price) - float(his["band_low"])) <= 0.5 * unit]
            if hit:
                line.update(verdict="agree", words=f"the reader's mini {hit[0].resistance.price:.2f} / {hit[0].support.price:.2f} too")
            elif minis:
                line.update(verdict="differ", words="the reader's mini is " + "; ".join(
                    f"{b.resistance.price:.2f} / {b.support.price:.2f} from {dt.date.fromisoformat(_iso(b.opened_day)):%d/%m}" for b in minis))
            else:
                line.update(verdict="differ", words="the reader shows no mini")
        else:                                     # a span: his word alone
            line.update(words=f'your word{": " + chr(34) + his["label"] + chr(34) if his.get("label") else ""}')
        out.append(line)
    return out


def _his_event_words(event: dict) -> str:
    first, last = str(event["first_day"]), str(event["last_day"])
    when = f"{dt.date.fromisoformat(first):%d/%m}" if first == last else f"{dt.date.fromisoformat(first):%d/%m}-{dt.date.fromisoformat(last):%d/%m}"
    if event["kind"] == "mini":
        return f"{when} {float(event['band_high']):.2f} / {float(event['band_low']):.2f}"
    return f"{when}{' at ' + format(float(event['price']), '.2f') if event.get('price') is not None else ''}"


def bars_words(row: dict, first: str, last: str, pad: int = 1) -> list:
    """The OHLC bars over a stretch of his days, one line each, with ``pad`` bars either side."""
    prepared, days = row["prepared"], row["days"]
    iso = [_iso(d) for d in days]
    lo = max(0, next((i for i, d in enumerate(iso) if d >= first), 0) - pad)
    hi = min(len(iso), next((i for i, d in enumerate(iso) if d > last), len(iso)) + pad)
    out = []
    for i in range(lo, hi):
        bar = prepared.iloc[i]
        out.append(f"{days[i]:%a %d/%m}  O {bar['Open']:.2f}  H {bar['High']:.2f}  L {bar['Low']:.2f}  C {bar['Close']:.2f}")
    return out


def format_events(rows: list) -> str:
    """The events block of the board: the count per kind, the former-LPS pattern, and every disagreement with
    its bars. Empty when no fix carries an event."""
    lined = [(r, event_agreement(r)) for r in rows if "refused" not in r and (r.get("setup") or {}).get("events")]
    if not lined:
        return ""
    counts = {k: [0, 0] for k in COUNTED}
    earlier, formers = [], 0
    for _, lines in lined:
        for line in lines:
            if line["kind"] in counts:
                counts[line["kind"]][1] += 1
                counts[line["kind"]][0] += line["verdict"] == "agree"
            elif line["kind"] == "former_lps":
                formers += 1
                if line.get("earlier_by") is not None:
                    earlier.append(line["earlier_by"])
    out = ["", f"  HIS EVENTS on {len(lined)} fixes: " + " · ".join(
        f"{_HIS_NAME[k]} {a}/{n}" for k, (a, n) in counts.items() if n)
           + (f"  (agree/placed)" if any(n for _, n in counts.values()) else "")]
    if formers:
        out.append(f"  former LPS placed {formers}: the entry was earlier on {len(earlier)}"
                   + (f" (the reader's LPS {min(earlier)}-{max(earlier)} trading days after it)" if earlier else ""))
    out.append("")
    out.append("  each fix's events: his · the reader's words; the bars under every disagreement")
    for row, lines in lined:
        for line in lines:
            tag = {"agree": "agree ", "differ": "DIFFER", "noted": "noted "}[line["verdict"]]
            out.append(f"  {row['key']:<22}{tag}  {line['name']} {_his_event_words(line['his'])} · {line['words']}")
            if line["verdict"] == "differ":
                out.extend(f"{'':<31}{bar}" for bar in bars_words(row, *line["days"]))
    return "\n".join(out)


def cached_bars(tickers: list) -> dict:
    """The US-Stocks parquet cache, read-only, one frame per ticker (missing tickers are left out)."""
    if not tickers:
        return {}
    path, _ = default_universe().cache_paths()
    wanted = sorted(set(tickers))
    import pyarrow.parquet as pq  # noqa: PLC0415
    have = set(pq.ParquetFile(path).schema.names)
    cols = [f"('{t}', '{c}')" for t in wanted for c in _OHLCV if f"('{t}', '{c}')" in have]
    if not cols:
        return {}
    big = pd.read_parquet(path, columns=cols)
    out = {}
    for t in wanted:
        if t in big.columns.get_level_values(0):
            frame = big[t].dropna(how="all")
            if len(frame):
                out[t] = frame
    return out


def fix_rows(fixes: list) -> list:
    """Every fix read by the walk board on its own bars: a row per fix, or a refusal in words."""
    frames = cached_bars([f["ticker"] for f in fixes])
    rows = []
    for fix in fixes:
        setup = fix_setup(fix)
        raw = frames.get(fix["ticker"])
        if raw is None:
            rows.append({"key": setup_key(setup), "refused": "no bars in the cache"})
            continue
        try:
            row = walk_board.score_setup(setup, raw)
        except (ValueError, KeyError) as exc:
            rows.append({"key": setup_key(setup), "refused": f"his anchor day is not a bar of the frame ({exc})"})
            continue
        row["population"] = "fix"
        row["setup"] = setup
        rows.append(row)
    return rows


def sealed_rows() -> list:
    frames, _ = load_sealed_fixture()
    setups = load_corpus()
    rows = []
    for s in setups:
        row = walk_board.score_setup(s, fixture_frame(frames, setup_key(s), s["ticker"]))
        row["population"] = "sealed"
        row["setup"] = s
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def format_board(rows: list, refused: list) -> str:
    read = [r for r in rows if "refused" not in r]
    sealed = [r for r in read if r["population"] == "sealed"]
    fixes = [r for r in read if r["population"] == "fix"]
    out = [f"THE BOX GAP — his pair against the reader's on {len(read)} drawings ({len(sealed)} sealed, "
           f"{len(fixes)} lens fixes{', ' + str(len(refused)) + ' fixes not read' if refused else ''})", ""]
    counts = Counter(r["verdict"] for r in read)
    out.append("  THE READER'S BOX: " + " · ".join(f"{v} {counts.get(v, 0)}" for v in walk_board.VERDICTS)
               + f"  (of {len(read)})")
    causes = Counter(cause(r) for r in read)
    agree = sum(causes[c] for c in AGREE)
    out.append(f"  agree {agree} · differ {len(read) - agree}, by cause:")
    for name, n in sorted(((c, n) for c, n in causes.items() if c not in AGREE), key=lambda x: (-x[1], x[0])):
        who = ", ".join(r["key"] for r in read if cause(r) == name)
        out.append(f"    {n:>3}  {name}  ({who})")
    named = [f"{t} {next((r['verdict'] for r in read if r['ticker'] == t), 'not drawn')}" for t in NAMED]
    out.append("  named charts: " + " · ".join(named))
    if fixes:
        moved = sum(1 for r in fixes if r["setup"]["reader_then"]["R"] is not None and (
            abs(r["setup"]["reader_then"]["R"] - (r["box"].R if r["box"] else float("nan"))) >= 0.005
            or abs(r["setup"]["reader_then"]["S"] - (r["box"].S if r["box"] else float("nan"))) >= 0.005))
        out.append(f"  the fixes: the reader's box tonight differs from the one he fixed on {moved} of {len(fixes)}"
                   " (a rule has moved since, or the bars have)")
    out.append("")
    out.append("  each differing drawing: the box · the cause · which was a box first · where the box differs")
    for row in sorted(read, key=lambda r: (cause(r), r["key"])):
        if cause(row) in AGREE:
            continue
        born = _born_first(row)
        out.append(f"  {row['key']:<22}{row['verdict']:<7}{cause(row)}" + (f" · {born}" if born else ""))
        out.append(f"{'':<31}{walk_board._difference(row)}")
    for r in refused:
        out.append(f"  {r['key']:<22}not read: {r['refused']}")
    return "\n".join(out)


def differing(rows: list) -> list:
    return [r for r in rows if "refused" not in r and cause(r) not in AGREE]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", metavar="DIR", help="also write one OHLC page per differing drawing and a contact sheet")
    ap.add_argument("--fixes-only", action="store_true", help="read the lens fixes alone, not the sealed drawings")
    ap.add_argument("--db", metavar="PATH", help="the journal to read the fixes from, read-only (default: this checkout's; "
                                                 "a worktree has a scratch journal of its own, so name the live one)")
    args = ap.parse_args()
    if args.pages:
        refuse_sealed_output(args.pages)
    rows = [] if args.fixes_only else sealed_rows()
    rows += fix_rows(load_fixes(args.db))
    refused = [r for r in rows if "refused" in r]
    print(format_board(rows, refused))
    events = format_events(rows)
    if events:
        print(events)
    if args.pages:
        diff = differing(rows)
        pages = walk_board.render_pages(diff, {r["key"]: r["setup"] for r in diff}, args.pages)
        sheet = walk_board.write_contact_sheet(diff, pages, args.pages)
        print(f"\n{len(pages)} pages and the contact sheet written to {sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
