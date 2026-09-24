"""Contract tests for core.archive.result_adapter.seed_row_from_result.

The adapter maps the canonical live-evaluation result (`_build_live_result`, `_`-prefixed)
to the unprefixed key shape the seed archive writer consumes. These tests pin:

1. The mapping RULES (strip leading underscore + explicit renames) — fast, no engine.
2. The real EQUIVALENCE: on the frozen shadow fixture, the live chain (run with
   breadth=None, matching the seed path which has no live breadth at replay time) and the
   seed twin `_evaluate_at_date` produce the same values for every key the writer reads.
   This is also the pre-check for the A3 "_run_eval_chain" extraction: if live(breadth=None)
   already equals seed today, collapsing them onto one chain is provably lossless.
"""
import math

from core.archive.result_adapter import seed_row_from_result


def _close(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def test_adapter_strips_leading_underscore():
    out = seed_row_from_result(
        {"_lps_descent_frac": 0.42, "_bin_a_bars": 7,
         "_stage2_trend_pass": 1, "_htf_w_ma30": 1.5}
    )
    assert out["lps_descent_frac"] == 0.42
    assert out["bin_a_bars"] == 7
    assert out["stage2_trend_pass"] == 1
    assert out["htf_w_ma30"] == 1.5  # htf_archive_values(..., prefixed=False) reads this


def test_adapter_applies_explicit_renames():
    canon = {
        "Setup": "LPS", "Tier": "A", "Score": 95, "Current Price": 12.3,
        "Box Width": 0.1, "Touches": 6, "ATR Ratio": 0.8, "Breach Days": 0,
        "_R": 13.0, "_S": 11.0, "_base_len": 40, "_lps_len": 3,
        "_r_anchor_bar": 5, "_s_anchor_bar": 2, "_bars_since_BC": 50,
        "_vol_contraction": 0.7, "_tightness_ratio": 0.9, "_sub_scores": {"box_tightness": 1},
    }
    out = seed_row_from_result(canon)
    assert out["setup_type"] == "LPS" and out["tier"] == "A" and out["score"] == 95
    assert out["current_price"] == 12.3 and out["box_width"] == 0.1
    assert out["touches"] == 6 and out["atr_ratio"] == 0.8 and out["breach_days"] == 0
    assert out["r_level"] == 13.0 and out["s_level"] == 11.0
    assert out["base_length"] == 40 and out["lps_length"] == 3
    assert out["r_anchor"] == 5 and out["s_anchor"] == 2 and out["bars_since_BC"] == 50
    # strip-pass fields the writer also reads
    assert out["vol_contraction"] == 0.7 and out["tightness_ratio"] == 0.9
    assert out["sub_scores"] == {"box_tightness": 1}


def test_adapter_does_not_mutate_input():
    canon = {"Setup": "LPS", "_R": 1.0}
    seed_row_from_result(canon)
    assert canon == {"Setup": "LPS", "_R": 1.0}


def test_parent_is_inner_box_is_always_false():
    """The parent box is never itself 'inner' (_structure_to_boxes slot 11 = False), so
    structure_ctx['is_inner_box'] is False on BOTH live and seed by construction — the
    live/seed convergence on this flag is inert (locks finding A of the eval unify)."""
    from tools.shadow_diff import _load_fixture
    from engine_alpha.evaluation import _prepare_eval_frame, _resolve_structure_context

    frames, scalars = _load_fixture()
    checked = 0
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        prepared = _prepare_eval_frame(df)
        if prepared is None:
            continue
        ctx = _resolve_structure_context(prepared["df"], prepared["latest"])
        if ctx is None:
            continue
        assert ctx["is_inner_box"] is False, f"{ticker}: parent is_inner_box must be False"
        checked += 1
    assert checked > 0, "fixture produced no resolvable structure contexts"


def test_live_breadth_none_equals_seed_on_fixture():
    """The load-bearing equivalence: live(breadth=None) ≡ seed on the frozen fixture,
    re-keyed through the adapter. Proves the A3 extraction will be lossless."""
    from tools.shadow_diff import _load_fixture
    from engine_alpha.evaluation import _evaluate_ticker
    from core.archive.seed import _evaluate_at_date

    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))

    compared = 0
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        live = _evaluate_ticker(ticker, df, spy_6m, None)  # breadth=None to match seed
        seed = _evaluate_at_date(df, spy_6m)
        # Both engines must agree on whether the setup fires.
        assert (live is None) == (seed is None), f"{ticker}: live/seed fire disagreement"
        if live is None:
            continue
        adapted = seed_row_from_result(live)
        # "Ticker" is the only ticker-dependent field; seed runs the chain with
        # ticker="" so exclude that label from the numeric-equivalence comparison.
        mismatches = {
            k: (seed[k], adapted.get(k))
            for k in seed
            if k != "Ticker" and not _close(seed[k], adapted.get(k))
        }
        assert not mismatches, f"{ticker}: adapter/seed mismatch on {list(mismatches)[:8]}"
        compared += 1

    assert compared > 0, "fixture produced no comparable firing setups"
