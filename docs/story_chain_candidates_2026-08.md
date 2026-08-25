# Story-chain specimen candidates — the keep/junk sheet (2026-08-23)

**For the operator.** Both chain patterns (register rows 8–9) need 2–3 ruled example charts
before the engine work can be tested against anything real. This sheet is the candidate feed:
40 charts mined from the cached universe by a deliberately crude shape screen
(`tools/story_chain_candidates.py` — liquidity floors, rolling ranges, nothing like the real
engine read). **Your verdicts are the ground truth; the screen is just a memory aid.**

**How to rule:** eyeball each chart around the listed dates (TradingView or the workbench).
Write **KEEP** (a genuine example of the pattern — worth marking), **JUNK** (not the pattern),
or a short note in the Verdict column. 2–3 KEEPs per chain is enough to open the next stage;
more is better. A KEEP here only names the chart — the deep two-structure marks come later,
in the workbench, once the marking tool lands.

This file is sealed (EC-44): no tool can overwrite it; verdicts land by hand.

Sidecar with full stats: `output/story_chain_candidates_2026-08-23.json` (machine-local).

## Chain A — base on base
*The old range broke out, price ran, then built a small tight range fully ABOVE the old
ceiling. The engine today refuses the small range standalone. Dates: the parent range's span,
its breakout day, and the tight child range's span.*

| # | Ticker | Parent range | Breakout | Old ceiling | Child range | Child tightness (ATRs) | Height above ceiling (ATRs) | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | FBRX | 2026-04-13 → 07-08 | 2026-07-09 | 35.55 | 07-31 → 08-14 | 0.12 | 12.7 | |
| 2 | CRNX | 2026-04-09 → 07-06 | 2026-07-07 | 44.11 | 07-14 → 07-27 | 0.13 | 14.2 | |
| 3 | UTZ | 2026-04-23 → 07-20 | 2026-07-21 | 8.68 | 08-03 → 08-17 | 0.20 | 13.8 | |
| 4 | ITGR | 2026-02-24 → 05-19 | 2026-05-20 | 91.32 | 08-10 → 08-21 | 0.25 | 14.7 | |
| 5 | SAFT | 2026-04-09 → 07-06 | 2026-07-07 | 77.78 | 08-05 → 08-18 | 0.26 | 12.7 | |
| 6 | ATAI | 2026-04-16 → 07-13 | 2026-07-14 | 5.52 | 07-22 → 08-04 | 0.27 | 6.2 | |
| 7 | APGE | 2026-01-12 → 04-08 | 2026-04-09 | 85.94 | 06-22 → 07-06 | 0.29 | 9.7 | |
| 8 | ATKR | 2026-01-28 → 04-23 | 2026-04-24 | 73.32 | 08-03 → 08-17 | 0.31 | 7.4 | |
| 9 | DBRG | 2025-09-11 → 12-04 | 2025-12-05 | 14.00 | 2026-01-08 → 01-22 | 0.33 | 6.2 | |
| 10 | HZO | 2026-02-10 → 05-06 | 2026-05-07 | 32.00 | 08-10 → 08-21 | 0.35 | 11.6 | |
| 11 | OGN | 2025-10-22 → 2026-01-16 | 2026-01-20 | 9.28 | 04-29 → 05-12 | 0.35 | 7.4 | |
| 12 | DSGR | 2026-03-24 → 06-17 | 2026-06-18 | 28.28 | 07-20 → 07-31 | 0.39 | 9.9 | |
| 13 | GBTG | 2026-02-05 → 05-01 | 2026-05-04 | 6.30 | 05-11 → 05-22 | 0.46 | 11.3 | |
| 14 | BOW | 2026-02-11 → 05-07 | 2026-05-08 | 26.54 | 08-05 → 08-19 | 0.49 | 7.0 | |
| 15 | BZH | 2026-03-06 → 06-01 | 2026-06-02 | 26.26 | 08-10 → 08-21 | 0.53 | 11.6 | |
| 16 | SLAB | 2025-09-16 → 12-09 | 2025-12-10 | 143.46 | 2026-02-17 → 03-02 | 0.56 | 10.3 | |
| 17 | CBZ | 2026-04-09 → 07-06 | 2026-07-07 | 36.42 | 08-05 → 08-18 | 0.57 | 15.0 | |
| 18 | BHF | 2025-06-25 → 09-18 | 2025-09-19 | 54.90 | 11-17 → 12-01 | 0.58 | 6.4 | |
| 19 | TSEM | 2021-09-08 → 12-01 | 2021-12-02 | 37.40 | 2022-02-25 → 03-10 | 0.67 | 6.9 | |
| 20 | PAYO | 2026-03-05 → 05-29 | 2026-06-01 | 5.35 | 06-16 → 06-30 | 0.67 | 6.9 | |

## Chain B — after-shakeout recovery
*A range's floor was violently undercut, price recovered at least half the break, then a small
tight pullback formed and HELD above the shakeout's low. "Above floor" = the pullback sits back
inside/above the old range floor; "tactical band" = it holds below the old floor but above the
shakeout low (the tactical long you ruled valid). Deep crashes that never came back are
expected JUNK — your rulings are what teach the boundary.*

| # | Ticker | Range start | Undercut day | Old floor | Shakeout low | Undercut depth (ATRs) | Pullback | Pullback tightness (ATRs) | Where it holds | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SAFT | 2026-02-10 | 2026-05-07 | 70.69 | 68.90 | 1.1 | 07-29 → 08-07 | 0.30 | above floor | |
| 2 | BWMN | 2026-04-17 | 2026-07-15 | 26.99 | 25.07 | 1.6 | 08-13 → 08-19 | 0.31 | above floor | |
| 3 | MKTX | 2026-02-17 | 2026-05-13 | 141.19 | 130.14 | 2.3 | 08-10 → 08-19 | 0.33 | above floor | |
| 4 | DBRG | 2025-08-20 | 2025-11-13 | 10.28 | 8.94 | 2.1 | 12-31 → 2026-01-07 | 0.33 | above floor | |
| 5 | VREX | 2026-02-11 | 2026-05-08 | 10.27 | 9.09 | 1.9 | 08-11 → 08-17 | 0.33 | above floor | |
| 6 | TECH | 2026-02-09 | 2026-05-06 | 48.25 | 43.20 | 1.7 | 06-29 → 07-09 | 0.35 | above floor | |
| 7 | CPRI | 2023-03-06 | 2023-05-31 | 36.40 | 34.25 | 1.4 | 08-31 → 09-07 | 0.35 | above floor | |
| 8 | FHN | 2021-09-24 | 2021-12-20 | 15.52 | 15.00 | 1.0 | 2022-03-17 → 03-23 | 0.35 | above floor | |
| 9 | HKD | 2023-03-29 | 2023-06-26 | 6.49 | 6.10 | 1.7 | 08-03 → 08-09 | 0.37 | above floor | |
| 10 | IMXI | 2025-04-22 | 2025-07-18 | 9.67 | 8.83 | 2.4 | 08-26 → 09-02 | 0.41 | above floor | |
| 11 | TWO | 2025-11-26 | 2026-02-25 | 9.84 | 8.78 | 1.4 | 05-20 → 05-27 | 0.46 | above floor | |
| 12 | PSO | 2023-02-03 | 2023-05-02 | 9.87 | 9.29 | 2.7 | 05-17 → 05-23 | 0.48 | above floor | |
| 13 | PDI | 2025-01-07 | 2025-04-04 | 18.56 | 16.00 | 8.5 | 04-24 → 04-30 | 0.49 | tactical band | |
| 14 | NWL | 2024-04-09 | 2024-07-05 | 6.20 | 5.39 | 3.5 | 08-16 → 08-22 | 0.49 | above floor | |
| 15 | NATH | 2025-08-20 | 2025-11-13 | 99.37 | 90.59 | 2.8 | 2026-01-22 → 01-28 | 0.50 | above floor | |
| 16 | ITGR | 2026-02-03 | 2026-04-30 | 81.99 | 77.05 | 1.7 | 08-04 → 08-10 | 0.50 | above floor | |
| 17 | BOH | 2022-12-09 | 2023-03-09 | 72.58 | 34.71 | 26.4 | 03-27 → 03-31 | 0.51 | tactical band | |
| 18 | SMFG | 2024-05-08 | 2024-08-05 | 11.34 | 10.74 | 1.5 | 08-26 → 08-30 | 0.53 | above floor | |
| 19 | AVTR | 2024-03-05 | 2024-05-30 | 23.37 | 21.78 | 3.4 | 08-15 → 08-21 | 0.54 | above floor | |
| 20 | NGVT | 2025-08-13 | 2025-11-06 | 52.40 | 45.85 | 3.1 | 12-23 → 12-30 | 0.54 | above floor | |

## Rulings received

- **2026-08-25 — ALL 40 ROWS RULED JUNK (blanket).** The Verdict columns above stay blank
  deliberately: this single ruling covers every row, and it is an ACTIVE ruling, not
  junk-by-default. Operator, verbatim: *"all garbage, Most of these are Stocks are setups
  that consist of extremely tiny spread after a significant gap, that look nothing like
  regular Price action with almost no trading volume or price change for that matter these
  examples you chose are almost entirely stocks that are being bought out and maybe leaving
  the market soon I usually avoid stocks like these Because I haven't seen good trades
  coming out of things like these."* Diagnosis: the crude tightness screen adversely
  selected **deal-pinned/buyout stocks** — a significant gap, then near-zero spread and
  volume, price pinned near the acquisition price. No chart advances to specimen; register
  rows 8–9 stay DESCRIBED. A round-2 sheet requires the miner to exclude the deal-pinned
  signature first (decisions.md 2026-08-25 row).
