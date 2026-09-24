"""Pins the whole ``python -m core.archive.analyze`` report card, byte for byte.

The report is a text surface the operator reads (and the backend serves at
``/archive/analysis``), so a refactor that shifts one column, drops one
caveat or rounds one number differently is a behaviour change even when every
unit test stays green. These pins build small synthetic archives through the
backend's own models, run the report over them, and compare the FULL output
(and the numbers behind it, at full precision) with the goldens in
``tests/fixtures/analyze_report/``.

The archives are built to walk every branch of the report:

* ``mixed`` - live screener episodes with continuation re-flags, seed rows,
  three engine epochs (so the Phase-A anchor family is scoped), placeholder
  contamination, a base-length outlier, and outcomes that produce HARMFUL,
  INERT, BENEFICIAL, unknown and TARGET-DISAGREEMENT verdicts.
* ``winners`` - a triggered-only gallery on one epoch: every caveat, the
  binary and the non-binary "verdicts withheld" refusals, a constant column
  that cannot be bucketed.
* ``empty`` - the table exists and holds nothing.

No RNG anywhere: every value comes from ``_wave``, so the goldens cannot
drift with a library's random stream. When the report changes ON PURPOSE,
review the diff the failure prints, then write ``golden_outputs()`` over
the goldens.
"""
import contextlib
import difflib
import io
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.orm import sessionmaker

from _paths import FIXTURES_DIR
from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from core.archive import analyze  # noqa: E402

GOLDEN_DIR = FIXTURES_DIR / "analyze_report"

_NEW_EPOCH = "vNEW1111111111bbbb"
_OLD_EPOCH = "vOLD0000000000aaaa"
_ONLY_EPOCH = "vONLY222222222cccc"

_INTEGER_COLUMNS = {c.name for c in archive_models.SetupArchive.__table__.columns
                    if str(c.type) == "INTEGER"}


def _wave(i: int, step: int, lo: float, hi: float, period: int = 23) -> float:
    """A deterministic spread of values in [lo, hi] - no RNG, so the pin cannot drift."""
    return round(lo + (hi - lo) * ((i * step) % period) / (period - 1), 4)


def _business_day(start: str, offset: int) -> str:
    return str(np.busday_offset(np.datetime64(start, "D"), offset, roll="forward"))


def _structure(i: int) -> dict:
    """Every structural feature, varied per row so tables and correlations have variance."""
    row = {}
    for k, feature in enumerate(analyze.STRUCTURAL_FEATURES):
        value = _wave(i, (k % 21) + 2, 0.0, 10.0 if feature in _INTEGER_COLUMNS else 1.0)
        row[feature] = int(value) if feature in _INTEGER_COLUMNS else value
    row["box_width"] = _wave(i, 5, 0.03, 0.20)
    row["base_length"] = 20 + int(_wave(i, 7, 0, 100))
    row["breadth_pct"] = _wave(i, 9, 20.0, 80.0)
    return row


def _mixed_rows() -> list[dict]:
    """48 live episodes (12 re-flagged the next day), 6 seeds, 2 sector rows."""
    rows = []
    for i in range(48):
        label = ("win", "loss", "timeout")[i % 3]
        if i % 8 == 7:
            label = None
        cash_grab = label == "win" and i % 9 == 0
        durable = label == "win" and not cash_grab
        # touch density: low on the durable wins, high elsewhere - and the MFE
        # follows it, so the two outcome families disagree about this term.
        touch = _wave(i, 3, 0.0, 3.0) if durable else _wave(i, 3, 5.0, 10.0)
        epoch = _OLD_EPOCH if i < 28 else _NEW_EPOCH
        first_day = _business_day("2026-03-02" if i < 28 else "2026-07-06", 2 * i)
        row = {
            "ticker": f"T{i:02d}", "scan_date": first_day, "source": "screener",
            "universe_type": "us_equities", "engine_config_version": epoch,
            "setup_type": ("BREAKOUT" if i in (9, 19)
                           else "REBOUND" if i % 3 == 1 else "LPS"),
            "tier": "D" if i in (5, 15) else "SABC"[i % 4],
            "score": 50 + _wave(i, 4, 0, 40),
            **_structure(i),
            "tightness_ratio": 0.70 if i % 5 == 0 else _wave(i, 6, 0.2, 0.9),
            "lps_zone_type": ("inner", "outer", None)[i % 3],
            "phase_d_inner": i % 2, "lps_in_inner": (i // 2) % 2,
            "lps_swing_type": "HL" if i % 4 < 2 else "LL",
            "inner_source": ("box", "pivot")[i % 2],
            "spy_trend": ("UP", "DOWN", "FLAT")[i % 3],
            "triggered": 0 if i % 3 == 2 else 1,
            "bars_to_date": 70 if i < 40 else 10,
            "fwd_return_20d": round(0.12 - 0.9 * _wave(i, 5, 0.03, 0.20)
                                    + 0.3 * _wave(i, 11, -0.1, 0.1), 4),
            "fwd_return_60d": None if i % 6 == 5 else _wave(i, 13, -0.2, 0.4),
            "r_multiple_20d": None if i % 7 == 6 else _wave(i, 8, -1.0, 4.0),
            "barrier_label": label,
            "days_to_2_5r": 6 + i % 5 if durable else None,
            "days_to_15pct": 4 if cash_grab else (10 if durable else None),
            # round-trips 1..5 bars after target (5 = the inclusive cash-grab
            # edge, T09), and every other durable win stopped 6 bars later.
            "days_to_stop": (5 + i % 5 if cash_grab
                             else 12 + i % 5 if durable and i % 2 == 0
                             else 3 + i % 6 if label == "loss" else None),
            "mfe_20d": round(0.10 + 0.03 * touch, 4),
            "score_box_tightness": (12.0 if durable else 6.0) + _wave(i, 2, 0, 2),
            "score_touch_density": touch,
            "score_traversal_quality": _wave(i, 4, 0, 8),
            "score_atr_squeeze": _wave(i, 6, 0, 8),
            "score_lps_tightness": _wave(i, 10, 0, 8),
            "score_vol_contraction": _wave(i, 12, 0, 8),
            "score_base_age": _wave(i, 14, 0, 8),
            "score_uptrend_bonus": 0.0,
            "score_rs_bonus": 0.0,
            "score_setup_quality": _wave(i, 16, 0, 8),
            "pp_clock": 5 + i % 4 if i >= 28 else None,
            "pp_pole_gain": _wave(i, 3, 0.2, 0.9) if i >= 28 else None,
        }
        if i == 7:
            row["base_length"] = 300               # an anchor mis-detection outlier
        rows.append(row)
        if i % 4 == 0:                             # the next-day continuation re-flag
            rows.append({**row, "scan_date": _business_day(first_day, 1),
                         "fwd_return_20d": -0.5, "score_base_age": 99.0})
    for j in range(6):
        rows.append({
            "ticker": f"SEED{j}", "scan_date": _business_day("2025-11-03", 3 * j),
            "source": "seed", "universe_type": "us_equities",
            "engine_config_version": None, "setup_type": "LPS", "tier": "A",
            "score": 70.0, **_structure(100 + j), "triggered": 1, "bars_to_date": 80,
            "fwd_return_20d": 0.2, "fwd_return_60d": 0.35, "r_multiple_20d": 3.0,
            "barrier_label": "win", "days_to_2_5r": 5, "mfe_20d": 0.3,
            "score_box_tightness": 10.0, "score_touch_density": 4.0,
        })
    for ticker in ("XLE", "XLK"):                  # another universe: never in scope
        rows.append({"ticker": ticker, "scan_date": "2026-07-06", "source": "screener",
                     "universe_type": "us_sectors", "setup_type": "LPS", "tier": "S",
                     "score": 99.0, "fwd_return_20d": 9.9})
    return rows


def _winners_rows() -> list[dict]:
    """20 labelled seed wins (4 losses) + 10 unlabelled screener rows, one epoch."""
    rows = []
    for i in range(30):
        seed = i < 20
        label = ("loss" if i % 5 == 4 else "win") if seed else None
        rows.append({
            "ticker": f"W{i:02d}", "scan_date": _business_day("2026-05-04", i),
            "source": "seed" if seed else "screener", "universe_type": "us_equities",
            "engine_config_version": _ONLY_EPOCH,
            "setup_type": ("LPS", "REBOUND")[i % 2], "tier": "SA"[i % 2],
            "score": 60 + _wave(i, 3, 0, 30), **_structure(i),
            "breadth_pct": 55.0,                   # constant: cannot be tertiled
            "triggered": 1, "bars_to_date": 65,
            "fwd_return_20d": _wave(i, 5, 0.01, 0.30),
            "fwd_return_60d": _wave(i, 7, 0.05, 0.60),
            "r_multiple_20d": _wave(i, 9, 0.5, 5.0),
            "barrier_label": label,
            "days_to_2_5r": 7 if label == "win" else None,
            "days_to_stop": 4 if label == "loss" else None,
            "mfe_20d": _wave(i, 4, 0.1, 0.5),
            "score_box_tightness": _wave(i, 2, 0, 12),
            "score_touch_density": _wave(i, 6, 0, 10),
        })
    return rows


def _build_archive(path, rows) -> str:
    engine = database.make_sqlite_engine(str(path))
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        for row in rows:
            session.add(archive_models.SetupArchive(**row))
        session.commit()
    finally:
        session.close()
        engine.dispose()
    return str(path)


def build_archives(root) -> dict:
    return {
        "mixed": _build_archive(root / "mixed.db", _mixed_rows()),
        "winners": _build_archive(root / "winners.db", _winners_rows()),
        "empty": _build_archive(root / "empty.db", []),
    }


@pytest.fixture(scope="module")
def archives(tmp_path_factory):
    return build_archives(tmp_path_factory.mktemp("analyze_pin"))


@contextlib.contextmanager
def _reading(db_path):
    """Point the report at one synthetic archive for the duration."""
    previous = analyze._DB_PATH
    analyze._DB_PATH = db_path
    try:
        yield
    finally:
        analyze._DB_PATH = previous


def _printed(fn, *args, **kwargs) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fn(*args, **kwargs)
    return out.getvalue()


def _run_report(db_path, **kwargs) -> str:
    """The report exactly as ``run`` prints it, with the machine's path masked."""
    with _reading(db_path):
        return _printed(analyze.run, **kwargs).replace(db_path, "<DB>")


# ── The numbers behind the text, at full precision ──────────────────────────

def _plain(value):
    """JSON-ready: numpy scalars to Python; NaN stays NaN (json writes it)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _values(db_path) -> dict:
    with _reading(db_path):
        raw = analyze.load_archive()
    df = analyze.dedup_to_episodes(raw)
    enriched = analyze.derive_outcomes(df)
    derived = ["id", "barrier_win", "durable_win", "win_quality",
               "bars_target_to_stop", analyze.MAGNITUDE_TARGET]
    corr_20d = {"box_tightness": 0.4, "touch_density": -0.2, "base_age": 0.0}
    corr_60d = {"box_tightness": 0.1, "touch_density": 0.3, "base_age": 0.05}
    current = {"box_tightness": 10, "touch_density": 6, "base_age": 4}
    analyze._LINES.clear()
    composition = analyze.section_composition(df, 30)
    analyze._LINES.clear()
    return _plain({
        "raw_ids": sorted(raw["id"].tolist()),
        "episode_ids": sorted(df["id"].tolist()),
        "epochs": analyze.engine_epochs(df),
        "current_epoch": analyze.current_epoch(df),
        "anchor_seam": analyze.anchor_seam(df),
        "composition": composition,
        "perf_by_tier": {t: analyze._perf_row(df[df["tier"] == t])
                         for t in sorted(df["tier"].dropna().unique())},
        "derived": enriched.reindex(columns=derived).to_dict("records"),
        "signal_edge": analyze.signal_edge(enriched),
        "suggested_weights": analyze.suggested_weights(df, corr_20d, corr_60d, current),
    })


def _values_json(db_path) -> str:
    return json.dumps(_values(db_path), indent=1, sort_keys=True) + "\n"


# (golden file, archive, run() keyword arguments)
_REPORT_CASES = [
    ("mixed.txt", "mixed", {}),
    ("mixed_no_dedup.txt", "mixed", {"dedup": False, "min_rows": 100}),
    ("mixed_seed_only.txt", "mixed", {"source": "seed"}),
    ("winners.txt", "winners", {}),
    ("winners_screener_only.txt", "winners", {"source": "screener"}),
    ("empty.txt", "empty", {}),
]
_VALUE_CASES = ["mixed", "winners", "empty"]


# ── Branches no stored archive reaches, pinned one section at a time ─────────

def _seam_without_dates() -> pd.DataFrame:
    """``current_epoch`` needs a scan_date to pick today's reader, so a frame
    spanning two epochs without one has nothing to scope the family to."""
    return pd.DataFrame({
        "engine_config_version": ["vA", "vB", "vA"],
        "setup_type": ["LPS"] * 3, "tier": ["S"] * 3,
        "box_width": [0.05, 0.06, 0.07], "bin_a_bars": [3, 4, 5],
    })


def _every_signal_earns_its_points() -> pd.DataFrame:
    """Trustworthy verdicts with nothing to subtract and no magnitude column."""
    wins = [i % 2 == 0 for i in range(30)]
    return pd.DataFrame({
        "barrier_label": ["win" if w else "loss" for w in wins],
        "score_box_tightness": [8.0 + (i % 3) if w else 2.0 - (i % 3) * 0.5
                                for i, w in enumerate(wins)],
        "score_touch_density": [5.0 + i * 0.1 if w else i * 0.05
                                for i, w in enumerate(wins)],
    })


def _exactly_min_n_labelled_rows() -> pd.DataFrame:
    """8 realized R multiples and nothing else: just enough to pick a primary
    outcome (min_n is inclusive), far too few for a verdict."""
    return pd.DataFrame({
        "r_multiple_20d": [0.5 * i - 1.0 for i in range(8)] + [None, None],
        "score_box_tightness": [float(i % 4) for i in range(10)],
    })


def _one_thin_tightness_feature() -> pd.DataFrame:
    """box_width has 12 paired rows (tested); atr_ratio has 11 (skipped)."""
    return pd.DataFrame({
        "box_width": [0.02 * (i + 1) for i in range(12)],
        "atr_ratio": [0.1 * i for i in range(11)] + [None],
        "fwd_return_20d": [0.3 - 0.02 * i for i in range(12)],
    })


_SECTION_CASES = [
    ("fingerprint across a seam with no scan dates",
     analyze.section_fingerprint, _seam_without_dates),
    ("signal edge where every sub-score earns its points",
     lambda df: analyze.section_signal_edge(df, True), _every_signal_earns_its_points),
    ("signal edge on exactly min_n labelled rows",
     lambda df: analyze.section_signal_edge(df, True), _exactly_min_n_labelled_rows),
    ("tightness test with one thin feature",
     lambda df: analyze.section_tightness(df, True), _one_thin_tightness_feature),
]


def _sections_text() -> str:
    parts = []
    for label, section, frame in _SECTION_CASES:
        analyze._LINES.clear()
        section(frame())
        parts.append(f"#### {label}\n" + "\n".join(analyze._LINES) + "\n")
    analyze._LINES.clear()
    return "".join(parts)


def golden_outputs(archives) -> dict:
    """Every golden's current text, keyed by file name (the re-pin helper)."""
    out = {name: _run_report(archives[db], **kwargs) for name, db, kwargs in _REPORT_CASES}
    out.update({f"{db}_values.json": _values_json(archives[db]) for db in _VALUE_CASES})
    out["sections.txt"] = _sections_text()
    return out


def _golden(name: str) -> str:
    with open(GOLDEN_DIR / name, encoding="utf-8") as fh:
        return fh.read()


def _assert_matches_golden(name: str, actual: str) -> None:
    expected = _golden(name)
    if actual == expected:
        return
    diff = "".join(difflib.unified_diff(
        expected.splitlines(keepends=True), actual.splitlines(keepends=True),
        fromfile=f"golden/{name}", tofile="actual", n=2))
    raise AssertionError(f"{name} drifted from its golden:\n{diff[:6000]}")


# ── The report text ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,db,kwargs", _REPORT_CASES,
                         ids=[c[0] for c in _REPORT_CASES])
def test_report_text_is_pinned(archives, name, db, kwargs):
    _assert_matches_golden(name, _run_report(archives[db], **kwargs))


@pytest.mark.parametrize("db", _VALUE_CASES)
def test_the_values_behind_the_report_are_pinned(archives, db):
    _assert_matches_golden(f"{db}_values.json", _values_json(archives[db]))


def test_the_branches_no_archive_reaches_are_pinned_per_section():
    _assert_matches_golden("sections.txt", _sections_text())


def test_the_goldens_are_exactly_the_pinned_cases():
    names = ({c[0] for c in _REPORT_CASES}
             | {f"{db}_values.json" for db in _VALUE_CASES}
             | {"sections.txt"})
    assert {p.name for p in GOLDEN_DIR.iterdir()} == names


def _markdown_copy(path, db_path) -> str:
    """The file ``--md`` wrote, byte for byte (text mode: the platform's line
    ending), with the machine's path masked."""
    return path.read_bytes().decode("utf-8").replace(db_path, "<DB>")


def _fenced(name: str) -> str:
    return ("```\n" + _golden(name)[:-1] + "\n```\n").replace("\n", os.linesep)


def test_the_markdown_copy_is_the_report_fenced(archives, tmp_path):
    md = tmp_path / "report.md"
    out = _run_report(archives["mixed"], md_path=str(md))
    assert out == _golden("mixed.txt") + f"\n[report written to {md}]\n"
    assert _markdown_copy(md, archives["mixed"]) == _fenced("mixed.txt")


def test_a_relative_markdown_path_lands_under_the_project_root(
        archives, tmp_path, monkeypatch):
    monkeypatch.setattr(analyze, "_PROJECT_ROOT", str(tmp_path))
    out = _run_report(archives["winners"], md_path="nested.md")
    written = tmp_path / "nested.md"
    assert out == _golden("winners.txt") + f"\n[report written to {written}]\n"
    assert _markdown_copy(written, archives["winners"]) == _fenced("winners.txt")


# ── The CLI: flags, the -m entry point and its exit codes ───────────────────

@pytest.mark.parametrize("argv,name,db", [
    ([], "mixed.txt", "mixed"),
    # 48 live episodes against a 48-row bar: the bar is met, so no caveat.
    (["--min-rows", "48"], "mixed.txt", "mixed"),
    (["--no-dedup", "--min-rows", "100"], "mixed_no_dedup.txt", "mixed"),
    (["--source", "seed"], "mixed_seed_only.txt", "mixed"),
    (["--source", "screener"], "winners_screener_only.txt", "winners"),
])
def test_main_parses_the_flags_into_the_pinned_runs(archives, monkeypatch, argv, name, db):
    monkeypatch.setattr(sys, "argv", ["analyze", *argv])
    with _reading(archives[db]):
        out = _printed(analyze.main)
    assert out.replace(archives[db], "<DB>") == _golden(name)


def test_main_writes_the_markdown_copy_named_by_md(archives, monkeypatch, tmp_path):
    md = tmp_path / "flag.md"
    monkeypatch.setattr(sys, "argv", ["analyze", "--md", str(md)])
    with _reading(archives["mixed"]):
        _printed(analyze.main)
    assert _markdown_copy(md, archives["mixed"]) == _fenced("mixed.txt")


def test_main_rejects_an_unknown_flag_with_argparse_exit_2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["analyze", "--bogus"])
    with pytest.raises(SystemExit) as exc, contextlib.redirect_stderr(io.StringIO()):
        analyze.main()
    assert exc.value.code == 2


def _cli(db_path, *args):
    env = {**os.environ, "CHROLLO_DB_PATH": db_path,
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-B", "-m", "core.archive.analyze", *args],
                          cwd=str(ROOT), env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=180)


def test_the_module_entry_point_prints_the_pinned_report_and_exits_0(archives):
    """The backend runs exactly this command as a subprocess after a scan."""
    result = _cli(archives["mixed"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.replace(archives["mixed"], "<DB>") == _golden("mixed.txt")


def test_a_missing_archive_exits_1_naming_the_path(tmp_path):
    missing = str(tmp_path / "absent.db")
    result = _cli(missing)
    assert result.returncode == 1
    assert f"FileNotFoundError: Archive DB not found at {missing}" in result.stderr
    assert result.stdout == ""
