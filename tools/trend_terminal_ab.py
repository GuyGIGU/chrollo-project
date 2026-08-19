"""Trend-terminal box gate A/B — which boxes the dark flag removes, TODAY.

``TREND_TERMINAL_BOX_GATE_ENABLED`` (dark, kill-by 2026-08-31) refuses a box
that OPENS before the trend running into it printed its climax, unless
``MIN_BASE_DAYS`` bars have printed since that climax. Operator ruling
2026-07-27 (LIVN): *"We can't start the anchor from the opposite direction of
the trend if we are still inside that trend"* + *"way too young"*.

The flip is blocked on ONE thing: the operator's eyeball of the boxes it
deletes. The 2026-07-27 evidence sheet (`tools/fidelity/full_package/LOSSES.md`,
39 losses) was hand-built with no committed instrument, so it could not be
re-measured — and the rule it documents is a MATURITY rule, which means its loss
set decays with the calendar: every one of those 39 losses opened 2026-06-03..
07-07 with 5-19 bars since its climax, and a box only has to wait to become
legal. An eyeball sheet for a self-healing rule has a shelf life. This is that
sheet's missing instrument.

WHAT IT MEASURES. Per name: ``read_structure`` on the faithful live frame with
the gate OFF and ON, diffing the ELECTED BOX IDENTITY (start bar, R, S) — the
same identity the rail-margin campaign's accept-condition E diffs, because a
displaced election is a different read even when the fire count survives:

    identical  same box either way
    lost       elects OFF, abstains ON      <- the eyeball set
    moved      elects a DIFFERENT box ON    <- the gate is not supposed to do this
    gained     abstains OFF, elects ON      <- likewise

For every loss it reports the numbers the rule actually turns on: the covering
trend's terminal bar, ``bars since`` it (``len(df) - terminal``, the quantity
compared against ``MIN_BASE_DAYS``), and how far into the box the trend topped.
Overshoot magnitude is deliberately NOT reported: it is Tested-DEAD as a test
(falsified 3x, see docs/decisions.md) and printing it invites re-proposal.

FAITHFULNESS. Reuses ``ar_first_reaction_diff._prep_live`` — baseline filter ->
trim to ``DAILY_STRUCTURE_PERIOD`` -> ATR cols -> the ATR snapshot — so the
frame is the one ``_evaluate_ticker`` reads, never the untrimmed 5y frame (which
elects an older root). Flags move only through ``tools.replay.flag_capture``
(self-restoring; a leaked flag poisons every later row in the batch).

Read-only: reads the parquet cache and the payload artifact, writes nothing but
its own report. No network, no backend, nothing live imports it.

    python -m tools.trend_terminal_ab                  # the live payload's names
    python -m tools.trend_terminal_ab --json OUT.json  # also dump the rows
    python -m tools.trend_terminal_ab --universe       # every name in the cache
    python -m tools.trend_terminal_ab --jobs 1         # serial (debugging)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:                                  # invoked as a script
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path()

import pandas as pd                                          # noqa: E402

from config import settings                                  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash       # noqa: E402
from engine_alpha.structure.market_structure import (        # noqa: E402
    trend_terminal_floor,
)
from tools.ar_first_reaction_diff import _load_cache, _prep_live  # noqa: E402
from tools.replay import read_structure_under                # noqa: E402

_FLAG = "TREND_TERMINAL_BOX_GATE_ENABLED"
_PAYLOAD = os.path.join(_ROOT, "output", "screener_data.json")


def _identity(structure):
    """The elected box's identity: (start bar, R, S). ``None`` when the read
    abstains. Rounded because R/S are float rail prices — an identity compared
    on raw doubles reports phantom moves."""
    if structure is None or structure.box is None:
        return None
    box = structure.box
    return (int(box.start_bar), round(float(box.R), 4), round(float(box.S), 4))


def _capture(df, atr):
    """The elected box with the gate OFF and ON. Both reads go through
    flag_capture, so neither the flag's live value nor a crash mid-read can
    leak into the next name."""
    return {
        "off": read_structure_under(df, atr, {_FLAG: False}),
        "on": read_structure_under(df, atr, {_FLAG: True}),
    }


def _verdict(off_id, on_id):
    if off_id is None and on_id is None:
        return "no_read"
    if on_id is None:
        return "lost"
    if off_id is None:
        return "gained"
    return "identical" if off_id == on_id else "moved"


def _maturity(df, structure):
    """Why the gate refused this box, in the rule's own quantities.

    ``bars_since`` is ``len(df) - terminal`` — literally the expression
    ``trend_terminal_legal_open`` compares against ``MIN_BASE_DAYS``, and also
    the ``base_len`` the box would have if it started at the climax. A negative
    ``climax_at_box_bar`` would mean the trend topped BEFORE the box opened,
    which is legal by the first branch and should never appear on a loss row.
    """
    floor = trend_terminal_floor(df)
    start = int(structure.box.start_bar)
    if not (0 <= start < len(floor.bar)):
        return None
    term = int(floor.bar[start])
    if term < 0:
        return None                          # no covering segment: legal anyway
    out = {
        "terminal_bar": term,
        "terminal_date": str(df.index[term].date()) if term < len(df) else None,
        "bars_since": len(df) - term,
        "climax_at_box_bar": term - start,
    }
    # Where the claimed climax sits relative to the box's OWN ceiling, as a
    # fraction of box height. This is a diagnostic of the INPUT, not a candidate
    # gate: the operator's 2026-07-28 ruling found `segment_trends` box-blind —
    # every in-base rally above R prints another HH, so the "trend" never ends
    # and its terminal lands inside the base. A terminal sitting ON the box's own
    # R is that defect's fingerprint.
    #
    # NOT to be confused with overshoot MAGNITUDE as a rejection rule, which is
    # Tested-DEAD, falsified 3x (docs/decisions.md). That asks "did the trend run
    # too far past R to be legitimate?" This asks "is the thing we called a trend
    # climax actually just this base's own ceiling?" Different question, and only
    # the second one is about whether the reader's input is sound.
    price = float(floor.price[start]) if len(floor.price) > start else float("nan")
    height = float(structure.box.R) - float(structure.box.S)
    if price == price and height > 0:        # NaN-safe
        out["terminal_price"] = round(price, 4)
        out["terminal_vs_R_box_frac"] = round(
            (price - float(structure.box.R)) / height, 3)
    return out


def _row(ticker, df, reads):
    off, on = reads["off"], reads["on"]
    off_id, on_id = _identity(off), _identity(on)
    row = {
        "ticker": ticker,
        "verdict": _verdict(off_id, on_id),
        "off_box": off_id,
        "on_box": on_id,
    }
    if off is not None and off.box is not None:
        start = int(off.box.start_bar)
        row.update({
            "box_open": str(df.index[start].date()),
            "R": round(float(off.box.R), 4),
            "S": round(float(off.box.S), 4),
            "base_len": len(df) - start,
        })
        if row["verdict"] == "lost":
            row["why"] = _maturity(df, off)
    return row


def _work(args):
    """Pool worker (top-level for pickling): one name's off/on capture."""
    ticker, df, atr = args
    try:
        return _row(ticker, df, _capture(df, atr))
    except Exception as exc:                          # one bad name never kills the batch
        return {"ticker": ticker, "verdict": "error", "error": repr(exc)}


def _population(universe: bool, cache_level0):
    """The names to measure: the live payload's fired list (what the operator
    actually sees), or every ticker in the cache under --universe."""
    if universe:
        exclude = {getattr(settings, "MARKET_INDEX_SYMBOL", "SPY"), "SPY"}
        return sorted(t for t in cache_level0 if t not in exclude), "cache universe"
    with open(_PAYLOAD, encoding="utf-8") as fh:
        payload = json.load(fh)
    identity = payload.get("scan_identity") or {}
    return (list(payload.get("ordered_tickers") or []),
            f"payload {identity.get('scan_date')} "
            f"({(identity.get('engine_config_version') or '?')[:12]})")


def run(universe: bool, jobs: int):
    cache, level0 = _load_cache()
    tickers, basis = _population(universe, level0)
    print(f"  basis: {basis}; {len(tickers)} names; "
          f"manifest {manifest_hash()[:12]}", file=sys.stderr, flush=True)

    prepped = []
    for ticker in tickers:
        if ticker not in level0:
            continue
        try:
            df, atr = _prep_live(cache[ticker].dropna())
        except Exception:                             # malformed column -> skip
            continue
        if df is not None:
            prepped.append((ticker, df, atr))
    print(f"  {len(prepped)}/{len(tickers)} survive the baseline filters; "
          f"capturing off/on with jobs={jobs}", file=sys.stderr, flush=True)

    rows = []
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool:
            for i, row in enumerate(pool.imap_unordered(_work, prepped, chunksize=4)):
                if i and i % 50 == 0:
                    print(f"  ...{i}/{len(prepped)}", file=sys.stderr, flush=True)
                rows.append(row)
    else:
        for i, args in enumerate(prepped):
            if i and i % 50 == 0:
                print(f"  ...{i}/{len(prepped)}", file=sys.stderr, flush=True)
            rows.append(_work(args))
    rows.sort(key=lambda r: r["ticker"])
    return rows, basis


def report(rows, basis):
    counts = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    print(f"\n  TREND-TERMINAL BOX GATE A/B — {basis}")
    print("  " + "-" * 62)
    for verdict in ("identical", "lost", "moved", "gained", "no_read", "error"):
        if counts.get(verdict):
            print(f"    {verdict:<10} {counts[verdict]:>4}")

    losses = [r for r in rows if r["verdict"] == "lost"]
    if not losses:
        print("\n  Nothing is removed on this basis — the gate is a no-op today.")
        return losses
    # Sorted by the number the rule turns on, so the closest calls read first.
    losses.sort(key=lambda r: (r.get("why") or {}).get("bars_since", 10**6))
    print(f"\n  the {len(losses)} losses, by post-climax maturity "
          f"(the gate refuses below MIN_BASE_DAYS = {settings.MIN_BASE_DAYS})\n")
    print("  ticker   box open      R          S       base_len  trend climax  "
          "bars since  climax @ box-bar")
    print("  " + "-" * 94)
    for row in losses:
        why = row.get("why") or {}
        print(f"  {row['ticker']:<7}  {row.get('box_open', '?'):<12} "
              f"{row.get('R', 0):>9.2f}  {row.get('S', 0):>9.2f} "
              f"{row.get('base_len', 0):>9}  {why.get('terminal_date', '?'):<12} "
              f"{why.get('bars_since', '?'):>10}  {why.get('climax_at_box_bar', '?'):>15}")

    moved = [r for r in rows if r["verdict"] in ("moved", "gained")]
    if moved:
        # By construction, not a defect: filtering candidates lets a later legal
        # framing win the root instead of losing the whole story (bricks.py). The
        # 2026-07-27 run observed none and the sheet wrote that up as a property
        # of the gate — worth flagging loudly because a re-framed read is a
        # different OPINION, which needs its own eyeball, not just a removal.
        print(f"\n  !! {len(moved)} name(s) RE-FRAMED — a different legal box won "
              "the root:")
        for row in moved:
            print(f"     {row['ticker']:<7} {row['verdict']:<8} "
                  f"off={row['off_box']} on={row['on_box']}")
    return losses


# ------------------------------------------------------------------ sheet ----
# The eyeball sheet, GENERATED. Its predecessor (2026-07-27) was hand-written,
# so when the population moved on there was no way to refresh it and the ruling
# would have been taken on names that no longer lose.

_PREAMBLE = """`TREND_TERMINAL_BOX_GATE_ENABLED` (dark; kill-by 2026-08-31). The gate refuses a
box that OPENS before the trend running into it printed its climax, unless
`MIN_BASE_DAYS` bars have printed since that climax. Operator ruling 2026-07-27
(LIVN): *"We can't start the anchor from the opposite direction of the trend if
we are still inside that trend"* + *"way too young"*.

> **This is not an open eyeball. It was ruled DO-NOT-FLIP on 2026-07-28.** The
> operator read the three cheapest class-B falsifiers — IRMD, IART, CYRX — and
> ruled all three **KEEP**: the gate was wrong to remove them. Diagnosis:
> `segment_trends` is **box-blind**. Every in-base rally above R prints another
> HH, so the "uptrend" never ends, its terminal lands inside the base, and the
> maturity clock starts on the wrong bar. Verdict: *"It's not wrong; it's
> early."* **The unblock is 15-20 dated trend-end labels** from the operator,
> then fix `segment_trends`, then re-run this A/B — NOT a floor change, and NOT
> overshoot magnitude (Tested-DEAD, falsified 3x).
>
> ⚠ **Provenance:** that ruling has **no `decisions.md` row** and no trace in the
> repo — it was reconstructed on 2026-08-13 from an agent session memory, which
> is exactly why a what's-next board that same day mis-reported this flag as
> "blocked purely on your eye". Treat it as accurate but UNCONFIRMED until the
> operator signs a `decisions.md` row.

So this sheet's job is no longer *"should we flip?"*. It is **fresh evidence for
that diagnosis**, and the current cohort for when the labels land. Every PNG is
rendered with the gate **OFF** — the box as it exists today, the one the gate
would refuse.

> **The sheet has a shelf life, by construction.** The rule is a MATURITY rule:
> a box that is too young only has to wait. Re-measured 2026-08-13: **not one of
> the original 39 losses still loses** — the cohort turned over completely in 14
> sessions. Re-measure before ruling — `python -m tools.trend_terminal_ab`."""


def _class_split(losses, half):
    early = [r for r in losses if (r.get("why") or {}).get("climax_at_box_bar", 0) <= half]
    late = [r for r in losses if r not in early]
    return early, late


def _box_blind_line(rows):
    """The box-blind tell, counted — computed so it stays true on a re-run
    rather than being a sentence someone has to remember to update."""
    fracs = [(r.get("why") or {}).get("terminal_vs_R_box_frac") for r in rows]
    fracs = [f for f in fracs if f is not None]
    if not fracs:
        return ""
    above = [f for f in fracs if f > 0]
    fracs.sort()
    median = fracs[len(fracs) // 2]
    return (f"**{len(above)} of {len(fracs)} of these terminals sit ABOVE this "
            f"box's own R** (median {median:+.2f} box heights, range "
            f"{min(fracs):+.2f}..{max(fracs):+.2f}). A trend that ends outside "
            "the base prints its extreme outside the base; these do not.")


def _md_table(rows):
    out = ["| ticker | box open | R | S | base_len | trend climax | bars since | "
           "climax @ box-bar | terminal vs R |",
           "|---|---|---:|---:|---:|---|---:|---:|---:|"]
    for row in sorted(rows, key=lambda r: (r.get("why") or {}).get("bars_since", 0)):
        why = row.get("why") or {}
        frac = why.get("terminal_vs_R_box_frac")
        out.append(
            f"| {row['ticker']} | {row.get('box_open', '?')} | {row.get('R', 0):.2f} | "
            f"{row.get('S', 0):.2f} | {row.get('base_len', 0)} | "
            f"{why.get('terminal_date', '?')} | **{why.get('bars_since', '?')}** | "
            f"{why.get('climax_at_box_bar', '?')} | "
            f"{'—' if frac is None else format(frac, '+.2f')} |")
    return "\n".join(out)


def write_sheet(rows, basis, out_dir):
    """Write LOSSES.md + index.html for the render folder."""
    refuse_sealed_output(os.path.join(out_dir, "LOSSES.md"))
    os.makedirs(out_dir, exist_ok=True)
    counts = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    losses = [r for r in rows if r["verdict"] == "lost"]
    moved = [r for r in rows if r["verdict"] in ("moved", "gained")]
    half = int(settings.MIN_BASE_DAYS) // 2
    early, late = _class_split(losses, half)
    close = [r for r in losses
             if (r.get("why") or {}).get("bars_since", 0) >= settings.MIN_BASE_DAYS - 2]

    md = [f"# Trend-terminal box gate — the {len(losses)} boxes the flag removes",
          "",
          f"Measured against **{basis}**. Generated by "
          "`python -m tools.trend_terminal_ab --sheet` — never hand-written.",
          "", _PREAMBLE, "",
          "## A/B", "", "| | |", "|---|---|"]
    for verdict in ("identical", "lost", "moved", "gained", "no_read", "error"):
        if counts.get(verdict):
            md.append(f"| {verdict} | **{counts[verdict]}** |")
    md += ["",
           f"`MIN_BASE_DAYS` = {settings.MIN_BASE_DAYS}. **{len(close)} of the "
           f"{len(losses)} losses sit within 2 bars of that floor** — the constant "
           "is doing real work at its exact value.",
           "",
           "## Class A — the trend topped inside the box's first "
           f"{half} bars  (n={len(early)})",
           "",
           "The LIVN case, and the one the ruling was written for: price ran, "
           "topped, and the \"box\" is the reaction itself. Nothing here has had "
           "time to become a base.",
           "", _md_table(early), "",
           "## Class B — an upthrust inside a range that had already worked  "
           f"(n={len(late)})",
           "",
           "**The class the operator already ruled against the gate.** The "
           "question is whether an upthrust inside a range that has already "
           "worked restarts the clock on the base; the rule as written says yes "
           f"(the box must show {settings.MIN_BASE_DAYS} bars *after* the "
           "climax), and on 2026-07-28 he read three of these — IRMD, IART, "
           "CYRX — and said no: the base was there before the poke and is still "
           "there after it. Read the `terminal vs R` column as the box-blind "
           "tell — it is where the claimed trend climax sits relative to this "
           "box's OWN ceiling, in box heights. A terminal at or just above R is "
           "not a trend climax; it is this base's upthrust, mislabelled by a "
           "reader that cannot see the box.",
           "", _box_blind_line(late), "", _md_table(late), ""]

    if moved:
        md += ["## Moved — the gate DID re-frame a box", "",
               "The 2026-07-27 sheet stated *\"the gate never re-frames a box — "
               "it keeps it or refuses it\"* on a run that observed 0 moved. "
               "That is now falsified, and it is by construction: filtering "
               "candidates lets a *later legal framing win the root instead of "
               "losing the whole story* (`bricks.py`). Worth its own look — a "
               "re-framed read is a different opinion, not a removal.", "",
               "| ticker | box OFF (start, R, S) | box ON (start, R, S) |",
               "|---|---|---|"]
        for row in moved:
            md.append(f"| {row['ticker']} | `{row['off_box']}` | `{row['on_box']}` |")
        md.append("")

    md += ["## Re-run", "",
           "```", "python -m tools.trend_terminal_ab --sheet DIR",
           "python -m tools.full_package_render "
           + " ".join(r["ticker"] for r in losses + moved) + " --out DIR",
           "```", ""]
    md_path = os.path.join(out_dir, "LOSSES.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    cards = []
    for row in losses + moved:
        why = row.get("why") or {}
        klass = "moved" if row["verdict"] != "lost" else (
            "A" if row in early else "B")
        cards.append(
            f'<section id="{row["ticker"]}"><h2>{row["ticker"]}'
            f'<span class="k k{klass}">class {klass}</span></h2>'
            f'<p class="meta">box {row.get("box_open", "?")} · '
            f'R {row.get("R", 0):.2f} / S {row.get("S", 0):.2f} · '
            f'base_len {row.get("base_len", 0)} · climax '
            f'{why.get("terminal_date", "?")} · <b>{why.get("bars_since", "?")} '
            f'bars since</b> · climax at box-bar '
            f'{why.get("climax_at_box_bar", "?")}</p>'
            f'<img src="{row["ticker"]}.png" alt="{row["ticker"]}" loading="lazy">'
            "</section>")
    nav = " ".join(f'<a href="#{r["ticker"]}">{r["ticker"]}</a>'
                   for r in losses + moved)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Trend-terminal box gate — {len(losses)} losses</title>
<style>
:root {{ color-scheme: dark; }}
body {{ margin:0; padding:24px 28px; background:#0f1115; color:#e6e8ec;
       font:14px/1.55 "Segoe UI",system-ui,sans-serif; }}
h1 {{ font-size:21px; margin:0 0 4px; }}
.sub {{ color:#9aa0aa; margin:0 0 16px; max-width:1100px; }}
nav {{ position:sticky; top:0; z-index:9; background:#0f1115; padding:10px 0 12px;
      border-bottom:1px solid #262b34; margin-bottom:22px; }}
nav a {{ display:inline-block; margin:2px 6px 2px 0; padding:3px 8px; border-radius:4px;
        background:#1a1e26; color:#9fc7ff; text-decoration:none; font-size:12px;
        font-family:ui-monospace,Consolas,monospace; }}
section {{ margin:0 0 36px; }}
h2 {{ font-size:17px; margin:0 0 2px; scroll-margin-top:78px; }}
.k {{ font-size:11px; margin-left:10px; padding:2px 7px; border-radius:10px;
     background:#1a1e26; color:#9aa0aa; font-weight:400; }}
.kB {{ background:#3a2a1a; color:#ffc98a; }}
.kmoved {{ background:#2a1a3a; color:#d0a8ff; }}
.meta {{ color:#9aa0aa; font-size:12.5px; margin:0 0 8px;
        font-family:ui-monospace,Consolas,monospace; }}
img {{ width:100%; border:1px solid #262b34; border-radius:6px; background:#fff; }}
</style></head><body>
<h1>Trend-terminal box gate — the {len(losses)} boxes the flag removes</h1>
<p class="sub">Measured against {basis}. Rendered gate-OFF: each chart is
the box as it exists today, the one the gate would refuse. <b>Class A</b> = the
trend topped inside the box's first {half} bars (the LIVN case).
<b>Class B</b> = an upthrust inside a range that had already worked (the
contested class). Full numbers in LOSSES.md.</p>
<nav>{nav}</nav>
{''.join(cards)}
</body></html>"""
    html_path = os.path.join(out_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return md_path, html_path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--universe", action="store_true",
                    help="measure every cache ticker instead of the payload's fires")
    ap.add_argument("--jobs", type=int,
                    default=max(1, (os.cpu_count() or 4) - 2),
                    help="worker processes (default: cores-2)")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the rows to this path")
    ap.add_argument("--from-json", default=None,
                    help="re-report/re-sheet a saved run instead of measuring again")
    ap.add_argument("--sheet", default=None,
                    help="write LOSSES.md + index.html for the render folder")
    args = ap.parse_args()

    if args.from_json:
        with open(args.from_json, encoding="utf-8") as fh:
            saved = json.load(fh)
        rows, basis = saved["rows"], saved["basis"]
    else:
        rows, basis = run(args.universe, args.jobs)
    losses = report(rows, basis)
    if args.json_out:
        with open(refuse_sealed_output(args.json_out), "w", encoding="utf-8") as fh:
            json.dump({
                "basis": basis,
                "flag": _FLAG,
                "manifest": manifest_hash(),
                "min_base_days": int(settings.MIN_BASE_DAYS),
                "rows": rows,
            }, fh, indent=1)
        print(f"\n  wrote {args.json_out} ({len(rows)} rows, {len(losses)} losses)")
    if args.sheet:
        md_path, html_path = write_sheet(rows, basis, args.sheet)
        print(f"\n  wrote {md_path}\n  wrote {html_path}")
    print(f"\n  tickers for the render sheet:\n  "
          + " ".join(r["ticker"] for r in losses))


if __name__ == "__main__":
    main()
