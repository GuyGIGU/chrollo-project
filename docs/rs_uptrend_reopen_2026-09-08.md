# The RS / uptrend demotion, re-examined 2026-09-08

Read-only measurement against the live archive, main at `f8b6101`. **This is a
Tested-DEAD row being re-opened**, which the repo's own rules say costs a full A/B cycle
and should not be done lightly. The justification is not "the canon has RS and we don't"
— that argument is forbidden and is not made here. It is that **the measurement which
killed it scored a criterion the operator does not trade**, and his own ruling names the
door.

- `decisions.md` Tested-DEAD: *"Scoring `rs` / `uptrend` — DEMOTED to 0 — Edge read
  2026-07-22 over 1977 episodes: actively harmful. Merged `fd7fe3b`; S-tier share
  51%→29%."* (2026-07-25)
- `decisions.md` ruling 2026-08-06: *"RS and uptrend stay demoted at 0 … **never
  re-inflated outside an operator A/B**."*

So the question this doc puts to him is not "flip it". It is **"is this enough to spend
the A/B your own ruling requires?"**

## What was measured, and what it was measured against

The Stage-1 classifier (`core/archive/analyze.signal_edge`) ranks each sub-score by its
rank-association with an outcome, and `EDGE_TARGETS` puts `durable_win` first and
`barrier_win` second. Both derive from `barrier_label`, which
`core/archive/outcomes.compute_barrier_events` resolves on **whichever barrier is touched
first** — a 2.5R / +15% target, or a stop at `s_level × 0.97`.

That means a name which dips through a mechanical stop three percent under support and
*then* runs is scored a **loss**. The operator does not use that stop; he manages exits by
eye in TWS. So the verdict "actively harmful" was returned against a rule he does not
trade.

## The measurement

Deduped episodes, screener basis (n = 4,169). Signals are the RAW archived columns —
`excess_return_6m` and `yearly_return` — because the sub-scores themselves have been
zero since the demotion.

**The two statistics disagree on identical rows.** Labelled rows only, by RS quartile:

| RS quartile | n | win rate | loss rate | P(MFE≥25%) | P(MFE≥40%) |
|---|---|---|---|---|---|
| RS-low | 433 | **47.3%** | 46.2% | 9.70% | 1.62% |
| 2 | 433 | 46.2% | 46.0% | 6.00% | 1.62% |
| 3 | 433 | 39.5% | 55.9% | 7.62% | 1.39% |
| RS-high | 433 | **37.6%** | **61.4%** | **16.17%** | **5.31%** |

High-RS names get stopped out *most* and reach the big moves *most*. The demotion is not
noise — the lower win rate is real. It is a real fact about a criterion that scores the
path, on a strategy that is paid for the destination.

**The direct evidence of the mechanism.** Among rows the archive labels `loss`, the share
that nevertheless reached +25%: RS-low 2.00%, Q2 0.50%, Q3 3.31%, **RS-high 5.64%**.
Twenty-eight rows are filed as losses and went on to +25% — and those twenty-eight are
**16.4% of every row in the archive that reached +25% at all**. One in six of the
archive's biggest winners is recorded as a failure.

**Decomposing the sign flip** (Spearman, `excess_return_6m`):

| | rho | p | n |
|---|---|---|---|
| A. `barrier_win`, labelled rows — the 2026-07-25 basis | −0.0417 | 0.061 | 2,015 |
| B. P(MFE≥25%), **the same labelled rows** | **+0.0808** | 0.00076 | 1,732 |
| C. P(MFE≥25%), all matured rows | +0.1023 | 6.9e-08 | 2,768 |
| D. P(MFE≥25%), only the rows the label-gate drops | +0.0524 | 0.092 | 1,036 |

**The flip is the TARGET, not the missing rows** — the sign reverses at step B, on
identical rows, before any row is added back. (The label-gate bias found in
[edge_denominator_2026-09-08.md](edge_denominator_2026-09-08.md) adds to it but is not the
cause.)

`yearly_return` reads BENEFICIAL on *every* target including the label-gated ones
(+0.139 vs `barrier_win`, p=0.00057, n=615) — on today's archive it does not look harmful
at all. n is thin and the column is only populated on 2,091 of 4,169 episodes.

**Incidentally, RS is the strongest predictor of resolution in the archive** —
Spearman(`excess_return_6m`, does-this-row-resolve-at-all) = **+0.2295, p=2.1e-34**. High-RS
setups *do something*. That is what drives them into the labelled subsample in the first
place.

## What this does NOT establish — read this before quoting the above

1. **I did not reproduce the original numbers.** The demotion cited corr −0.19 / −0.22 at
   n=1977; I measure −0.042 on today's 2,015 labelled episodes. Different cohort, and the
   original measured the *ramped sub-score* while these are the *raw signals*. The two
   measurements are not comparable, and the disagreement may be cohort, not method. A
   faithful reproduction is the first task of any A/B, not an optional extra.
2. **Nothing here shows that restoring the weights improves the ranking.** It shows the
   evidence for removing them scored the wrong criterion. Those are different claims.
3. **The cost is known and large**: the demotion moved S-tier share 51% → 29%. Restoring
   roughly doubles the S-tier count, which he would feel on every scan.
4. RS-high really does get stopped out more. If he *does* want the tier ordering to favour
   names that hold a tight stop, the original demotion is defensible on its own terms and
   this doc changes nothing.

## THE A/B RAN — 2026-09-08, same day. Verdict: leave the weights at zero.

The operator said go. All three legs ran. **Nothing was flipped, and the recommendation is
that nothing should be.**

### Leg 1 — the faithful reproduction

The pre-demotion cohort still carries real archived `score_rs_bonus` / `score_uptrend_bonus`
(mean 5.10 / 4.54, max 15.0 on 5,076 rows over 30 scan days). Deduped to episodes that is
**2,078** — against the original's cited 1,977. So their variable, their cohort:

| | vs `durable_win` (their target) | vs P(MFE≥25%), same rows |
|---|---|---|
| `score_rs_bonus` | **−0.1411** (p=1.1e-07) | **+0.0905** (p=3.8e-05) |
| `score_uptrend_bonus` | **−0.0906** (p=0.00069) | **+0.1497** (p=7.7e-12) |

**The sign reversal reproduces on their own data.** The original cited −0.22 / −0.19; I get
−0.141 / −0.091 — same sign and same verdict, about two-thirds the magnitude.

**And a finding that matters more than the reversal:** the tool's own noise floor on this
cohort is **0.150**, and −0.141 / −0.091 both sit *inside* it. Under `signal_edge`'s own
adequacy rule the correct verdict on the deduped pre-demotion cohort is **INERT, in both
directions** — the "actively harmful" call does not survive dedup. (The dedup docstring
already recorded that dedup moves rs from ~−0.20 to −0.18; on this cohort it moves further.)

### Leg 2 — does the restored ordering rank better?

The divisor is a constant within an ordering, so it cannot affect rank; this is a clean
head-to-head on 2,768 matured episodes, re-earning the two terms through the engine's own
`_ramp` at cap 15.

| ordering | top-decile P(MFE≥25%) | spread vs bottom | top-decile P(≥40%) | spread | ρ vs mfe_20d |
|---|---|---|---|---|---|
| current | 9.06% | 2.04x | 2.79% | 4.10x | +0.1208 |
| restored | **10.80%** | **2.63x** | **3.48%** | **5.12x** | **+0.1471** |

Better on every cut. **But a cluster bootstrap over scan days (2,000 resamples, days as the
cluster because rows within a day are not independent) does not establish it:**

- top-decile P(MFE≥25%): **+1.84pp, 95% CI [−0.35, +4.35]**, P(improves) 92.2%
- top-decile P(MFE≥40%): **+0.68pp, 95% CI [−0.66, +2.11]**, P(improves) 77.8%

Both intervals cross zero. The point estimate favours restoring every time; the evidence
does not clear the bar.

### Leg 3 — the cost, and a correction

At the top decile, restoring buys the extra reach with real drawdown:

| | med MFE | med MAE | MFE/\|MAE\| | med fwd 20d | win-of-labelled |
|---|---|---|---|---|---|
| current | 7.35% | −7.29% | 1.01 | −0.18% | 36.2% |
| restored | 8.15% | **−8.52%** | **0.96** | −0.30% | 37.7% |

Same trade the ADR read found this morning: **the tail is bought with a wider stop.**

**Correction to this document's earlier claim.** It said restoring "roughly doubles S-tier"
on the strength of the 51% → 29% figure in the Tested-DEAD row. **That figure is from the
old raw-sum ladder and does not predict today's behaviour.** Tier now derives from
`ta_grade`, whose divisor is `taxonomy.structural_cap_sum()` — computed live from the caps,
currently **171.0**. Restoring 15 + 15 moves it to **201.0**, so a setup must earn
Δ ≥ 0.175 × its current points *just to hold its grade*. Restoring at the current cuts
(62/52/42) would **lower most grades and shrink S-tier**, not double it. Any real flip would
have to re-choose the tier cuts the way the 2026-08-09 flip did.

### What shipped instead — the measuring stick, not the weights

The defect worth fixing is not the two weights. It is that `EDGE_TARGETS` puts two
path-sensitive targets first and every sub-score verdict inherits them silently. So
`core/archive/analyze.py` now also carries the magnitude target (`mfe_tail`, threshold
imported from `edge_report.TAIL_THRESHOLDS` — one home, EC-3), judged on **its own** noise
floor because it keeps the rows the barrier gate drops. **The primary is deliberately
unchanged** — swapping it would silently rewrite every standing verdict. Each row now
reports both verdicts and a **`verdict_disagrees` flag**, and the report prints a loud block
telling the reader not to act on the shortlist for those terms.

It fires on the live archive, and on two terms nobody was looking at:

| term | vs `durable_win` | vs P(MFE≥25%) |
|---|---|---|
| `score_adr` | +0.042 inert | **+0.269 beneficial** — the strongest association in the table |
| `score_high_proximity` | −0.068 inert | **−0.157 harmful** |
| `score_base_age` | **+0.193 beneficial** | +0.010 inert — the only term currently graded beneficial, and it does not survive the cross-check |

Seven guards, each mutation-proven.

### Recommendation

**Leave `SCORE_RS_BONUS` and `SCORE_UPTREND_BONUS` at zero.** The evidence for restoring
does not clear a bootstrap, the measured cost is a deeper drawdown at the top of the list,
and a real flip would drag the tier ladder with it. The Tested-DEAD row stands — with this
appended as the counter-evidence, and with the honest note that its "actively harmful"
verdict reads INERT once the cohort is deduped and judged at the tool's own floor.
