"""The conductor fundamentals post-pass (program Task 12): flag-off is None +
zero provider calls, the as-of is explicit per ticker (the ungated legacy path
can never feed an archived write), attempted-vs-populated counters distinguish
"flag off" from "all failed", the reporting-event cache reuses while no new
filing can exist and refetches after, provider failure leaves the paying scan
untouched, and the in-worker attach point is gone. Post-review additions
(2026-08-17): a vendor outage is never cached as a filing-gated fact, a
malformed cache entry is dropped loudly and the cached replay is
namespace-restricted, and one poisoned ticker costs itself — never the loop."""
import copy
import inspect
import json

import pandas as pd
import pytest

from core.fundamentals import post_pass


def _income(ends, eps, revenue):
    return pd.DataFrame([eps, revenue],
                        index=["Diluted EPS", "Total Revenue"],
                        columns=pd.to_datetime(ends))


class _FakeProvider:
    def __init__(self, stmt=None, next_earnings=None, fail=False):
        self.stmt, self.next_earnings, self.fail = stmt, next_earnings, fail
        self.calls = []

    def get_income_stmt(self, ticker, quarterly=True):
        self.calls.append("stmt")
        if self.fail:
            raise RuntimeError("vendor down")
        return self.stmt

    def get_earnings_dates(self, ticker, limit=12):
        self.calls.append("earnings")
        return None

    def earnings_date(self, ticker):
        self.calls.append("next")
        return self.next_earnings


def _prices(end="2026-04-10", periods=300):
    idx = pd.bdate_range(end=end, periods=periods)
    return pd.DataFrame({"Close": [10.0] * periods}, index=idx)


def _provider():
    ends = ["2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30",
            "2025-03-31", "2024-12-31"]
    return _FakeProvider(
        stmt=_income(ends, [9.99, 1.20, 1.10, 1.05, 1.00, 1.00],
                     [200.0, 120.0, 118.0, 115.0, 100.0, 100.0]),
        next_earnings="2026-05-01")


def _run(results, frames, provider, tmp_path, monkeypatch, *, fund=True):
    from config import settings
    monkeypatch.setattr(settings, "FUNDAMENTALS_ENABLED", fund, raising=False)
    monkeypatch.setattr(settings, "RS_LINE_ENABLED", False, raising=False)
    return post_pass.attach_fundamentals_post_pass(
        results, frames, provider=provider,
        cache_path=str(tmp_path / "fund_cache.json"))


def test_flags_off_is_none_and_untouched(tmp_path, monkeypatch):
    provider = _provider()
    results = [{"Ticker": "AAA", "Score": 1.0}]
    before = copy.deepcopy(results)
    out = _run(results, {"AAA": _prices()}, provider, tmp_path, monkeypatch,
               fund=False)
    assert out is None
    assert results == before
    assert provider.calls == []
    assert not (tmp_path / "fund_cache.json").exists()


def test_fields_attach_with_explicit_as_of_and_counters(tmp_path, monkeypatch):
    seen = {}
    from core.fundamentals import metrics as metrics_mod
    real = metrics_mod.compute_metrics

    def spy(ticker, as_of=None, provider=None):
        seen["as_of"] = as_of
        return real(ticker, as_of=as_of, provider=provider)
    monkeypatch.setattr(metrics_mod, "compute_metrics", spy)

    provider = _provider()
    frames = {"AAA": _prices()}
    results = [{"Ticker": "AAA", "Score": 1.0}]
    counts = _run(results, frames, provider, tmp_path, monkeypatch)
    # The as-of is the ticker's OWN last bar — explicit, never None.
    assert pd.Timestamp(seen["as_of"]) == frames["AAA"].index[-1]
    # The filing-gated YoY reads the latest AVAILABLE quarter (2025-12-31).
    assert results[0]["_fund_eps_growth_yoy"] == pytest.approx(0.20)
    assert results[0]["_days_to_earnings"] == 21
    assert "_rs_trailing_return" in results[0]
    assert counts["attempted"] == 1 and counts["populated"] == 1
    assert counts["failed"] == 0 and counts["cache_hits"] == 0


def test_missing_as_of_is_a_loud_refusal_not_a_call(tmp_path, monkeypatch):
    provider = _provider()
    results = [{"Ticker": "AAA", "Score": 1.0}]
    counts = _run(results, {"AAA": _prices().iloc[:0]}, provider, tmp_path,
                  monkeypatch)
    assert counts["refused_no_as_of"] == 1
    assert counts["attempted"] == 0
    assert provider.calls == []                # the ungated path never runs
    assert "_fund_eps_growth_yoy" not in results[0]


def test_provider_failure_is_contained_and_counted(tmp_path, monkeypatch):
    provider = _FakeProvider(fail=True, next_earnings=None)
    results = [{"Ticker": "AAA", "Score": 1.0}]
    before = copy.deepcopy(results)
    counts = _run(results, {"AAA": _prices()}, provider, tmp_path, monkeypatch)
    assert counts == {"attempted": 1, "populated": 0, "cache_hits": 0,
                      "refused_no_as_of": 0, "rs_attempted": 0,
                      "rs_populated": 0, "errored": 0, "failed": 1}
    # "attempted, all failed" is VISIBLE — and the paying row is untouched
    # except the price-local trailing return (no vendor involved).
    results[0].pop("_rs_trailing_return", None)
    assert results == before


def test_reporting_event_cache_reuses_then_refetches(tmp_path, monkeypatch):
    provider = _provider()
    frames = {"AAA": _prices()}

    _run([{"Ticker": "AAA"}], frames, provider, tmp_path, monkeypatch)
    calls_after_first = len(provider.calls)

    row = {"Ticker": "AAA"}
    counts = _run([row], frames, provider, tmp_path, monkeypatch)
    assert len(provider.calls) == calls_after_first     # no new filing: no call
    assert counts["cache_hits"] == 1 and counts["populated"] == 1
    assert row["_fund_eps_growth_yoy"] == pytest.approx(0.20)
    assert row["_days_to_earnings"] == 21               # recomputed, not stale

    # Past the cached next-earnings date a new filing may exist: refetch.
    late = {"AAA": _prices(end="2026-05-05")}
    _run([{"Ticker": "AAA"}], late, provider, tmp_path, monkeypatch)
    assert len(provider.calls) > calls_after_first


def test_vendor_outage_is_never_cached_as_a_fact(tmp_path, monkeypatch):
    # Metrics fail but the earnings-date probe succeeds: the pre-review code
    # cached the empty family until the next earnings date — one throttled
    # night froze tickers at "absent" for a quarter. Now nothing is cached
    # and the healed vendor is refetched (2026-08-17 review, findings 2/6).
    class _OutageProvider(_FakeProvider):
        def get_income_stmt(self, ticker, quarterly=True):
            self.calls.append("stmt")
            raise RuntimeError("429")

    outage = _OutageProvider(next_earnings="2026-05-01")
    counts = _run([{"Ticker": "AAA"}], {"AAA": _prices()}, outage, tmp_path,
                  monkeypatch)
    assert counts["populated"] == 0 and counts["failed"] == 1

    healed = _provider()
    row = {"Ticker": "AAA"}
    counts = _run([row], {"AAA": _prices()}, healed, tmp_path, monkeypatch)
    assert counts["cache_hits"] == 0            # the outage was NOT a fact
    assert counts["populated"] == 1             # the alarm can clear
    assert row["_fund_eps_growth_yoy"] == pytest.approx(0.20)


def test_malformed_cache_is_dropped_and_replay_is_namespaced(tmp_path, monkeypatch):
    # The cache lives in output/ — the default tool-report directory — so it
    # is validated per entry (EC-20/assume breach) and the cached replay may
    # only touch the _fund_ namespace: no on-disk content can overwrite a
    # paying row's own fields (2026-08-17 review, Hunt).
    (tmp_path / "fund_cache.json").write_text(json.dumps({
        "BAD": "not-a-dict",
        "EVIL": {"as_of": "2026-04-01", "next_earnings": "2026-05-01",
                 "fund_fields": {"Score": 0.0,
                                 "_fund_eps_growth_yoy": 0.11}},
    }), encoding="utf-8")
    row = {"Ticker": "EVIL", "Score": 55.0}
    counts = _run([row], {"EVIL": _prices()}, _provider(), tmp_path,
                  monkeypatch)
    assert counts["cache_dropped"] == 1         # BAD refused loudly at load
    assert counts["cache_hits"] == 1            # EVIL's shape is legal...
    assert row["Score"] == 55.0                 # ...but only _fund_ replays
    assert row["_fund_eps_growth_yoy"] == pytest.approx(0.11)


def test_one_poisoned_ticker_costs_itself_not_the_loop(tmp_path, monkeypatch):
    # Per-ticker containment (EC-20): a frame that raises on access is a
    # counted skip; the NEXT ticker still populates and the pass returns.
    class _Boom:
        columns = ["Close"]

        def __len__(self):
            return 300

        @property
        def index(self):
            raise RuntimeError("poisoned frame")

    rows = [{"Ticker": "BOOM"}, {"Ticker": "AAA"}]
    counts = _run(rows, {"BOOM": _Boom(), "AAA": _prices()}, _provider(),
                  tmp_path, monkeypatch)
    assert counts["errored"] == 1
    assert rows[1]["_fund_eps_growth_yoy"] == pytest.approx(0.20)


def test_the_in_worker_attach_point_is_gone():
    from engine_alpha import evaluation
    assert not hasattr(evaluation, "_attach_advisory_metadata")
    src = inspect.getsource(evaluation._run_guarded_chain)
    assert "per_ticker_advisory" not in src
    assert "_attach_advisory_metadata" not in src
