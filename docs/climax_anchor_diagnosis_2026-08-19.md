# The climax anchor — what it actually computes (2026-08-19)

The 2026-08-14 marks ruling
([`anchor_marks_ruling_2026-08-14.md`](anchor_marks_ruling_2026-08-14.md)) left the
anchor defect named but not mechanised, and closed with an ask: 15–20 more dated
trend-end marks on clean structures. **This document withdraws that ask.** The
mechanism was established from the code and the price cache alone, and the
operator's marks were not the missing input.

Diagnosis method: a 14-agent fan-out (4 grounding angles → 6 adversarial
refutations → synthesis), every claim required to cite `file:line` or a command
with its real output, every agent required to file what it could **not**
establish. All six hypotheses were refuted as explanations of the split; what
survived is below, together with the refuted ones, because a killed theory is
evidence too.

---

## The finding: the anchor is not a chart measurement

`Structure.climax_bar` — the number `tools.operator_marks_diff` scores, and the
dot the overlay draws — is **reconstructed backward from the elected box**, not
read off the trend.

`_enforce_climax_terminality` ([`bricks.py:591-642`](../engine_alpha/structure/narrative/bricks.py))
discards the raw resolver's pair whenever the pair is non-terminal and
re-anchors to the extreme of a **fixed 60-trading-day window ending at the box
open**:

```
lo = max(0, pbs - _SEG_LEAD_IN)          # bricks.py:625, _SEG_LEAD_IN = 60 (bricks.py:30)
...
return lo + int(np.argmax(window)), pbs  # BC branch, bricks.py:634
return lo + int(np.argmin(window)), pbs  # SC branch, bricks.py:642
```

Two consequences follow directly from that `return`:

1. The climax is the extreme of a window whose **right edge is the box open** —
   never a pivot the trend reader elected.
2. The AR is set to `pbs` — the box open — **by assignment**. This is why the
   drawn AR equals `box.start_bar` on 6 of 6 live reads, and why the operator's
   own identity ("the AR low *is* the root swing *is* where the consolidation
   starts") is satisfied by construction rather than by reading a reaction.

### The error decomposes exactly

For a mark at his trend end, the signed error is an identity, verified on all
six measurable names:

```
dCx = A + B        A = climax - box.start_bar   (structurally in [-60, 0])
                   B = box.start_bar - his trend end   (exogenous to the anchor)
```

`A` is pinned near its floor across the marked cohort (−60 on five of six), so
**A cannot separate the names — the entire split lives in `B`, where the elected
box happens to open.**

| ticker | A | B | dCx | reading |
|---|---|---|---|---|
| LZB | −60 | +60 | **+0** | exact because the box opened right after his peak — the terms cancel |
| HTH | −60 | +54 | −6 | **not** a near miss: two large errors nearly cancelling |
| CATO | −60 | +42 | −18 | same shape (from the recorded 2026-08-13 capture) |
| CNI | — | — | −54 | see the polarity finding below — a different cause |
| EC | — | −1 | −61 | the blockade is worth 1 bar of a 61-bar error |
| BCPC | −60 | −22 | −82 | his peak sits 22 days **past** the box open — unreachable at any polarity |

`A ∈ [-60, 0]` is mechanically guaranteed: `base_len = int(len(df) - start_bar)`
([`bricks.py:344`](../engine_alpha/structure/narrative/bricks.py)) makes the segmentation
window start at exactly `box.start_bar - 60`, and all four return paths of
`_resolve_phase_a_raw` plus both enforcers are bounded to `[pbs-60, pbs]`
(bricks.py:576, 625, 758-759, 784-796).

---

## The second finding: a Tested-DEAD keying is still live here

The **polarity** of that window extreme — highest High or lowest Low — is taken
from `root.kind`, the BC/SC label of the seed anchor:

```
kind = getattr(root, "kind", None)       # bricks.py:612
if kind not in ("BC", "SC"): return      # bricks.py:613
```

The seed is a *scan origin*, a median ~394 trading days from the box. On the
live specimens its label contradicts the shape of the pair it is judging **4
times out of 4** (BCPC / CNI / HTH / AMH: SC-labelled seed, BC-shaped drawn
pair, seeds 255–417 trading days away).

[`decisions.md`](decisions.md) Tested-DEAD, 2026-07-27:

> **Keying the box's cause trend on `root.kind`** — **DEAD**. The root is a
> *scan origin*, not the box's cause. […] Derive the cause from the segment
> covering the bar.

That row killed the keying for the trend-terminal box gate. **The same keying is
still consumed here**, in the climax repair. The prescribed remedy is already
recorded in the same row.

**CNI is the clean demonstration.** `_resolve_phase_a_raw` returned the
operator's exact pair — **2026-07-17 → 2026-07-21** — and the mis-polarised SC
branch replaced the climax with the argmin of Lows inside the lead-in window.
The engine found his answer and overwrote it.

---

## The calibration that deflates the alarm

The twelve renders the marks were taken on were selected as the largest AR
pull-ins — which **is** the lookback distance `box.start_bar - climax_bar`. All
twelve sit at 56–60. Fleet-wide that quantity is nothing like its cohort value:

Full-cache sweep, 2026-08-19 (5,545 tickers → 1,633 baseline survivors → **381
live structures**), measuring `box.start_bar - climax_bar`:

| statistic | value |
|---|---|
| minimum | 0 trading days |
| **median** | **9 trading days** |
| within 10 days | **53.8%** |
| at the 60-day ceiling | **2.89%** |
| above 60 | **0** (the bound is mechanical, not empirical) |
| the 12-render marks cohort | **all twelve at 56–60** |

Run **twice independently** — once inside the diagnosis fan-out, once by the
main session afterwards from a separate probe — with identical results on every
line. The probe is read-only and reproducible: load the cache, `_prep_live`,
`read_structure`, record `box.start_bar - climax_bar`.

Because lookback enters the error additively, the cohort's median dCx (−50.5 on
2026-08-14, −36 today) **may not be quoted as the fleet-wide anchor error**. It
is a maximum-order-statistic sample on exactly the term that drives it.

---

## Ruled out (all six hypotheses refuted as explanations of the split)

| hypothesis | verdict |
|---|---|
| Invariant blockade (`climax ≤ ar ≤ box.start` forbids reaching forward) | Real, but binds on **BCPC only**, worth 22 of its 82 days, and only once polarity is right. Worth 1 bar on EC. |
| "Extreme pivot vs last peak" definitional mismatch | Conflates two objects. The diff tool scores the drawn Phase-A climax, **not** `segment_trends`' terminal (which it reports separately, 2 of 9). |
| Truncation instability | The fact is confirmed (HTH 03-31→06-26, CNI alternates, BCPC 10-17→12-18) but it **predicts the wrong partition**: AMH is 60 days early *and* perfectly stable at every left-edge step; LZB is exact *and* perfectly stable. Its one channel is `root.kind`, which is frame-sensitive. |
| Polarity as *the* separator | The mechanism is real and reproduced, but its output is near-constant across the six (`climax = box_start − 60` on five of six) while dCx spans −82…0. A large error, not the separator. |
| Corpus selection bias as *the* separator | Selection pins lookback at its ceiling for the whole corpus and therefore cannot separate its members. Survives only as a quoting rule (above). |
| Backward reconstruction as a *causal* claim | Survives as arithmetic (the identity), refuted as cause. |

---

## What this diagnosis did NOT establish

- **MAN's exact pair could not be reproduced.** `decisions.md` (2026-08-14)
  records that a counterfactually-seeded probe at clock 10 found his exact pair
  to the day. Under the supported override today `read_structure` returns None
  for MAN, and it could not be verified that those dates were ever a *published*
  Phase-A anchor rather than an in-process probe result. **Do not lean on that
  claim without re-deriving it.**
- **CATO and EC do not fire today.** Their rows in the diff table are carried
  `recorded` from 2026-08-13, so two of the six numbers are not live reads.
- **His marked bar is the local extreme on LZB only** — on HTH, CNI and BCPC it
  is not the highest High within ±10 trading days, so "the engine missed his
  peak" and "his peak is not an extremum the reader would elect" are not
  separated.
- **Churn was measured on one pair of dates** (2026-08-11 vs 2026-08-18): 31.7%
  of climaxes moved. Whether that is typical for an arbitrary five-day window is
  unknown.
- **No A/B was run, no flag flipped, no engine code changed.** Nothing here is
  evidence that a different anchor would rank, score or recall better.
- Whether failure (a) (the pivot is not found) and (b) (Phase A cannot reach it)
  are one program or two remains **unruled**
  ([`anchor_marks_ruling_2026-08-14.md:129`](anchor_marks_ruling_2026-08-14.md)).

---

## Standing facts this does not change

The anchors are overlay + Phase-A diagnostics only. The guard's own docstring
([`bricks.py:609-610`](../engine_alpha/structure/narrative/bricks.py)) states it: *"no
rail, gate, score, or tier reads these anchors."* Nothing the operator trades is
affected by any error described here. The two flags that depend on the anchor
(`TREND_TERMINAL_BOX_GATE_ENABLED`, `AR_FIRST_REACTION_ENABLED`) are both dark.

## RULED AND LANDED, same day

The operator took the fix (*"sure lets take the fix"*). `_cause_is_up` now reads
the polarity from the confirmed segment covering the box open
(`trend_terminal_floor.direction`, cause-wins), with the seed label surviving
only where no segment covers — so an unreadable frame keeps its previous repair
instead of losing it. Pinned by a polarity test and a no-cover fallback twin in
`tests/test_bricks.py`.

**Measured against the same nine marks, immediately after:**

| ticker | before | after | |
|---|---|---|---|
| CNI | −54 | **+0** | lands on his date exactly — the overwrite is gone |
| BCPC | −82 | **−39** | 43 trading days closer |
| AMH | −60 | +0 | (excluded as circular, reported for completeness) |
| HTH | −6 | **+54** | **regressed** — see below |
| LZB / CATO / EC | +0 / −18 / −61 | unchanged | |

Aggregate: earlier-than-his-trend-end **5 of 6 → 3 of 6**, median **−36 → −9**
trading days. The directional bias largely closes.

**HTH regressed and that is recorded, not buried.** Its former −6 was never
agreement — the decomposition above shows it was −60 + 54, two large errors
cancelling. Re-keyed, the up-cause branch takes the run-up high, which on HTH is
the box-open bar itself (the sanctioned one-bar collapse form), 54 trading days
after his mark. **The re-key fixes which END of the lead-in window is taken; it
does not touch the window.** `A ∈ [-60, 0]` still holds, so the anchor is still a
function of where the box opens.

Guided-List ratchet after the fix: **28/33 held, same marks fingerprint.**

## Still open — for the operator

**The species story form converts two sealed expected-misses.** With
`POWER_PLAY_STORY_FORM_ENABLED` ON, the Guided-List ratchet breaks: **EGBN
(2026-01-15, now fires 01-07, tier A)** and **PKE (2026-02-24, now fires 02-18,
tier B)**, both recorded misses of stage `rail-placement`. Good news is still a
ratchet break — the guard's own words — and re-freezing the sealed standard is
the operator's ruling. Note EGBN is a name with an *already open* condition-D
ruling, diagnosed (`project_spread_profile_gap`) as ~85% a decisive high-shelf
LPS — i.e. price holding above the rail, which is exactly what "contracting above
resistance" names. The conversion is plausibly correct; it still needs his word
and a re-freeze. **The preset half shipped alone in the meantime**, deviating
knowingly from "the two flags flip together or not at all".

**And the AR flag's 2026-09-15 kill-by still stands.** Its blocking condition was
"cannot be ruled until `climax_bar` lands on a trend end". That is now partly
satisfied — the anchor is materially closer on aggregate — so the flip question
can be re-put on current numbers (`python -m tools.operator_marks_diff`) rather
than allowed to expire by default. Today the retarget is closer on 5 of 6 names
but carries more total error (166 vs 129 trading days), because on the names
where the climax now collapses to the box open the retarget has nothing left to
move.
