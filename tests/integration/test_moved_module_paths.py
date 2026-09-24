"""No live code may name a module the 2026-09 domain refactor moved.

The refactor moved the engine's structure modules into subpackages, the
pipeline into screening/market_data/universe/context/telemetry, and the backend
routers and services into domains/ and app/; the dashboard writer left output/
for core/pipeline/screening/. An import of an old name fails only
when its line runs (lazy imports hide from every boot check), and an old name in
a "keep in sync" comment sends the next reader to a file that is gone. The
modules that became packages of the same name (structure.lps, .narrative,
.metrics and pipeline.universe) are still valid names and are not listed; the
double-rewrite forms that broke them are. The flat tools/ folder was then sorted
into category folders (2026-09-24): tools.<name> became tools.<category>.<name>,
so the old dotted names, the ``from tools import <name>`` spelling and the old
``tools/<name>.py`` paths are all stale.

Comments also spell a module as a path (``<folder>/<module>.NAME``,
a frontend twin's pointer at its backend source), so every old name is matched
in its slash form too, and the frontend's JS is scanned with the Python.

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
# Every tool that left the flat tools/ folder for a category folder (tools/_bootstrap.py stayed).
_OLD_TOOL_NAMES = (
    "ChrolloBackup", "agreement", "backtest_engine", "bar_state_census",
    "build_universe_returns", "calibration_harness", "calibration_stat_card",
    "cause_veto_corpus", "chart_framing_census", "correspondence_census",
    "doctrine_audit", "event_map_census", "event_map_chronology", "fold_parity",
    "full_package_render", "guided_list_export", "htf_audit", "marks_corpus",
    "marks_json", "miss_lane_census", "near_miss_census", "near_miss_report",
    "negative_corpus", "operator_marks_diff", "pointer_audit", "power_play_census",
    "power_play_fixture", "power_play_sheets", "provider_parity", "rail_area_census",
    "rail_margin_ab", "rail_margin_evidence", "reader_pin", "recover_service_python",
    "replay", "restore_drill", "run_maturation", "settings_reference", "shadow_diff",
    "shape_profile", "shelf_harness", "story_chain_candidates", "structure_case_audit",
    "ta_grade_archive_replay", "ta_grade_timing",
)
_OLD_ENGINE_AND_PIPELINE += [("tools." + tail) for tail in _OLD_TOOL_NAMES]
_OLD_TOOLS_ALT = "(?:" + "|".join(_OLD_TOOL_NAMES) + ")"

_STALE = re.compile("|".join(
    [r"(?<![\w.])" + re.escape(name) + r"(?!\w)" for name in _OLD_ENGINE_AND_PIPELINE]
    + [r"(?<![\w.])(?:webapp\.backend\.)?" + re.escape(name) + r"(?!\w)" for name in _OLD_BACKEND]
    # The same names spelled as paths (<folder>/<module>.NAME in a comment).
    + [r"(?<![\w./\\])" + re.escape(name.replace(".", "/")) + r"(?![\w/])"
       for name in _OLD_ENGINE_AND_PIPELINE]
    + [r"(?<![\w./\\])(?:webapp/backend/)?" + re.escape(name.replace(".", "/")) + r"(?![\w/])"
       for name in _OLD_BACKEND]
    # The double-rewrite collision: a sibling module imported from the
    # implementation module instead of from its package.
    + [r"narrative\.reader" + r" import (?:bricks|chain)\b",
       r"universe\.descriptor" + r" import (?:ticker_admission|tickers)\b",
       r"metrics\.base" + r" import (?:pivots|indicators)\b",
       r"lps\.detection" + r" import detection\b"]
    # The two tools spellings a dotted name cannot see: the package-level import
    # and the old file path in a comment or message.
    + [r"\bfrom tools" + r" import\b[^\n#]*\b" + _OLD_TOOLS_ALT + r"\b",
       r"(?<![\w./\\])tools[/\\]" + _OLD_TOOLS_ALT + r"\.(?:py|mjs|bat|ps1)\b"]
))

_SKIP_PARTS = {".git", ".claude", ".council", ".venv", "__pycache__",
               "node_modules", "context-handling", "dist"}
_FRONTEND = "webapp/frontend/"
# Historical records keep the names they were written with.
_HISTORICAL = ("docs/archive/", "research/fidelity/")


def _live_code_files():
    """Every live .py file, plus the frontend's .js/.jsx/.mjs."""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_PARTS]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(_HISTORICAL):
                continue
            if name.endswith(".py") or (rel.startswith(_FRONTEND) and name.endswith((".js", ".jsx", ".mjs"))):
                yield path, rel


def test_no_live_code_names_a_moved_module():
    offences = []
    scanned = frontend = 0
    for path, rel in _live_code_files():
        scanned += 1
        frontend += rel.startswith(_FRONTEND)
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            match = _STALE.search(line)
            if match:
                offences.append(f"{rel}:{number}: {match.group(0)}")
    assert scanned >= 500 and frontend >= 150, f"scan went vacuous ({scanned} files, {frontend} frontend)"
    assert not offences, "names of moved modules survive:\n" + "\n".join(offences)
