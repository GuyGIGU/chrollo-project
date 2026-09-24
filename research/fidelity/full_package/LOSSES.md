# Trend-terminal box gate — the 39 boxes the flag removes

> ## ⚠ SUPERSEDED 2026-08-13 — do not rule from this sheet
>
> Re-measured on the 2026-08-12 payload: **21 losses, and not one of them is on
> this page.** The rule is a MATURITY rule, so its loss set rolls forward with
> the calendar — every name below was refused for having 5–19 bars since its
> climax, and 14 sessions have printed since. They matured; a different cohort
> took their place. Ruling from this page would be ruling on charts that no
> longer lose.
>
> Two corrections this sheet's numbers no longer support:
> * **"The gate never re-frames a box — it keeps it or refuses it."** Falsified.
>   The 2026-08-12 run has a `moved` case (APH), and it is by construction:
>   filtering candidates lets a later legal framing win the root.
> * The A/B was hand-run with no committed instrument, which is why this page
>   could not be refreshed. There is one now: `python -m tools.trend_terminal_ab`.
>
> **Current sheet: [`../trend_terminal_2026-08-13/LOSSES.md`](../trend_terminal_2026-08-13/LOSSES.md).**
> Kept verbatim below as the record of what was measured on 2026-07-27 — the
> class analysis and the PXS/MIDD/LIVN reasoning still hold.

`TREND_TERMINAL_BOX_GATE_ENABLED` (`c1c8432`, dark). Eyeball sheet for the flip ruling. Every PNG in this folder is one of the 39 — rendered **flag OFF**, i.e. the box as it exists today, the one the gate would refuse.

## A/B, re-run 2026-07-27 against the live payload (332 rows, cache through 2026-07-23)

| | |
|---|---|
| identical | **293** |
| lost | **39** |
| moved | **0** |
| gained | **0** |

The gate never re-frames a box — it keeps it or refuses it. Sealed marks ratchet re-run in both flag states: **28/33 PASS**, identical. Doctrine gate unchanged at its 2 pre-existing violations (AMCX B6 stale-payload, LIVN C6).

### Where the losses sit in the population

- Boxes whose covering trend had **already printed its climax at the box open** (`terminal_bar <= box.start_bar`): **188** — of those lost: **0**.
- Boxes whose trend **topped INSIDE the box**: **144** — lost **39**, kept **105** (kept = ≥ `MIN_BASE_DAYS` 20 bars printed since).
- Every loss opens between **2026-06-03** and **2026-07-07**. **0 of the 188 boxes opening before 2026-06-01 is touched.** Longest base_len removed: 35 bars (payload max: 267).

> Note vs the `c1c8432` commit message, which said *35 of 39 open Jun–Jul* and *4 of 190 already-topped boxes touched*. Re-measured here: **39/39** open in Jun–Jul and **0** already-topped boxes touched. Definition used: *already-topped* = the covering confirmed segment's `terminal_bar` is at or before the box's back-extended `start_bar`. Trust this run.

## The 39, by maturity (the number the rule turns on)

`bars since` = bars printed between the covering trend's climax and the frame's right edge — the gate refuses below **20**. Because `base_len = len(df) - start_bar`, that number is literally *the base_len the box would have if it started at the climax*: the rule says **the part of the base that comes after the climax must itself clear `MIN_BASE_DAYS`** — the same constant the box already has to satisfy. `climax @ box-bar` = how far into the box the trend topped. `past R` = how far the climax ran beyond the box's own R, as % of box height — **shown only to identify the PXS *shape*; overshoot magnitude is Tested-DEAD as a test (falsified 3×)**.

| ticker | box open | R | S | base_len | trend climax | bars since | climax @ box-bar | past R |
|---|---|---:|---:|---:|---|---:|---:|---:|
| CNS | 2026-07-07 | 80.48 | 76.15 | 13 | 2026-07-17 | **5** | 8 | 103% |
| CYRX | 2026-06-04 | 16.73 | 14.29 | 34 | 2026-07-17 | **5** | 29 | 7% |
| HUM | 2026-07-02 | 415.00 | 388.10 | 15 | 2026-07-16 | **6** | 9 | 52% |
| CNC | 2026-06-30 | 69.29 | 63.71 | 17 | 2026-07-14 | **8** | 9 | 1% |
| TOI | 2026-06-17 | 5.50 | 4.90 | 25 | 2026-07-14 | **8** | 17 | 195% |
| VMD | 2026-07-06 | 12.41 | 11.82 | 14 | 2026-07-13 | **9** | 5 | 34% |
| M | 2026-07-07 | 24.09 | 22.32 | 13 | 2026-07-10 | **10** | 3 | — |
| ATEN | 2026-07-01 | 38.39 | 35.51 | 16 | 2026-07-09 | **11** | 5 | 3% |
| BHVN | 2026-06-24 | 16.74 | 14.50 | 21 | 2026-07-09 | **11** | 10 | 24% |
| DMRA | 2026-07-06 | 30.75 | 27.18 | 14 | 2026-07-09 | **11** | 3 | 17% |
| MIRM | 2026-07-01 | 130.00 | 115.73 | 16 | 2026-07-09 | **11** | 5 | 0% |
| NRIX | 2026-06-30 | 24.88 | 23.10 | 17 | 2026-07-09 | **11** | 6 | 12% |
| PHVS | 2026-06-25 | 35.33 | 32.93 | 20 | 2026-07-09 | **11** | 9 | 53% |
| ALKS | 2026-06-26 | 55.28 | 50.96 | 19 | 2026-07-07 | **13** | 6 | 9% |
| CFG | 2026-06-30 | 72.94 | 69.49 | 17 | 2026-07-07 | **13** | 4 | 0% |
| IRMD | 2026-06-03 | 98.41 | 89.69 | 35 | 2026-07-07 | **13** | 22 | 53% |
| MIDD | 2026-06-18 | 139.52 | 130.63 | 24 | 2026-07-07 | **13** | 11 | 102% |
| SPG | 2026-06-26 | 228.58 | 220.04 | 19 | 2026-07-07 | **13** | 6 | 12% |
| ESTA | 2026-06-30 | 92.84 | 86.13 | 17 | 2026-07-06 | **14** | 3 | 0% |
| LIVN | 2026-06-18 | 83.98 | 77.71 | 24 | 2026-07-06 | **14** | 10 | 21% |
| NUTX | 2026-06-12 | 150.00 | 142.91 | 28 | 2026-07-06 | **14** | 14 | 762% |
| NVST | 2026-06-23 | 27.02 | 25.18 | 22 | 2026-07-06 | **14** | 8 | 48% |
| PSMT | 2026-06-09 | 183.00 | 174.15 | 31 | 2026-07-06 | **14** | 17 | 190% |
| ABCB | 2026-07-01 | 92.44 | 89.08 | 16 | 2026-07-02 | **15** | 1 | 0% |
| COSO | 2026-06-15 | 27.51 | 26.27 | 27 | 2026-07-02 | **15** | 12 | 41% |
| FFIN | 2026-06-26 | 35.42 | 34.22 | 19 | 2026-07-02 | **15** | 4 | 29% |
| RCKY | 2026-06-17 | 42.35 | 39.67 | 25 | 2026-07-02 | **15** | 10 | 3% |
| BLTE | 2026-06-24 | 157.99 | 144.51 | 21 | 2026-07-01 | **16** | 5 | 0% |
| BOF | 2026-06-22 | 4.74 | 4.13 | 23 | 2026-07-01 | **16** | 7 | 84% |
| ASML | 2026-06-22 | 1959.04 | 1730.29 | 23 | 2026-06-30 | **17** | 6 | 18% |
| LNTH | 2026-06-17 | 111.86 | 101.61 | 25 | 2026-06-30 | **17** | 8 | 0% |
| RBA | 2026-06-17 | 117.05 | 106.92 | 25 | 2026-06-30 | **17** | 8 | 0% |
| TACT | 2026-06-17 | 5.70 | 4.95 | 25 | 2026-06-30 | **17** | 8 | 43% |
| WTS | 2026-06-24 | 375.89 | 340.84 | 21 | 2026-06-30 | **17** | 4 | 53% |
| APLE | 2026-06-24 | 17.06 | 16.30 | 21 | 2026-06-29 | **18** | 3 | 0% |
| IART | 2026-06-11 | 18.92 | 17.14 | 29 | 2026-06-29 | **18** | 11 | 0% |
| LQDT | 2026-06-24 | 39.55 | 37.53 | 21 | 2026-06-29 | **18** | 3 | 19% |
| PBI | 2026-06-22 | 18.25 | 16.80 | 23 | 2026-06-29 | **18** | 5 | 0% |
| PB | 2026-06-17 | 74.37 | 70.12 | 25 | 2026-06-26 | **19** | 6 | 0% |

## Classes — rule on these, not on 39 charts

### Class A — the base was born at the top (31 of 39)

The box opens, price pushes to its high within ≤10 bars, and everything since is under 20 bars. This is the young-base story the ruling describes, with no complications.

`ABCB ALKS APLE ASML ATEN BHVN BLTE BOF CFG CNC CNS DMRA ESTA FFIN HUM LIVN LNTH LQDT M MIRM NRIX NVST PB PBI PHVS RBA RCKY SPG TACT VMD WTS`

### Class B — the trend topped LATE inside an already-working range (8 of 39) ⚠

These are the ones that could falsify the rule: the box had already been trading two-sided for 11–29 bars before the bar the engine calls the trend's climax. Two distinct shapes inside the class:

| ticker | box open | base_len | climax | @ box-bar | bars since | past R | shape |
|---|---|---:|---|---:|---:|---:|---|
| CYRX | 2026-06-04 | 34 | 2026-07-17 | 29 | **5** | 7% | **CTOS shape** — climax ≈ the box's own R |
| IRMD | 2026-06-03 | 35 | 2026-07-07 | 22 | **13** | 53% | **PXS shape** — real upthrust above R |
| PSMT | 2026-06-09 | 31 | 2026-07-06 | 17 | **14** | 190% | **PXS shape** — real upthrust above R |
| TOI | 2026-06-17 | 25 | 2026-07-14 | 17 | **8** | 195% | **PXS shape** — real upthrust above R |
| NUTX | 2026-06-12 | 28 | 2026-07-06 | 14 | **14** | 762% | **PXS shape** — real upthrust above R |
| COSO | 2026-06-15 | 27 | 2026-07-02 | 12 | **15** | 41% | **PXS shape** — real upthrust above R |
| IART | 2026-06-11 | 29 | 2026-06-29 | 11 | **18** | 0% | **CTOS shape** — climax ≈ the box's own R |
| MIDD | 2026-06-18 | 24 | 2026-07-07 | 11 | **13** | 102% | **PXS shape** — real upthrust above R |

- **PXS shape** (IRMD 53%, COSO 41%, MIDD 102%, PSMT 190%, TOI 195%, NUTX 762%): an upthrust *inside* an established base — the exact pattern behind the accepted PXS (47.9%) / VIK (82%) / MATX (101%). What separates them from those is only maturity: **PXS has 54 bars since its climax and survives this gate; IRMD has 13.**
- **CTOS shape** (CYRX 7%, IART 0%): the bar the engine calls "the trend's climax" barely clears — or exactly equals — the box's own R anchor. The `trend_terminal_floor` docstring names this false-positive class by name (CTOS 2026-05, 2.7% of box height) and says the terminal PRICE is what defends against it — **but the shipped `trend_terminal_legal_open` never reads the price array.** See the note at the bottom.

### Closest to the floor — five names die by ≤ 2 bars

| ticker | bars since | short by |
|---|---:|---:|
| PB | 19 | 1 |
| PBI | 18 | 2 |
| IART | 18 | 2 |
| APLE | 18 | 2 |
| LQDT | 18 | 2 |

Ten of the 39 sit within 3 bars of the floor (17, 18, 19). `MIN_BASE_DAYS` = 20 is doing real work at its exact value here.

## Evidence FOR the flip

- **MIDD is removed.** Box 2026-06-18, blow-off to 148.55 on 2026-07-07 (102% of box height past R), then breakdown — the chart already ruled *"no setup at all"* in the cause-before-effect record. The live cause-veto does **not** catch this instance (its third AND-leg, the tightened LPS shelf, rescues it). This gate does.
- **LIVN is removed** — the origin case, and with it the standing C6 doctrine violation (`tip=504 lps.start=500`).
- **PXS survives** at 54 bars since its 2026-05-06 climax — the cautionary keep stays kept, with 34 bars of headroom over the floor.
- **Nothing mature is touched**: no box older than 2026-06-03, none longer than 35 bars, 0 moved, 0 gained.
- Only **1 of the 33 Guided-List marks** appears in the loss list (**WTS**), and it is not the marked base: his mark is 2026-06-12 at R=312.40/S=288.59; the removed box is a *later, higher* one at 2026-06-24 R=375.89/S=340.84 — i.e. the marked base broke out, ran ~20%, and the gate refuses the fresh 4-bar-old consolidation on top of it. The ratchet is unaffected.

## Open question the renders should settle

Class B asks one question, in the operator's own vocabulary: **when a range that has already been working for 11–29 bars prints an upthrust, does that upthrust restart the clock on the base?** The rule as written says yes (the box must show 20 bars *after* it). PXS says the answer is yes-but-it-had-53. IRMD, CYRX, IART, COSO, PSMT are where that reading is cheapest to falsify.

---

### Defect found while measuring (not fixed — needs a ruling)

`market_structure.trend_terminal_floor`'s docstring closes with:

> *"The PRICE is what makes the rule survive contact: a candidate is only mid-trend if the trend went on to an extreme materially beyond that candidate's OWN rail (CTOS 2026-05 … a false positive that cost a pinned Guided-List hit; LIVN's is 20.6%)."*

That describes **`TREND_TERMINAL_OVERSHOOT_BOX` — the knob that was built, measured and removed the same day**, and which `decisions.md` records as DEAD, falsified 3×. `trend_terminal_legal_open` reads only `terminal_floor.bar`; the `price` and `direction` arrays are computed, returned, and never consulted by the gate. The docstring therefore tells the next session that the dead lever is the live mechanism, in the first function they will open. It is a stale-docstring fix, no behavior change.

