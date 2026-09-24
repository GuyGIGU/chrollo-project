"""Power-Play ruling sheets — the census-to-operator surface (program Task 4).

The species census (`tools/research/power_play_census.py`) measures; THIS tool spends the
operator's attention. It reads the census sidecar, force-ranks the episodes by
species-informativeness, folds near-duplicates, caps the batch at a
ruling-session budget, renders each chosen episode AS-OF its own first legal
look (the chart the engine saw — never the aftermath), and writes one
keyboard-drivable page whose verdicts export machine-ingestibly, keyed VERBATIM
to the census row identity (ticker, climax, AR, clock, first legal look) plus
the run stamps — the `read_verdicts` keying discipline, no transcription seam.

THE SECTIONS (each asks ONE question; populations quoted, charted subset
capped — nothing silently dropped):

  S1  the wall's misfiles — `not_watched_clock` episodes whose census breakout
      (first close above the POLE PEAK) printed within days of the AR, plus the
      named anchors. A base contracting above resistance crosses its own pole peak
      MID-BASE by construction (MAN: wall says resolved 07-29; the operator's
      breakout was 08-13), so this cohort holds species members misfiled as
      "resolved". Ask: still a base at the look?
  S2  the clock's marginal catch — cascaded at the short clock, walled at the
      next one up. What shortening the clock BUYS. Ask: wanted species?
  S3  what the form admits (`elected_episode` at the short clock), weakest
      boundary cases first, LIVE rows leading. Ask: species or junk?
  S4  the best poles the form refuses (`no_election`), textbook-first — the
      expensive error class if the form is wrong. Ask: should it have admitted?
  S5  the latch (`elected_other`) — the watch elected an OLDER base while the
      fresh episode sat unread (the FTNT July precedent). Ask: which read?

HONESTY RULES (stated on the sheet itself): cards are as-of only — no forward
returns on cards (the aggregate tables carry them, complete horizons only);
every row is a shadow-clock counterfactual and says so; the census verdict is
the FIRST legal look only (an episode may elect later as the shelf matures);
a VOID census (tripwire) is refused outright — sheets are never built from it.

Read-only against the cache + sidecar; writes SHEETS.md + index.html + PNGs
under --out (sealed-output guarded, EC-14). Renders are cached by
engine_config_version — a re-run on the same stamp redraws nothing.

    python -m tools.research.power_play_sheets --census output/power_play_census_species.json
    python -m tools.research.power_play_sheets ... --cache "..\\Chrollo Project\\market_data_cache_5y.parquet"
    python -m tools.research.power_play_sheets ... --no-render      # selection + SHEETS.md only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

try:  # works under both `python -m tools.research.power_play_sheets` and `python tools/research/power_play_sheets.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output
_ROOT = configure_path()

import pandas as pd                                          # noqa: E402

from config import settings                                  # noqa: E402

_DEFAULT_CENSUS = os.path.join("output", "power_play_census_species.json")
_DEFAULT_OUT = os.path.join("output", "power_play_sheets")

# The census verdicts that mean "the cascade actually ran" (its CLOSED set).
_ELECTION = ("elected_episode", "elected_other", "no_election")

# The operator's own diagnosed names (program doc; ruling c029555) — pinned
# into S1 whenever the sidecar carries them, budget notwithstanding: the
# frozen fork evidence, made flesh.
_NAMED_ANCHORS = ("MAN", "FTNT", "HELE")

# The literature boundary the informativeness rank measures against
# (docs/minervini_oneil_canon.md): flag depth <= ~25%; the pole screen edge
# itself (params.pole_min_gain) is the FTNT/MAN species divide. Depth is also
# the book's own VALIDITY test — a 50-98% "flag" is a failed flag (the
# MRVL/ARM ruling), and on this cache those rows are reverse-split artifacts
# and penny wrecks, so book-valid rows outrank the rest in every section.
_DEPTH_BOOK = 0.25

# "LIVE" means actionable NOW: unresolved (no close above the pole peak yet)
# AND the first legal look sits within this many calendar days of the cache's
# last session. An unresolved 2024 episode is not live, it just never resolved.
_LIVE_CAL_DAYS = 45

# Bump to force a redraw of cached renders on layout changes (joins the
# engine_config_version in the render stamp).
_RENDER_REV = 3

# S1's fast-resolution tell: a census breakout within this many CALENDAR days
# of the AR is the drift-up signature (MAN: 5 days) — the shelf formed AT the
# highs and crossed the pole peak while still building.
_MISFILE_CAL_DAYS = 7

# Default ruling-session budget (the operator's "40 keystrokes").
_BUDGET = 40

# Per-section shares of the budget (normalized; S1 leads — it holds his names).
_SECTION_SHARE = {"S1": 10, "S2": 10, "S3": 8, "S4": 8, "S5": 4}

_SECTION_ASK = {
    "S1": "still a base at the look, or genuinely resolved?",
    "S2": "a wanted Power Play at its first look?",
    "S3": "species or junk?",
    "S4": "should the form have admitted this?",
    "S5": "old base right, or should the fresh episode win?",
}

_SECTION_TITLE = {
    "S1": "the wall's misfiles — resolved-by-pole-peak while still basing",
    "S2": "the clock's marginal catch — watched at the short clock only",
    "S3": "what the form admits — boundary cases first",
    "S4": "the best poles the form refuses",
    "S5": "the latch — an older base won the fresh episode's root",
}


# ---------------------------------------------------------------- loading ----

def load_sidecar(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    tripwire = doc.get("tripwire")
    if tripwire != "OK":
        raise ValueError(
            f"census run is VOID (tripwire: {tripwire!r}) — sheets are never "
            "built from a voided run; re-run the census first")
    return doc


def fold_episodes(rows):
    """(ticker, climax, ar) -> {clock: row} — the per-episode clock ladder."""
    episodes: dict = {}
    for row in rows:
        episodes.setdefault(
            (row["ticker"], row["climax"], row["ar"]), {})[row["clock"]] = row
    return episodes


def _watched(row):
    return row is not None and row.get("verdict") in _ELECTION


def _cal_days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


# ---------------------------------------------------------------- ranking ----

def boundary_key(row, pole_min=0.9):
    """Distance to the FTNT/MAN species boundary, ascending = most
    informative: height above the pole screen edge (the species divide
    itself — everything in the sidecar already cleared it) plus how far the
    flag overruns the book's depth limit."""
    return (float(row["pole_gain"]) - float(pole_min)
            + 2.0 * max(0.0, float(row["depth"]) - _DEPTH_BOOK))


def textbook_key(row):
    """Archetype-first, ascending: strongest pole, shallowest flag."""
    return (-float(row["pole_gain"]), float(row["depth"]))


def book_valid(row):
    """The book's own flag test: depth within the ~25% limit."""
    return float(row["depth"]) <= _DEPTH_BOOK


def _is_live(row, last_session):
    """Unresolved AND the look is recent — actionable now, not merely
    never-resolved."""
    if row.get("breakout") is not None or not row.get("first_legal_look"):
        return False
    return _cal_days(row["first_legal_look"], last_session) <= _LIVE_CAL_DAYS


# -------------------------------------------------------------- selection ----

def _card(section, ladder, row, chips, rank_note):
    return {
        "id": f"{row['ticker']}_{row['climax']}_c{row['clock']}",
        "section": section,
        "ticker": row["ticker"],
        "climax": row["climax"],
        "ar": row["ar"],
        "breakout": row.get("breakout"),
        "pole_gain": row["pole_gain"],
        "depth": row["depth"],
        "clock": row["clock"],
        "first_legal_look": row.get("first_legal_look"),
        "census_verdict": row["verdict"],
        "ladder": {str(c): ladder[c]["verdict"] for c in sorted(ladder)},
        "elected": row.get("elected"),
        "chips": chips,
        "rank_note": rank_note,
    }


def select_cards(doc, budget=_BUDGET):
    """The force-ranked, deduped, budget-capped card list + section metadata.

    Pure — no I/O, no rendering — so the battery can pin membership, ranking,
    dedup, and the no-silent-caps accounting without touching matplotlib."""
    clocks = sorted(int(c) for c in doc["params"]["clocks"])
    short = clocks[0]
    next_up = clocks[1] if len(clocks) > 1 else short
    pole_min = float(doc["params"].get("pole_min_gain", 0.9))
    episodes = fold_episodes(doc["rows"])

    def srow(ladder):
        return ladder.get(short)

    # Populations, per section (selection pools before ranking/capping).
    pools: dict[str, list] = {k: [] for k in _SECTION_SHARE}
    for ladder in episodes.values():
        r = srow(ladder)
        if r is None or r.get("first_legal_look") is None:
            continue                       # pending / absent: nothing to render
        v = r["verdict"]
        if v == "not_watched_clock":
            named = r["ticker"] in _NAMED_ANCHORS
            fast = (r.get("breakout") is not None
                    and _cal_days(r["ar"], r["breakout"]) <= _MISFILE_CAL_DAYS)
            if named or fast:
                pools["S1"].append((ladder, r, named))
            continue
        if v not in _ELECTION:
            continue                       # refused_universe: not a ruling row
        up = ladder.get(next_up)
        if up is not None and up.get("verdict") == "not_watched_clock":
            pools["S2"].append((ladder, r))
        if v == "elected_episode":
            pools["S3"].append((ladder, r))
        elif v == "no_election":
            pools["S4"].append((ladder, r))
        elif v == "elected_other":
            pools["S5"].append((ladder, r))

    # Rank each pool (most informative first). Book-valid rows (flag depth
    # within the book's limit) outrank the rest everywhere — the deep-"flag"
    # tail of this cache is reverse-split artifacts and failed flags, and the
    # operator's attention never leads with those.
    last_session = doc["cache_state"]["last_session"]
    pools["S1"].sort(key=lambda t: (not t[2], not book_valid(t[1]),
                                    boundary_key(t[1], pole_min)))
    pools["S2"].sort(key=lambda t: (not book_valid(t[1]),
                                    boundary_key(t[1], pole_min)))
    pools["S3"].sort(key=lambda t: (not book_valid(t[1]),
                                    not _is_live(t[1], last_session),
                                    boundary_key(t[1], pole_min)))
    pools["S4"].sort(key=lambda t: (not book_valid(t[1]), textbook_key(t[1])))
    pools["S5"].sort(key=lambda t: (not book_valid(t[1]),
                                    not _is_live(t[1], last_session),
                                    textbook_key(t[1])))

    # Budget: scale the shares, keep at least 1 per non-empty section.
    total_share = sum(_SECTION_SHARE.values())
    quotas = {k: max(1, round(budget * s / total_share)) if pools[k] else 0
              for k, s in _SECTION_SHARE.items()}

    cards, seen = [], set()
    sections = {}
    for key in ("S1", "S2", "S3", "S4", "S5"):
        taken = 0
        for entry in pools[key]:
            if taken >= quotas[key]:
                break
            ladder, row = entry[0], entry[1]
            ep_key = (row["ticker"], row["climax"])
            if ep_key in seen:
                continue                   # near-duplicate / cross-section fold
            seen.add(ep_key)
            chips = [key]
            if key == "S1" and entry[2]:
                chips.append("anchor")
            if _is_live(row, last_session):
                chips.append("LIVE")
            elif row.get("breakout") is None:
                chips.append("unresolved")
            if not book_valid(row):
                chips.append(f"depth>{_DEPTH_BOOK:.0%}")
            chips.append(f"clock {row['clock']} counterfactual")
            note = ("named anchor" if key == "S1" and entry[2] else
                    "boundary-ranked" if key in ("S1", "S2", "S3") else
                    "textbook-ranked")
            cards.append(_card(key, ladder, row, chips, note))
            taken += 1
        sections[key] = {
            "title": _SECTION_TITLE[key],
            "ask": _SECTION_ASK[key],
            "population": len(pools[key]),
            "book_valid": sum(1 for e in pools[key] if book_valid(e[1])),
            "charted": taken,
        }
    return {"cards": cards, "sections": sections,
            "clocks": clocks, "short_clock": short, "next_clock": next_up}


# ----------------------------------------------------------- aggregates ----

def forward_table(rows, clocks):
    """Median forward return + win rate per (clock, verdict), COMPLETE
    horizons only — the aggregate clock evidence the cards deliberately omit."""
    out = []
    for clock in sorted(clocks, reverse=True):
        for verdict in _ELECTION:
            for h in (10, 20):
                vals = sorted(
                    r[f"fwd_{h}"] for r in rows
                    if r["clock"] == clock and r["verdict"] == verdict
                    and r.get(f"fwd_{h}_complete") and r.get(f"fwd_{h}") is not None)
                if not vals:
                    continue
                out.append({
                    "clock": clock, "verdict": verdict, "horizon": h,
                    "n": len(vals),
                    "median": vals[len(vals) // 2],
                    "win_pct": round(100 * sum(1 for v in vals if v > 0) / len(vals)),
                })
    return out


# -------------------------------------------------------------- renders ----

def _draw_bars(ax, o, h, low, c):
    """OHLC bars, up teal / down red (the sibling render tools' idiom)."""
    n = len(c)
    tick = 0.34
    lw = 1.0 if n > 90 else 1.3
    for i in range(n):
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=lw, alpha=0.6, zorder=2)
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=lw, alpha=0.6, zorder=2)
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=lw, alpha=0.6, zorder=2)


def _pos(df, iso):
    """Exact positional index of an ISO date in the frame, or None."""
    ts = pd.Timestamp(iso)
    p = df.index.searchsorted(ts)
    if p < len(df) and df.index[p] == ts:
        return int(p)
    return None


def render_cards(cards, frames, out_dir, stamp, pole_window):
    """As-of PNG per card, cached by (engine_config_version, render rev).
    Returns the per-card image names (None where the frame is missing)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stamp = f"{stamp}#r{_RENDER_REV}"
    png_dir = os.path.join(out_dir, "png")
    os.makedirs(png_dir, exist_ok=True)
    stamp_path = os.path.join(png_dir, "renders.json")
    old_stamp = {}
    if os.path.exists(stamp_path):
        with open(stamp_path, encoding="utf-8") as fh:
            old_stamp = json.load(fh)
    new_stamp = {}

    for card in cards:
        name = card["id"] + ".png"
        out = os.path.join(png_dir, name)
        df = frames.get(card["ticker"])
        if df is None:
            card["img"] = None
            card["chips"].append("no cache frame")
            continue
        card["img"] = "png/" + name
        if old_stamp.get(name) == stamp and os.path.exists(out):
            new_stamp[name] = stamp
            continue                       # cached render, same config

        as_of_p = _pos(df, card["first_legal_look"])
        cx = _pos(df, card["climax"])
        arp = _pos(df, card["ar"])
        if as_of_p is None or cx is None or arp is None:
            card["img"] = None
            card["chips"].append("date not in frame")
            continue
        sl = df.iloc[:as_of_p + 1]
        start = max(0, cx - int(pole_window) - 3)
        win = sl.iloc[start:]
        o = win.get("Open", win["Close"]).to_numpy(dtype=float)
        h = win["High"].to_numpy(dtype=float)
        lo = win["Low"].to_numpy(dtype=float)
        c = win["Close"].to_numpy(dtype=float)
        vol = (win["Volume"].to_numpy(dtype=float)
               if "Volume" in win.columns else None)

        fig, (ax, vax) = plt.subplots(
            2, 1, figsize=(12.5, 6.4), sharex=True,
            gridspec_kw={"height_ratios": [4, 1], "hspace": 0.04})
        _draw_bars(ax, o, h, lo, c)

        def x(p):
            return p - start

        peak_high = float(df["High"].iloc[cx])
        ax.axhline(peak_high, color="#e0a030", ls=":", lw=1.1, alpha=0.85)
        ax.text(0.995, peak_high, "pole peak ", color="#e0a030",
                va="bottom", ha="right", fontsize=8,
                transform=ax.get_yaxis_transform())
        ax.scatter([x(cx)], [peak_high], marker="*", s=240, color="#e0a030",
                   edgecolor="white", linewidth=0.7, zorder=7)
        ar_low = float(df["Low"].iloc[arp])
        ax.scatter([x(arp)], [ar_low], marker="v", s=90, color="#8b5cf6",
                   edgecolor="white", linewidth=0.6, zorder=7)
        ax.annotate("AR", (x(arp), ar_low), textcoords="offset points",
                    xytext=(0, -11), ha="center", fontsize=8,
                    color="#8b5cf6", va="top")
        if card["breakout"]:
            bp = _pos(df, card["breakout"])
            if bp is not None and bp <= as_of_p:
                ax.axvline(x(bp), color="#e04848", ls="--", lw=1.0, alpha=0.6)
                ax.annotate("close > pole peak", (x(bp), peak_high),
                            textcoords="offset points", xytext=(3, 4),
                            fontsize=7.5, color="#e04848")
        elected = card.get("elected")
        if elected:
            op = _pos(df, elected["open"])
            if op is not None:
                ax.hlines([elected["R"], elected["S"]], x(op), len(win) - 1,
                          colors="#5b8aff", ls="--", lw=1.1, alpha=0.9)
                ax.text(len(win) - 1, elected["R"], " R", color="#5b8aff",
                        va="center", fontsize=8, fontweight="bold")
                ax.text(len(win) - 1, elected["S"], " S", color="#5b8aff",
                        va="center", fontsize=8, fontweight="bold")
        if vol is not None:
            vax.bar(range(len(win)), vol, width=0.7, color="#4a5568", alpha=0.8)
            vax.set_yticks([])
        vax.set_xlim(-1, len(win))
        step = max(1, len(win) // 8)
        ticks = list(range(0, len(win), step))
        vax.set_xticks(ticks)
        vax.set_xticklabels([str(win.index[t])[:10] for t in ticks],
                            rotation=30, ha="right", fontsize=7)
        ax.margins(y=0.08)
        ax.grid(True, alpha=0.12)
        ax.set_title(
            f"{card['ticker']} — as of {card['first_legal_look']} "
            f"(clock {card['clock']} first legal look) · "
            f"pole {card['pole_gain']:+.0%} / depth {card['depth']:.0%} · "
            f"{card['census_verdict']}",
            fontsize=11, fontweight="bold", loc="left")
        fig.subplots_adjust(left=0.06, right=0.985, top=0.92, bottom=0.14)
        fig.savefig(out, dpi=110)
        plt.close(fig)
        new_stamp[name] = stamp

    with open(stamp_path, "w", encoding="utf-8") as fh:
        json.dump(new_stamp, fh, indent=1)
    return cards


# ---------------------------------------------------------------- output ----

def _funnel_md(doc):
    lines = ["| clock | watch-able | not-watched | pending | refused | "
             "elected-ep | elected-other | no-elect |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for clock in doc["params"]["clocks"]:
        c = doc["per_clock"][str(clock)]
        watchable = (c["elected_episode"] + c["elected_other"]
                     + c["no_election"] + c["refused_universe"])
        lines.append(
            f"| {clock} | {watchable} | {c['not_watched_clock']} | "
            f"{c['pending']} | {c['refused_universe']} | "
            f"**{c['elected_episode']}** | {c['elected_other']} | "
            f"{c['no_election']} |")
    return "\n".join(lines)


def _fwd_md(fwd_rows):
    lines = ["| clock | verdict | horizon | n | median | win % |",
             "|---:|---|---:|---:|---:|---:|"]
    for r in fwd_rows:
        lines.append(
            f"| {r['clock']} | {r['verdict']} | {r['horizon']} | {r['n']} | "
            f"{r['median']:+.3f} | {r['win_pct']} |")
    return "\n".join(lines)


def write_sheet(doc, sel, out_dir, census_path, wall_clock):
    """SHEETS.md + index.html. Sealed-output guarded before anything writes."""
    md_path = refuse_sealed_output(os.path.join(out_dir, "SHEETS.md"))
    html_path = refuse_sealed_output(os.path.join(out_dir, "index.html"))
    os.makedirs(out_dir, exist_ok=True)

    cards = sel["cards"]
    manifest = doc["engine_config_version"]
    stamp12 = manifest[:12]
    asked = len(cards)
    fwd_rows = forward_table(doc["rows"], sel["clocks"])
    cache = doc["cache_state"]

    md = [
        "# Power-Play ruling sheets — the ruling loop (program Task 4)",
        "",
        f"Generated by `python -m tools.research.power_play_sheets` from "
        f"`{os.path.basename(census_path)}` — never hand-written. "
        f"manifest `{stamp12}` · marks `{doc['marks_fingerprint'][:12]}` · "
        f"cache {cache['tickers']} tickers through {cache['last_session']} · "
        f"census wall clock: {wall_clock or 'unrecorded'}.",
        "",
        "**Every row on every sheet is a shadow-clock counterfactual** — the "
        "live scan still reads the default clock; nothing here fired. The "
        "census verdict is the episode's FIRST legal look only: an episode "
        "refused at its first look may elect later as the shelf matures.",
        "",
        "**Cards are as-of only.** Each chart is truncated at that episode's "
        "own first legal look — the bars the engine saw, never the aftermath, "
        "and no forward returns ride the cards (rule the chart, not the "
        "outcome). The aggregate tables below carry the forward evidence, "
        "complete horizons only.",
        "",
        "## The funnel, per clock",
        "",
        _funnel_md(doc),
        "",
        "## Forward returns (complete horizons only, first-look verdicts)",
        "",
        _fwd_md(fwd_rows),
        "",
        "## The wall's known misfile (read before ruling S1)",
        "",
        "The census's breakout wall is the first close above the POLE PEAK "
        "(`ticker_episodes`). A base contracting above resistance crosses its own pole "
        "peak while the base is still building — MAN's July episode is filed "
        "`not_watched_clock` at EVERY clock by that definition (wall says "
        "resolved 2026-07-29; the operator's breakout was 2026-08-13). S1 "
        "exists to measure that misfile rate on real charts.",
        "",
    ]
    for key in ("S1", "S2", "S3", "S4", "S5"):
        meta = sel["sections"][key]
        md += [f"## {key} — {meta['title']}",
               "",
               f"Population {meta['population']} "
               f"({meta['book_valid']} pass the book's flag-depth test — those "
               f"lead the rank), charted {meta['charted']} (force-ranked; the "
               f"rest are NOT ruled, only counted). **Ask: {meta['ask']}**",
               ""]
        section_cards = [c for c in cards if c["section"] == key]
        if section_cards:
            md += ["| ticker | climax | AR | pole | depth | look (clock "
                   f"{sel['short_clock']}) | census verdict | chips |",
                   "|---|---|---|---:|---:|---|---|---|"]
            for c in section_cards:
                md.append(
                    f"| {c['ticker']} | {c['climax']} | {c['ar']} | "
                    f"{c['pole_gain']:+.0%} | {c['depth']:.0%} | "
                    f"{c['first_legal_look']} | {c['census_verdict']} | "
                    f"{' '.join(c['chips'])} |")
            md.append("")
    md += [
        "## Rulings banked / asked / unblocked",
        "",
        f"Rulings asked: **{asked}** (live tally on the page; verdicts export "
        "from the page keyed verbatim to the census row identity + this "
        "manifest — no transcription).",
        "",
        "What this batch unblocks: the CLOCK ruling (then the EC-8 cost bound "
        "measured by the scan's own ScanTimer at that clock, then the "
        "both-flags flip decision); S1 keeps measure the breakout-wall "
        "misfile rate (a species-form wall calibration); S2/S3 keeps supply "
        "dated climax/AR marks — the trend-end labels Task 11's "
        "`segment_trends` fix is blocked on. Certified must-fire marks still "
        "graduate per-mark, operator-confirmed, into `docs/marks/` (EC-9) — "
        "bulk sheet verdicts never write there.",
        "",
        "## Re-run",
        "",
        "```",
        "python -m tools.research.power_play_census --out output\\power_play_census_species.json",
        "python -m tools.research.power_play_sheets --census output\\power_play_census_species.json",
        "```",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(_page_html(doc, sel, wall_clock))
    return md_path, html_path


def _page_html(doc, sel, wall_clock):
    cards = sel["cards"]
    manifest = doc["engine_config_version"]
    stamp12 = manifest[:12]
    payload = {
        "tool": "power_play_sheets",
        "engine_config_version": manifest,
        "marks_fingerprint": doc["marks_fingerprint"],
        "census_last_session": doc["cache_state"]["last_session"],
    }
    sections_html = []
    for key in ("S1", "S2", "S3", "S4", "S5"):
        meta = sel["sections"][key]
        section_cards = [c for c in cards if c["section"] == key]
        if not section_cards:
            continue
        blocks = []
        for c in section_cards:
            chips = "".join(f'<span class="k">{ch}</span>' for ch in c["chips"])
            ladder = " · ".join(f"{cl}:{v}" for cl, v in c["ladder"].items())
            img = (f'<img src="{c["img"]}" loading="lazy" alt="{c["ticker"]}">'
                   if c.get("img") else '<p class="meta">no render</p>')
            blocks.append(f"""
<section class="card" id="{c['id']}" data-id="{c['id']}">
<h3>{c['ticker']} <span class="dt">{c['climax']} → {c['ar']}</span>{chips}</h3>
<p class="meta">pole {c['pole_gain']:+.0%} · depth {c['depth']:.0%} · look
{c['first_legal_look']} (clock {c['clock']}) · {c['census_verdict']} ·
ladder {ladder}</p>
{img}
<div class="verdict">
<button data-r="keep">KEEP (k)</button>
<button data-r="junk">JUNK (j)</button>
<button data-r="skip">SKIP (s)</button>
<span class="state"></span>
</div>
</section>""")
        sections_html.append(
            f'<h2>{key} — {meta["title"]}</h2>'
            f'<p class="sub">population {meta["population"]}, charted '
            f'{meta["charted"]}. <b>Ask: {meta["ask"]}</b></p>'
            + "".join(blocks))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Power-Play ruling sheets — {len(cards)} rulings asked</title>
<style>
:root {{ color-scheme: dark; }}
body {{ margin:0; padding:24px 28px; background:#0f1115; color:#e6e8ec;
       font:14px/1.55 "Segoe UI",system-ui,sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
h2 {{ font-size:16px; margin:30px 0 2px; }}
h3 {{ font-size:15px; margin:0 0 2px; scroll-margin-top:64px; }}
.sub {{ color:#9aa0aa; margin:0 0 14px; max-width:1100px; }}
.dt {{ color:#9aa0aa; font-size:12px; font-weight:400;
      font-family:ui-monospace,Consolas,monospace; }}
header {{ position:sticky; top:0; z-index:9; background:#0f1115;
         padding:8px 0 10px; border-bottom:1px solid #262b34;
         margin-bottom:14px; }}
.k {{ font-size:10.5px; margin-left:8px; padding:2px 7px; border-radius:10px;
     background:#1a1e26; color:#9aa0aa; font-weight:400; }}
.meta {{ color:#9aa0aa; font-size:12px; margin:0 0 6px;
        font-family:ui-monospace,Consolas,monospace; }}
.card {{ margin:0 0 30px; }}
.card.done {{ opacity:0.55; }}
img {{ width:100%; max-width:1150px; border:1px solid #262b34;
      border-radius:6px; background:#fff; display:block; }}
.verdict {{ margin:6px 0 0; }}
.verdict button {{ background:#1a1e26; color:#e6e8ec; border:1px solid #262b34;
                  border-radius:5px; padding:5px 14px; margin-right:8px;
                  cursor:pointer; font:12.5px "Segoe UI",sans-serif; }}
.verdict button.on {{ background:#2c3444; border-color:#5b8aff; }}
.state {{ color:#9fc7ff; font-size:12px; margin-left:6px;
         font-family:ui-monospace,Consolas,monospace; }}
#tally {{ color:#9fc7ff; font-family:ui-monospace,Consolas,monospace;
         font-size:13px; }}
#export {{ float:right; background:#1a2c1f; color:#9fdcae;
          border:1px solid #2c4434; border-radius:5px; padding:5px 14px;
          cursor:pointer; }}
.prov {{ color:#6b7280; font-size:11.5px;
        font-family:ui-monospace,Consolas,monospace; }}
</style></head><body>
<header>
<h1>Power-Play ruling sheets <button id="export">Export verdicts</button></h1>
<div id="tally"></div>
<div class="prov">manifest {stamp12} · marks {doc['marks_fingerprint'][:12]} ·
cache through {doc['cache_state']['last_session']} · census wall clock
{wall_clock or 'unrecorded'} · every row is a shadow-clock counterfactual ·
keys: k=keep j=junk s=skip &darr;/&uarr; move</div>
</header>
{''.join(sections_html)}
<script>
const CARDS = {json.dumps([{k: c[k] for k in (
    "id", "section", "ticker", "climax", "ar", "breakout", "clock",
    "first_legal_look", "census_verdict", "pole_gain", "depth")} for c in cards])};
const STAMP = {json.dumps(payload)};
const KEY = "pp_sheets_" + STAMP.engine_config_version.slice(0, 12);
// Storage can be unavailable (data: snapshots, locked-down browsers) — the
// session then lives in memory and the export still works; only persistence
// across a reload is lost.
function loadBank() {{
  try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }}
  catch (e) {{ return {{}}; }}
}}
function saveBank() {{
  try {{ localStorage.setItem(KEY, JSON.stringify(bank)); }} catch (e) {{}}
}}
let bank = loadBank();
const els = Array.from(document.querySelectorAll(".card"));
let cur = 0;
function paint() {{
  els.forEach((el) => {{
    const r = bank[el.dataset.id];
    el.classList.toggle("done", !!r);
    el.querySelectorAll("button").forEach(
      (b) => b.classList.toggle("on", b.dataset.r === r));
    el.querySelector(".state").textContent = r ? r.toUpperCase() : "";
  }});
  const n = Object.keys(bank).length;
  document.getElementById("tally").textContent =
    "banked " + n + " / asked " + CARDS.length;
}}
function rule(el, r) {{
  bank[el.dataset.id] = r;
  saveBank();
  paint();
  const i = els.indexOf(el);
  if (i >= 0 && i + 1 < els.length) {{
    cur = i + 1;
    els[cur].scrollIntoView({{behavior: "smooth", block: "start"}});
  }}
}}
els.forEach((el) => el.querySelectorAll(".verdict button").forEach(
  (b) => b.addEventListener("click", () => rule(el, b.dataset.r))));
document.addEventListener("keydown", (e) => {{
  if (e.target.tagName === "INPUT") return;
  const map = {{k: "keep", j: "junk", s: "skip"}};
  if (map[e.key]) {{ rule(els[cur], map[e.key]); e.preventDefault(); }}
  if (e.key === "ArrowDown" && cur + 1 < els.length) {{
    els[++cur].scrollIntoView({{block: "start"}}); e.preventDefault(); }}
  if (e.key === "ArrowUp" && cur > 0) {{
    els[--cur].scrollIntoView({{block: "start"}}); e.preventDefault(); }}
}});
document.getElementById("export").addEventListener("click", () => {{
  const verdicts = CARDS.filter((c) => bank[c.id]).map(
    (c) => Object.assign({{}}, c, {{ruling: bank[c.id]}}));
  const out = Object.assign({{}}, STAMP,
    {{exported_at: new Date().toISOString(), verdicts: verdicts}});
  const text = JSON.stringify(out, null, 1);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], {{type: "application/json"}}));
  a.download = "power_play_verdicts_" +
    new Date().toISOString().slice(0, 10) + ".json";
  a.click();
  if (navigator.clipboard) navigator.clipboard.writeText(text);
}});
paint();
</script>
</body></html>"""


# ------------------------------------------------------------------ main ----

def _load_frames(cache, tickers):
    path = cache or settings.CACHE_FILENAME
    data = pd.read_parquet(path, engine=settings.PARQUET_ENGINE)
    level0 = set(data.columns.get_level_values(0))
    return {t: data[t].dropna() for t in tickers if t in level0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--census", default=_DEFAULT_CENSUS,
                    help="census sidecar JSON (the species run)")
    ap.add_argument("--out", default=_DEFAULT_OUT,
                    help="sheet output dir (SHEETS.md + index.html + png/)")
    ap.add_argument("--cache", default=None,
                    help="parquet cache path (default: settings.CACHE_FILENAME)")
    ap.add_argument("--budget", type=int, default=_BUDGET,
                    help="ruling-session budget (cards asked)")
    ap.add_argument("--no-render", action="store_true",
                    help="selection + SHEETS.md only; skip the PNGs")
    ap.add_argument("--wall-clock", default=None,
                    help="the census run's measured wall clock, quoted on the "
                         "sheet (e.g. \"48 min, 2026-08-18 10:09->10:56\")")
    args = ap.parse_args(argv)

    refuse_sealed_output(os.path.join(args.out, "SHEETS.md"))   # pre-flight
    doc = load_sidecar(args.census)
    sel = select_cards(doc, args.budget)
    print(f"  {len(sel['cards'])} cards selected "
          f"(budget {args.budget}); sections: "
          + ", ".join(f"{k} {m['charted']}/{m['population']}"
                      for k, m in sel["sections"].items()), file=sys.stderr)

    if not args.no_render:
        frames = _load_frames(args.cache, {c["ticker"] for c in sel["cards"]})
        render_cards(sel["cards"], frames, args.out,
                     doc["engine_config_version"],
                     doc["params"]["pole_window_bars"])
    else:
        for card in sel["cards"]:
            card["img"] = None

    md_path, html_path = write_sheet(doc, sel, args.out, args.census,
                                     args.wall_clock)
    print(f"  wrote {md_path}\n  wrote {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
