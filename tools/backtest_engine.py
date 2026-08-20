"""Standalone-edge BACKTEST HARNESS — the event-study measuring stick.

Reads the LIVE setup archive (READ-ONLY) and measures the screener's STANDALONE
edge from the outcome columns the frozen engine + forward-return updater already
wrote. ADDITIVE: touches no engine math, no scoring, no schema.

What it reports:
  1. Sample composition + an HONEST maturity caveat (a young archive is
     underpowered; the report says so loudly).
  2. Screener-side edge — MFE/MAE + barrier-label distributions sliced by tier,
     setup_type, and horizon. MFE is the HEADLINE metric (realized R conflates the
     screener with the operator's discretionary exit).
  3. Null / base-rate model — screener-median MFE vs random same-count draws from
     the day's eligible universe, with a bootstrap CI. The eligible universe's
     outcomes are NOT stored, so this needs an injected universe_returns dataset;
     absent it, the harness REPORTS THE DATA DEPENDENCY (does not fabricate).
  4. IS/OOS split keyed on engine_config_version (degrades gracefully when the
     column is absent/single-valued — the current production state).
  5. Multiple-testing haircut (BH-FDR) over the per-slice null p-values.
  6. Missed-winners scorecard (reuses core.archive.missed_winners).

Usage:
    python -m tools.backtest_engine                 # full report, prod DB read-only
    python -m tools.backtest_engine --source screener   # unbiased (live) only
    python -m tools.backtest_engine --json out.json     # also dump structured JSON
    python -m tools.backtest_engine --db PATH           # point at a fixture DB

Read-only: never writes to the DB. Offline: never hits the network.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Optional

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.backtest_engine` and bare-script
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore

_PROJECT_ROOT = configure_path()

from core.archive.analyze import derive_outcomes, safe_rank_corr  # reused verbatim
from core.archive.missed_winners import (  # reused verbatim
    Engagement,
    EpisodeOutcome,
    summarize,
)
from core.backtest import edge_report, is_oos, null_model, stats
from core.backtest.loader import DEFAULT_DB_PATH, load_episodes
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE

# Outcome-maturity floors below which a number is "directional at best".
MATURE_MIN_N = 25          # mirrors analyze.EDGE_MIN_N
WIN_R_BAR = 2.0            # missed-winners winner bar (>= +2R MFE within 60d)

_LINES: list[str] = []


def _safe_print(text: str) -> None:
    """Print even on a legacy cp1252 console (the report is pure ASCII, but be
    defensive so a stray non-ASCII char never crashes the run)."""
    try:
        print(text)
    except UnicodeEncodeError:
        import sys
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def emit(line: str = "") -> None:
    _LINES.append(line)


def header(title: str) -> None:
    emit()
    emit("=" * 72)
    emit(f"  {title}")
    emit("=" * 72)


def subhdr(title: str) -> None:
    emit()
    emit(f"-- {title} " + "-" * max(0, 68 - len(title)))


def _pct(v, nd: int = 1) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v * 100:+.{nd}f}%"


def _f(v, nd: int = 3) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    return f"{v:.{nd}f}"


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — composition + maturity caveat
# ─────────────────────────────────────────────────────────────────────────────
def section_composition(df: pd.DataFrame, source: Optional[str] = None) -> dict:
    header("1. SAMPLE COMPOSITION & MATURITY CAVEAT")
    n = len(df)
    emit(f"Episodes (de-duplicated, one row per logical setup): {n}")
    if n == 0:
        emit("Archive is empty — nothing to measure.")
        return {"n": 0, "mature": False}

    by_source = df["source"].fillna("?").value_counts().to_dict() if "source" in df else {}
    by_tier = df["tier"].fillna("?").value_counts().to_dict() if "tier" in df else {}
    by_type = df["setup_type"].fillna("?").value_counts().to_dict() if "setup_type" in df else {}
    emit(f"By source:     {by_source}")
    emit(f"By tier:       {by_tier}")
    emit(f"By setup_type: {by_type}")
    if "scan_date" in df.columns:
        emit(f"Date range:    {df['scan_date'].min()} -> {df['scan_date'].max()}")

    def _cnt(col: str) -> int:
        return int(pd.to_numeric(df[col], errors="coerce").notna().sum()) if col in df else 0

    n_barrier = int(df["barrier_label"].notna().sum()) if "barrier_label" in df else 0
    n_elapsed = _cnt("mfe_to_date")
    n_mfe20 = _cnt("mfe_20d")
    n_mfe60 = _cnt("mfe_60d")
    n_fwd20 = _cnt("fwd_return_20d")
    n_fwd60 = _cnt("fwd_return_60d")
    emit()
    emit(f"Resolved barrier_label: {n_barrier}")
    emit(f"mfe_to_date present: {n_elapsed}  (elapsed-window headline; always-on)")
    emit(f"mfe_20d present: {n_mfe20}   mfe_60d present: {n_mfe60}  (fixed, maturing)")
    emit(f"fwd_return_20d present: {n_fwd20}   fwd_return_60d present: {n_fwd60}")

    subhdr("Maturity verdict")
    # The PRIMARY headline is the elapsed-window mfe_to_date on the unbiased LIVE
    # ('screener') subset — it is populated as soon as a setup has any forward bar,
    # so the report is never "stuck on no mature data". Seed/manual rows are a
    # hand-picked winners gallery; they are excluded from the headline and flagged.
    n_live_elapsed = 0
    if "source" in df.columns and "mfe_to_date" in df.columns:
        live = df[df["source"] == edge_report.UNBIASED_SOURCE]
        n_live_elapsed = int(pd.to_numeric(live["mfe_to_date"], errors="coerce").notna().sum())
    mature = n_live_elapsed >= MATURE_MIN_N
    emit("!  ELAPSED-WINDOW READ (window-agnostic; always-on).")
    emit("   The headline is the favorable excursion over WHATEVER forward window has")
    emit("   elapsed so far (capped at 60 bars), recomputed every run as the window")
    emit("   grows. It is a real edge TODAY; the fixed 20d/60d MFE are SECONDARY and")
    emit("   shown as they mature. Read it as DIRECTIONAL on a thin sample, sharper")
    emit("   as the archive ages.")
    if not mature:
        emit(f"   LIVE (source='{edge_report.UNBIASED_SOURCE}') mfe_to_date "
             f"n={n_live_elapsed} < {MATURE_MIN_N} -> headline edge is indicative only.")
    if n_elapsed > n_live_elapsed:
        emit(f"   !! {n_elapsed - n_live_elapsed} of {n_elapsed} mfe_to_date rows are"
             " SEED/MANUAL (a hand-picked winners gallery) — EXCLUDED from the")
        emit(f"      headline by construction (it is computed on source="
             f"'{edge_report.UNBIASED_SOURCE}' only).")
    # Provenance line — TRUE to what this run actually included (no false claim).
    if source is None:
        emit("   Composition above spans ALL sources; the HEADLINE edge is computed")
        emit(f"   on the unbiased source='{edge_report.UNBIASED_SOURCE}' subset only.")
    else:
        emit(f"   This run is filtered to source='{source}'.")
    return {"n": n, "mature": mature, "n_elapsed": n_elapsed,
            "n_live_elapsed": n_live_elapsed, "n_mfe20": n_mfe20,
            "n_barrier": n_barrier}


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — screener-side edge report (MFE headline)
# ─────────────────────────────────────────────────────────────────────────────
def _emit_edge_block(block: dict, indent: str = "  ") -> None:
    hcol = block.get("headline_mfe_col", edge_report.HEADLINE_MFE_COL)
    emit(f"{indent}n={block['n']}   headline {hcol} median: "
         f"{_pct(block.get('headline_mfe_median'))} (n={block.get('headline_mfe_n', 0)})")
    mfe = block.get("mfe", {})
    for col, d in mfe.items():
        if d["n"] == 0:
            continue
        emit(f"{indent}  {col}: median {_pct(d['median'])}  IQR [{_pct(d['q25'])},"
             f" {_pct(d['q75'])}]  max {_pct(d['max'])}  n={d['n']}")
    mae = block.get("mae", {})
    for col, d in mae.items():
        if d["n"] == 0:
            continue
        emit(f"{indent}  {col}: median {_pct(d['median'])}  worst {_pct(d['min'])}  n={d['n']}")
    bar = block.get("barrier", {})
    if bar.get("n_labelled"):
        sh = bar["shares"]
        emit(f"{indent}  barrier: win {_pct(sh.get('win'))} / loss {_pct(sh.get('loss'))}"
             f" / timeout {_pct(sh.get('timeout'))}  (n={bar['n_labelled']})")


def _emit_headline(h: dict) -> None:
    """Emit the bias-safe headline edge + its provenance flags."""
    emit(f"  basis: source='{h['source_basis']}'  unbiased={h['unbiased']}  "
         f"n_unbiased={h['n_unbiased']} of n_input={h['n_input']}")
    if h.get("contaminated_input"):
        emit("  !! input contained SEED/MANUAL rows — EXCLUDED from this headline by")
        emit("     construction (contaminated_input=True). They never enter THE edge.")
    bars = h.get("bars_to_date") or {}
    bar_ctx = f"  (avg {_f(bars.get('median'), 0)} forward bars elapsed)" if bars.get("n") else ""
    emit(f"  HEADLINE {h['headline_mfe_col']} median: {_pct(h.get('headline_mfe_median'))}"
         f"  (n={h.get('headline_mfe_n', 0)}){bar_ctx}")
    ab = h.get("abnormal") or {}
    if ab.get("n"):
        emit(f"  abnormal (excess vs SPY, same window) median: "
             f"{_pct(ab.get('median'))} (n={ab['n']})")
    sec = h.get("secondary_mfe", {})
    shown = [(c, d) for c, d in sec.items() if d.get("n")]
    if shown:
        emit("  secondary (fixed windows, shown as they mature):")
        for c, d in shown:
            emit(f"    {c}: median {_pct(d.get('median'))}  n={d['n']}")


def section_edge(df: pd.DataFrame, source: Optional[str] = None) -> dict:
    header("2. SCREENER-SIDE EDGE  (elapsed-window MFE = headline; realized R omitted)")
    emit("MFE = max favorable excursion: what the setup made available. The HEADLINE")
    emit("is the elapsed-window mfe_to_date on the unbiased source='screener' subset")
    emit("(always-on, never gated on a full 20/60 window). Realized R is omitted on")
    emit("purpose — the operator exits discretionarily, so realized R would conflate")
    emit("the screener with the human exit.")
    # In a default run the headline basis is 'screener'; an explicit --source run
    # reports its own basis (so a --source seed inspection is still honest).
    basis = source if source is not None else edge_report.UNBIASED_SOURCE
    report = edge_report.build_edge_report(df, source_basis=basis)

    subhdr("Headline edge (BIAS-SAFE)")
    _emit_headline(report["headline"])

    subhdr("Overall (descriptive — over the loaded frame, NOT the edge)")
    _emit_edge_block(report["overall"])

    subhdr("By tier")
    for tier in ["S", "A", "B", "C", "D"]:
        block = report["by_tier"].get(tier)
        if not block:
            continue
        emit(f"  tier {tier}:")
        _emit_edge_block(block, indent="    ")

    subhdr("By setup_type")
    for stype, block in report["by_setup_type"].items():
        emit(f"  {stype}:")
        _emit_edge_block(block, indent="    ")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — null / base-rate model
# ─────────────────────────────────────────────────────────────────────────────
def section_null(df: pd.DataFrame, universe_returns: Optional[pd.DataFrame],
                 metric_col: str, seed: int) -> dict:
    header("3. NULL / BASE-RATE MODEL  (screener MFE vs random same-count draws)")
    emit("Headline edge = median(screener MFE) − median(random-draw MFE), where")
    emit("each null draw picks, per scan day, the SAME COUNT of names the screener")
    emit("fired that day, uniformly at random from that day's eligible universe.")

    overall = null_model.run_null_model(
        df, universe_returns, metric_col=metric_col, seed=seed
    )
    per_slice: dict[str, dict] = {}
    if not overall.available:
        emit()
        emit("!  NULL MODEL NOT COMPUTED — data dependency:")
        for chunk in overall.reason.split(". "):
            if chunk.strip():
                emit(f"   {chunk.strip()}")
        emit()
        emit("   STATUS: machinery is BUILT and tested; it needs an injected")
        emit("   universe_returns dataset (per-name eligible-universe MFE by")
        emit("   scan_date). The orchestrator owns that universe fetch.")
        return {"overall": overall.as_dict(), "by_tier": {}, "p_values": {}}

    emit()
    emit(f"  metric: {overall.metric_col}   n_screener={overall.n_screener}")
    emit(f"  screener median MFE: {_pct(overall.screener_median)}")
    emit(f"  null     median MFE: {_pct(overall.null_median)}")
    emit(f"  EDGE: {_pct(overall.edge)}   "
         f"{int(overall.ci_level*100)}% CI [{_pct(overall.ci_low)}, {_pct(overall.ci_high)}]")
    emit(f"  permutation p-value: {_f(overall.p_value)}  (null draws={overall.n_draws})")

    p_values: dict[str, float] = {"overall": overall.p_value}
    if "tier" in df.columns:
        subhdr("By tier")
        for tier in sorted(df["tier"].dropna().unique(), key=str):
            sub = df[df["tier"] == tier]
            res = null_model.run_null_model(
                sub, universe_returns, metric_col=metric_col, seed=seed
            )
            per_slice[str(tier)] = res.as_dict()
            if res.available:
                emit(f"  tier {tier}: edge {_pct(res.edge)} "
                     f"CI [{_pct(res.ci_low)},{_pct(res.ci_high)}] p={_f(res.p_value)} "
                     f"(n={res.n_screener})")
                p_values[f"tier={tier}"] = res.p_value
            else:
                emit(f"  tier {tier}: not computed ({res.reason.split('.')[0]})")
    return {"overall": overall.as_dict(), "by_tier": per_slice, "p_values": p_values}


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — IS/OOS split
# ─────────────────────────────────────────────────────────────────────────────
def section_is_oos(df: pd.DataFrame) -> dict:
    header("4. IN-SAMPLE / OUT-OF-SAMPLE SPLIT  (keyed on engine_config_version)")
    split = is_oos.split_is_oos(df)
    if not split.available:
        emit()
        emit("!  No IS/OOS split available:")
        emit(f"   {split.reason}")
        return split.as_dict()

    emit(f"  config versions: {split.n_versions}")
    emit(f"  in-sample  versions={list(split.is_versions)}  n={len(split.is_index)}")
    emit(f"  out-sample version ={list(split.oos_versions)}  n={len(split.oos_index)}")
    hcol = edge_report.HEADLINE_MFE_COL
    for name, idx in (("IN-SAMPLE", split.is_index), ("OUT-OF-SAMPLE", split.oos_index)):
        sub = df.loc[list(idx)]
        d = edge_report.describe(sub[hcol]) if hcol in sub.columns else {"n": 0, "median": None}
        emit(f"  {name}: headline {hcol} median {_pct(d.get('median'))} (n={d.get('n', 0)})")
    return split.as_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Section 5 — abnormal return vs SPY
# ─────────────────────────────────────────────────────────────────────────────
def section_abnormal(df: pd.DataFrame, spy_col: Optional[str], metric_col: str) -> dict:
    header("5. ABNORMAL RETURN vs SPY  (setup MFE minus same-window SPY move)")
    emit("The screener fires in up and down tapes alike, so raw MFE conflates the")
    emit("setup with the market. Abnormal return subtracts the same-window SPY move")
    emit("per setup, isolating the setup-specific edge.")
    if spy_col is None or spy_col not in df.columns:
        emit()
        emit("!  NOT COMPUTED — data dependency:")
        emit("   The archive stores SPY CONTEXT flags (spy_trend, regime_spy_*) but")
        emit("   not the same-WINDOW SPY return per setup. Abnormal return needs a")
        emit(f"   per-row SPY-return column aligned to {metric_col}'s window (e.g.")
        emit("   'spy_20d'). The orchestrator owns that SPY price join (offline if")
        emit("   the SPY series is cached). Machinery is BUILT and tested:")
        emit("   core.backtest.stats.abnormal_return / abnormal_return_frame.")
        return {"available": False, "reason": "no per-row same-window SPY return column"}

    out = stats.abnormal_return_frame(df, metric_col, spy_col)
    emit()
    if out.get("reason"):
        emit(f"!  {out['reason']}")
    else:
        emit(f"  n={out['n']}   setup median {_pct(out['median_setup'])}   "
             f"SPY median {_pct(out['median_spy'])}")
        emit(f"  ABNORMAL (excess) median: {_pct(out['abnormal_median'])}")
    return {"available": out.get("reason") is None, **out}


# ─────────────────────────────────────────────────────────────────────────────
# Section 6 — multiple-testing haircut
# ─────────────────────────────────────────────────────────────────────────────
def section_haircut(p_values: dict[str, float]) -> dict:
    header("6. MULTIPLE-TESTING HAIRCUT  (Benjamini-Hochberg FDR)")
    clean = {k: v for k, v in p_values.items() if v is not None}
    if not clean:
        emit()
        emit("!  No p-values to correct — the null model wasn't computed (needs the")
        emit("   universe_returns dataset). Haircut activates once null p-values exist.")
        return {"entries": [], "computed": False}

    entries = stats.multiple_testing_haircut(clean, alpha=0.05, method="fdr_bh")
    emit()
    emit(f"  {len(clean)} slices tested. Raw p < 0.05 can be a fluke across many")
    emit("  slices; the adjusted p has survived an FDR haircut.")
    emit()
    emit(f"  {'slice':<18}{'raw_p':>9}{'adj_p':>9}  significant")
    emit("  " + "-" * 46)
    for e in entries:
        emit(f"  {e.label:<18}{_f(e.p_value):>9}{_f(e.p_adjusted):>9}  "
             f"{'YES' if e.significant else 'no'}")
    return {"entries": [vars(e) for e in entries], "computed": True}


# ─────────────────────────────────────────────────────────────────────────────
# Section 7 — missed-winners scorecard (reused module)
# ─────────────────────────────────────────────────────────────────────────────
def section_missed_winners(df: pd.DataFrame) -> dict:
    header("7. MISSED-WINNERS SCORECARD  (reuses core.archive.missed_winners)")
    emit(f"A winner = achievable R reached >= +{WIN_R_BAR}R within 60d (MFE-based")
    emit("r_multiple_60d). Engagement is unknown here (the journal join is the")
    emit("orchestrator's), so all matured winners bucket as NEVER_ENGAGED — i.e.")
    emit("this counts the engine's raw winner-find rate, not operator engagement.")

    outcomes = []
    for r in df.itertuples(index=False):
        rm = getattr(r, "r_multiple_60d", None)
        rm = float(rm) if rm is not None and not (isinstance(rm, float) and np.isnan(rm)) else None
        outcomes.append(EpisodeOutcome(
            ticker=str(getattr(r, "ticker", "")),
            first_seen=str(getattr(r, "scan_date", "")),
            tier=str(getattr(r, "tier", "")),
            score=getattr(r, "score", None),
            r_multiple_60d=rm,
            engagement=Engagement.NEVER_ENGAGED,
        ))
    scorecard = summarize(outcomes, min_r=WIN_R_BAR)
    emit()
    emit(f"  episodes total: {scorecard['episodes_total']}   "
         f"matured (60d R present): {scorecard['episodes_matured']}")
    emit(f"  winners (>= +{WIN_R_BAR}R within 60d): {scorecard['winners_total']}")
    if scorecard["missed_winners"]:
        emit("  top achievable winners:")
        for w in scorecard["missed_winners"][:10]:
            emit(f"    {w['ticker']:<8} {w['first_seen']}  tier {w['tier']}  "
                 f"R60={_f(w['r_multiple_60d'], 2)}")
    return scorecard


# ─────────────────────────────────────────────────────────────────────────────
# Section 8 — predictor sanity (reuses analyze helpers)
# ─────────────────────────────────────────────────────────────────────────────
def section_predictors(df: pd.DataFrame) -> None:
    header("8. PREDICTOR SANITY  (rank-corr vs MFE_20d; reuses analyze helpers)")
    enriched = derive_outcomes(df)  # adds barrier_win / durable_win
    target = "mfe_20d"
    if target not in df.columns or pd.to_numeric(df[target], errors="coerce").notna().sum() < 8:
        emit()
        emit(f"!  Too few matured {target} rows for rank correlations (need >= 8).")
        return
    feats = ["score", "box_width", "atr_ratio", "tightness_ratio",
             "lps_descent_frac", "trav_n_full_traversals"]
    rows = []
    for f in feats:
        if f in df.columns:
            c = safe_rank_corr(df[f], df[target])
            if c is not None:
                rows.append((f, c))
    if not rows:
        emit()
        emit("!  No feature had enough paired rows for a rank correlation.")
        return
    rows.sort(key=lambda x: abs(x[1]), reverse=True)
    emit()
    emit("  (directional only on this thin sample — not a verdict)")
    emit(f"  {'feature':<24}{'rank_r vs MFE_20d':>18}")
    for f, c in rows:
        emit(f"  {f:<24}{c:>+18.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────
def run(db_path: Optional[str] = None, source: Optional[str] = None,
        universe_returns: Optional[pd.DataFrame] = None,
        metric_col: str = "mfe_20d", seed: int = 1337,
        spy_col: Optional[str] = None,
        json_path: Optional[str] = None,
        universe_type: Optional[str] = DEFAULT_UNIVERSE_TYPE) -> dict:
    _LINES.clear()
    out = None
    if json_path:
        out = json_path if os.path.isabs(json_path) else os.path.join(_PROJECT_ROOT, json_path)
        refuse_sealed_output(out)   # pre-flight: fail before the expensive pass (EC-14)
    # Stock-only standalone-edge population by default: the ETF universes now
    # archive under source='screener' too, so pin universe_type to keep this
    # calibration ground truth uncontaminated (mirrors services/engine_edge.py).
    df = load_episodes(db_path=db_path, source=source, universe_type=universe_type)

    header("CHROLLO STANDALONE-EDGE BACKTEST HARNESS  (PRELIMINARY)")
    emit(f"DB: {db_path or DEFAULT_DB_PATH}  (read-only)")
    if source:
        emit(f"Filtered to source = '{source}'")

    comp = section_composition(df, source=source)
    if comp["n"] == 0:
        report = "\n".join(_LINES)
        _safe_print(report)
        return {"composition": comp}

    edge = section_edge(df, source=source)
    # The null model treats its frame as the screener-fired set; on a default
    # (unfiltered) run, restrict it to the unbiased source so a future injected
    # universe_returns can't quote a seed/manual-contaminated edge (mirrors
    # section_edge's source_basis — bias-safe by construction here too).
    null_df = df if source is not None else (
        df[df["source"] == edge_report.UNBIASED_SOURCE] if "source" in df.columns else df
    )
    null_res = section_null(null_df, universe_returns, metric_col, seed)
    split = section_is_oos(df)
    abnormal = section_abnormal(df, spy_col, metric_col)
    haircut = section_haircut(null_res.get("p_values", {}))
    missed = section_missed_winners(df)
    section_predictors(df)

    header("END OF PRELIMINARY REPORT")
    report = "\n".join(_LINES)
    _safe_print(report)

    structured = {
        "composition": comp, "edge": edge, "null_model": null_res,
        "is_oos": split, "abnormal_vs_spy": abnormal,
        "haircut": haircut, "missed_winners": missed,
    }
    if json_path:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(structured, f, indent=2, default=str)
        print(f"\n[structured report written to {out}]")
    return structured


def main() -> None:
    ap = argparse.ArgumentParser(description="Chrollo standalone-edge backtest harness.")
    ap.add_argument("--db", default=None, help="sqlite archive path (default: prod DB, read-only)")
    ap.add_argument("--source", default=None, help="restrict to source: screener / seed / manual")
    ap.add_argument("--metric", default="mfe_20d", help="MFE metric column for the null model")
    ap.add_argument("--seed", type=int, default=1337, help="RNG seed (determinism)")
    ap.add_argument("--spy-col", default=None,
                    help="per-row same-window SPY return column for abnormal return "
                         "(absent in the stock archive; supply once joined)")
    ap.add_argument("--universe", default=None,
                    help="parquet of (scan_date, ticker, mfe_20d) eligible-universe MFE — "
                         "activates the null / base-rate model (see tools.build_universe_returns)")
    ap.add_argument("--json", default=None, help="also write a structured JSON report here")
    args = ap.parse_args()
    universe_returns = None
    if args.universe:
        path = args.universe if os.path.isabs(args.universe) else os.path.join(_PROJECT_ROOT, args.universe)
        universe_returns = pd.read_parquet(path)
    run(db_path=args.db, source=args.source, metric_col=args.metric,
        seed=args.seed, spy_col=args.spy_col, json_path=args.json,
        universe_returns=universe_returns)


if __name__ == "__main__":
    main()
