# June 29 Edge Read Pre-Registration

Date written: 2026-06-23

This note freezes the prior before the first live 20-trading-day cohort matures.
The June 29 read is a confirmation check of the screener's standalone edge, not
a tuning session.

## Scope

Command:

```powershell
python -m tools.edge_report --date 20260629
```

Default scope is `source='screener'`, excluding seed/manual rows. The runner first
matures newly eligible forward returns, then writes `docs/edge_read_20260629.md`
using the existing archive analysis report.

## Prior Predictions

Based on the 2026-06-23 dry run and the already-labelled durable/barrier outcomes:

- `score_rs_bonus`: predicted HARMFUL.
- `score_base_age`: predicted BENEFICIAL.
- Other sub-scores: predicted INERT unless the fresh 20d target shows otherwise.
- Tightness prime-directive test: open; June 29 can inform it but should not be
  treated as final multi-regime proof.
- HTF re-accumulation, daily-nested HTF, and `score_traversal_quality`: not
  testable in the June 29 cohort if the matured subset remains the 2026-05-31 to
  2026-06-07 live cohort.

## Decision Rule

A sub-score is considered confirmed only if:

- The primary `signal_edge` verdict is trustworthy under the report's existing
  sample gates.
- At least two populated targets are decisive beyond the noise floor.
- Those decisive targets agree in sign, with no decisive target flipping the
  other way.

Confirmation authorizes only drafting a re-weight proposal. It does not authorize
changing scoring weights. Any scoring change remains a separate, reviewed step
with shadow-diff verification.

If `durable_win` and `fwd_return_20d` disagree, the signal is fragile and stays
parked. If `fwd_return_20d` is still unpopulated, the June read is not mature.

## Known Limits

- The first 20d confirmation cohort is expected to be scans from roughly
  2026-05-31 through 2026-06-07.
- That cohort is expected to be a single bull-regime sample, not a multi-regime
  robustness test.
- HTF tags and traversal-quality cohorts are expected to mature later in July.
- Existing over-long `base_length` outliers are noted but not fixed in this read.

## Outcome Recording

After running the command, record:

- Matured subset size and scan-date span.
- Regime mix.
- Which sub-scores were confirmed, fragile, or still pending.
- Any proposed follow-up, without changing weights in the same step.
