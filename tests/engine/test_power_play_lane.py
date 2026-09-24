"""The species scan lane (program Task 8): the composed twin's flag-off
byte-identity, per-ticker containment (a lane failure never converts a firing
result into a drop — EC-20), the bounded watch's wall verdicts on hand-reasoned
frames, and the closed-set wire vocabulary derived server-side.

Post-review additions (2026-08-17, findings 3/11): the election half is now
pinned END TO END on hand-reasoned tape — one frame each for admitted_dark
(with input-tied assertions + a mutation probe, EC-17/32), refused_story,
refused_occupancy (EC-22), the breakout-day boundary on both sides (EC-34),
and one conductor-level run proving a watch reaches the published
market-context block (the sink was previously touched only by fakes)."""
import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha import evaluation
from engine_alpha.evaluation import (
    PP_WIRE_STATUS,
    species_watch,
    wire_status,
)
from engine_alpha.structure.context.power_play import PP_STATES
from core.calibration.replay import flag_capture

# The census battery's hand-reasoned pole frame (self-contained copy — Beck's
# readability rule): peak 439 (High 100.5), AR 446 (Low 88.0), shelf from 447,
# breakout = first close > 100.5. ``shelf_bars`` parametrizes the shelf length:
# 18 -> breakout at 465 (after the species clock's first legal look 460),
# 8  -> breakout at 455 (BEFORE it: the refused_clock wall).
_PEAK, _AR = 439, 446


def _pole_frame(shelf_bars=18, tail=10):
    brk = 447 + shelf_bars
    n = brk + 1 + tail
    closes = np.empty(n)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:447] = np.linspace(98, 88.5, 7)
    shelf = np.arange(447, brk)
    closes[447:brk] = np.where(shelf % 2 == 0, 90.0, 92.0)
    # The breakout close clears the RULED departure wall decisively: the
    # alternating shelf's ATR10 is exactly 2.5, so the wall sits at
    # 100.5 + 2.5 = 103.0 — a 103.0 close is a knife-edge, 104.0 departs.
    closes[brk] = 104.0
    closes[brk + 1:] = 103.5
    idx = pd.bdate_range("2024-06-03", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes + 0.5,
                         "Low": closes - 0.5, "Close": closes,
                         "Volume": 200_000.0}, index=idx)


def _drift_frame(n=300):
    closes = 50 + 15 * np.arange(n) / (n - 1)
    idx = pd.bdate_range("2024-06-03", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes + 0.4,
                         "Low": closes - 0.4, "Close": closes,
                         "Volume": 200_000.0}, index=idx)


# ── the composed twin ───────────────────────────────────────────────────────

def test_twin_flag_off_is_exactly_the_base():
    df = _drift_frame(60)                       # refuses baseline fast
    with flag_capture(NEAR_MISS_LANE_ENABLED=False,
                      POWER_PLAY_PRESET_ENABLED=False):
        base, row, stats = evaluation.evaluate_ticker_with_power_play("X", df)
        assert base == evaluation._evaluate_ticker("X", df)
    assert row is None and stats == {}


def test_twin_swallows_and_counts_a_lane_failure(monkeypatch):
    df = _drift_frame(60)

    def boom(_df):
        raise RuntimeError("lane bug")
    monkeypatch.setattr(evaluation, "species_watch", boom)
    with flag_capture(NEAR_MISS_LANE_ENABLED=False,
                      POWER_PLAY_PRESET_ENABLED=True):
        base, row, stats = evaluation.evaluate_ticker_with_power_play("X", df)
        assert base == evaluation._evaluate_ticker("X", df)   # never a drop
    # The error path keeps its counter AND the elapsed time — the EC-8 cost
    # instrument must not undercount exactly the failing tickers.
    assert row is None and stats["pp_errored"] == 1
    assert stats["pp_eval_ms"] >= 0


def test_twin_refuses_to_publish_on_a_crashed_base_eval(monkeypatch):
    """A crashed base evaluation is an UNKNOWN verdict, not a no-fire: the
    watch row must not stamp a definitive-looking status on a night the
    paying read never finished (2026-08-25 sweep — the near-miss lane's own
    incomplete-evidence refusal, applied to the species register)."""
    df = _drift_frame(60)
    monkeypatch.setattr(evaluation, "_evaluate_ticker",
                        lambda *a, **k: evaluation.EVAL_ERROR)
    with flag_capture(NEAR_MISS_LANE_ENABLED=False,
                      POWER_PLAY_PRESET_ENABLED=True):
        base, row, stats = evaluation.evaluate_ticker_with_power_play("X", df)
    assert base is evaluation.EVAL_ERROR
    assert row is None and stats == {"pp_base_errored": 1}


def test_twin_composes_with_the_near_miss_triple():
    df = _drift_frame(60)
    with flag_capture(NEAR_MISS_LANE_ENABLED=True,
                      POWER_PLAY_PRESET_ENABLED=True):
        base, _row, _stats = evaluation.evaluate_ticker_with_power_play("X", df)
    assert isinstance(base, tuple) and len(base) == 3   # the near-miss triple


# ── the bounded watch's wall verdicts ───────────────────────────────────────

def test_wire_vocabulary_is_pinned_exactly():
    # Widening PP_WIRE_STATUS must be a CONSCIOUS two-sided diff: the JS
    # label mirror (webapp/frontend/src/shared/presentation/wireVocabulary.js,
    # POWER_PLAY_STATUS_LABELS) moves in the SAME change. A membership-only
    # assertion let a server-side widening ship with every gate green and
    # the operator's first sight of it a raw slug (2026-08-17 review,
    # Dodds/Fowler).
    assert PP_WIRE_STATUS == ("fired", "watched_ungraded", "not_watched_clock",
                              "refused_occupancy", "refused_story")


def test_watch_reads_the_episode_and_types_the_occupancy_refusal():
    # PINNED end-to-end (2026-08-17 review, findings 3/5): the alternating
    # two-level shelf's own pairs die at respect/occupancy in the episode's
    # roots' cascades, so the scoped typing says refused_occupancy — the old
    # flat any-record scan read a trace level that carries no verdicts at
    # all, so this state was typed blindly for EVERY non-elected read.
    watch, stats = species_watch(_pole_frame(shelf_bars=18))
    assert stats == {"pp_watched": 1, "pp_refused_occupancy": 1}
    assert watch is not None
    assert watch["state"] == "refused_occupancy"
    assert watch["clock"] == settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"]
    idx = _pole_frame(18).index
    assert watch["fields"]["climax_date"] == str(idx[_PEAK].date())
    assert watch["fields"]["ar_date"] == str(idx[_AR].date())


def test_short_shelf_hits_the_clock_wall_without_an_election():
    # RULED clock 8 (2026-08-18): first legal look = max(446+8+4, 439+8+5)
    # = 458; an 8-bar shelf breaks out at 455 — the wall itself is the
    # finding. (A re-ruled clock re-pins this arithmetic deliberately.)
    df = _pole_frame(shelf_bars=8)
    watch, stats = species_watch(df)
    assert watch is not None and watch["state"] == "refused_clock"
    assert stats.get("pp_refused_clock") == 1
    assert watch["payload"]["first_legal_look"] == str(df.index[458].date())


def test_too_young_to_watch_is_pending_not_a_record():
    df = _pole_frame(shelf_bars=18).iloc[:458]      # ends before bar 458
    watch, stats = species_watch(df)
    assert watch is None
    assert stats == {"pp_watched": 1, "pp_pending": 1}


def test_no_pole_no_watch():
    assert species_watch(_drift_frame()) == (None, {})


# ── the election half, END TO END on hand-reasoned tape (findings 3/11) ─────
# The admitting shape (probed live 2026-08-17): full-range traversals with
# the bars' bodies respecting their own pivot rails (hl 0.15 — rails anchor
# at pivot CLOSES), an R-engaged hang ENDING AT THE EVAL EDGE (the story
# admission reads pdf[:-skip], so its last bar must be the hang), and the
# pullback-and-rest LPS with drying volume in the 5-bar skip zone the
# admission never sees (read_structure needs box + LPS to return a setup).

_TRAV = [90.0, 91.5, 93.0, 91.4, 89.8, 91.2, 92.8, 91.3, 89.9, 91.4]
_HANG = [92.9, 92.8, 92.9, 93.0, 93.0]
_DIP = [90.6, 90.0, 89.9, 89.9, 89.9]
_VOLS = ([200e3] * 10 + [180e3, 160e3, 140e3, 130e3, 120e3]
         + [110e3, 100e3, 90e3, 85e3, 80e3])


def _species_frame(shelf=None, vols=None, hl=0.15):
    shelf = np.array(_TRAV + _HANG + _DIP if shelf is None else shelf, float)
    n = 447 + len(shelf)
    closes = np.empty(n)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:447] = np.linspace(98, 88.5, 7)
    closes[447:] = shelf
    spread = np.full(n, 0.5)
    spread[447:] = hl
    vol = np.full(n, 200_000.0)
    vol[447:] = _VOLS if vols is None else vols
    idx = pd.bdate_range("2024-06-03", periods=n)
    return pd.DataFrame({"Open": closes, "High": closes + spread,
                         "Low": closes - spread, "Close": closes,
                         "Volume": vol}, index=idx)


def test_the_species_read_admits_the_holding_shelf_end_to_end():
    # EC-17: the REAL cascade elects under the species flags — no builder in
    # isolation, no monkeypatched rung. EC-32: the measured facts are
    # INPUT-TIED — recomputed from the frame's own bars + the elected rails.
    df = _species_frame()
    watch, stats = species_watch(df)
    assert watch is not None and watch["state"] == "admitted_dark"
    assert stats == {"pp_watched": 1, "pp_admitted_dark": 1}
    elected = watch["payload"]["elected"]
    fields = watch["fields"]
    assert fields["shelf_start_date"] == elected["open"]
    # The elected shelf opens within the admission tolerance of the AR.
    open_pos = int(df.index.get_indexer([pd.Timestamp(elected["open"])])[0])
    assert abs(open_pos - _AR) <= 5
    # Input-tied: the thirds quantization recounted from the frame's closes
    # against the elected rails (the frame is under the 2y trim, so eval
    # positions ARE raw positions here).
    R, S = elected["R"], elected["S"]
    shelf_closes = df["Close"].iloc[open_pos:]
    assert fields["shelf_bars"] == len(shelf_closes)
    assert fields["lower_third_bars"] == int(
        (shelf_closes <= S + (R - S) / 3.0).sum())
    assert 0 < fields["zone_coverage"] < 1 and fields["zone_collided"] == 0


def test_mutation_probe_an_unengaged_edge_cannot_admit():
    # EC-32's teeth, proven once: sink the hang (the story admission's edge
    # bars) to mid-box and the SAME frame must stop admitting — an
    # input-blind admission would stay green.
    shelf = _TRAV + [91.0, 91.1, 91.0, 91.1, 91.0] + _DIP
    watch, _stats = species_watch(_species_frame(shelf=shelf))
    assert watch is None or watch["state"] != "admitted_dark"


def test_a_terminal_drift_shelf_is_refused_story():
    # PINNED (EC-22): a tight top-hugging band whose zones collide reads as
    # one open S visit + one open R visit — terminal S drift, the not-a-hang
    # — and the episode's own roots' cascades name the story stage.
    shelf = [90.5, 91.5, 92.0, 91.8, 92.1, 91.6, 92.0, 91.9, 92.1, 91.7,
             92.0, 91.8, 92.1, 91.9, 92.0, 92.1, 91.9, 92.0, 92.1]
    watch, stats = species_watch(_species_frame(
        shelf=shelf, vols=[200e3] * len(shelf), hl=0.5))
    assert watch is not None and watch["state"] == "refused_story"
    assert stats == {"pp_watched": 1, "pp_refused_story": 1}


def test_breakout_on_the_first_legal_look_refuses_exactly(monkeypatch):
    # EC-34: the frozen MAN fact is an EQUALITY (first look = breakout day)
    # and the wall comparison is >= — pin BOTH sides of the boundary so a
    # one-bar flip cannot inflate watchability with the suite green.
    on_the_day = _pole_frame(shelf_bars=11)     # brk 458 == first look 458
    watch, stats = species_watch(on_the_day)
    assert watch is not None and watch["state"] == "refused_clock"
    assert watch["payload"]["first_legal_look"] == watch["payload"]["breakout"]
    one_later = _pole_frame(shelf_bars=12)      # brk 459 > first look 458
    watch, _ = species_watch(one_later)
    assert watch is None or watch["state"] != "refused_clock"


# ── the conductor publishes the lane (finding 3's plumbing half) ────────────

class _InlineFuture:
    def __init__(self, fn, *args):
        try:
            self._result = fn(*args)
            self._error = None
        except BaseException as e:      # pragma: no cover - surfaced in result()
            self._error = e

    def result(self):
        if self._error is not None:
            raise self._error
        return self._result


class _InlinePool:
    """Executes submits inline: a SPAWNED worker re-imports settings and
    loses the in-test flag flip, so the pool — and only the pool — is faked;
    the worker function is the real composed twin."""

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *args):
        return _InlineFuture(fn, *args)


def test_conductor_publishes_the_watch_to_market_context(monkeypatch):
    # The sink was previously touched only by fakes (2026-08-17 review,
    # finding 3): run the REAL run_screener + worker ladder on an admitting
    # frame and assert the row lands in the published block with its stats
    # and the phase timer — and that the dark fundamentals pass leaves NO
    # phantom phase (finding 7's regression pin).
    import core.pipeline.screening.screener as screener_module

    df = _species_frame()

    class _Provider:
        def fetch(self, tickers, universe=None):
            return df       # single-ticker fetches return the FLAT frame

    monkeypatch.setattr(screener_module, "ProcessPoolExecutor", _InlinePool)
    monkeypatch.setattr(screener_module, "as_completed",
                        lambda futures: iter(list(futures)))
    monkeypatch.setattr(screener_module, "get_tickers", lambda *a, **k: ["AAA"])
    monkeypatch.setattr(screener_module, "get_provider", lambda: _Provider())
    monkeypatch.setattr(
        screener_module, "get_market_context",
        lambda data, frames, *a, **k: {"spy_6m_return": 0.0, "breadth_pct": 1.0})
    monkeypatch.setattr(screener_module, "persist_scan_metrics",
                        lambda metrics, universe=None: None)

    with flag_capture(POWER_PLAY_PRESET_ENABLED=True,
                      NEAR_MISS_LANE_ENABLED=False):
        _results, _data, _tickers, market_context = screener_module.run_screener()

    block = market_context["power_play"]
    assert [r["ticker"] for r in block["candidates"]] == ["AAA"]
    row = block["candidates"][0]
    assert row["status"] in ("fired", "watched_ungraded")   # admitted, mapped
    assert row["elected"]["open"]                           # the facts rode
    assert block["counts"]["pp_watched"] == 1
    assert block["counts"]["pp_admitted_dark"] == 1
    metrics = market_context["_scan_metrics"]
    assert "power_play_lane_worker_s" in metrics["phases_s"]
    assert "fundamentals" not in metrics["phases_s"]        # no phantom phase
    assert "fundamentals" not in market_context


# ── the wire vocabulary (derived server-side, one registry) ─────────────────

def test_wire_status_is_the_closed_set():
    assert wire_status("admitted_dark", fired=True) == "fired"
    assert wire_status("admitted_dark", fired=False) == "watched_ungraded"
    assert wire_status("refused_clock", fired=False) == "not_watched_clock"
    assert wire_status("refused_story", fired=False) == "refused_story"
    for state in PP_STATES:
        for fired in (True, False):
            assert wire_status(state, fired) in PP_WIRE_STATUS
