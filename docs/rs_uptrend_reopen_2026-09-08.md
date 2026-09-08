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

## The proposed A/B, if he wants it

Reproduce the 2026-07-22 read faithfully on the original variables; re-run it against a
label-free target (P(MFE≥25%) / ≥40%); then a frozen-frame A/B at the old weights (15 / 15)
measuring the marks ratchet, the reader pin, the junk corpus, and the S-tier share, with
the Guided-List must-fire floor as the gate. No weight moves before that returns.
