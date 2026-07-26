# Council Plan: The Near-Miss Lane

**Scope:** Measure-first telemetry for one-leg box-election-gate refusals: any candidate framing
that failed exactly ONE gate leg narrowly (width / window / respect / occupancy family /
traversal) while passing all others is recorded with its evidence — failing leg, native-unit
margin, episode sentence, would-be score/tier — into an archived cohort with a census-style CLI
review report. No gate moves; a near-miss never scores, never fires, never enters the picks.
**Context:** Builds on the Event Map program's proven shape (research census → hard operator
ruling → dark-flagged build → guarded flip) and its machinery: the cascade trace seam narrates
every refusal today (but live scans run `trace=None` and the payload is prose);
`metrics.measure_gate_margins`/`base_rail_touches` already measure gate margins engine-side;
`tools/rail_margin_evidence.py` + `tools/event_map_census.py` are the instrument templates.
**Boundaries:** The EGBN class is OUT (never-proposed framings — rail placement is its own
program; this lane only reads refusals of proposed pairs). LPS/universe/firing gates OUT (later
programs). Webapp UI OUT (graduates later; rows carry render-complete evidence so graduation is
a UI task, not a data program). Gate loosening / margin compensation / threshold fuzzing:
PERMANENTLY out (tested-dead).
**Council dispatched:** McKinney (10), Beck (11), Friedman (11), Leach (10), Performance (9),
Fowler (7), Ramírez (7), Hunt (6), Dodds (1 — forward-looking only; lane verified clean: no
router reflects new tables), Saarinen (0 — no UI surface). 72 recommendations → 13 tasks.

## Task Sequence

### 1. The canonical leg registry + the structured seam record
| | |
|---|---|
| **Domain** | Fowler × Carmack — Primitive Obsession / Inconsistent Vocabulary; EC-3/EC-18 |
| **Ref** | `references/refactoring.md` → P4/P5 |
| **Depends on** | — |

Give the gate legs ONE machine-readable home owned by `box_gates`: identifiers, the statistic
each leg reads, its threshold binding, its native quantum (fraction / bar count / touches /
ratio), and its exact comparison form — with `_occupancy_failures` prose, trace narration, and
every future census/lane surface DERIVED from it (today the leg names exist only as scattered
detail-string fragments, and the lane is about to make them cohort keys). In the same change,
recontract the trace seam so the record carries leg id + measured statistic + threshold as
NUMBERS with the sentence derived from them (rail_margin_evidence's regex-parse-and-void is the
measured cost of prose records), and fix the two call sites that build detail f-strings
unconditionally (width/window in `collect_zigzag_candidates` — verified: argument evaluation
leaks work when trace is None). Byte-parity gates prove nothing moved.

### 2. The framing identity, named once
| | |
|---|---|
| **Domain** | Fowler × Carmack — Data Clumps ("an object dying to be born") |
| **Ref** | `references/refactoring.md` → P5 |
| **Depends on** | — |

The same identity concept is already spelled three ways (`_trace_find`, rail_margin_evidence
dedup, event_map_census dedup) and the lane needs a fourth, cross-night form. Define it ONCE:
an in-window form for O(1) per-evaluation dedup, and a date-anchored form (ticker + rail prices
+ anchor DATES — never positional bar indices, which slide nightly with the 2y trim) for
persistence and the census. Recorder, census, and the store's UNIQUE key all derive from this
single definition. Cross-refs: Leach (store key), Performance (dedup map), McKinney
(observation unit — census distributions weight by framing, recurrence kept as a count).

### 3. The margin measurement core — native quanta, full vector, sign-locked
| | |
|---|---|
| **Domain** | McKinney × Carmack — Never trust output: validate at the source |
| **Ref** | `references/quality-llm.md` → P2 (recast: measurement honesty) |
| **Depends on** | Task 1 |

Pure per-leg margin functions beside the leg registry, extending the `measure_gate_margins`/
`base_rail_touches` foundation: each margin a SIGNED count in the leg's own quantum, computed
from raw integer numerators at measurement time (never re-derived from 4dp-rounded fractions or
parsed from prose), each self-checking that its sign reproduces the gate's actual verdict on
that window (mismatch voids loudly — the rail program's pattern, generalized). Because the
cascade short-circuits, "exactly one leg" is unknowable at the refusal point: build the
full-vector COMPLETION primitive that runs the gates' own pure helpers over a given judged
window post-hoc (the `gate_stats` pattern) — the judged-window definition (strict / rescued
trim / band mask), rails, and ATR travel on the record as one basis clump, captured at the seam
(rescued/band margins are structurally unmeasurable otherwise). Surface the respect gate's
already-computed consecutive-run maximum instead of a second O(n) pass.

### 4. The refusal-volume counters probe
| | |
|---|---|
| **Domain** | Performance × Carmack — Measure before you claim |
| **Ref** | `references/quality-performance.md` → P1 |
| **Depends on** | Tasks 1–2 |

Counters-only instrumentation over the deterministic replay corpus (sealed fixtures + negative
corpus; optionally one dark counter run on a real scan): the distribution of pair examinations
per evaluation, stage-of-death histogram, and the single-leg-failure rate — the 69×44 figure is
the busy TAIL and nobody has measured the MEDIAN. These numbers size the dedup map, the
finalist top-K, and the write caps; without them every downstream bound is a guess against the
wrong percentile. The event-map program's degenerate-prefilter lesson applies verbatim: this
lane asserts no cost shape it has not measured.

### 5. The margin census instrument
| | |
|---|---|
| **Domain** | McKinney × Carmack — Grounding: an answer with no source is a guess |
| **Ref** | `references/quality-llm.md` → P3/P7; EC-13/EC-14 |
| **Depends on** | Tasks 1–3 |

The evidence tool the ruling will be made on: the complete margin vector at every leg over the
33 marks on BOTH bases (drawn rails/window AND the engine-examined candidate at as_of — the
AP-8 basis-honesty analog; the converting statistic is the examined one) plus every proposed
junk-corpus candidate INCLUDING passing candidates' headroom; the junk mass sitting immediately
under each floor quantified explicitly (the rail campaign proved floors sit where junk begins —
the expected junk share of any "narrow" band must be a number the operator sees before ruling);
the co-failure structure and exactly-k-fail histograms at BOTH taxonomy granularities
(occupancy-as-one vs occupancy-as-eight). Shape per Performance: one traced engine walk per
case, one measurement pass per pair, ruling research iterates on cached fingerprint+manifest-
stamped JSON rows — never re-walks. Promote `judged_window` + the count math from
rail_margin_evidence into `tools/replay` (the declared home; census would be the third
sibling-instrument import). `--check` pins IDENTITY and outcomes: marks fingerprint, negative-
corpus digest (delegate to the marks_corpus gate), engine manifest (margins are RELATIVE to
knobs — a knob move re-bases every distribution), headline counts — a failed pin names the
drifted axis. EC-14 on every write; modes refuse to combine.

### 6. Pre-registration → the census run → the HARD operator ruling gate
| | |
|---|---|
| **Domain** | McKinney × Carmack — Evals: score once, never iterate against the tables |
| **Ref** | `references/quality-llm.md` → P7; EC-15/EC-16/EC-18 |
| **Depends on** | Tasks 4–5 |

Pre-register BEFORE the tables are seen: the candidate leg taxonomies (finest grain ~15 legs;
crash filter in or out — a slightly-too-deep undercut is a spring-shaped refusal and today it
vanishes at an early return; policy stages dethroned/rescue_unused/story explicitly OUT; leg
dynamics noted — window misses self-resolve, width misses are permanent) and the candidate
narrowness definitions (e.g. within one native quantum; junk-calibrated percentile band per
leg). Score once. Then the operator rules IN ONE SITTING from a closed decision menu (the
event-map menu shape: both legs named per option with exposure classes, a standing-ruling stamp
slot, CLOSED banner after): taxonomy, narrowness, cross-scan recurrence semantics (per-night
rows vs episode row — the forward-return anchor is the FIRST refusal date either way), and the
retention/purge posture. The ruling ships EC-15/16 in the SAME change: a committed
`docs/near_miss_lane_2026-XX.md` protocol doc carrying the stamped tables, and every citing
surface updated. The ruled definition becomes ONE predicate/config (EC-18) that the collector,
census, and report all delegate to — with a truth-table pin (the Option-A precedent). **HARD
GATE: no lane code that filters by margin exists before this ruling.**

### 7. The collector, inline phase — a bounded recorder on the consultation seam
| | |
|---|---|
| **Domain** | Performance × Carmack — Budget the critical path |
| **Ref** | `references/quality-performance.md` → P3/P4/P6; EC-8 |
| **Depends on** | Task 6 |

A dedicated lightweight recorder attached ONLY at the outer Phase-B consultation seam (the
enforce-traversal path — not the inner-box calls to the same enumeration), riding the Task-1
seam contract: at each refusal it records the raw-numbers tuple the gate already has in hand —
no strings, no dicts, no full-trace materialization (~3,000 twelve-field prose records per busy
evaluation is the cost of threading the research trace live) — into a per-evaluation hash map
keyed on the Task-2 absolute identity (O(1), canonical-record rule keeps the nearest margin).
Flag `NEAR_MISS_LANE_ENABLED` ships the complete EC-8 bundle in this task (manifest key +
ledger row with kill-by + inert test + flag-off byte-parity — imports and compute strictly
inside the flag, lazily read per AP-3) and the recording-shape knobs are manifest-listed so a
future re-ruling rotates `engine_config_version` (the TA_SCORE_V2 pre-registration lesson).
Engine-side: zero logging, counters only. **Acceptance in this task, not later:** Beck's
per-identity election-stability guard (every Guided List hit, flag OFF vs ON, canonical fields
identical PER IDENTITY) + the whole-shadow-panel identity leg + the flag-ON negative-corpus
replay — the collector sits on the exact seam where the bar-dwell campaign proved aggregate
guards go blind.

### 8. The collector, deferred phase — bounded completion, cheapest evidence first
| | |
|---|---|
| **Domain** | Performance × Carmack — Right-size the work over real n |
| **Ref** | `references/quality-performance.md` → P3/P4 |
| **Depends on** | Task 7 |

After the election settles, complete the full leg vector (Task 3's primitive) ONLY for the
deduped finalists — top-K nearest per ticker, K sized from Task 4's measured rate — never
inside the pair loop; the ruled one-leg-narrow predicate (Task 6) then defines the cohort.
Evidence by cost: completion verdicts and margins first, the episode sentence next (one O(n)
read per finalist), the would-be score/tier strictly LAST and only for rows surviving every
other cut — with the stated fallback that if even top-1 costs materially, score/tier ships
NULL-until-measured. Any inline nearness screen added later must be an EXACT necessary
condition of the ruled definition with selectivity MEASURED in the Task-13 A/B, not asserted —
the degenerate-prefilter failure does not get repeated on a path that runs 1,500 times a night.

### 9. The cohort table + the writer
| | |
|---|---|
| **Domain** | Leach × Carmack — Constraints are assertions; schema choices compound |
| **Ref** | `references/quality-postgres.md` → P1/P4/P5; EC-19; AP-7 |
| **Depends on** | Tasks 2, 6 |

A DEDICATED table — never rows/columns on `setup_archive` (fires have NOT NULL tier/score by
design; every existing consumer treats that table as the fire population with no discriminator;
one forgotten filter poisons the edge record). On the shared declarative Base so `create_all`
provisions it from every entry path; generalize the model-diff ADD-only migrator (startup +
writer passes — both verified hardcoded to setup_archive) to cover the new table AT BIRTH, or
its first model-only column silently never reaches the live DB. UNIQUE constraint on the Task-2
date-anchored identity; EC-19 treatment for the failing-leg label (CHECK at create_all + one
stamping point + test), vocabulary sourced from the Task-1 registry. Rows carry: raw margins
per CONSULTED leg in native units (NULL = never-consulted, NOT NULL everything knowable at
refusal — fresh table, no retrofit later); the outcome substrate captured at refusal time
(would-be trigger, S-level for the risk denominator, scan-time close on the scan-time price
scale — forward returns are UNCOMPUTABLE later without them and the split-rescale guard
degrades silently); `engine_config_version` + lane-ruleset version stamps (a re-ruling
PARTITIONS, never reinterprets); render-complete geometry per Dodds (R/S, window anchors as
dates, consultation date) so the future webapp lane is a UI task. Writer: in-memory dedup,
per-ticker + global caps (Task 4 numbers), ONE batched session/commit (autoflush-off; the
"database is locked" lesson), the ARCHIVE_LIVE_SCANS-style enable pass-through so test scans
never pollute the cohort, and the error split — no blanket try/except around the collector
(programmer errors surface), ONE narrow logged catch around the flush (an archive failure never
kills the night's picks).

### 10. The forward-returns hookup
| | |
|---|---|
| **Domain** | Leach × Carmack — Bounded queries; one outcome implementation |
| **Ref** | `references/quality-postgres.md` → P4; EC-18 |
| **Depends on** | Task 9 |

A second maturation pass over the new table that DELEGATES to `core/archive/outcomes.py` —
never a re-derived barrier/window math that forks the meaning of MFE between fires and
near-misses. Copy forward_returns' two bounding devices exactly (the still-maturing re-touch
predicate + the max-scan-age cutoff — a junk-heavy cohort holds proportionally MORE dead
tickers), ride the same job invocation and batched download, register in scan_runs so the
watchdog sees it. The outcome clock anchors at FIRST refusal (the first-fire analog for a
non-fire cohort), per the Task-6 recurrence ruling.

### 11. The review report CLI
| | |
|---|---|
| **Domain** | Friedman × Carmack — Dashboards drive action; trust is destroyed by single failures |
| **Ref** | `references/quality-ux.md` → P1/P2/P6/P9; EC-13/EC-14 |
| **Depends on** | Tasks 6, 9 |

The lane's product. One near-miss = one fixed-shape row in decision order: failing leg + native
margin with its threshold in the ENGINE's vocabulary first (`r_touches 1<2` — any normalized
rank second, labeled as the ruled construct it is; rank within a leg by native margin, never a
cross-leg scalar until one is ruled), then episode sentence, then the would-be tier explicitly
labeled counterfactual ("would-be: A — never elected, never fired") in a visually non-picks
idiom, then operator coordinates (calendar dates + prices, the census drill idiom — never bar
indices). Header: the junk-heavy expectation stated BEFORE row one (floors sit where junk
begins; rows are refusals under review, never missed winners), identity/freshness/taxonomy
stamps (fingerprint, manifest seam, scan-date span, taxonomy version in force). Bounded
default batch (5–10, forced-ranked, "showing N of M — --all for the rest"), recurrence as a
first-class column (first/last-seen, nights-seen; NEW identities above already-seen). Empty and
refused states are affirmative reports ("0 near-misses recorded; collector ON; populations
consulted") — silence must be distinguishable from a dead collector. Integrity: EC-14 on
writes, modes refuse to combine, filtered runs stamp the EXACT set scored, unknown filter
values abort naming the offender, and the tool is read-only against every ground-truth store —
no path that promotes a near-miss into a mark (EC-9 stays one-way).

### 12. The guard battery
| | |
|---|---|
| **Domain** | Beck × Carmack — The red step is the proof |
| **Ref** | `references/quality-testing.md` → P1/P4/P5/P6; EC-17 |
| **Depends on** | Tasks 7–9 (the per-identity guard lands INSIDE Task 7) |

The composable N+M+1 battery, not a legs×units×flags matrix: per-leg detection tests on
eye-readable synthetic frames with HAND-DERIVED expected margins stated before implementation
(heterogeneous units are exactly where pasted-output tautologies hide); unit-normalization
tests; ONE end-to-end EC-17 happy path — a hand-built frame failing exactly one leg narrowly
through the real evaluation entry at production flags, asserting the full recorded evidence AND
that the ticker fires in NEITHER flag state. Plus: the exactly-one-leg truth table (zero / one
/ two failing legs, wide vs narrow, the ruled occupancy-granularity answer — the Option-A
pin pattern); the flag-off boom proof isolated from sibling flags on the same seam; as-of
honesty via a truncation sweep + one deliberately discriminating lookahead case; the store
integrity trio (closed-set stamping refusal, fresh-DB CHECK, zero-vs-NULL mapping); dedup with
exact pinned counts (recurrence is the BASIC case). Four recorded red steps, logged like Task
9's: recording forced flag-off → boom red; predicate loosened to two-leg → truth table red;
dedup identity removed → count pin red; as-of swapped for full-frame → lookahead pin red.

### 13. The cost A/B + the flip gate
| | |
|---|---|
| **Domain** | Performance × Carmack — Measure before you claim |
| **Ref** | `references/quality-performance.md` → P1; EC-8/EC-15 |
| **Depends on** | Tasks 7, 8, 9, 12 |

Acceptance numbers written BEFORE the collector is built (in Task 7's ledger row): flag-off
byte-identical and compute-free; flag-on timed on the deterministic replay harness with
per-evaluation p50/p95 and whole-corpus wall clock pinned; budget = median indistinguishable
from noise, a hard tail ceiling; any inline screen's selectivity measured here. The executed
A/B updates the ledger row in the same change (EC-15) and the flip remains an operator
decision against the committed record.

## Risks & Watchpoints
- **McKinney — masked co-failures:** the cascade's first kill hides the rest of the vector; any
  shortcut that labels near-misses from the kill stage alone mislabels multi-leg failures as
  one-leg misses. The Task-3 completion primitive is load-bearing; never bypass it.
- **McKinney — coupled legs:** the dwell trio partitions to one, touch-thirds bound by touches,
  respect's two legs share a mask — "exactly one" is granularity-sensitive, which is WHY the
  taxonomy is ruled from the co-failure census, not asserted.
- **Performance — inverted trigger economics:** unlike every prior dark measure, this one fires
  on the COMMON case (refusals). If any task finds itself adding work inside the pair loop,
  stop — that work belongs in the deferred phase or nowhere.
- **Leach/Friedman — sample honesty:** per-night rows must never be averaged as independent
  samples (one persistent box ≠ thirty observations); first-refusal anchors the clock.
- **Ramírez — the config-shadow trap:** all flag reads lazy at call time; the backend cwd
  shadows the repo-root config package.
- **Friedman — the shadow-signal hazard:** the would-be tier is the lane's most seductive
  number; if the report ever starts reading like a picks list, the lane has become the gate
  bypass the scope forbids.
- **Beck — guard economy:** one replay-scale guard (the per-identity test), not one per leg;
  the suite's expensive tier must stay runnable nightly.
- **Chair — expectation setting:** the lane cannot see EGBN (never proposed). If the operator's
  first weeks of review show mostly junk, that is the MEASURED expectation, not a defect — the
  forward-returns cohort is the payoff, not nightly gold.

## External Setup Required
No external setup required. All tasks can be implemented within the codebase.

## Summary
| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Canonical leg registry + structured seam record | Fowler | — |
| 2 | Framing identity, named once | Fowler | — |
| 3 | Margin core: native quanta, full vector, sign-locked | McKinney | 1 |
| 4 | Refusal-volume counters probe | Performance | 1–2 |
| 5 | Margin census instrument | McKinney | 1–3 |
| 6 | Pre-registration → census → HARD operator ruling | McKinney | 4–5 |
| 7 | Collector inline phase + EC-8 bundle + identity guard | Performance | 6 |
| 8 | Collector deferred phase (bounded completion) | Performance | 7 |
| 9 | Cohort table + writer | Leach | 2, 6 |
| 10 | Forward-returns hookup | Leach | 9 |
| 11 | Review report CLI | Friedman | 6, 9 |
| 12 | Guard battery | Beck | 7–9 |
| 13 | Cost A/B + flip gate | Performance | 7–9, 12 |

## Verdict
The load-bearing decision is the two-phase collector: inline capture that records only numbers
already in hand, and bounded deferred completion for a top-K of finalists — get that wrong and
the lane's cost tracks the refusal count on the one hot path this project has; get it right and
the whole feature is nearly free. The most critical domain is McKinney's measurement honesty:
the cascade short-circuits, so "failed exactly one leg" is not observable at the kill site —
the completion primitive and the co-failure census are what make the lane's core predicate
mean anything at all. Start with Task 1: the leg registry is small, benefits the existing
narration immediately, and every other task keys off its vocabulary. The dependency spine runs
1→3→5→6 and nothing that filters by margin may exist before the Task-6 ruling — hold that gate
as hard as the event-map program held its Option-A gate, because it is the same discipline that
made that program's evidence trustworthy. Keep the Performance seat on hand during Tasks 7–8;
its refusal-economics framing is the difference between a free lane and a slow scan.
