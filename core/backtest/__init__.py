"""Standalone-edge backtest harness (Phase 1 Track G).

An ADDITIVE, read-only event-study layer that measures the screener's STANDALONE
edge from the outcome columns already stored in the setup archive. It touches no
engine math, no scoring, no archive schema — it only READS what the frozen engine
+ the forward-return updater have already written.

Design (why this is honest, not a winners gallery):

  * MFE is the HEADLINE edge metric (not realized R). The operator manages exits
    discretionarily, so realized R conflates the screener with the human exit;
    MFE ("what the setup made available") isolates the screener's contribution.
  * Every analysis runs on EPISODE-COLLAPSED rows (one row per logical setup, via
    ``core.archive.episodes.build_episodes``). A persisting base re-flagged for 15
    days is ONE event, not 15 — counting continuations would badly inflate edge.
  * The null / base-rate machinery consumes an INJECTABLE ``universe_returns``
    dataset. The archive records FIRING setups only (no denominator), and the
    eligible universe's outcomes are not stored, so the harness never fabricates a
    baseline — it asks the caller for one and reports honestly when it is absent.
  * Read-only against the production DB (sqlite ``mode=ro`` URI). Unit tests build
    a small in-memory fixture archive; the production DB is never mutated.

Modules:
  loader      — read-only archive load + episode collapse to canonical rows
  edge_report — MFE/MAE + barrier-label distributions sliced by tier/type/horizon
  null_model  — random same-count draws + bootstrap CI on the MFE edge
  stats       — multiple-testing haircut (BH-FDR / Bonferroni) + abnormal-vs-SPY
  is_oos      — IS/OOS split keyed on engine_config_version (graceful if absent)
  deflated_sharpe, event_study, exit_sim — the signal-edge rigor layer; only
                tools/research/backtest_* import them, production never does
"""
from __future__ import annotations

__all__ = ["loader", "edge_report", "null_model", "stats", "is_oos"]
