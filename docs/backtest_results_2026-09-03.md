# Signal-edge results — 2026-09-03

The verdict the parked branch was built to produce, run for the first time on the live archive.
Supersedes the preliminary `backtest_results_2026-07-07.md` (which predates the base-rate model).

**Ruling that commissioned it:** operator, 2026-09-01 asks sweep — *revive it, run and report; no
engine change either way.*

**Basis.** 4,078 de-duplicated episodes, 2026-01-16 → 2026-09-02, read from a COPY of the live
archive (`webapp/backend/trading_journal.db`, 41.9 MB) — the live file was never opened. Null model
fed by `tools/build_universe_returns.py`: 50,842 rows over 31 matured scan dates.

---

## The headline: no measurable edge over a random same-day pick

| | median 20-day MFE |
|---|---|
| screener fires (n=2,438) | **+7.5%** |
| random same-count draw from that day's eligible universe | **+7.4%** |
| **edge** | **+0.1%**, 95% CI **[−0.1%, +0.4%]**, permutation p = **0.203** (2,000 draws) |

Per tier, every interval straddles zero — and the ordering is not the tier ordering:

| tier | edge | 95% CI | raw p | n |
|---|---|---|---|---|
| B | +0.4% | [−0.2%, +1.2%] | 0.144 | 420 |
| A | +0.2% | [−0.3%, +0.7%] | 0.214 | 860 |
| S | +0.0% | [−0.4%, +0.6%] | 0.479 | 1,127 |
| C | −0.3% | [−2.0%, +1.6%] | 0.590 | 31 |

**Benjamini-Hochberg across the 5 slices: nothing significant** (adjusted p 0.357 – 0.590).

### The sharpest finding: the tier ranking does not survive the base rate

Raw MFE ranks the way it should — **S +8.2% > A +5.9%**, barrier win rate **S 42.2% > A 38.2%**,
breakout rate **S 92.5% > A 87.2% > B 86.1% > C 80.6%**, monotonic on three independent measures.
Against the null that ordering **disappears**: S scores +0.0% and B +0.4%, all inside noise.

The natural reading is that the raw tier ranking substantially reflects *which names get picked* —
higher-MFE names generally — rather than a per-name edge over what was available that day. The
ranking is real as a description of the picks; it is not evidence of selection skill.

---

## What this does NOT say — stated because a null result invites over-reading

1. **It does not measure the strategy, only the screener.** The metric is max favorable excursion:
   what the setup made *available*. Realized R is deliberately excluded because the exit is the
   operator's and discretionary — including it would conflate the engine with the human.
2. **It does not price selectivity.** The screener reduces ~5,900 names to a nightly handful with a
   readable structure and an 89% breakout rate. Whether that beats a random draw on *attention cost*
   is a different question this harness never asks — and the 89% has **no base rate attached**, so
   it is not yet evidence either.
3. **Survivorship cuts toward the engine, not away.** The 5y cache holds only current survivors, so
   the eligible universe is missing later-delisted names (disproportionately losers). That inflates
   the null, making +0.1% a **conservative lower bound**. It does not rescue it to significance.
4. **One period, one regime.** Every fire in the archive is tagged BULLISH (n=3,982); there are zero
   neutral/downtrend observations, so the regime-segmented test cannot run at all. Per the standing
   ruling, bull-only is the *relevant* population (these are long setups in uptrends) — the live
   concern is **sample size and a single window**, not regime validity.
5. **No out-of-sample read yet.** 19 engine config versions are in-sample (n=3,019); the single
   out-of-sample version has 170 rows and **zero** matured, so OOS is n=0.

## What it does say

Within the population the operator actually trades, over eight months, **the engine's 20-day MFE is
statistically indistinguishable from picking the same number of eligible names at random that day.**
That is the question the program existed to answer, and it now has an answer rather than a plan.

---

## Reproducing it

```
python -m tools.research.build_universe_returns --out <scratch>/universe_returns.parquet
python -m tools.research.backtest_engine --universe <scratch>/universe_returns.parquet --json <scratch>/report.json
```

Both are read-only. `build_universe_returns` resolves the archive by `__file__`, so in a worktree it
reads that worktree's scratch DB — stage a **copy** of the live archive there, never the live file,
and restore the scratch DB afterwards.

## Owed to the operator

The measurement is complete; what to do about it is his ruling. The register row for this program
carries the ask.
