"""No live Python may name a module the 2026-09 domain refactor moved.

The refactor moved the engine's structure modules into subpackages, the
pipeline into screening/market_data/universe/context/telemetry, and the backend
routers and services into domains/ and app/; the dashboard writer left output/
for core/pipeline/screening/. An import of an old name fails only
when its line runs (lazy imports hide from every boot check), and an old name in
a "keep in sync" comment sends the next reader to a file that is gone. The
modules that became packages of the same name (structure.lps, .narrative,
.metrics and pipeline.universe) are still valid names and are not listed; the
double-rewrite forms that broke them are.

Names are built by concatenation so this guard's own source never matches.
"""
import os
import re
from pathlib import Path

from _paths import REPO_ROOT as ROOT

_STRUCTURE = "engine_alpha." + "structure."
_PIPELINE = "core." + "pipeline."
_OLD_ENGINE_AND_PIPELINE = [_STRUCTURE + tail for tail in (
    "box_events", "box_gates", "box_primitives", "box_trace", "bricks", "chain",
    "consolidation", "displacement", "event_map", "event_vocabulary",
    "gate_margins", "htf", "indicators", "inner_box", "market_structure",
    "near_miss", "phase_a", "phase_d", "phase_features", "pivots", "power_play",
    "rail_qualification", "scope", "segmentation", "strategy_read", "trace_export",
)] + [_PIPELINE + tail for tail in (
    "cache", "cache_status", "candles", "data_freshness", "downloads",
    "fetch_health", "file_lock", "health_board", "market_calendar",
    "market_context", "market_data_health", "providers", "rate_limit",
    "scan_job", "scan_metrics", "screener", "ticker_admission", "tickers",
)]
_OLD_BACKEND = [("routers." + tail) for tail in (
    "analytics", "archive", "archive_actions", "archive_browse",
    "archive_calibration", "archive_reviews", "archive_schemas", "calibration",
    "candles", "engine_edge", "ibkr", "journal", "market_data", "portfolio",
    "portfolio_streams", "prices", "screener", "tags", "trade_risk", "trades",
    "watchlist",
)] + [("services." + tail) for tail in (
    "alpaca_prices", "archive_queries", "auto_import", "calibration_agreement",
    "calibration_fired", "candle_cache", "concordance", "core_settings",
    "csv_import", "earnings", "engine_edge", "episode_cache", "frontend",
    "journal_stats", "log_encoding", "market_data", "portfolio_snapshot",
    "screener_data", "startup", "trade_risk", "trigger_grade",
    "watchlist_candles", "watchlist_ledger",
)] + [("ibkr." + tail) for tail in ("broadcaster", "mapping", "service")]
# The scan's payload writers left the runtime output/ folder for screening/.
_OLD_ENGINE_AND_PIPELINE += [("output." + tail) for tail in ("dashboard", "terminal")]

_STALE = re.compile("|".join(
    [r"(?<![\w.])" + re.escape(name) + r"(?!\w)" for name in _OLD_ENGINE_AND_PIPELINE]
    + [r"(?<![\w.])(?:webapp\.backend\.)?" + re.escape(name) + r"(?!\w)" for name in _OLD_BACKEND]
    # The double-rewrite collision: a sibling module imported from the
    # implementation module instead of from its package.
    + [r"narrative\.reader" + r" import (?:bricks|chain)\b",
       r"universe\.descriptor" + r" import (?:ticker_admission|tickers)\b",
       r"metrics\.base" + r" import (?:pivots|indicators)\b",
       r"lps\.detection" + r" import detection\b"]
))

_SKIP_PARTS = {".git", ".claude", ".council", ".venv", "__pycache__",
               "node_modules", "context-handling"}
# Historical records keep the names they were written with.
_HISTORICAL = ("docs/archive/", "tools/fidelity/")


def _live_python_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_PARTS]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(ROOT)
            if name.endswith(".py") and not rel.as_posix().startswith(_HISTORICAL):
                yield path, rel


def test_no_live_python_names_a_moved_module():
    offences = []
    scanned = 0
    for path, rel in _live_python_files():
        scanned += 1
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            match = _STALE.search(line)
            if match:
                offences.append(f"{rel.as_posix()}:{number}: {match.group(0)}")
    assert scanned >= 300, "scan went vacuous"
    assert not offences, "names of moved modules survive:\n" + "\n".join(offences)
