# HTF context — edge verdict (2026-07-04)

**Question:** should the higher-timeframe context reads (`htf_w_reaccum`, `htf_w_daily_nested`,
weekly/monthly Stage-2) enter the *score*, or stay measure-only annotations?

**Verdict: do NOT score HTF. Keep it exactly as-is — archived + surfaced as the "⬆ HTF Re-accum"
chip, never a score term or veto.** The operator's intuition holds: *there is a reason we gate the
universe the way we do*, and that gate already forces the HTF-uptrend alignment an HTF score term
would try to reward. This is a read off already-collected data — not a deferral for more maturation.

## The data (read-only query, `webapp/backend/trading_journal.db`; 1,231 HTF-carrying fires,
scan dates 2026-01-16 → 2026-07-03)

| field | value | share |
|---|---|---|
| `htf_w_stage2` = 1 | 1,149 / 1,231 | **93.3 %** |
| `htf_w_trend_state` = "up" | 1,149 / 1,231 | 93.3 % |
| `htf_w_trend_state` = "down" | **0** | **0.0 %** |
| `htf_m_stage2` = 1 | 981 / 1,231 | 79.7 % |

Of the 909 fires that pass the daily MA-stack, **901 (99.1 %) are also weekly-Stage-2.** A feature
that is true 93 % of the time — and is a near-tautology of an existing gate — has almost no variance
for a score to exploit.

## Why it's redundant by construction

The Phase-1 baseline gate (`core/pipeline/evaluation.py:92-96`, `config/settings.py:9-11`) admits a
name only if `Close ≥ MIN_PRICE` **and** `Close > SMA_50` **and** `Close > SMA_200` **and**
`yearly_return > −0.20`. Requiring price above *both* the rising 50- and 200-day averages is nearly
the daily equivalent of a Weinstein weekly Stage-2. So the universe we score is *already* the
HTF-uptrend cohort — zero fires are weekly-downtrend. There is no HTF-downtrend population left for an
HTF term to discriminate against.

## The apparent `reaccum` edge does not survive scrutiny

At first glance `htf_w_reaccum=1` looks predictive (mean abnormal 20-bar return **+1.38 % vs −0.60 %**,
win 65 % vs 47 %). It is a confounded, single-cohort artifact:

- **One overlapping week, one regime.** All 784 matured HTF rows fall on scan dates 2026-06-21…06-27,
  every one `regime_state = UNDER_PRESSURE` (HTF context began being computed ~06-21; only that first
  week has crossed the 20-bar forward horizon; `fwd_return_20d` non-null for just 32 rows). This is
  the same single-cohort trap flagged in `docs/edge_read_2026-06-30.md:175-181`.
- **The lift is NOT from the HTF uptrend.** Decomposing `reaccum` (= `in_consol AND stage2`):
  `in_consol=1 & stage2=1` → +1.38 %; `in_consol=1 & stage2=0` → **+1.36 %** (the uptrend flag is
  inert); `in_consol=0 & stage2=1` → −0.73 %. 100 % of the separation is "a weekly box exists"
  (`in_consol`), and since 93 % of fires are already Stage-2, `reaccum ≈ in_consol`.
- **`in_consol` is a proxy for base length, which is already scored.** `in_consol=1` setups have
  median base_length 51 vs 29 — and `score_base_age` already rewards that. They also carry a *lower*
  median engine score (105.3 vs 113.7), so the engine is not under-crediting them; there is no gap for
  an HTF term to fill.
- **`daily_nested` points the wrong way.** `daily_nested=1` returned **worse** (+0.27 % / 54 % win)
  than `daily_nested=0` (+1.85 % / 68 % win) — the original "best daily setup is one nested inside the
  HTF box" thesis is contradicted, not supported, by the only data we have (n=63 vs 148, one week).

## Consequences for open work

- **TA-score rework:** do **not** add an HTF/`reaccum` term to the Wave-1 tag-fold. HTF stays out of
  the number. (The design's `weekly_reaccum` candidate is retired by this read.)
- **HTF track:** keep `HTF_CONTEXT_ENABLED = True` as a measure-only archive + chip. Re-open the
  scoring question only if a genuinely multi-regime matured archive (earliest defensible ~late-Aug 60d
  read, or a 20d read spanning visibly different tape) later shows `reaccum` separating *after*
  controlling for base length and regime — which the current data gives no reason to expect.

## Evidence map

- Population / definition: `core/structure/htf.py:203,248-251`; `config/settings.py:562`;
  `webapp/backend/archive_models.py:249-267`; `core/archive/result_adapter.py:19`.
- Universe gate: `core/pipeline/evaluation.py:92-96`; `config/settings.py:9-11`.
- Audit tool (measures only, no edge stat): `tools/htf_audit.py:65-93`.
- Prior single-cohort read: `docs/edge_read_2026-06-30.md:17,37,175-181`.
