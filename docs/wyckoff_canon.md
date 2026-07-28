# Wyckoff as Chrollo uses him — the concordance

**What this file is.** [`strategy_alpha.md`](strategy_alpha.md) says *what Chrollo does*. This file
says *which Wyckoff ideas Chrollo took, which it deliberately left, and which of his words it
reuses with a different meaning*. It exists so that an agent reasoning from Wyckoff knowledge does
not "fix" the engine toward textbook fidelity the operator does not want.

**Read it before** proposing, justifying, or reviewing any change whose argument contains the words
*"Wyckoff says…"*, *"canonically…"*, or *"to be more Wyckoff-correct…"*.

Established 2026-07-26 from the operator's two supplied schematics + the StockCharts tutorial,
and from his framing ruling of the same date.

---

## 0. The framing ruling — read this first

> **Wyckoff is a source of ideas, not a specification.**
>
> Operator, 2026-07-26: *"the truth is that Wyckoff doesn't actually work — taking his ideas and
> trying to dynamically apply them to how charts act today allows us to understand and find high
> quality places for trades that do big moves in a short amount of time."*

Three consequences that govern everything below:

1. **Textbook fidelity is not a success criterion.** The criterion is whether the read finds
   high-quality setups that move big, fast. A divergence from the schematic is **not a defect**
   unless it costs a real setup.
2. **Anti-bloat is a standing rule.** *"I don't want to bloat out the chart reader — not every
   little lever like PS or ST needs to be pursued. From real-life setups that worked, none of them
   really appear nowadays and they appear unreliable."* An absent canonical event is a **scope
   decision**, not a backlog item.
3. **Geometry first, volume second.** *"Volume does have a role, but our main focus should be the
   geometrical visual technical ability first, before we delve into measuring volume and making
   conclusions based on that rather than old textbooks from 100 years ago."*

**Therefore: do not open a PR whose entire justification is "canon has this and we don't."**
The burden is a real chart, a real setup, a real miss.

---

## 1. Sources of record

| Source | Standing |
|---|---|
| StockCharts ChartSchool, *"The Wyckoff Method: A Tutorial"* | The canonical secondary source. Already the cited authority for the two-form LPS sentence in [lps_final_structure_canon_2026-07-10.md](lps_final_structure_canon_2026-07-10.md). |
| **Accumulation Schematic #1** (Bogomazov / Pruden) | **The closer match to the live engine.** Spring → Test → LPS → SOS → BU/LPS, with Phase B contracting into the turn. |
| **Accumulation Schematic #2** (same authors) | The **no-spring** variant. Chrollo covers this path with the **V tip**, not with a Phase-C event. |

Both were supplied by the operator on 2026-07-26. Neither is a target to reproduce.

---

## 2. The two schematics, and which code path each names

### Schematic #1 — the spring path (closest to the engine)

Phase A: PS → SC → AR → ST. Phase B: boundaries widen (first rally clears the AR high; the
"ST in Phase B" undercuts the SC low), then **the swings contract into the right edge — the
clustering bars**. **Phase C: Spring → Test** (the Test is shallower and holds above the spring
low). **Phase D: LPS → SOS → BU/LPS.** Phase E: markup.

Engine correspondence: `find_spring` (penetration → reclaim → hold) owns Phase C; the contraction
into the right edge is `measure_contractions` + `atr_squeeze`; `detect_lps` owns the terminal event;
`measure_resistance_events` types the SOS; `buec_shelf` is the BU/LPS.

### Schematic #2 — the no-spring path (the V tip)

Same Phase A/B. **Phase C has no spring** — the lows hold above support and the turn happens at a
higher level.

**RULED (operator, 2026-07-26): the `v_tip` covers this.** *"In the code the 'V' TIP idea replaces
the gap between Phase C and Phase D in case a spring doesn't happen, and the first chart I showed
kind of resembles that."*

So the no-spring turn is **not** a missing Phase C. It is the V tip occupying the C→D seam
(`_bin_d_boundary_source = v_tip`, plus `support_tests` / `rising_support` / `inner_box` as the
other right-side evidence variants). **Do not build a third `bin_c_type` for it.**

> ⚠️ Consequence an agent must carry: `bin_c_present == 0` is **normal and correct** for the
> majority of bases. It means *"no spring"*, never *"supply was never tested"*. Any "was supply
> tested?" feature reads `_bin_d_boundary_source` / `phase_d_evidence_json`.

---

## 3. The operator's three spins on the canon

These are the deliberate departures. They are **rulings**, not drift.

### 3.1 Test and LPS are the same behavior; the label is reserved for the last one

> *"In my version I classify Test and LPS as the same behavior, but saving the LPS label to the last
> event that happened, for consistency measures."*

Canon labels several LPSs and separates the Phase-C "Test" from them. Chrollo treats all of it as
one behavior — **support forming and holding around the support zone** — and reserves the name
**LPS** for the terminal, trigger-owning instance.

**The code already implements this exactly:**
- `strategy_alpha.md` already states *"An LPS is support forming and holding around the support
  zone, in general… It is NOT defined by being a higher low."*
- `detect_lps_tests` enumerates the plural (rendered as **support test** bands) — canon's LPS-1..n.
- `select_active_lps_candidate` returns a single winner, recency-first — canon's last one.

So the drawn staircase *is* the Test/LPS sequence, and only the last band is named LPS. **Nothing to
build.** The vocabulary just needed stating.

### 3.2 The shakeout and its recovery are the load-bearing event

The emphasis is not the spring's *depth* but that it **recovers**, and that it comes in many
variations. Chrollo encodes this as one bounded-excursion model — penetration → reclaim →
significance → hold — with the scale typed at a single seam (`SPRING` vs `TERMINAL_SHAKEOUT`), so
the chart label, the phase read and the archive can never drift.

The `BIN_C_*` depth and linger caps are **breakdown defences**, not fidelity knobs: past them the
excursion is a genuine breakdown, not a shakeout. Do not loosen them to catch a deeper "variation".

### 3.3 Geometry first; volume is confirmation, never the conclusion

The precise doctrine — quote this, not "volume is unreliable":

> Volume **may confirm a pullback LPS and may score**. It **never defines an event**, never gates
> the holding-shelf form, and never places a rail.

Backing: [`lps.py:550`](../engine_alpha/structure/lps.py) and [`:581`](../engine_alpha/structure/lps.py)
guard `_vol_dry_refused` behind `if not holding_shelf:` — *"the shelf form is geometry-only
(grades-not-vetoes: volume never gates it)"*. `SCORE_VOL_CONTRACTION = 20` is the third-largest of
15 score components.

> ⚠️ **"Geometry is the only veto" does not scope the LPS detector.** `_vol_dry_refused` genuinely
> rejects candidates, and `vol_contraction` *multiplies* the pullback form's quality at
> [`lps.py:598-605`](../engine_alpha/structure/lps.py) — so a threshold edit changes **which window
> is elected**, not just how many fire. A doctrine-purity pass that deletes it moves the sealed
> ratchet.

---

## 4. What Chrollo took, adapted, and deliberately left

| Canonical event | Chrollo | Status |
|---|---|---|
| **SC / BC** — climax | `RootSwing.kind`, via `collect_root_anchors` | **TAKEN** — geometric only (pivot extremity + 15% / 20-bar prior move) |
| **AR** | `root.ar_bar` | **ADAPTED** — the Phase-B window *origin*, **never a rail** |
| **PS** — Preliminary Support | — | **DROPPED** (§0.2) — doesn't appear in working setups |
| **ST** — Phase-A secondary test | — | **DROPPED** (§0.2). Phase B opens at the AR low, so any post-AR retest is Phase-B material |
| **Spring / shakeout** | `SPRING` / `TERMINAL_SHAKEOUT` | **TAKEN** — the load-bearing event (§3.2) |
| **Test** | *support test* band | **MERGED into LPS** (§3.1) |
| **SOS** | `SOS` | **TAKEN** — typed by terminal geometry; no volume/spread tell, by §0.3 |
| **LPS** | `LPS` | **ADAPTED** — the terminal instance only (§3.1); **never gated on a prior SOS** |
| **BU** — back-up | `buec_shelf`, displayed *"LPS above R"* | **TAKEN**, but the canon *name* is retired — describe it plainly (§5) |
| **Creek / Ice** | — | **DROPPED** — never an object, and the word is now purged from the repo (§5) |
| **UT / UTAD / SOW / PSY** | — | **DROPPED** — distribution mirror, out of scope |
| **LPSY** — last point of supply | — | **DEFERRED to engine β.** *"LPSY is like an LPS but for distribution processes — an event that signals weak buyers. Perhaps when we get to work on engine β I would touch on that; for now it has no use for us."* (operator, 2026-07-26) |
| **Cause & Effect → P&F target** | cause = base length (`SCORE_BASE_AGE`); **no target** | **HALF-TAKEN** — Chrollo hands over a setup, not a trade plan |
| **Effort vs Result** | — | **DROPPED** by §0.3 |
| **Composite Man / five-step / nine tests** | — | **DROPPED** |

### The phases

| Phase | Canon | Chrollo |
|---|---|---|
| **A** | PS, SC, AR, ST | climax + AR only; ends at the AR |
| **B** | cause-building; **boundaries extend** | cause-building; **rails frozen**, breaches spent from a 20% / 10-consecutive-bar respect budget |
| **C** | always happens — spring *or* higher-level test | **means "an undercut below S"**; the no-spring case is the **V tip** (§2) |
| **D** | opens at the SOS | opens at earliest right-side evidence (`support_tests` ranks first) |
| **E** | markup | **does not exist**; `markup` is an in-box wave label |

### The two accumulation types (operator definitions, 2026-07-26)

| Type | Definition | Example |
|---|---|---|
| **Genesis Accumulation** (plain "Accumulation") | The **first, original** consolidation, which **predates the trend** and causes it | MSFT 2000–2014: a ~14-year range (SC ≈ 25, AR ≈ 36). Last LPS **2014-02-01**, then **+1500%** |
| **Re-accumulation** | An accumulation process occurring **already inside a trend** — usually with a prior consolidation behind it | The ordinary continuation base |

> ⚠️ **Correction to an earlier claim in this file: genesis accumulation is NOT out of scope.**
> The SMA-200 gate ([`evaluation.py:104-107`](../engine_alpha/evaluation.py), and structurally at
> [`box_primitives.py:60-64`](../engine_alpha/structure/box_primitives.py) where
> `collect_root_anchors` returns `[]` below the 200-day) does not block a genesis base. It blocks
> **firing early in one** — in Phase A/B while price is still under its 200-day, down near the SC.
> By the time the terminal LPS forms at the top of the range, price is above the 200-day and the
> setup is perfectly reachable. MSFT's 2014-02-01 LPS would pass this gate.

**What genuinely bounds genesis bases is scale, not trend:**

- `DAILY_STRUCTURE_PERIOD = '2y'` — the daily reader is trimmed to two years, so a 14-year cause is
  never *visible* as a box.
- `MAX_BOX_WIDTH = 0.18` — MSFT's 25→36 range is ~44% wide; it could never be elected as one box.
- `BASE_AGE_CAP_DAYS = 120` — cause credit saturates at ~6 months, so a decade-long cause scores
  exactly the same as a four-month one.

**The consequence is benign and worth stating plainly:** Chrollo catches a genesis-accumulation
*trade* through its **terminal LPS**, which is a right-edge event well inside the 2-year window —
without ever seeing, or getting credit for, the cause behind it. The whole-base view is the HTF
(weekly/monthly) reader's job. So the honest limitation is not "we can't trade genesis bases", it is
**"we systematically under-credit their cause"**.

---

## 5. False friends — words that will mislead you

Chrollo deliberately reuses Wyckoff's words with its own meanings. Importing canon meaning produces
wrong code.

| Word | Canon | Chrollo | The trap |
|---|---|---|---|
| **creek** / **ice** | a **wavy line** across rally highs (creek); its mirror in distribution (ice) | **RETIRED 2026-07-26 — the word is gone from this repo.** It never named an object, and carried three incompatible senses (the scalar `R`; a *body-basis* level in contrast to the wick-extreme `R`; canon's wavy line) | Operator ruling: *"I don't use that word… we can probably describe the event without needing to use it."* Say **"a break above R"** for the jump and **"the body level vs the wick extreme"** for the rail-placement family. Do not reintroduce it |
| **BU / BUEC** | back-up to the edge of the creek | **RETIRED as explanatory vocabulary 2026-07-26.** The wire key `buec_shelf` is frozen and stays; the *explanation* is now plain: an LPS that forms above the old resistance, after price broke out and came back to rest on it | Operator ruling: *"also don't know what BU means and probably can describe without it."* Read `buec_shelf` / `OVERSHOOT_R` as **"LPS above R"** |
| **LPS** | the low of a reaction **after an SOS**; a higher low; **several** | the **terminal** support test right of the V — no SOS precondition, not defined as a higher low, exactly one | adding `if not sos_events: return None` deletes most live fires — the population is pre-breakout coils where no SOS exists yet |
| **Phase C** | always happens | an undercut below S, full stop | §2 — the no-spring case is the V tip |
| **Phase D** | opens at the SOS | opens at earliest right-side evidence | `support_tests` ranks *first*, above anything SOS-shaped |
| **markup** | **Phase E** | an in-box R-rail **wave label** that can sit mid-base | `grep markup` to ask "is this in markup?" returns a wave, not a regime |
| **upthrust** | a **distribution** event (Phase C) | any failed breach of R inside an accumulation box, **stage-agnostic** | `if etype == "upthrust": # distribution` **fires constantly on good setups** |
| **sos_reclaim** | an SOS is the advance *through* resistance | an above-R **support test** — i.e. a **BU**. `phase_d.py` never imports the function that types an SOS | **wrong polarity.** Frozen wire key — the fix is this sentence, not a rename |
| **distribution** | Wyckoff distribution | `REGIME_DISTRIBUTION_DAY_*` / `regime_distribution_days` are **O'Neil index distribution days** | "add distribution detection" → agent lands in `market_context.py` and wires an index-breadth counter into a per-stock read |
| **Throwback** | Edwards & Magee vocabulary (the retest of broken resistance from above). Wyckoff's name is **BU / BUEC** | **RETIRED from display 2026-07-26** — `buec_shelf` / `OVERSHOOT_R` now read *"LPS above R"* (short *"above R"*) | Still present in prose and in the frozen negative-corpus case name `BBVA-throwback` (`tests/baselines/negative_corpus_meta.json`) — that is a **fixture identity**, do not rename it |
| **equilibrium box** | = canon's **trading range** | Chrollo's rename (both names live in the repo) | treating them as synonyms → agent writes `R = ar_high; S = sc_low`, trips `MAX_BOX_WIDTH = 0.18`, then "fixes" it by raising the cap — **silently reverting the worked-equilibrium rewrite** |

**Chrollo coinages — do not map these onto a Wyckoff term:** `root swing`, `rail`, `dead space`,
`band rails`, `story pool`, `the V`, `holding shelf`, `terminal valley`, `dwell` / `traversal` /
`occupancy` / `coverage`, `Stale-Support Reject`.

> ⚠️ **`band rails` is not a two-line boundary band.** Both schematics draw two resistance and two
> support lines; Chrollo carries **one scalar R and one scalar S**. There is no `box.R_outer`.
> `band rails` is a last-resort excursion-qualified candidate pool. `BAND_MAX_BOX_WIDTH = 0.23` is a
> class allowance for a pair already carrying a qualified deep below-rail event — raising it "to
> model the band" relaxes a junk defence.

> ⚠️ **`Mini-BC` / `Mini-AR` never existed in code and the name is retired** (2026-07-26). The two
> docs used to contradict each other — `structure_legend.md` built a section on them,
> `strategy_alpha.md:39` forbids the labels — and the legend is now aligned to the binding rule.
> `RootSwing.kind` is always the full `'BC'`/`'SC'`: a *qualification label* for which direction the
> anchor scan matched, never a claim about the stock's primary trend.

---

## 6. Do not propose these — tested-DEAD

Each was A/B'd against sealed acceptance criteria and rejected **by name**. A re-proposal must beat
the sealed protocol, not re-argue from canon.

| Tempting move | Why it is wrong here |
|---|---|
| Loosen respect / dwell / occupancy so canon's Phase-B boundary extension fits | Every lever tested: `EQ_MIN_HALF_DWELL` 0.15→0.125 admits ten junk candidates; →0.10 breaks the ratchet; `EQ_MAX_MID_DWELL` →0.50/0.55 breaks 4-6 pinned hits (MATX stops firing) and fires DGII junk; `MIN_BOUNDARY_RESPECT_PCT` →0.75 admits FLG + BBVA. *"Every gate floor is already sitting exactly where the junk begins."* |
| Re-read a bounded poke-and-close-back-inside as "respect" | Tested and REJECTED as a gate — admitted FLG + BBVA at every bound ≥ 0.5 ATR while converting **zero** Guided List misses. The wick-basis gate **is** the upthrust/junk defence |
| Swap dwell to a bar-as-unit basis | Tested and REJECTED — 10/26 hit identities break; DGII + FLG fire |
| Set rails to the climax→AR extremes | The cascade deliberately descends past them; canon-literal framing trips `MAX_BOX_WIDTH` at once, and raising the cap reverts the rewrite. Breaks `doctrine_audit` B2/B3/B4 |
| Cluster / order-statistic rail placement | Failed decisively: 20/66 rails within 0.5 ATR (needed 60). `cluster_rails` has **no engine caller** — a tripwire, not plumbing |
| Bounded compensation across gate margins | Tested-DEAD — the fail-one-leg-with-surplus profile has exact junk twins |
| Require a prior SOS before an LPS | The decoupling is *why* the engine reads a pre-breakout coil at all |
| Build a no-spring Phase C event | **Superseded by the V-tip ruling** (§2) |
| Add PS / ST detectors | **Ruled out** (§0.2) — anti-bloat |
| Add a volume gate anywhere | §0.3 + measure-first: a never-gated archived column, scored only after an edge read. The three volume constants are freeze-manifest-listed |
| Extend the LPS dry-up to the shelf form | Reverses the operator-ruled two-form doctrine, calibrated on his marked WTS + PBT shelves |
| Add a P&F count / cause-derived target | No machinery to extend — new doctrine. And **never** re-derive `TARGET_R_MULTIPLE`: that column set is the ground truth behind the 1,977-episode edge read and the RS/uptrend demotion |
| Restore `SCORE_RS_BONUS` / `SCORE_UPTREND_BONUS` | Demoted to 0 on evidence (corr −0.22 / −0.19 at n=1977) — the two worst terms in the book. Do **not** delete the zero-weighted ramps either; they preserve the archive trail |
| Build a universe RS ranker | One exists (`rs_rating`, live-wired, flag-off). `strategy_alpha.md:1294-1297` is **stale** — the action is a flag flip |
| Relax or tighten the SMA-200 baseline | Double-enforced veto; every pinned threshold was fitted on above-200MA tape. Either direction changes the firing set |
| Unify the "duplicated" Phase-D starts / two Vs / two Phase-C labels / `sos_reclaim` | Frozen capture seams. `phase_d.py:259-266` forbids collapsing without a fold_parity proof **and** an operator ruling |

---

## 7. Live gaps worth knowing (not a to-do list)

Filtered against §0.2 — these are the ones with a plausible cost, not canon-completeness items.

1. **Nothing asks "is this range distribution?"** A name that topped 3-6 months ago, ranges in the
   upper half, sits above a still-rising SMA_200 and is −20% YoY passes cleanly. The only live
   defence is the wick-basis respect gate plus the mandatory terminal LPS. This is a **geometry**
   question, so it is in-scope under §0.3 if it ever costs money.
2. **The near-miss lane is volume-blind.** All 15 `GATE_LEGS` are price geometry, so three refusals
   leave *no telemetry*: the LPS volume dry-up, the extension filter, and the SMA-200 refusal.
   "The near-miss lane shows nothing" ≠ "the box gates rejected it". Relevant now — this is the
   current working branch.
3. **The HTF read inherits every daily gap.** `htf.py` re-runs the same A→B→C→D bricks on
   weekly/monthly bars, so a no-spring turn one frame up reports as phase `'B'` (no V-tip path there).
4. ~~The LPS form enum has six values but only three carry labels~~ — **FIXED 2026-07-26.** All six
   now have signed display labels (`rising_support_shelf` → "LPS — rising support",
   `clean_downswing` → "LPS — clean pullback", `undercut_rebound` → "LPS — spring rebound").
   *Audit correction:* one critic called `clean_downswing` a negative verdict — it is not. Per
   `_clean_downswing` it requires both descent fractions at 1.0 in a tight box: a pristine
   single-swing pullback, and a positive form.
5. **The SC has no "close well off the low" test.** Canon's third climax component, and it is pure
   price — so it would pass §0.3 cleanly. Cheapest available fidelity upgrade *if* a real setup ever
   turns on it.

---

## The over-extension read — what the stretch family is for

**RULED (operator, 2026-07-26).** *"If the LPS is found at a genesis consolidation then that's the
energy source… its role is to measure an overly stretched position, to avoid traps of a deep
correction."*

So **the energy source is whatever consolidation the LPS is found at** — by definition, never a
"wrong reference". An earlier open question in this file asked whether a genesis base breaks the
stretch reference; it does not, and the question is withdrawn.

| Measure | Reference | Verdict |
|---|---|---|
| `lps_stretch_atr` / `lps_stretch_box` = `(lps_low − R) / ATR` or `/ box_height` | the elected box's ceiling — the code comment already calls `R` *"the energy source"* | ✅ **matches intent** |
| `last_supper_pullback_from_extension_pct` = `(anchor_high − lps_low) / anchor_high` | `anchor_high` = the High at the **elected LPS window's own first bar** ([`phase_features.py:264`](../engine_alpha/structure/phase_features.py), fed `elected_lps_anchor_bar` at [`:737`](../engine_alpha/structure/phase_features.py)) | ❌ **does not match intent** |

**The defect.** `LPS_LENGTH_MIN/MAX = 2/7`, so `anchor_high` is at most a **seven-bar-old local
high** — a window edge, not a pivot. The operator's anchor is *"the last pivot that caused that run
up"*. If the trapping run-up peaked 15 bars before the LPS, the measure reports a shallow local
pullback and **under-reports exactly the over-extension it exists to catch**. The field is named
*"pullback from extension"* but is not anchored on the extension.

**BUILT 2026-07-26 — four new measure-only columns**, anchored on the last zigzag **peak** at/before
the LPS low (`_run_up_pivot_bar` in [`phase_features.py`](../engine_alpha/structure/phase_features.py),
off the shared `_find_pivots` skeleton — no new detection machinery):

| Column | Meaning |
|---|---|
| `last_supper_pivot_stretch_atr` | `(run-up pivot high − R) / ATR` — **the operator's measure**: how far above the energy source the run-up reached |
| `last_supper_pivot_stretch_box` | same, in box-heights |
| `last_supper_pullback_from_pivot_pct` | `(pivot high − LPS low) / pivot high` — the corrected give-back depth |
| `last_supper_pivot_bars_back` | bars from the pivot to the LPS low — the mis-anchoring diagnostic |

Added **alongside** the existing three, never replacing them: redefining a live column in place makes
new rows non-comparable to every historical one while looking like a fix (the `bin_a_*` seam
precedent). Measure-only — never gated, never scored, no fire can move.

**Measured evidence (17 Guided-List tickers at their last valid fire):**

- The defect is real but **tail-shaped**: `8/17` report a deeper give-back under the pivot anchor,
  `9/17` are identical (median ratio **1.00×**). Where the run-up pivot sits within a bar or two of
  the LPS window, the old anchor was already right.
- The tail is where the trap lives: **EGBN 0.019 → 0.100 (5.3×)**, WTS 2.7×, CTOS 2.4×, PKE 1.5×.
  The old measure told EGBN it had given back **1.9%** when the real give-back from the run-up pivot
  was **10%** — a "not stretched at all" reading on a genuinely stretched entry.
- Live-archive confirmation of the ceiling: across 4,561 populated rows the old column's **maximum
  ever recorded value is 0.144**. It structurally cannot report a deep pullback.
- The mechanism is **not** mainly the 7-bar cap. The old anchor is the *elected window's first bar*,
  and elected windows are typically 2–3 bars, so its effective reach is ~2–3 bars, not 7.
- `pivot_stretch_atr` spans **−1.52 … +2.55 ATR** across the sample — negative meaning the run-up
  never cleared R (the LPS formed inside the box, no over-extension), so "measured and flat" stays
  distinguishable from "unmeasured".

Calibrate against forward returns before this is allowed to matter.

## Open questions for the operator

*(none currently — see the settled list below)*

**Settled 2026-07-26:**
- **LPSY** → engine β (row above); no use now.
- **Re-accumulation vs genesis accumulation** → defined above; the earlier "out of scope" claim was
  wrong and is corrected in place.
- **"Throwback"** → retired from the display layer; `buec_shelf` / `OVERSHOOT_R` now read
  **"LPS above R"**.
- **Genesis-cause credit → NO.** *"The algorithm probably won't be able to encounter a thing like
  this ever again — not sure it can even detect something like this at such scale."* Do not raise
  `BASE_AGE_CAP_DAYS` or build an HTF cause-credit path for genesis-scale bases. The 120-day
  saturation stands, and under-crediting a once-in-a-decade cause is an accepted cost.
- **The stretch reference** → correct as built; see the section above. The open item that remains is
  the `anchor_high` defect, which is a measurement bug, not a doctrine question.
