# Rail-Area Census — 2026-08-30

The **committed evidence record** (EC-16) behind the two 2026-08-30 rail-area rows in
`decisions.md`: *"THE RAIL AREA IS RULED: ±0.50 ATR, symmetric, both rails"* and *"the rail
area is BAR-SCALED (ATR)"*. Those rows cited a three-lane exploration that lived only in a
session scratchpad; nothing committed reproduced their numbers. `tools/rail_area_census.py`
is the promotion — a small instrument that recomputes **exactly the figures the rulings
quote**, prints itself against them, and fails loudly rather than re-fitting.

**Run it:**

```powershell
.\.venv\Scripts\python.exe -m tools.rail_area_census --json output/rail_area_census_2026-08-30.json
```

~50 seconds end to end, no flags, no network, no engine or archive write. The sidecar is
committed as `output/rail_area_census_2026-08-30.json` (`output/*.json` is gitignored, so it
lands with `git add -f`, exactly like its census siblings).

## Population stamp

| | |
|---|---|
| **drawn** | every `verdict='box'` CalibrationMark through the ONE validated loader (EC-13) — **35 marks**, measured on HIS rails over HIS window (`tools.replay.drawn_box_window`), plus **51 drawn rest spans** (`lps` / `last_supper` / `mini_consolidation`) |
| **junk** | the negative corpus's **18 frozen cases** → every strict candidate box the election examined (`rail_margin_evidence.junk_rows` recipe: rescued framings skipped, candidates killed before the respect gate skipped, deduped by `(R, S, cand_start, stage)`) — **1,647 candidates**, of which **98 SURVIVED-RESPECT** are the fair contrast against a drawn box |
| **archive** | `setup_archive`, **11,407 rows → 3,934 episodes** (`core.archive.episodes` first-seen grouper), read-only, sidecar-only (EC-46) |
| **marks_fingerprint** | `92d6a529c1ad4dc7…` — identical to the stamp on the sealed exploration |
| **engine_config_version** | `08c981629923c30e…` at reproduction; the sealed exploration stamped `0ac88199221d77be…`. **Every headline still reproduces across that manifest change** — the evidence does not depend on the epoch that happened to be live when it was taken. |

## Reproduction: 25 / 25

Every figure the ruling rows cite, recomputed by the committed instrument. The instrument
carries this table itself (`_RECORDED`) and prints RECORDED vs REPRODUCED on every run, so a
future drift surfaces as a `DIVERGES` line instead of a quiet re-fit.

| measure | recorded | reproduced |
|---|---|---|
| distance-blind cut · drawn R (ATR) | 0.510 | 0.5101 |
| distance-blind cut · drawn S (ATR) | 0.510 | 0.5103 |
| distance-blind cut · junk-survived R (ATR) | 0.528 | 0.5280 |
| distance-blind cut · junk-survived S (ATR) | 0.442 | 0.4424 |
| the SAME cuts in box fractions | 0.308 / 0.283 / 0.120 / 0.090 | 0.3079 / 0.2831 / 0.1200 / 0.0899 |
| his drawn ceiling rests, n | 22 (over 18 marks) | 22 (over 18 marks) |
| … contained at ±0.50 ATR | 86% | 86.4% |
| … contained at ±0.30 ATR | 64% | 63.6% |
| … sitting ABOVE R | 7 of 22 | 7 of 22 |
| his drawn support rests, n | 16 | 16 |
| … contained at ±0.50 ATR | 75% | 75.0% |
| … sitting ABOVE S | 11 of 16 | 11 of 16 |
| support tests (`S:rest`), n | 66 | 66 |
| … contained at ±0.30 ATR | 47% (so ±0.3 cuts 53%) | 47.0% |
| box height median · drawn | 1.73 ATR | 1.732 ATR |
| box height median · junk-survived | 3.05 ATR | 3.052 ATR |
| max pierce above R · drawn / junk-survived | 1.267 / 0.349 ATR | 1.267 / 0.349 |
| max pierce below S · drawn / junk-survived | 1.089 / 0.000 ATR | 1.089 / 0.000 |
| 1 ATR in box heights (archive median) | 0.403, n = 3,407 | 0.403, n = 3,407 |

## The measurements, with the definitions that must stay frozen

The definitions are the part that must not move; the numbers follow from them. The
instrument's `REPRODUCIBILITY NOTE` carries the same list at the point of use.

**1. His own drawn rests (engine-independent — the strongest lane).** Each drawn
`lps`/`last_supper`/`mini_consolidation` span is bucketed by where its **LOW** sits in the
box: `ceiling` at/above 0.70, `support` at/below 0.30 (census literals, frozen; they
coincided with `TRAVERSAL_HIGH_ZONE` / `TRAVERSAL_LOW_ZONE` when the evidence was sealed).
Distance is the span low against the rail, **signed — negative means the rest sits ABOVE the
line** — and containment is measured on `|d|`.

```
ceiling |rest low − R| (ATR)   n=22   median 0.258  p75 0.355  p90 0.633  max 1.303
    contained  ≤0.3 63.6%   ≤0.5 86.4%   ≤0.75 95.5%
    raw cluster: -1.303 -0.438 -0.360 -0.292 -0.271 -0.245 -0.131  0.000  0.010  0.049
                  0.089  0.106  0.149  0.159  0.226  0.241  0.285  0.339  0.340  0.486
                  0.650  0.731
support |rest low − S| (ATR)   n=16   median 0.417  p75 0.504  p90 0.705  max 0.736
    contained  ≤0.3 25.0%   ≤0.5 75.0%   ≤0.75 100.0%
    raw cluster: -0.711 -0.529 -0.496 -0.446 -0.437 -0.421 -0.414 -0.381 -0.356 -0.081
                 -0.054  0.000  0.011  0.308  0.699  0.736
```

**±0.50 ATR contains 86% of his ceiling rests and 75% of his support rests. At ±0.30 ATR the
area starts cutting into the operator's own near-rail population — it excludes 36% of these
ceiling rests, 75% of these support rests, and (from the grid below, the engine-typed
population) 53% of the 66 support tests.** And the sign carries no information: **7 of 22 ceiling
rests sit above R, 11 of 16 support rests sit above S**. Treating the rail as a two-sided
area is what his marks already do.

**2. The distance-blind cut.** An EXCURSION is a maximal run of consecutive bars with
`High > R` (or `Low < S`) — strict, wick basis, no tolerance anywhere. Lens 2 splits them by
**duration only**: `poke ≤ 2 bars`, `dwell ≥ 3 bars` (`DWELL_MIN_BARS = 3`). It never
consults distance, so the best Youden-J cut on max distance beyond the rail is a
measurement, not a definition (ties resolve to the lowest candidate cut; the candidate set is
the union of both classes' own values).

| population | rail | cut (ATR) | J | pokes ≤ cut | dwells > cut | n |
|---|---|---|---|---|---|---|
| drawn | R | **0.5101** | 0.720 | 85.2% | 86.8% | 61 / 53 |
| drawn | S | **0.5103** | 0.675 | 85.9% | 81.6% | 78 / 49 |
| junk survived-respect | R | **0.5280** | 0.838 | 93.4% | 90.4% | 121 / 52 |
| junk survived-respect | S | **0.4424** | 0.853 | 85.3% | 100.0% | 116 / 36 |

**Four cuts, two populations, both rails: 0.44–0.53 ATR** — a ±10% band around 0.5.

**3. The unit test — the discriminating measurement.** The same four cuts expressed in box
fractions are 0.3079 / 0.2831 / 0.1200 / 0.0899. The two populations differ in box height by
**1.76×** (drawn median 1.732 ATR, junk-survived 3.052 ATR).

> Across that change of box height the **ATR** cut spreads **1.19×** and the **box-fraction**
> cut spreads **3.42×**. ATR is the stable unit for a rail area; box fraction is not.

On the drawn corpus alone the two units look equally coherent — but that is a homogeneity
artifact (`0.51 ATR ÷ 1.73 ATR = 0.295 box`: one number written twice). The exchange rate
recovered from the archive makes the point at scale: `lps_stretch_box / lps_stretch_atr` is
the same numerator over two denominators, i.e. ATR per box height. **Median 1 ATR = 0.403 box
heights** (n = 3,407 episode rows; p5 0.223, p25 0.314, p75 0.524, p95 0.751), so ±0.50 ATR is
±0.202 box heights at the median and anywhere from ±0.112 to ±0.376 across p5–p95. **A 3.4×
spread — the two units are not interchangeable row by row.**

**4. The decision grid.** Share of each class CONTAINED at each candidate thickness, drawn
corpus, ATR (`lens1` classes come from the engine's own event words: `rest = SOS/range/test/
lps`, `graze = rejection`, `spike = upthrust/spring/markup/failed`).

| class | n | 0.20 | 0.25 | 0.30 | 0.40 | **0.50** | 0.60 | 0.75 | 1.00 |
|---|---|---|---|---|---|---|---|---|---|
| R graze | 45 | .556 | .578 | .711 | .889 | **.956** | .956 | .956 | .978 |
| S rest (test) | 66 | .348 | .409 | .470 | .742 | **.879** | .894 | .924 | .939 |
| R poke | 61 | .459 | .508 | .639 | .754 | **.836** | .869 | .918 | .967 |
| S poke | 78 | .397 | .449 | .526 | .744 | **.846** | .885 | .936 | .949 |
| **R spike** (want LOW) | 34 | .000 | .029 | .029 | .029 | **.029** | .147 | .382 | .559 |
| **S spike** (want LOW) | 36 | .083 | .083 | .167 | .194 | **.250** | .361 | .611 | .750 |

0.50 is where the near-rail population is nearly all in and the departure population is still
nearly all out. The full grid (both populations, all five classes) prints on every run and is
in the sidecar.

> **CIRCULARITY WARNING, carried from the sealed exploration and stated in the instrument.**
> `upthrust` vs `rejection` is decided by `BOUNDARY_ATR_BUFFER`, `measure_support_tests`
> skips `breach_S` by the same buffer, and `SOS` vs `markup` by `SOS_NEAR_R_MAX_BOX`. A
> distance split between those classes partly **re-derives 0.5** rather than measuring it.
> The drawn rests (1) and the distance-blind cut (2) are the evidence that does not; weigh
> them first.

**5. The negative finding — distance runs the WRONG way.** Per-box max pierce, medians:

| measure | drawn (n=35) | junk survived-respect (n=98) | junk ALL (n=1,647) |
|---|---|---|---|
| max above R, ATR | **1.267** | 0.349 | 6.441 |
| max above R, box | **0.767** | 0.119 | 3.266 |
| max below S, ATR | **1.089** | **0.000** | 1.365 |
| max below S, box | **0.611** | **0.000** | 0.815 |
| box height, ATR | 1.732 | 3.052 | — |

**Box-shaped junk pierces its rails ~3.6× LESS than the operator's drawn boxes do**, and half
the junk framings never breach support at all. Raw distance from a rail is not a quality
signal and must never be used as a junk filter. The class-conditional cuts are meanwhile the
SAME in both populations (0.44–0.53 everywhere) — rail-area thickness is a property of how
bars behave near a line, not a property of a good setup. *(The "junk ALL" column is a framing
artifact: 94% of those candidates die at the respect gate on windows whose rails are nowhere
near the price action. Reported for completeness, never quotable.)*

## The guard-rail the numbers do not overturn

Restated here because it travels with every quotation of ±0.50: **the rail area is position
vocabulary ONLY.** A 0.5-ATR allowance used as a gate, veto, rescue or junk filter is
Tested-DEAD twice — `ENGAGEMENT_MAX_EXCURSION_ATR` as an election gate (2026-07-24: admitted
FLG + BBVA at every bound ≥ 0.5, converted ZERO Guided List misses) and the ceiling rest at
0.5 instead of 0.3 (2026-08-29: fired junk ENIC at tier A, negative-corpus guard red). The
ruled value lands on the incumbent `TOUCH_TOLERANCE_ATR = 0.50`; **no number moves** — an
unevidenced constant becomes an evidenced one.

## Honest divergences

Three, all cosmetic; nothing re-fitted:

1. **support rests p75 — recorded 0.505, computed 0.5045.** The sealed synthesis transcribed
   the 4-dp value up; the underlying cluster is byte-identical. No other percentile differs.
2. **The sign split counts an exactly-on-the-rail span differently.** The sealed §3.1 split
   folded the one span whose low sits *exactly* on the rail into "below" (15/22 ceiling, 5/16
   support). This census reports three counts — **7 above / 1 exactly on / 14 below** and
   **11 above / 1 exactly on / 4 below** — which is the same population, split finer. The
   headline the rulings cite (7 of 22, 11 of 16 ABOVE) is unaffected.
3. **The manifest hash moved** (`0ac88199…` → `08c98162…`) between the sealed exploration and
   this reproduction, while `marks_fingerprint` did not. All 25 figures reproduce anyway.

## What this instrument deliberately does NOT port

The sealed exploration was ~46 KB across three lanes and answered far more than the rulings
cite. This is a **small** instrument for the ruling evidence; the rest was left out on
purpose, and is named here so nobody assumes it was measured and lost:

* **the straddle-run lane** (bars whose own range *contains* the rail — the third,
  wholly independent convergence at ~0.35 ATR reach). It agrees with (1) and (2) and adds no
  cited number. If the *"straddle / poke-return decomposition"* the ruling names as the next
  measurement worth building ever happens, it starts here.
* **the inside mirror** (how far under R / over S the bars sit — the "the inner half is the
  same size as the outer half" support for symmetry).
* **per-excursion reclaim speed, bar spread and net drift.**
* **the ceiling-rest razor's sanity anchor** (DSGN 0.010 / MATX 0.089 / MSGS 0.149 /
  NOK 0.241 reproduced two independent ways, and the ENIC 0.314 that could **not** be
  reproduced — its junk side stays unverified and needs the flags-on election path). The
  four drawn values are still visible inside §1's raw ceiling cluster above.
* **the `MINI_POSITION_TOL_ATR = 1.0` census** (at 1.0 ATR the engine's own
  `mini_consolidation_position` typed *every* drawn `lps`/`sos`/`last_supper`/
  `mini_consolidation` span as `at_ceiling`). That constant's ruling is still owed and its
  measurement was superseded the same week by the four-value position vocabulary.
* **the whole archive-outcome lane** — the censoring analysis, the KS-vs-uniform gate-shape
  finding, the near-vs-far Mann-Whitney grid (every p ≥ 0.10), and the `r_multiple_20d`
  confound. Its verdict — *distance predicts nothing; choose the thickness on structural
  fidelity, not edge* — is recorded in the ruling rows and needs no instrument to stand. Only
  the unit bridge (the ATR ↔ box-height exchange rate) survived into this census, because a
  ruling cites its number.
* **the bar-state census** (his three ceiling states × singular-vs-run × what-follows) is a
  SEPARATE commissioned instrument and is not this file's job.
