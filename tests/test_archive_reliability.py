"""Archive-pipeline reliability fixes (branch fix/archive-pipeline).

Covers the five defects from the 2026-07-01 adversarial audit (memory
project_archive_silent_stall):
  #1 maturation records its own scan_runs row + the watchdog checks it
  #2 a degraded-coverage but current-session day archives the per-ticker-fresh subset
  #3 the forward-return download start is padded so a non-trading-day earliest cohort resolves
  #4 the re-touch window is widened/decoupled so a straggler past the old 120d cap still matures
  #5 an orphaned status='running' scan_runs row is reconciled to failed at boot
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from core.pipeline import scan_job as scan_job_module
from core.archive import forward_returns as fr
from webapp.backend.services import scan_runner, scan_watchdog, startup


# ── helpers ──────────────────────────────────────────────────────────────────
def _panel(symbols, day):
    """A 1-bar MultiIndex OHLCV-ish panel (Close + Volume) for the given symbols."""
    return pd.concat(
        {
            s: pd.DataFrame({"Close": [10.0], "Volume": [1000]}, index=[pd.Timestamp(day)])
            for s in symbols
        },
        axis=1,
    )


def _ohlcv_panel(ticker, start, periods):
    """A single-ticker MultiIndex OHLCV panel of `periods` business days from
    `start` (the shape _batched_download returns), flat at 100.0."""
    idx = pd.bdate_range(start=pd.Timestamp(start), periods=periods)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    frame = pd.DataFrame(
        {c: ([100.0] * periods if c != "Volume" else [1000.0] * periods) for c in cols},
        index=idx,
    )
    return pd.concat({ticker: frame}, axis=1)


def _wire_scanjob(tmp_path, monkeypatch, expected="2026-06-25"):
    from core.pipeline.downloads import _price_regime

    meta_file = tmp_path / "cache_meta.json"
    meta_file.write_text(
        json.dumps({
            "last_full_refresh": datetime.now(timezone.utc).isoformat(),
            # current-regime tag: an untagged meta now classifies regime_mismatch
            "price_series": _price_regime(),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(scan_job_module, "_cache_paths",
                        lambda *a, **k: (str(tmp_path / "c.parquet"), str(meta_file)))
    monkeypatch.setattr(scan_job_module, "_expected_session_date", lambda: expected)
    return expected


def _wire_scan_io(monkeypatch, results, panel, tickers):
    monkeypatch.setattr(scan_job_module, "run_screener", lambda *a, **k: (results, panel, tickers, {}))
    monkeypatch.setattr(scan_job_module, "print_results", lambda *a, **k: None)
    monkeypatch.setattr(scan_job_module, "save_csv", lambda *a, **k: None)
    monkeypatch.setattr(scan_job_module, "print_finviz_url", lambda *a, **k: None)
    monkeypatch.setattr(scan_job_module, "generate_dashboard", lambda *a, **k: None)
    monkeypatch.setattr(scan_job_module.settings, "ARCHIVE_LIVE_SCANS", True)


# ── Fix #1: maturation records its own run + alerts on failure ────────────────
def test_scheduled_maturation_records_own_run_and_alerts_on_failure(monkeypatch):
    """The forward-return backfill is no longer a silent swallow: it opens a
    kind='maturation' scan_runs row, closes it 'failed' on error, and fires a
    maturation-specific alert — so a stalled maturation can't hide."""
    import services.scan_status as scan_status_mod
    import services.core_settings as core_settings_mod
    import core.archive.forward_returns as fr_mod

    started, finishes, alerts = [], [], []

    def fake_start(trigger, kind="scan"):
        started.append((trigger, kind))
        return 1 if kind == "scan" else 2

    monkeypatch.setattr(scan_runner, "_run_scan_process_unlocked",
                        lambda *a, **k: SimpleNamespace(output="ok", returncode=0, n_setups=5, n_errored=0))
    monkeypatch.setattr(scan_runner, "_result_status", lambda r: "ok")
    monkeypatch.setattr(scan_runner, "_tail_error", lambda out: None)
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: alerts.append(a))
    monkeypatch.setattr(scan_status_mod, "start_run", fake_start)
    monkeypatch.setattr(scan_status_mod, "finish_run",
                        lambda run_id, status, n_setups=None, error=None: finishes.append((run_id, status)))
    monkeypatch.setattr(core_settings_mod, "load_core_settings",
                        lambda: SimpleNamespace(FORWARD_RETURNS_MIN_AGE_DAYS=5))

    def _boom(min_age_days=5):
        raise RuntimeError("db locked")

    monkeypatch.setattr(fr_mod, "update_forward_returns", _boom)

    scan_runner.run_scheduled_scan_and_forward_returns()

    assert ("scheduled", "maturation") in started       # its own run was opened
    assert (2, "failed") in finishes                    # closed 'failed', not swallowed
    assert any(a[0] == "scheduled-maturation" and a[1] == "failed" for a in alerts)
    assert not scan_runner.SCAN_LOCK.locked()


# ── Fix #1: watchdog checks maturation + hung 'running' ───────────────────────
def test_watchdog_flags_failed_stale_maturation_and_hung_running(monkeypatch):
    alerts = []
    monkeypatch.setattr(scan_watchdog, "alert_if_needed", lambda *a, **k: alerts.append(a))
    now = datetime.now(timezone.utc)

    def run(kind, status, hours_ago=0.5, running=False):
        ts = (now - timedelta(hours=hours_ago)).isoformat()
        return {
            "kind": kind, "status": status, "n_setups": 1, "error": "e",
            "finished_at": None if running else ts, "started_at": ts,
        }

    # scan fresh+ok, maturation FAILED -> exactly one alert (for maturation).
    monkeypatch.setattr(scan_watchdog.scan_status, "latest_run",
                        lambda kind="scan": run("scan", "ok") if kind == "scan" else run("maturation", "failed"))
    alerts.clear(); scan_watchdog.run_scan_health_watchdog()
    assert len(alerts) == 1 and alerts[0][1] == "failed"

    # scan fresh+ok, maturation OK but STALE (>26h) -> stale alert.
    monkeypatch.setattr(scan_watchdog.scan_status, "latest_run",
                        lambda kind="scan": run("scan", "ok") if kind == "scan" else run("maturation", "ok", hours_ago=30))
    alerts.clear(); scan_watchdog.run_scan_health_watchdog()
    assert any(a[1] == "stale_data" for a in alerts)

    # scan stuck 'running' 3h -> hung alert; maturation absent -> silent (no cry-wolf).
    monkeypatch.setattr(scan_watchdog.scan_status, "latest_run",
                        lambda kind="scan": run("scan", "running", hours_ago=3, running=True) if kind == "scan" else None)
    alerts.clear(); scan_watchdog.run_scan_health_watchdog()
    assert any(a[1] == "failed" and "stuck 'running'" in a[3] for a in alerts)

    # both fresh+ok -> silence.
    monkeypatch.setattr(scan_watchdog.scan_status, "latest_run", lambda kind="scan": run(kind, "ok"))
    alerts.clear(); scan_watchdog.run_scan_health_watchdog()
    assert alerts == []


# ── Fix #2: per-ticker partial archive on degraded coverage ───────────────────
def test_archive_freshness_classifies_three_states(tmp_path, monkeypatch):
    expected = _wire_scanjob(tmp_path, monkeypatch)
    fresh = _panel(["AAA", "SPY", "QQQ"], expected)
    assert scan_job_module._archive_freshness(fresh, ["AAA"], None)[0] == "fresh"
    # Universe ticker BBB lacks today's close -> <95% eligible coverage, session current.
    assert scan_job_module._archive_freshness(fresh, ["AAA", "BBB"], None)[0] == "degraded_coverage"
    stale = _panel(["AAA", "SPY", "QQQ"], "2026-06-20")  # a session behind
    assert scan_job_module._archive_freshness(stale, ["AAA"], None)[0] == "stale_session"


def test_session_lag_panel_is_readable_but_never_archivable(tmp_path, monkeypatch):
    """The diff's headline invariant, pinned at the layer that enforces it.

    `session_lag` is the first state that lets a panel BEHIND the expected session get
    past evaluation, so `_archive_freshness` sees an input class it never saw before.
    An archive row is keyed on the EXPECTED session, so a row written off the prior
    session's bars would silently poison every forward return and edge read.

    Both halves matter: cache-mode must TOLERATE it (return False = refresh the
    dashboard, skip the archive, exit 0) or the operator watches his leaderboard render
    and then vanish behind a red failure; download-mode must still RAISE, because that
    job exists to reach the expected session."""
    expected = _wire_scanjob(tmp_path, monkeypatch)          # 2026-06-25
    lagging = _panel(["AAA", "SPY", "QQQ"], "2026-06-24")    # exactly one session behind

    status, _ = scan_job_module._archive_freshness(lagging, ["AAA"], None)
    assert status == "session_lag"
    assert status != "degraded_coverage", (
        "degraded_coverage would per-ticker archive the subset — that must never "
        "happen for a panel whose bars predate the expected session")

    # Cache mode: tolerated, and tolerated means NOT archivable.
    assert scan_job_module._passes_archive_freshness(
        lagging, ["AAA"], None, "cache", n_setups=3) is False

    # Download mode: still a failed refresh.
    with pytest.raises(scan_job_module.StaleMarketDataError):
        scan_job_module._passes_archive_freshness(
            lagging, ["AAA"], None, "download", n_setups=3)

    # And the all-or-nothing helper still refuses outright.
    with pytest.raises(scan_job_module.StaleMarketDataError):
        scan_job_module._assert_fresh_for_archive(lagging, ["AAA"], None)


def test_fresh_result_subset_keeps_per_ticker_fresh(tmp_path, monkeypatch):
    expected = _wire_scanjob(tmp_path, monkeypatch)
    panel = _panel(["AAA", "SPY", "QQQ"], expected)  # AAA fresh; BBB absent -> stale
    results = pd.DataFrame([{"Ticker": "AAA", "Score": 10.0}, {"Ticker": "BBB", "Score": 9.0}])
    fresh_df, n_dropped = scan_job_module._fresh_result_subset(results, panel, ["AAA", "BBB"], None)
    assert list(fresh_df["Ticker"]) == ["AAA"]
    assert n_dropped == 1


def test_download_degraded_coverage_archives_fresh_subset(tmp_path, monkeypatch):
    """The core Fix #2 behavior: a <95%-coverage but current-session download-mode
    day archives the per-ticker-fresh setups instead of discarding the whole cohort."""
    expected = _wire_scanjob(tmp_path, monkeypatch)
    panel = _panel(["AAA", "SPY", "QQQ"], expected)      # AAA fresh; BBB not in panel
    results = pd.DataFrame([{"Ticker": "AAA", "Score": 10.0}, {"Ticker": "BBB", "Score": 9.0}])
    _wire_scan_io(monkeypatch, results, panel, ["AAA", "BBB"])  # universe incl. missing BBB

    archived = {}

    def _archive(df, scan_date_str=None, enable=False, universe=None):
        archived["tickers"] = list(df["Ticker"])
        # scan_job threads ONE scan_date to both writers (payload identity +
        # archive upsert key) — a None here means the threading broke.
        archived["scan_date_str"] = scan_date_str
        return len(df)

    monkeypatch.setattr(scan_job_module, "archive_scan_results", _archive)

    result = scan_job_module.run_scan_and_export(mode="download")

    assert archived["tickers"] == ["AAA"]   # only the per-ticker-fresh setup archived
    # The one threaded scan_date reached the writer AND is the PANEL's own
    # session, not the wall clock — the ET+7 box's date.today() stamp was the
    # weekend-duplicate factory (council F2: bare truthiness let a broken
    # thread pass; equality against the panel session subsumes the shape check).
    assert archived["scan_date_str"] == expected
    assert result.n_archived == 1
    assert result.n_setups == 2             # both still counted as fired


def test_empty_day_dashboard_carries_panel_session_date(tmp_path, monkeypatch):
    """The empty-branch artifact carries the panel's own session too — one
    identity convention for 'scanned, matched nothing' and for fires alike
    (a weekend re-scan of Friday's panel must present as Friday, not as a
    new Saturday artifact)."""
    expected = _wire_scanjob(tmp_path, monkeypatch)
    panel = _panel(["AAA", "SPY", "QQQ"], expected)
    _wire_scan_io(monkeypatch, pd.DataFrame(), panel, ["AAA"])
    # The lane is not under test; keep the empty branch off the writer.
    monkeypatch.setattr(scan_job_module.settings, "NEAR_MISS_LANE_ENABLED", False)
    seen = {}
    monkeypatch.setattr(scan_job_module, "generate_dashboard",
                        lambda *a, **k: seen.update(k))

    result = scan_job_module.run_scan_and_export(mode="download")

    assert seen["scan_date"] == expected
    assert result.n_setups == 0


def test_download_fresh_archives_full_cohort(tmp_path, monkeypatch):
    expected = _wire_scanjob(tmp_path, monkeypatch)
    panel = _panel(["AAA", "BBB", "SPY", "QQQ"], expected)  # everyone fresh -> 100%
    results = pd.DataFrame([{"Ticker": "AAA", "Score": 10.0}, {"Ticker": "BBB", "Score": 9.0}])
    _wire_scan_io(monkeypatch, results, panel, ["AAA", "BBB"])

    archived = {}
    monkeypatch.setattr(scan_job_module, "archive_scan_results",
                        lambda df, scan_date_str=None, enable=False, universe=None: (archived.setdefault("t", list(df["Ticker"])), len(df))[1])

    result = scan_job_module.run_scan_and_export(mode="download")
    assert archived["t"] == ["AAA", "BBB"]
    assert result.n_archived == 2


def test_download_nonempty_stale_session_raises(tmp_path, monkeypatch):
    expected = _wire_scanjob(tmp_path, monkeypatch)
    stale = _panel(["AAA", "SPY", "QQQ"], "2026-06-20")  # whole panel a session behind
    results = pd.DataFrame([{"Ticker": "AAA", "Score": 10.0}])
    _wire_scan_io(monkeypatch, results, stale, ["AAA"])
    monkeypatch.setattr(scan_job_module, "archive_scan_results",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not archive stale")))

    with pytest.raises(scan_job_module.StaleMarketDataError):
        scan_job_module.run_scan_and_export(mode="download")


def test_download_degraded_all_stale_tickers_raises_not_silent(tmp_path, monkeypatch):
    """Council P2 (Fowler): a degraded-coverage day where NONE of the fired tickers
    carry today's close must RAISE (reported stale_data -> alert), not silently exit
    'ok' with n_archived=0 — otherwise it reintroduces the silent-stall the whole
    effort removes."""
    expected = _wire_scanjob(tmp_path, monkeypatch)
    # Session is current (SPY/QQQ present) but no equity ticker has today's bar.
    panel = _panel(["SPY", "QQQ"], expected)
    results = pd.DataFrame([{"Ticker": "AAA", "Score": 10.0}])  # AAA fired but not fresh
    _wire_scan_io(monkeypatch, results, panel, ["AAA"])
    monkeypatch.setattr(scan_job_module, "archive_scan_results",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not archive")))

    with pytest.raises(scan_job_module.StaleMarketDataError):
        scan_job_module.run_scan_and_export(mode="download")


# ── Fix #3: pad the download start for a non-trading-day earliest cohort ───────
def test_forward_returns_pads_start_for_non_trading_earliest(monkeypatch):
    import database
    import archive_models
    import core.pipeline.downloads as downloads
    from sqlalchemy.orm import sessionmaker

    engine = database.make_sqlite_engine(":memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add(archive_models.SetupArchive(
        ticker="AAA", scan_date="2026-05-31",  # a Sunday (non-trading)
        setup_type="LPS", tier="A", score=1.0, s_level=90.0, trigger_price=0.0,
        source="screener", universe_type="us_equities",
    ))
    session.commit(); session.close()

    captured = {}

    def fake_dl(tickers, params, label):
        captured["start"] = params["start"]
        # Simulate yfinance: only TRADING days are returned, so a non-trading
        # `start` yields a first bar strictly AFTER it.
        return _ohlcv_panel("AAA", params["start"], 90)

    monkeypatch.setattr(database, "make_sqlite_engine", lambda _p: engine)
    monkeypatch.setattr(downloads, "_batched_download", fake_dl)

    updated = fr.update_forward_returns(min_age_days=0, force=True)

    # The pad puts a trading bar on/before the Sunday scan_date, so scan_close
    # resolves and the row matures. (Unpadded, start == Sunday -> first bar Monday
    # -> mask_on all-False -> the row is skipped and updated == 0.)
    assert updated == 1
    assert pd.Timestamp(captured["start"]) < pd.Timestamp("2026-05-31")


# ── Fix #4: widened / decoupled re-touch window ───────────────────────────────
def test_forward_returns_window_widened_and_decoupled():
    assert fr.FORWARD_RETURN_MAX_SCAN_AGE_DAYS == 200
    assert fr.FORWARD_RETURN_MAX_SCAN_AGE_DAYS > fr.FORWARD_RETURN_DOWNLOAD_DAYS


def test_forward_returns_matures_straggler_past_old_120d_window(monkeypatch):
    import database
    import archive_models
    import core.pipeline.downloads as downloads
    from sqlalchemy.orm import sessionmaker

    engine = database.make_sqlite_engine(":memory:")
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    scan_date = (datetime.today() - timedelta(days=150)).strftime("%Y-%m-%d")
    session.add(archive_models.SetupArchive(
        ticker="AAA", scan_date=scan_date, setup_type="LPS", tier="A", score=1.0,
        s_level=90.0, trigger_price=0.0, source="screener", universe_type="us_equities",
    ))
    session.commit(); session.close()

    monkeypatch.setattr(database, "make_sqlite_engine", lambda _p: engine)
    monkeypatch.setattr(downloads, "_batched_download",
                        lambda tickers, params, label: _ohlcv_panel("AAA", params["start"], 120))

    # force=False so the (non-force) re-touch window governs selection. A 150-day-old
    # straggler with null windows is selected under the widened 200-day cap; under the
    # old 120-day cap it was excluded (150 > 120) and updated would be 0.
    updated = fr.update_forward_returns(min_age_days=0, force=False)
    assert updated == 1


# ── Fix #5: boot-time reconcile of orphaned 'running' rows ────────────────────
def test_reconcile_orphaned_running_marks_failed(tmp_path):
    from sqlalchemy import create_engine, text

    eng = create_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE TABLE scan_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "started_at VARCHAR, finished_at VARCHAR, status VARCHAR, "
            "n_setups INTEGER, error TEXT, trigger VARCHAR, kind VARCHAR)"
        ))
        conn.execute(text(
            "INSERT INTO scan_runs (started_at, status, trigger, kind) "
            "VALUES ('t0', 'running', 'scheduled', 'scan')"
        ))
        conn.execute(text(
            "INSERT INTO scan_runs (started_at, finished_at, status, trigger, kind) "
            "VALUES ('t0', 't1', 'ok', 'manual', 'maturation')"
        ))

    startup._reconcile_orphaned_runs(eng)

    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT status, finished_at, error FROM scan_runs ORDER BY id"
        )).fetchall()

    # the orphaned 'running' row -> failed, with finished_at + reason stamped
    assert rows[0][0] == "failed"
    assert rows[0][1] is not None
    assert "died before completion" in (rows[0][2] or "")
    # the genuinely-completed row is untouched
    assert rows[1][0] == "ok"
    eng.dispose()


def test_reconcile_orphaned_running_is_safe_when_table_absent(tmp_path):
    """Best-effort: a missing scan_runs table must not raise (boot must not fail)."""
    from sqlalchemy import create_engine

    eng = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    startup._reconcile_orphaned_runs(eng)  # no table yet -> swallowed, no raise
    eng.dispose()
