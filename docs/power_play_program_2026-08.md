# Power-Play species program — build record (2026-08)

The operator's ruling (`docs/decisions.md` 2026-08-14, commit `c029555`): **Power Plays are
wanted setups** — the young high-tension continuation base (explosive leg → holding shelf)
must be read, watched, and eventually graded, and "Acceptable Misses" is re-ruled. This doc
is the program's committed evidence record (EC-16): design rulings, audits, and the
task-by-task build trail. Nothing in this program flips live; every behavior lands dark
behind default-off flags, and flips are the operator's on eyeball evidence.

## The species, literature-verified (2026-08-17 research sweep)

**Power Play (Minervini, *Trade Like a Stock Market Wizard* 2013) = High Tight Flag
(O'Neil, *How to Make Money in Stocks*) — one pattern, two names** (Minervini's own coinage
is "velocity pattern"). Book criteria: prior advance **≥100% within 8 weeks** on huge
volume (O'Neil: 100–120% in 4–8 weeks; Bulkowski's studies accept ≥90% in ≤2 months);
pause **3–6 weeks — "some can emerge after only 10 or 12 days"** — correcting **≤20%**
(low-priced stocks up to 25%); VCP characteristics required **unless** the total correction
is ≤10% ("already tight enough"); Minervini's ONLY setup entered "with a dearth of
fundamentals" — the velocity is itself the institutional signal. Bulkowski's winning flags
retrace 10–34% of the pole and are **10–29 calendar days (~7–20 trading bars) wide** —
which sits almost entirely inside the engine's 25-bar effective reading clock
(`MIN_BASE_DAYS` 20 + `STRUCTURE_EDGE_SKIP_BARS` 5): the clock does not occasionally miss
the species, it excludes it by construction.

Specimen scorecard (measured from the cache, as-of 2026-08-13): **MAN = textbook HTF**
(best-40-bar pole +111.9%, correction 12.2%, shelf 20 bars — passes every book test;
invisible to the engine). FTNT (pole +40.9%/40 bars, +123.9% over 13 weeks) is the
*broader* continuation base, as are HELE (+70.9%) and AVTX (+64.9%) — all of which the
engine already fires. MRVL/ARM poles qualify (+124.6%/+135.6%) but −50% corrections mean
the original flag failed. The engine's gap is exactly the young, pole-qualified end.

---

## Task 1 — the `MIN_BASE_DAYS` audit and the ONE species preset

### Ruling vocabulary

Two mechanisms exist in the codebase, both deliberate, and the audit assigns every use
site to one of them:

- **FOLLOWS the preset** — the site reads `settings.MIN_BASE_DAYS` lazily at call time
  inside the election walk, so a scoped window override moves it (the
  `htf.timeframe_windows` behavior).
- **STAYS pinned** — the site is deliberately preset-immune. The codebase's documented
  precedent is `STRUCTURE_ATR_SAMPLE_OFFSET` (`config/settings.py:163-169`): an
  import-time copy, bound once, with a comment saying exactly why it must not follow
  window overrides.

### The audit (every use site, ruled)

**A. The seeding clock — the species lever (all FOLLOW):**

| Site | Mechanism | Ruling |
|---|---|---|
| `bricks.find_root_swing` → `collect_root_anchors(eval_df, settings.MIN_BASE_DAYS)` | lazy read, passed as `min_days` | **FOLLOWS** — this IS the reading clock |
| `box_primitives.collect_root_anchors` (3 legs: frame floor `min_days+15`, `scan_hi = end - min_days`, AR-age `(len - ar_low_bar) >= min_days` in both BC/SC branches) | parameter | **FOLLOWS** via the parameter |
| `bricks.validate_equilibrium` walk guard `len(eq_df) < MIN_BASE_DAYS` | lazy read | **FOLLOWS** — the clock's second enforcement |
| `consolidation.find_outer_box` / `detect_boxes` `min_days` defaults | lazy default | **FOLLOWS** (diagnostic mirror of the same walk) |

**B. In-walk maturity floors — FOLLOW, with the divergences recorded:**

| Site | Today (clock 20) | Under a species clock C | Ruling |
|---|---|---|---|
| `box_primitives.trend_terminal_legal_open` (closure binds `settings.MIN_BASE_DAYS` at factory time, in-walk) | ≥20 bars since covering trend's terminal (LIVN ruling 2026-07-27) | ≥C bars | **FOLLOWS** — same maturity concept as the clock; HTF already scales it (6/4). The LIVN ruling calibrates the DEFAULT lane; the species lane's boundary is exactly what the census + operator rulings decide. Flag currently dark anyway. |
| `lps.py` overshoot-rescope matured-cause floor `base_len >= 2*MIN_BASE_DAYS` (BBVA/CTOS ruling 2026-07-17) | ≥40 | ≥2C | **FOLLOWS** — "matured = 2× the minimum" is the invariant (HTF: 2×6); the acceptance battery pins that a species base at 2C may rescope while <2C falls back. Recorded as a deliberate divergence from the BBVA letter (which bound the default lane). |
| `rail_qualification.qualify_pair_events` window floor + 2× terminal-shakeout floor (SPCB ruling) | ≥20 / ≥40 judged | ≥C / ≥2C | **FOLLOWS** — band/story pools are in-walk; same 2× invariant |
| `rail_qualification._qualify_band` post-excision floor | ≥20 judged | ≥C | **FOLLOWS** |
| `inner_box.inner_zigzag` / `inner_box_at` window floors | ≥20 | ≥C | **FOLLOWS** (inner candidates still need `INNER_MIN_DAYS` 15, which is NOT in the preset — tiny species bases simply grow no inner box) |
| `gate_margins.complete_leg_vector` | caller-bound floors | measures gates in force | **FOLLOWS** — margins must describe the active law, or near-miss telemetry lies |

**C. Post-read sites — STAY at the default clock (the preset never wraps them):**

| Site | Why it stays |
|---|---|
| `scoring.py` base-age bonus `base_len > MIN_BASE_DAYS` | Age credit is real cause; a 10-bar base earning age points is fiction. Scoring runs OUTSIDE the walk-scoped override, so it stays at 20 with no code change. |
| `metrics.measure_story_richness` denominator floor | The floor exists to kill short-base denominator luck — precisely the species' shape. Species rows get honest raw numerators+denominators via the Task-7 archive family instead. Post-read → stays. |

**D. The import-time copy (the McKinney finding):**

`PIP_MACRO_MIN_BASE_BARS = MIN_BASE_DAYS` (`config/settings.py:131`) is bound at import
and will NOT follow a `MIN_BASE_DAYS` override. Today this is harmless everywhere: the HTF
walk never runs `resolve_phase_a`, so the constant is only consulted on the daily default
path. Under the species preset the macro Phase-A bridge (overlay-only, never a rail) would
demand 20 post-AR bars while the species clock demands C — an incoherent overlay read.
**Ruling: the species preset dict lists `PIP_MACRO_MIN_BASE_BARS` EXPLICITLY** (setattr
overrides the module attribute regardless of how it was initialized), so the one preset
moves both names together. A naive `MIN_BASE_DAYS`-only patch would silently lie — this is
why the preset is a declared dict, never a hand-threaded parameter.

**E. Instruments** (`tools/trend_terminal_ab.py`, `tools/calibration_stat_card.py`,
`tools/structure_case_audit.py`, `tools/backtest_watchlist.py` — the latter deleted
2026-08-20, superseded by `core.archive.seed_recall`): all read settings lazily
and therefore describe whatever law is in force; the census (Task 3) applies the species
preset through the same one mechanism and stamps the clock value on every row.

### The preset design (lands dark in Task 5)

- **Shape:** `POWER_PLAY_WINDOWS` — a settings dict in the exact `HTF_WEEKLY_WINDOWS`
  mold, carrying ONLY the keys the species moves:
  `{"MIN_BASE_DAYS": <census-ruled clock>, "PIP_MACRO_MIN_BASE_BARS": <same value>}`.
  Nothing else: `STRUCTURE_EDGE_SKIP_BARS` stays 5 (the edge reserve is a data-integrity
  frame, not a maturity clock — the HTF presets shrink it only because resampled frames
  are short), and no trend-qualification window moves (the species' prior leg is a
  full-sized daily trend; only the maturity clock is different). The clock VALUE is not
  chosen in this task — Task 3's census and the operator's ruling choose it; Task 5 lands
  it at the census-justified value, never a placeholder.
- **One mechanism, three presets (EC-3/EC-18):** the scoped save/restore core of
  `htf.timeframe_windows` is extracted into a shared `window_override(preset)` context
  manager; `timeframe_windows` delegates to it verbatim (byte-identical behavior, pinned
  by the existing HTF restore test), and the species lane enters through
  `window_override(settings.POWER_PLAY_WINDOWS)`. Never a forked collector, never a
  copied CM.
- **Scope: the election walk ONLY.** The override wraps the species pass's
  `read_structure` consultation (Task 8's lane worker), exactly as `timeframe_windows`
  wraps `_read_htf_structure`. Post-read scoring and metrics run outside it and keep the
  default clock (section C above falls out by construction, with zero special-casing).
- **Manifest:** `POWER_PLAY_WINDOWS` joins `ENGINE_SETTINGS_KEYS` beside
  `HTF_WEEKLY_WINDOWS`/`HTF_MONTHLY_WINDOWS`, together with the species flag and any pole
  qualifier knobs, in ONE dark-add rotation (the EC-29 seam) — Task 5 batches them.
- **Species-precondition names (reserved for Tasks 3/5):** the pole qualifier the census
  screens on — working names `POWER_PLAY_POLE_MIN_GAIN` (literature anchor ~0.90–1.00),
  `POWER_PLAY_POLE_WINDOW_BARS` (40 ≈ the 8-week book window), and the flag
  `POWER_PLAY_PRESET_ENABLED` (default off). Naming-doctrine-safe: "Power Play" is
  Minervini's own term, operator-adopted 2026-08-14.

### Task-1 verdict (part 1 of 2 — see Task 2 below)

The species lane needs exactly TWO settings names moved together through one scoped,
self-restoring, manifest-registered override — everything else either follows coherently
inside the walk (the HTF precedent, divergences recorded above) or stays default by
construction because the override never wraps post-read code. No second cascade, no
per-site pinning, no new mechanism.

---

## Task 3 — the census instrument

**Built: `tools/power_play_census.py`** (+ battery `tests/test_power_play_census.py`, 10
tests). The clock-sweep evidence the preset's value will be ruled from. Priced FIRST and the
arithmetic published in the tool: measured against the real cache 2026-08-17 — **5,523
tickers → 13,955 pole-qualified episodes; 55,820 elections ≈ 28 min**, vs a naive
every-ticker × every-session grid ≈ **46 hours per cache-year**. Key properties, each
carried by a battery test:

- **Vectorized species-precondition screen** (the pole is a rolling return) emits bounded
  (ticker, episode) pairs; episode = (ticker, climax, AR) via the collector's own mechanics
  (trailing local-max peak; AR = argmin low within `AR_MAX_BARS`, close-confirmed at
  `AR_MIN_DROP_PCT`), deduped deterministically.
- **First legal look solved from the collector's walls:**
  `p >= max(ar + clock + skip − 1, climax + clock + skip)` — hand-reasoned in the battery.
- **Honest absences are first-class rows:** `not_watched_clock` (breakout before the
  clock's first legal look — no election run, the wall IS the finding) and `pending`
  (first legal look beyond the cache). Verdicts are a CLOSED set.
- **Truncate-then-prep** via `tools.replay.prepared_frame_with_reason` (prep cached per
  (ticker, as-of)); the election re-runs per clock through the ONE two-key override
  `{MIN_BASE_DAYS, PIP_MACRO_MIN_BASE_BARS}` (Task 1 §D).
- **Outcomes start at each clock's OWN knowable bar** (forward returns from the row's
  as-of on the raw frame — the EC-10 pattern), partial horizons partitioned with
  `*_complete` flags.
- **Sidecar only** (`--out` JSON, never `setup_archive`), stamped with clocks, screen
  params, `engine_config_version`, cache state, and the power-play marks fingerprint.
- **Battery:** determinism (byte-identical double run), the lookahead tripwire on the
  operand the pipeline guarantees (a prepared frame past its as-of VOIDs the run and the
  verdict prints on EVERY output mode — EC-31), sealed-output guard (EC-14), match basis
  in DATES (2y-trimmed frames never compare positions across frames).

Also fixed in this task (pre-existing EC-14): `tools/trend_terminal_ab.py` `--json` and
`--sheet` wrote user-supplied paths without `refuse_sealed_output`; both now route
through it.

---

## Task 4 — the ruling sheets (built 2026-08-18, after the species census re-run)

**The re-run executed first** (the one executable next step, Task 6 section below):
full-cache species read (clock + form), 13,857 episodes × 4 clocks = 55,428
elections, **measured wall clock 48 min (10:09 → 10:56)** vs the 369-min plan —
`ROW_MS = 400` embeds the pre-fix prep assumption and now overprices ~7.7×
(the per-ticker prep cache shares (ticker, as-of) preps across clocks and the
refused-universe majority); retune it at the census's next touch, not silently.
Tripwire OK; sidecar `output/power_play_census_species.json`, manifest
`c1edd7c03102`, marks `4f53cda18c2b`. The 2026-08-17 clock-only sidecar is
superseded evidence, as recorded.

**Built: `tools/power_play_sheets.py`** (+ battery `tests/test_power_play_sheets.py`,
11 tests — pure selection, no matplotlib). The census-to-operator surface on the
`trend_terminal_ab` page pattern: counts lead, force-ranked cards, one monospace
provenance line, generated never hand-written. Key properties:

- **Five sections, one ask each** (populations quoted; charted subset capped at
  the 40-ruling budget; nothing silently dropped): S1 the wall's misfiles,
  S2 the clock's marginal catch (cascaded at 8, walled at 10 — 125 episodes,
  of which only 4 elect at first look: **the walls after the clock are the
  real story**), S3 what the form admits (83), S4 the best book-valid poles it
  refuses (1,591), S5 the latch (`elected_other`, 92 — OKTA and GH sit here
  LIVE).
- **The S1 discovery (decision-relevant for the clock ruling):** the census
  breakout wall is the first close above the POLE PEAK (`ticker_episodes`);
  a drift-up holding shelf crosses its own pole peak MID-BASE, so **MAN's own
  July episode files `not_watched_clock` at every clock** (wall says resolved
  07-29; the operator's breakout was 08-13) — and HELE (both episodes) and
  FTNT's June shelf file identically. The not-watched counts therefore misfile
  some of the species' best members. S1 charts the four named-anchor episodes +
  the fast-resolution cohort (census breakout ≤ 7 calendar days after the AR;
  714 episodes) so the operator's keeps measure the misfile rate — a
  species-form wall calibration, ruled before any wall change is proposed.
- **Force-ranking** (the operator's attention is the budget): book-valid rows
  (flag depth ≤ the literature's ~25% limit) outrank the rest everywhere —
  the deep-"flag" tail of this cache is reverse-split artifacts and failed
  flags. S1/S2/S3 rank boundary-first (nearest the pole screen edge — the
  FTNT/MAN divide), S4/S5 textbook-first (the expensive error class leads).
  LIVE means unresolved AND the look within 45 days of the cache edge;
  merely-unresolved old rows chip "unresolved".
- **Cards are as-of only**: each chart truncates at that episode's own first
  legal look (pole window + shelf, volume subpanel, pole-peak line, climax/AR
  marks, elected rails when present) — never the aftermath, and no forward
  returns ride the cards. The aggregate tables carry the forward evidence
  (complete horizons only). **Headline: clock 8's elected cohort is the only
  one with positive forward returns** (median fwd_20 +2.8%, 54% winners,
  n=79; clocks 10/15/20 all negative on their elected cohorts).
- **Verdict capture with no transcription seam**: keyboard k/j/s + one click
  per card, banked tally, export downloads a JSON whose rows carry the census
  identity VERBATIM (ticker, climax, AR, clock, first legal look, census
  verdict) + `engine_config_version` + marks fingerprint — the
  `read_verdicts` keying discipline. Storage-blocked browsers degrade to an
  in-session bank (export still works). Renders cache by
  (manifest, render-rev); a VOID census (tripwire) is refused outright.
- Outputs under `output/power_play_sheets/` (SHEETS.md + index.html + png/),
  every write path through `refuse_sealed_output` (EC-14). Bulk verdicts land
  in the editable population at ingest time, never in the sealed corpus
  (Task 2 ruling); certified must-fire marks still graduate per-mark (EC-9).

**RULED 2026-08-18 — all 40 cards, same day** (sealed evidence:
`docs/power_play_verdicts_2026-08-18.json`, EC-44; export keyed verbatim to the
census identity + manifest `c1edd7c03102`). The tally, 25 keep / 15 junk / 0
skip:

- **S1 (the wall's misfiles): 6 keep / 4 junk** — all four named-anchor
  episodes KEPT (MAN, FTNT, HELE ×2) plus BLNK and EYE. A MAJORITY of the
  wall's book-valid "resolved" filings were still real bases at the look —
  the close-above-pole-peak wall misfiles the species at scale. The four
  junks (APGE, BYRN, GPRE, PPSI) share no clean arithmetic tell with the
  keeps (EYE kept at a 1-day gap, PPSI junked at 1 day): the separator is
  his eye, exactly why the wall calibration must be ruled from charts, not
  a threshold.
- **S2 (the clock's marginal catch): 8 keep / 2 junk** — what only the
  8-trading-day wait can watch is overwhelmingly WANTED (junk: CNR, TRDA).
- **S3 (what the form admits): 6 keep / 2 junk** — the two junked
  admissions are exactly the two weakest poles charted (VCYT +93%, STAA
  +90%, the boundary probes).
- **S4 (best book-valid poles refused): 1 keep / 7 junk** — the form's
  refusals are mostly RIGHT by his eye; **ABVX** (+1054% pole, 14% flag) is
  the one refusal he'd have admitted. He junked MDGL.
- **S5 (the latch): 4 keep / 0 junk** — GH, OKTA (both LIVE), CVGI, ELTX.
  CAVEAT recorded: the sheet's S5 question was two-in-one (old base right
  vs fresh episode wanted); the keeps are read as "the fresh episode is a
  wanted setup" pending the operator's clarification.

**Answered same day (operator, 2026-08-18 — decisions.md):** the clock is
RULED 8 ("everything else stays the same" — confirmed); the form STANDS, and
the species-scoped occupancy/traversal relaxation is approved as a measured
experiment (*"the main point of these is that we understand and read
correctly, its less about the raw numbers and more about the shape of
things"*) — swept via the census `--override` lever (validated names, sidecar-
stamped), first run: clock 8 with `EQ_MIN_HALF_DWELL=0`, `EQ_MIN_COVERAGE=0`,
`EQ_MIN_TOUCHES_PER_RAIL=1`, `EQ_MIN_TOUCH_THIRDS=1`, `TRAVERSAL_MIN=0`,
`TRAVERSAL_MIN_DENSITY=0` → `output/power_play_census_relaxed.json`. The
edge-reserve sweep was DECLINED ("I don't see why we should?") — the reserve
stays 5. **His S5 answer was a defect report, not a latch verdict:** on the
S5 charts (CVGI/OKTA/GH, marked screenshots) the engine's AR marker sits
several bars past where the first reaction's down-move finished — the argmin-
within-15-bars form drags the AR to a later marginal low; on OKTA he marks
TWO acceptable ARs (the clustered-AR read, as on MAN). This corroborates the
open first-reaction-AR program ([[project_ar_first_reaction]], kill-by
2026-09-15) and extends it to the species episode collector
(`ticker_episodes` uses the same argmin form). Recorded; not changed in this
diff.

**The relaxed-floors experiment EXECUTED and FALSIFIED the same evening**
(Tested-DEAD row 2026-08-18; sidecar `output/power_play_census_relaxed.json`,
overrides stamped, tripwire OK): every occupancy + traversal floor OFF at
clock 8 flips only 36/1,591 refusals to episode elections, the flipped cohort
loses money (fwd_20 med −5.1%, 31% win, n=35), ABVX still does not elect, and
the one newly-electing S4 card (ANL) is one the operator junked. The floors
stay; the run also caught two instrument defects fixed in the same touch (the
census now SAVES BEFORE REPORTING — a cp1252 console killed a finished sweep
at the '≈' print — and a hidden detached process can be OS-suspended: prefer
session-attached runs for sub-hour sweeps).

**Still open:** the EC-8 ScanTimer bound at clock 8 → the both-flags flip;
the breakout-wall calibration (S1's misfile evidence + the recaptured MAN
fact — now THE species lever; see the section below); the AR-drag fix inside
the first-reaction program. S2/S3 keeps double as dated climax/AR trend-end
labels (Task 11's unblock).

---

## The breakout-wall calibration (2026-08-18, post-rulings)

**The misfile:** the wall resolves an episode at the first close above the
POLE PEAK; a drift-up base crosses that line mid-base (MAN: wall said
resolved 07-29, the operator's breakout was 08-13), so the wall filed 6 of
his 10 ruled S1 cards — every named anchor included — as "resolved" while
they were still real bases by his eye.

**Candidate walls probed against the 10 S1 rulings** (as-of forms only; a
good wall keeps his 6 keeps UNRESOLVED at their clock-8 looks and still
files his 4 junks):

| wall form | keeps unresolved | junks still filed |
|---|---:|---:|
| current (close > pole peak) | 0/6 | 4/4 |
| crossing must hold 2 bars | 1/6 | 4/4 |
| crossing must hold 3 bars | 3/6 | 4/4 |
| **departure: close > peak + 1×ATR10** | **4/6** | **4/4** |

The departure form wins and is a SHAPE statement in the engine's own unit
(hugging the peak is base-building; only a real departure resolves): it
keeps all four named anchors (MAN, FTNT, HELE ×2) alive and files all four
junks. Its two misses: BLNK (departed by the yardstick 4 days before the
look, he still called it a base) and EYE (resolves exactly ON its look day —
the `p < breakout` boundary). Not tuned past 1.0 on n=10, deliberately.

**Landed dark:** `POWER_PLAY_BREAKOUT_DEPARTURE_ATR = 0.0` (settings +
manifest dark-add; 0.0 reproduces the close-above-peak wall byte-identically
in a dedicated code branch), implemented at the ONE episode mechanics site
(`ticker_episodes` — census and live lane inherit together, EC-18/EC-43),
with the hug case pinned by hand-reasoned battery
(`test_departure_wall_ignores_peak_hugging_crossings`: a 0.2-above-peak hug
does not resolve at ×1.0, the +5.5 departure does; identity unchanged).

**The A/B:** full-cache clock-8 run with
`--override POWER_PLAY_BREAKOUT_DEPARTURE_ATR=1.0` →
`output/power_play_census_wall.json`. (The FIRST run was a silent no-op —
the `--override` lever wrapped only the elections while the wall is consumed
at SCREEN time; caught by the identical summary counts, fixed by scoping run
overrides over the whole read, pinned by
`test_run_overrides_scope_the_screen_not_just_the_elections`.)

**READ-OUT (2026-08-18, tripwire OK):**

- **MAN ELECTS.** Under the departure wall the July episode's breakout
  re-dates to **2026-08-13 — the operator's own breakout date, to the day**
  — and the species read at clock 8 elects his base (`elected_episode`).
  The specimen the program was built around is now read end-to-end.
- **903 of 2,207 filings get their looks back**; they land honestly:
  497 `refused_universe` (the baseline filters refuse them anyway),
  371 `no_election`, 25 `elected_other`, **10 `elected_episode`** — and the
  newly-elected cohort MAKES money (fwd_20 median +2.6%, 67% winners, n=9;
  contrast the falsified floors experiment, whose flips lost −5.1%).
- **Election quality is preserved while catching more**: the wall run's
  whole elected cohort is n=88 med +2.7% / 56% win vs production's n=79
  med +2.8% / 54% — +12% more elections at the same forward quality.
- His S1 cards under the wall: MAN elected; HELE ×2 + FTNT watched (refused
  elsewhere at first look — the wall no longer the wall); BLNK/EYE stay
  filed (the probe's two known misses); ALL FOUR junks stay filed.
- Census cost: cascades 1,766 → 2,172 (+23% instrument work at clock 8).

**RULED SAME NIGHT (operator: "Lets go with your recommendation" —
decisions.md row 2026-08-18).** Landed: knob 1.0, ratchet recaptured — **the
new frozen fact: MAN @ 2026-08-12 is `admitted_dark` at clock 8** (his exact
dates; the dark lane reads the specimen end-to-end); FTNT's watch honestly
reports its June shelf unframed (`pp_shelf_unframed`) while its live fire
stays the control. Two corrections landed with it, both caught by the
knife-edge batteries: the yardstick now measures the ten bars BEFORE the
crossing (the first form let a breakout bar raise its own wall), and the
synthetic frames depart decisively (a 103.0 close against a 103.0 wall was
float-knife-edge). The A/B re-ran under the landed arithmetic on same-cache
legs (the nightly scan refreshed the cache mid-evening — through 2026-08-18;
the inclusive-form sidecar is superseded): MAN elects at his date; 855
filings regain looks (464 refused_universe / 359 no_election / 22 other /
10 newly elected @ +2.6% med, 67% win); cohort 88 @ +2.7%/56% vs legacy 79
@ +2.8%/54%. Full suite 1,551/0. **Open = the EC-8 ScanTimer bound at clock
8 → the operator's both-flags flip.**

---

## Task 5 — the species preset lands dark

**Built (one dark-add rotation = the program's declared EC-29 seam):**

- `config/settings.py`: `POWER_PLAY_PRESET_ENABLED = False` +
  `POWER_PLAY_WINDOWS = {MIN_BASE_DAYS, PIP_MACRO_MIN_BASE_BARS}` (the two names move
  together — Task 1 §D) + the pole-qualifier knobs `POWER_PLAY_POLE_MIN_GAIN` /
  `POWER_PLAY_POLE_WINDOW_BARS` (the census reads them as its screen defaults).
- `engine_alpha/structure/htf.py`: the scoped save/restore core of `timeframe_windows`
  extracted as **`window_override(preset)` — the ONE window-override mechanism**;
  `timeframe_windows` delegates (behavior pinned by the existing HTF restore test).
- `engine_alpha/freeze/manifest.py`: the four names in ONE batch with the seam comment;
  the hash rotates once, and the two epochs are output-identical (nothing reads the new
  keys on any eval path yet), so pooled analytics may bridge the seam.
- `docs/flag_ledger.md`: the Dark-table row (kill-by 2026-10-31) — machine-enforced by
  `tests/test_invariants.py`.
- Battery `tests/test_power_play_preset.py` (6): flag dark; the dict moves EXACTLY the
  two names, equal, and shorter than the default clock; override scopes + restores both
  (exception path included); typo refusal before any set; HTF delegation intact;
  manifest batch present.

**RULED 2026-08-18 (was provisional 10):** the dict's clock value is **8** — the
operator's ruling off the census + his 40 sheet verdicts (decisions.md row;
"everything else stays the same": species lane only, both flags stay dark). The
ratchet baseline was recaptured at the ruled value in the same declared change
(EC-29); the new frozen MAN fact — watched at 8, `refused_clock` by the
breakout wall — is the wall calibration's standing evidence. The EC-8 cost
bound (Task 8's ScanTimer phase at clock 8) remains the flip's open gate.

---

## Task 6 — the species story form in the ONE story admission

**RENAMED 2026-08-18 (operator naming ruling, decisions.md):** built as the
"holding shelf"; the record now names the BEHAVIOR measured — the form is
`event_map.resistance_contraction_admission`, its admitting sentence derives from
the terminal posture via `resistance_contraction_label` ("contracting above
resistance" / "contracting at resistance"), and the battery is
`tests/test_resistance_contraction.py`. The section below is the build-time
record with the old name where it was written.

**Built (dark behind `POWER_PLAY_STORY_FORM_ENABLED` — its own gate BY DESIGN):**

- `event_map.holding_shelf_admission` (now `resistance_contraction_admission`) —
  the second NAMED ruled form beside
  `story_admission` (EC-18: one implementation each, both in event_map; instruments
  delegate). Provisional legs from the operator's eye model + the MAN diagnosis:
  **floor never FAILED** (`n_failed_s == 0`) + **no terminal S-drift** + **the right edge
  ENGAGED at the ceiling** (`terminal_r_engagement`: an open R episode — the
  extreme-proximity hang; a terminal `R^` bar produces the same open episode, so
  post-breakout is covered by construction).
- `episode_sequence_stats` gains two additive keys: `n_failed_s` (knowable-failed under
  the same as-of discipline as completed) and `terminal_r_engagement` (right-edge read;
  "open" is only ever assigned to terminal episodes).
- `_story_pool_candidates`: the O(1) prefilter grows the shelf form's exact necessary
  condition (`last_high >= R − tol` — the engagement HALF of `frame_terminal_posture`)
  behind the flag; admission tries the S-test form FIRST (its record stays byte-identical:
  bare profile, trace detail "ruled form"), then the shelf form, which NAMES itself —
  `story_admission_profile` = `holding shelf | <profile>`, trace "story-admitted (holding
  shelf): …". Refusal message unchanged in both modes.
- **Why a second flag:** the lane chooser (`POWER_PLAY_PRESET_ENABLED`) will one day be
  ON in the live scan; if the form keyed on it, the PAYING read's admission would grow
  shelf admissions the moment the lane flips. The species lane instead toggles
  `POWER_PLAY_STORY_FORM_ENABLED` under the ONE scoped override (`htf.window_override`,
  riding the preset dict) around its OWN election only — a passenger never touches the
  paying read. (The build-time record here said `flag_capture`; corrected 2026-08-17
  review, Fowler — and `tools.replay.flag_capture` now DELEGATES to `window_override`,
  so the instruments and the lane share one save/restore core.) Joined the one manifest
  rotation + its own flag-ledger Dark row (kill-by 2026-10-31, flips together with the
  preset or not at all).
- The census now measures THE SPECIES READ (clock + form) — its override key set is
  derived from `settings.POWER_PLAY_WINDOWS` itself plus the form flag. The 2026-08-17
  sidecar run predates BOTH this and the as-of-consistent first-legal-look fix (council
  review finding 4) — it is superseded evidence; the sheets must not be built from it.

  **THE RULING LOOP'S RE-RUN (the one executable next step, EC-36).** Interpreter: the
  ChrolloDashboard venv python, named once here — this machine's bare `python` is the
  documented two-installs trap. Copy-runnable, from the repo root:

  ```
  "C:\Users\User\AppData\Local\ChrolloDashboard\venv\Scripts\python.exe" -m tools.power_play_census --out output\power_play_census_species.json
  ```

  (Hours-scale on the full cache — the honest pricing is in the tool's `--plan` output;
  detach it if the session must survive. The sidecar then feeds the Task 4 sheets.)
- Battery `tests/test_holding_shelf_admission.py` (7): the truth table with each refusing
  leg distinguishable (EC-27); the two forms proven DISTINCT judgments on shared stats;
  the substrate keys out of the REAL episode reader on a hand-reasoned 12-bar window
  (closes-basis breach → failed S; terminal hang → open R); the as-of knowability rule;
  the dark default. The form's EC-17 cascade acceptance did NOT land in Task 10 (its
  frozen pair pins only `refused_clock`/pending — recorded as falsified by the 2026-08-17
  council review, finding 3) and LANDED POST-REVIEW: `tests/test_power_play_lane.py`
  now drives the real cascade to `admitted_dark` on hand-reasoned tape with input-tied
  assertions + a mutation probe (EC-32), plus pinned `refused_story` /
  `refused_occupancy` producers (EC-22) and the breakout-day boundary on both sides
  (EC-34).
- Theory moved in the same change (the reading rule): `strategy_alpha.md` "The
  rail-episode read" now records the two named ruled forms; rail comparisons stay on the
  reader's ATR zones (never float equality) with the pinned (end_bar, start_bar,
  S-before-R) same-bar tiebreak.

---

## Task 7 — the species archive family

**Built: `engine_alpha/structure/power_play.py`** — the family's owning declaration
(`POWER_PLAY_COLUMN_SQL`, 11 `pp_*` columns), the lane's ONE fields builder
(`power_play_fields`, EC-23 paired writes: state⇒clock, thirds numerator+denominator
together, coverage+collided together, `state=None` ⇒ the whole family NULL), and the ONE
writer-facing extraction (`power_play_archive_values` — NaN-scrub, INTEGER coerce, and
the write-time closed-set refusal: the single stamping point, since SQLite's ADD COLUMN
path strips the fresh-DB CHECK).

- **The closed set** (`pp_state`): `refused_clock` / `refused_occupancy` /
  `refused_story` / `admitted_dark`; NULL = never evaluated. Enforced three ways
  (EC-19): model CHECK (`ck_setup_archive_pp_state`, fresh-DB), producer refusal
  (live DB), archive-layer test (in-memory create_all + illegal insert refused).
- **Three writers, one producer (EC-30):** live (`writer.py` splat, prefixed) + seed
  (`seed.py` splat, unprefixed) + manual (the model-driven `archive_row_from_result`
  auto-map, covered by its exact-equality guard). The AST-guard
  (`test_archive_row_assembly`) now names `power_play_archive_values` in BOTH writer
  splat-set assertions — a writer dropped from the family fails the suite.
- **EC-33 leak check** through the producer's own extraction: an empty row extracts
  ALL None for every family column, both prefixed modes — covers future fields by
  construction.
- **Raw quantization:** `pp_lower_third_bars` / `pp_shelf_bars` archive thirds-occupancy
  as integer counts (an 8-12-bar window's fraction hides its denominator);
  `pp_zone_coverage` (raw, unclamped) + `pp_zone_collided` make a collided 0.00
  distinguishable from a measured 0.00 (the LEVI collision squared — species ATR
  reaches into the pole).
- **Anchor-family from birth:** `pp_clock` + `pp_pole_gain` joined
  `PHASE_A_ANCHOR_FEATURES` in the same change that created the columns.
- **Model-only registration (AP-7):** columns on `SetupArchive` only; NOT in
  `_NEW_COLUMNS`; pinned by the battery.
- Battery `tests/test_power_play_archive.py` (12). EC-22 note: each legal value is
  produced end-to-end through fields→extraction here; the LANE-level end-to-end (real
  scan worker emitting each state) lands with Task 8, and the cascade acceptance with
  Task 10.
- Also in this change: `tools.settings_reference --write` regenerated the settings
  quick-reference (the docs-sync gate caught the POWER_PLAY block drift — the full
  suite run was 1 failed/1471 passed on exactly that, now healed).

---

## Task 8 — scan integration: the contained species lane

**Built (all dark behind the two flags; flag-off byte-identical at every seam):**

- **One episode mechanics, two consumers (EC-18):** `ticker_episodes` +
  `first_legal_look` MOVED from the census into `engine_alpha/structure/power_play.py`;
  the census imports them. The instrument and the lane can never drift.
- **`species_watch(df)`** — the bounded per-ticker watch (at most ONE episode: the most
  recent with an AR ≤ 90 bars old). Verdict ladder: no episode → nothing; first legal
  look beyond the frame → `pp_pending`, no record; breakout before the species clock's
  first legal look → **`refused_clock` with NO election run** (the wall is the
  finding); else the REAL species read — the live-twin prep, then `read_structure`
  under the ONE `window_override` carrying the clock pair + the shelf-form flag,
  scoped to this read. An election opening at the episode's AR (dates, ±5) →
  `admitted_dark` + shelf/thirds/zone measurements; otherwise the refusal is typed
  from the election trace (a story-stage rejection → `refused_story`, else
  `refused_occupancy`; an empty trace → `pp_no_seed`, Task 9's seam).
- **The composed twin** `evaluation.evaluate_ticker_with_power_play`: WRAPS the
  near-miss-aware submission (the two live lanes compose, never compete); returns
  `(base, pp_row, pp_stats)`. Containment per EC-20: any lane failure is swallowed at
  this seam and counted (`pp_errored`) — never converting a firing result into a
  drop. A watched FIRE carries the Task-7 family on its result row into the archive.
- **Plumbing:** worker ladder pp→near-miss→plain in `_evaluate_frames`; the species
  sink is created inside `run_screener` and its rows ride
  `market_context["power_play"]` — which the dashboard payload already carries
  wholesale, so the publisher block ships with ZERO `output/dashboard.py` changes
  (also zero conflict surface with the operator's staged watchlist work).
- **Cost attributable from day one:** `timer.phases["power_play_lane_worker_s"]` =
  the lane's summed in-worker time (named as an aggregate, not wall clock) — the
  production instrument EC-8's flip bound will cite, measured at the ruled clock.
- **`SCAN_RESULT_JSON` optional keys:** `ScanExportResult.power_play_counts`
  (threaded through every return site) → the one structured line carries a
  `power_play` object only when the lane ran. No new stdout scraping.
- **The wire status is a server-side closed set** (`PP_WIRE_STATUS`: fired /
  watched_ungraded / not_watched_clock / refused_occupancy / refused_story), derived
  in the twin via `wire_status` — no client may reconstruct it (EC-28).
- Battery `tests/test_power_play_lane.py` (8). EC-22 lane-level per-state emission and
  the cascade acceptance land in Task 10 (admitted/refused states need real frozen
  frames; refused_clock and the walls are pinned here on hand-reasoned frames).

---

## Task 9 — seeding-refusal visibility at the anchor seam

**Built:** `collect_root_anchors(eval_df, min_days, seeding_trace=None)` — the optional
refusal recorder at the SEEDING seam (the near-miss recorder attaches one seam later, at
pair election; seeding refusals were structurally invisible to both the trace and the
lane). `None` default is byte-identical AND compute-free: the young zone beyond
`scan_hi` is only walked when a trace rides. The seam's OWN closed vocabulary
(`SEEDING_LEGS = frame_short / below_trend_sma / ar_age` — proven disjoint from the
near-miss `GATE_LEGS` set; the build shipped a fourth `climax_age` leg the 2026-08-17
review proved UNREACHABLE — the AR sits after its climax, so a young climax forces a
young AR and `ar_age` always wins — narrowed to the three producible legs, review
finding 14): frame-level refusals record as frame records (incl. the defensive
scan-band guard, settings-unreachable today, which records `frame_short` when a trace
rides — review finding 13, reachability corrected in verification); age-walled
qualifying pairs record with their pair identity (kind, climax_bar, ar_bar) under
`ar_age` — the wall that clears last, the one the first-legal-look arithmetic turns on. First consumer wired: the census's
election rows now carry `seeding_refusals`, so the census and the live product answer
"why didn't it seed" with the same words. Battery `tests/test_seeding_refusals.py` (5):
None-default byte-identity, the MAN-shape young-AR pair recorded with identity, one
producing case per frame-level leg, vocabulary containment + disjointness.

---

## Task 10 — the acceptance battery and the species dark ratchet

**Built:** `tools/power_play_fixture.py` (the deliberate ratchet-capture tool — writes
`tests/baselines/power_play_fixture.parquet` + `power_play_baseline.json`; a re-run is a
ratchet recapture, legal only in a declared flip/seam commit, EC-29) +
`tests/test_power_play_acceptance.py` (9). The committed pair: **MAN @ 2026-08-12**
(the session BEFORE his breakout) and **FTNT @ 2026-08-13** (its live tier-S fire),
content-digest-bound and re-verified at check time (EC-12). The baseline is a CHANGE
DETECTOR, not a must-fire spec — species must-fire marks arrive only by per-mark
operator graduation, and the sealed 28/33 corpus is untouched.

**The frozen facts the capture surfaced (feed the census ruling):**

- **MAN @ 08-12 = species PENDING at the provisional clock 10.** First legal look =
  AR + clock + skip − 1 → **2026-08-13, breakout day itself** — one session too late
  for a pre-breakout read. **Clock 8 is the first value that watches MAN pre-breakout**
  (first look ≈ 08-11). This is exactly the fork the operator's sheets must rule.
- **FTNT's July shelf does NOT pole-qualify** (+40.9% over 40 bars — tier-2 broad
  species, matching the literature scorecard); the watch latches its older May episode
  (long broken out → refused_clock) while the DEFAULT read elects (the live control).

Battery: digests verified; species + default reads reproduce the baseline exactly
(any-deviation-fails, production values); the frozen behavioral facts pinned (FTNT
elects at default, MAN does not, states in the closed set); the EC-32 input-tied
assertion (FTNT's frozen pole_gain recomputed from the fixture frame's own bars) +
the mutation probe (a flattened pole is not watched — the suite goes red on an
input-blind watch); and the LIVN-shape 13-bar synthetic seeds under the species clock
ONLY. Integration fallout fixed in the same change: the scan-metrics fakes gained the
new `_evaluate_frames` kwarg; the archive column-parity guard and the anchor-seam pin
were extended to the power-play splat/family (analyze's scoped fingerprint table now
filters to columns the frame carries — the pp_* names are dark until the lane runs).

**Census pricing correction (recorded honestly):** the tool's ~30 ms/election figure
omits the per-(ticker, as-of) PREP cost (~hundreds of ms) — the real full-cache run is
hours, not 28 minutes. The sheets (Task 4) should quote the measured wall clock of the
completed sidecar run, and the tool's plan text needs the prep term at the next touch.

---

## Task 12 — the fundamentals layer, lit honestly at the vendor seam

**Built: `core/fundamentals/post_pass.py`** — the conductor-level post-pass replacing
the in-worker attach point (`evaluation._attach_advisory_metadata`, now DELETED: it ran
inside pool workers where the process-global rate bucket multiplied outbound rate by
worker count and fragmented 429-cooldowns). One process, the provider's one throttle, a
serial bounded loop over the FIRING set only. Wired as its own `ScanTimer` phase
(`fundamentals`) — the flip bound's production instrument.

- **Explicit as-of, always:** every call passes the ticker's own frame-last-bar as-of;
  a ticker with no derivable as-of is a LOUD counted per-ticker refusal
  (`refused_no_as_of`) — the `as_of=None` gate-skipping legacy path can never feed an
  archived write.
- **Attempted-vs-populated counters:** `None` when every advisory flag is off (the
  whole block absent = "flag off"); counters present with `populated: 0` = "attempted,
  all failed" — the 0-of-262 class is an alarm now, riding the scan metrics (health
  surface) and `SCAN_RESULT_JSON` (`fundamentals` optional key,
  `ScanExportResult.fundamentals_counts`).
- **Reporting-event cache** (`output/fundamentals_cache.json`): the four filing-gated
  metrics reuse while `as_of < next_earnings` (no new report can exist — keyed on the
  FACT, never a wall-clock TTL, EC-25) and refetch after; `days_to_earnings` is always
  recomputed; price-local fields never cached.
- **Containment:** vendor failure degrades to absent keys + counters; the paying row
  is untouched. Zero new supply chain (the pinned yfinance through the one provider
  seam, AP-4).
- **RE-WORKED 2026-08-17 (council review findings 2/6/7 — the review's one crash-class
  P1 lived here):** the pass now carries the full EC-20 battery its sibling lanes had —
  per-ticker counted swallow (`errored`), shape-validated cache entries dropped loudly
  (`cache_dropped`), a namespace-restricted cached replay (only `_fund_*` can reach a
  paying row from disk), an `OSError`-wide loader, and a narrow seam catch at the
  conductor (`pass_errored`). A vendor outage is NEVER cached as a filing-gated fact
  (an entry writes only when metrics actually populated). The RS-line half gained its
  own `rs_attempted`/`rs_populated` pair + a per-ticker stderr line (the 0-of-N class
  was still silent on that half), and the next-earnings date is fetched ONCE (days-to-
  earnings is arithmetic on it). The fundamentals ScanTimer phase records ONLY when the
  pass runs — a dark scan's persisted metrics stay byte-identical, as this record
  always claimed. And `per_ticker_advisory` is RETIRED (EC-3): the build's claim that
  it "stays the one field builder" was false in the way that matters — the post-pass
  had duplicated its assembly, leaving a tested function with zero production callers —
  so the post-pass is now the ONE assembly and the advisory battery moved with it
  (`tests/test_advisory_wiring.py` re-targeted; primitives stay in `advisory.py`).
- **Scope note:** the pass covers fires; species-candidate enrichment (payload display
  sugar) is deferred until the species lane graduates.
- Battery `tests/test_fundamentals_post_pass.py` (9): flags-off None + zero calls +
  no cache file; explicit-as-of spy; loud no-as-of refusal without a call; containment
  with exact counters; cache reuse-then-refetch across the next-earnings fact; the
  outage-never-cached recovery; the malformed-cache drop + namespace restriction; the
  poisoned-ticker per-item swallow; the in-worker attach point proven gone.

---

## Task 11 — the trend-state layer (the landable half, and the declared blocker)

**Built:** `market_structure.TREND_STATES` + `classify_trend_state(segments, n_bars)` —
the trending / correcting / consolidating / choppy read as a PURE classification over
`segment_trends`' own segment dicts (never a third daily trend reader; HTF's
`trend_state` stays the declared second labeled form). Provisional rules, measure-only,
NO live consumer yet: a running edge segment names the state directly; a terminal
within `MIN_BASE_DAYS` of the edge is the operator's transition zone (up-terminal →
correcting, down-terminal → consolidating); older terminals → consolidating; no
structure → choppy. Battery `tests/test_trend_state.py` (9 hand-reasoned synthetic
variants — operator marks enter baselines only after graduation; the aged
down-terminal cell gained its value pin in the 2026-08-17 review).

**An open ruling this site carries (2026-08-17 review, McKinney):** the classifier
reads `MIN_BASE_DAYS` lazily for its transition-zone width, and this site postdates the
Task 1 FOLLOWS/STAYS audit — it carries NO ruling. If a future consumer ever calls it
inside the species window override, the transition zone silently halves to the species
clock. The audit row must be ruled (STAYS likely wants the import-time-copy precedent)
IN THE CHANGE THAT WIRES A CONSUMER — nothing moves today (measure-only, unwired).

**The blocked half, stated:** the `segment_trends` box-blindness FIX (in-base rallies
above R print HHs, so the trend "never ends" and the maturity clock starts on the wrong
bar — the corroborated 2026-07-28/08-14 diagnosis) is CALIBRATION-BLOCKED on the 15–20
dated trend-end labels the ruling loop (Task 4) collects into
`docs/power_play_marks_2026-08.json`. Decision recorded at design time, not PR time:
it lands as a **declared seam commit with evidenced baseline recapture** (its output
feeds live reads — `trend_terminal_floor`, `measure_trend_bases` — so it cannot be
flag-off byte-identical if unflagged), in its own change, after the labels land. Until
then the classification above deliberately consumes the reader AS IS.

---

## Task 14 — the minimal frontend surface

**Built (thin by design; all additive, zero collision with the staged watchlist work):**

- `wireVocabulary.js`: **`POWER_PLAY_STATUS_LABELS`** — the server-derived closed set
  (`PP_WIRE_STATUS` mirrored; EC-33 discipline pinned in the node battery) with
  operator-language labels ("Power Play — watched, ungraded" etc.; unknown slugs render
  verbatim until signed) + the four DAILY trend states joined `TREND_STATE_LABELS`
  (one registry, disjoint keys).
- `components/powerPlayRegister.js`: the pure projection (the setupStoryRows
  precedent) — `market_context.power_play` → display rows; the status token passes
  through untouched (the wire carries verdicts, EC-28); numbers through the `fx`
  null-guard (null = em-dash, never 0, never red); NO thresholds, NO color ramps.
- `components/PowerPlayRegister.jsx`: the MARK-register chrome (muted, narrow, plain
  words — never chip/pill chrome, never tier color; promotion to chip chrome is the
  flip's visible record). Deliberately not mounted at build time (the screener
  surfaces were mid-flight on the operator's watchlist branch); **MOUNTED
  2026-08-19 at that merge**, in `HomeView`'s regime cell beside `RegimePanel`,
  reading the same `marketContext`. It returns null on an empty projection, so it
  costs the cell no height while both species flags are dark. The data rides the ONE screener
  payload (`market_context` travels wholesale) — no second store, no second fetch,
  no census React route (frozen sheets stay the census surface).
- Battery `components/powerPlayRegister.test.js` (6, in the node --test list):
  empty/malformed context → empty register; signed labels + plain facts; unknown slug
  verbatim; fx guard (measured zero SURVIVES, null is an em-dash); the closed-set
  mirror; counts pass through as facts.

Gates: node --test 260/260, eslint clean, vite build green (worktree
`npm install` performed).

---

## Task 2 — one home and one canonical artifact for the double-duty marks

### Rulings

- **The certified home is `docs/marks/`** (already covered by
  `tools._bootstrap.refuse_sealed_output`, already carrying the EC-7 habits). Certified
  species must-fire marks graduate there per-mark, operator-confirmed, one-way (EC-9) —
  and join the species dark ratchet (Task 10) only then.
- **The canonical pre-certification artifact is `docs/power_play_marks_2026-08.json`**,
  in the docs root beside its siblings (`trend_end_marks_2026-08.json`,
  `phase_c_marks_2026-07.json`) — deliberately OUTSIDE `docs/marks/`, exactly as the
  trend-end file's own readme rules: calibration ground truth is not a must-fire spec.
  Append-only, hand-curated during ruling sessions, no tool write path. Bulk sheet
  verdicts (Task 4) land in the editable DB population, never in this file.
- **Double-duty is a property of the ONE artifact, not two files:** each ruled conflict
  mark carries a keep/junk verdict (the species boundary, for the census) AND dated
  trend_end/ar marks (the trend-state labels, for Task 11). Both consumers load through
  the one validated loader and stamp the exact set scored.
- **The shared loader is `tools.marks_json`** (`load_marks_json` +
  `marks_json_fingerprint`) — the file-family analog of
  `tools.calibration_harness.load_marks`/`marks_fingerprint` (EC-13): a malformed row
  aborts naming the offender; the fingerprint is order-insensitive over exactly the
  marks scored. `tools/operator_marks_diff.py` (the existing trend-end consumer) now
  loads through it instead of a raw `json.load` — one loader, every consumer.
- **Uncertified marks never back a pytest assertion** (the Beck watchpoint): the 9
  trend-end marks are explicitly "a direction of travel", and the species artifact
  starts empty. Committed tests use synthetic hand-reasoned frames until marks graduate.
- **Deferred to the certification change (recorded here so it is not lost):** migrating
  certified marks under `docs/marks/`, and growing the `_SEALED_DIRS` guard tuple if a
  new sealed directory is chosen, with a case-variant refusal test in the same change
  (EC-35).

### Also fixed in this task

`tools/operator_marks_diff.py --json` wrote to a user-supplied path WITHOUT routing
through `refuse_sealed_output` — a pre-existing EC-14 violation, fixed in the same touch
that retrofitted the loader.

---

## Council review + the fix program (2026-08-17, post-build)

The finished build went through `/council-review` (run `2026-08-17-2120`: 10 seats,
52 raw findings, 15 shipped after dedup + Chair verification against source — 3 P1,
12 P2; the full record is the run's FINAL-REVIEW.md, machine-local `.council/`
scaffolding, distilled HERE per EC-16). The operator ruled "fix all"; every shipped
finding, every below-the-cap P2, and the whole P3 sweep were fixed in the same
change-set. The load-bearing outcomes, each already recorded in its task section above:

- **The decision records were trued up in this commit** (finding 1, P1 — EC-15): both
  flag-ledger rows re-stated at build end (the lane IS wired and consulting the preset
  flag; the Task-10 frozen fact — clock 10 lands MAN's first legal look ON breakout
  day, clock 8 is the first pre-breakout value — now sits beside the 2026-08-14
  diagnosis it corrects; the story-form row's mechanism name and acceptance status
  corrected).
- **The fundamentals post-pass got its containment** (finding 2, P1 — EC-20; Task 12
  section). The one crash-class landmine: a locked/corrupt cache file could have cost
  a whole scan night, and a name-collided cache entry could have poisoned firing rows.
- **The election half is proven end to end** (finding 3, P1 — EC-17/22/32/34; Task 6/10
  sections + `tests/test_power_play_lane.py`): the real cascade now produces
  `admitted_dark` (input-tied + mutation-probed), `refused_story`,
  `refused_occupancy`, the breakout-day boundary on both sides and both consumers, the
  composed twin on the frozen FTNT/MAN frames, and a conductor-level publish test.
- **The census evidence is as-of-consistent** (finding 4 — `first_legal_look` now
  solves against the running argmin the walk would have seen on each day, with a
  divergence-producing test; the MAN/FTNT frozen facts verified immune) and the
  instrument enters the read through the SAME mechanism + derived key set as the lane
  (finding 9 — `flag_capture` delegates to `window_override`).
- **Refusal attribution is scoped and honest** (finding 5): typed only from the
  EPISODE'S own roots' cascades (the trace is root-level records with the pair cascade
  nested — the old flat scan read a level with no verdicts, so `refused_story` was
  unreachable); a foreign election rides the payload as `elected_other`, and an
  unframed shelf counts `pp_shelf_unframed` instead of fabricating a refusal.
- **One verification CORRECTION to a shipped finding** (13): the silent scan-band exit
  is arithmetically UNREACHABLE under current settings (the 200-bar `ROOT_TREND_SMA`
  gate refuses every frame short enough to land there) — the young frames the finding
  worried about record `below_trend_sma` loudly. The guard now records `frame_short`
  defensively anyway; no new vocabulary was invented for a dead branch.
- The rest, one line each: outage-proof + namespace-restricted fundamentals cache and
  flag-gated timer phase (6/7/Task 12); the manual archive writer takes the pp splat
  with a per-writer guard (8 — EC-30's third occurrence); the docs-root marks corpora
  joined the sealed set as FILES (10 — EC-14); the census prep cache clears per ticker
  and pre-flights its refusals (12/H4); `climax_age` narrowed out of `SEEDING_LEGS`
  (14); the ruling loop's re-run is one copy-runnable command (15 — EC-36, Task 6
  section above); `wire_status` validates its output and the wire tuple is pinned
  exactly on both sides; the pole knobs read settings directly; the peak window
  derives from `LOCAL_PEAK_BARS`; `species_watch` moved to the evaluation layer
  (structure measures, the lane coordinates); the shared engagement predicate
  (`frame_r_engaged`) serves prefilter + posture; the marks loader refuses transposed
  spans; `operator_marks_diff` stamps its population + post-filter fingerprint
  (EC-13); the register composes the house `fx`, renders token-ramp muting, JetBrains
  Mono meta lines, tail-composed rows, and a counts footer; `SCAN_RESULT_JSON` gates
  optional keys on None-ness; the twin's error path keeps partial counters + elapsed
  time (the EC-8 instrument stays honest on failing tickers).

**Full gates after the fix program:** the entire suite + frontend trio green (the
count is in the session's final gate log; the ratchet baseline was NOT recaptured —
the frozen facts survived every arithmetic fix, verified, EC-29).

---

## The first-legal-look reserve correction (2026-08-20, MEASURED — operator-gated)

The 2026-08-17 finding 4 above fixed half of the as-of consistency. The 2026-08-20
council review (finding 3) found the other half: `first_legal_look` modelled the
5-bar edge reserve correctly in its age WALLS (`+ skip` throughout) but then read the
reaction's prefix state — has a confirming close printed, where does the reaction low
stand — at bar `p`, the as-of the walk is STANDING on, instead of bar `p - skip`, the
last bar the walk is allowed to ANCHOR on. It graded the walk on evidence the walk
could not yet have seen.

**The corrected invariant** (now stated in the function's own docstring): a walk
standing on session `p` reads the reaction only through bar `p - skip`, clamped to the
reaction window's last bar. Two consequences follow, and a third fell out of stating
it: the terminal bound must also wait for the whole reaction window to clear the
reserve (`j1 - 1 + skip`), because the old closed form could return a session on which
the reaction had not confirmed at all.

**Measured against the cache through 2026-08-19** (read-only; 5,548 frames, 13,882
pole-qualified episodes; arithmetic-only, no elections):

| clock | looks that move | direction | shift (sessions) | wall-state flips |
|---|---|---|---|---|
| 20 | 0 | — | — | 0 |
| 15 | 0 | — | — | 0 |
| 10 | 761 (5.5%) | all earlier | −10 … −14, median −12 | 36 |
| **8** | **1,678 (12.1%)** | **all earlier** | **−8 … −14, median −11** | **106** |

The default read is untouched — the divergence is a species-clock phenomenon exactly
as the original note claimed, but larger than "identical at the default clock" implied
for the short clocks. **The bias is one-directional on this corpus:** the late-watching
direction (a low deepening inside the reserve) fires 1,678 times at clock 8; the
early-watching direction (a confirming close inside the reserve) fires zero times, and
the new terminal bound never binds. Both directions are pinned as tests anyway —
`tests/test_first_legal_look.py`, whose oracle case adjudicates the answer against
`collect_root_anchors` itself rather than against a restatement of its walls.

**Adjudicated against the real seeder** (150 moved rows sampled, 75 adjudicable — the
rest are blocked in the window by gates the model deliberately does not carry, the
200-SMA trend gate above all): corrected **65/75 exact, 0 later than the seeder**;
legacy **1/75 exact, 66 later than the seeder**. The old arithmetic was systematically
telling the census the episode became watchable a fortnight after it actually did.

**Census consequence at clock 8, complete (not sampled):** unmoved rows re-elect
identically by construction, so the whole delta is the moved cohort — all 1,678 rows
re-elected on both legs (268 s). 259 of 1,678 change verdict. `not_watched_clock`
**107 → 12** (96 rows regain their looks). And the finding the ruling has to weigh:
**`elected_episode` 5 → 0** — SIFY (2023-07-18), TSHA (2025-10-15), HERE (2024-10-07),
OCUL (2023-02-15), LEE (2026-03-03) all lose their episode election at the corrected,
earlier look, and **no row gains one**. Their fwd_20 was −17.7% / +39.9% / −12.3% /
+14.8% / −4.6% (2 of 5 winners, median −4.6%), so against the 2026-08-18 clock-8
cohort (88 elected @ +2.7% median / 56% winners) the correction removes five names
whose record was worse than the cohort's. It re-derives the evidence the clock-8
ruling was made on; the ruling is the operator's to re-affirm.

**Species register consequence today:** of 1,128 tickers carrying a filed episode,
129 move their printed first-legal-look date and **12 change classification** — 9 that
read `pending` (no record) now reach the universe gate and are refused there (still no
record, different counter), and three filed rows move: **MGNX** `refused_clock` → no
record, **QLYS** `refused_clock` → `refused_story` (2026-08-13 → 2026-07-27), **STRZ**
`refused_clock` → `refused_occupancy` (2026-07-14 → 2026-06-25). None becomes
`admitted_dark`.

**The named specimens are immune, at every clock.** MAN: first legal look 2026-08-11,
before its 2026-08-13 breakout, unchanged — the frozen `admitted_dark` fact stands.
FTNT: 2026-06-26 at clock 8, unchanged. Gates green: 1,599 tests, doctrine audit PASS,
`shadow_diff` no canonical drift, marks ratchet 28/33 held on the same fingerprint —
the paying read does not move, this is species-lane and instrument arithmetic only.

---

## The first-legal-look correction LANDED, and the evidence re-derived under it (2026-08-23)

The proposal branch merged as `2b03d0b` (council 2026-08-22 verdict MERGE — an independent
175-case oracle read the corrected walk 175/175 exact against the real seeder, main 169/175 with
both bias directions; operator-delegated). The Correction lane's evidence half ran the same day:
the census re-executed at clocks 8 and 10 on the corrected arithmetic (clocks 15/20 are proven
untouched — zero looks move), sidecar `output/power_play_census_postfix_2026-08-22.json`
(13,878 episodes / 5,511 tickers, cache through 2026-08-21, manifest `c26961bf…`).

**The clock-8 ruling's own acceptance condition — "clock 8's elected cohort is the only
forward-positive one" — HOLDS on the corrected arithmetic, and sharpens:**

| clock | elected cohort | median fwd_20 | winners |
|---|---|---|---|
| 8 | n=85 | **+3.8%** | **58%** |
| 10 | n=83 | −1.7% | 46% |

(The ruling's pre-fix basis read +2.8% / 54% / n=79 on the cache through 2026-08-18; three newer
sessions ride this re-run, so the delta is arithmetic + tape jointly — the HEADLINE is the
acceptance condition, and it survives under both.) The live register was verified untouched
before the merge: NNBR / QTTB / BRKR byte-identical under both arithmetics; MAN and FTNT immune
at every clock. The 2026-08-18 clock-8 ruling therefore STANDS un-re-litigated, now on evidence
the corrected walk derived.
