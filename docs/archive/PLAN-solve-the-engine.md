# Council Plan: Solve the Engine — Engine Alpha extraction + calibration gap closure

**Scope:** (A) Extract the chart-reading engine into a standalone pure `engine_alpha/` package that
webapp/tools/tests summon through a facade — byte-identical behavior, freeze battery green,
manifest hash unmoved. (B) Close the operator-eye gap per the 7-family taxonomy: take
surfaced-at-his-picks from 5/16 toward 14+/16 (16/16 stretch), one lever per engine-identity
rotation. Fix the measuring instrument first.

**Context:** The agreement harness (17 operator marks, 22 dated LPS events) grades the frozen
engine-α reader blind at 11/16 of the operator's boxes. Per-mark dissection produced 7 gap
families (`scratchpad gap_taxonomy.md`, copied to `.council/council-plan-output/2026-07-16-1955/`);
2–3 "misses" are harness artifacts, ~4 are covered by already-built dark flags, the rest need
scoped detection changes. `core/structure` + `core/scoring` are leaf packages; the eval chain is
already ~pure — the extraction is mechanical, not architectural surgery.

**Boundaries (out of scope):** scoring reweights / tier thresholds (β); HTF scoring; frontend
redesign; broker surfaces; `MIN_BOUNDARY_RESPECT_PCT` (doctrine + probes proved threshold moves
useless); editing the sealed `docs/marks/` corpus (EC-7); the parked plain-name renames (would
rotate identity cosmetically); physically relocating knob definitions out of `config/settings.py`
(the mutable-singleton override seam stays).

**Council dispatched:** Fowler (extraction owner), McKinney (lever correctness owner), Beck
(gating owner), Ramírez, Leach, Performance, Hunt, Dodds, Saarinen, Friedman — 85 recommendations,
all seats returned substance. Chair: Carmack filter applied at synthesis.

---

## Task Sequence

### Phase 0 — Fix the ruler (engine byte-identical throughout)

### 1. Harness truth: re-anchor the fired walk and grade rails at the fire session
| | |
|---|---|
| **Domain** | Beck × McKinney — The red step is the proof (P1); Grounding/no-clairvoyance (P3) |
| **Ref** | `quality-testing.md` → P1/P10; `quality-llm.md` → P3 |
| **Depends on** | — |

Anchor the fired-walk to the mark's event window (marked-LPS end / knowable_from → breakout + k
sessions, with an explicit session cap and the faithful-basis clamp preserved, loudly named), grade
rail agreement from the read produced on the fire session's own truncated frame via a fully
deterministic best-completed-read selection rule, and label post-fire retirements "consumed —
breakout underway" in the trace. Ship with: a named harness-policy version token folded into BOTH
the backend chip memo signature and the frontend chip cache key (Ramírez P6, Dodds P2); the chip
vocabulary treated as an open enum with neutral fallback and per-field null guards (Dodds P3);
per-mark delta rendering that attributes movement to exactly one axis — ground truth vs grading vs
engine (Friedman P9); the marks ORM session stays read-only, population + fingerprint stamps
unchanged (Hunt P7/EC-9). Pin every new grading semantic with hand-specified expected values (MS
fired at its 05-19 tier-S fire; NGL graded at its span-start fire; PBT's flag-on fire visible;
UNF byte-unchanged as control). Proof of engine-neutrality: before/after reports carry the SAME
`engine_config_version` and SAME `marks_fingerprint` (Leach P1).

### 2. Margin telemetry: dwell/respect margins archived on every fired box, proven inert
| | |
|---|---|
| **Domain** | Leach × McKinney — Migrations are production operations (P3); measure-first |
| **Ref** | `quality-postgres.md` → P3/P5; `quality-llm.md` → P5/P7 |
| **Depends on** | — (lands with Task 1) |

Archive signed distance-to-boundary for the dwell and respect gates (and the raw LPS
volume-ratio + OVERSHOOT_R window/box/ATR triple that Tasks 10/12 need) as nullable ADD-only
columns declared once on the archive model so all three self-migration paths pick them up —
telemetry, not identity; EC-4 threading NOT triggered; never stored on or beside marks (Hunt P3).
One test proves decisions are byte-identical with telemetry on (Beck P9). Surface minimally on
/calibration: one quiet mono sortable margin column at the detail tier, neutral ink, fixed-width
placeholder so rows never jump; no distribution panel this batch (Saarinen P1/P2/P9).

### 3. Re-baseline the scoreboard under the fixed instrument
| | |
|---|---|
| **Domain** | Beck — The red step is the proof (P1) |
| **Ref** | `quality-testing.md` → P1 |
| **Depends on** | Task 1 |

Freeze one agreement report (expected ~7/16 fired: MS + NGL convert with the engine untouched)
stamped with marks fingerprint + engine hash + harness-policy version as THE program baseline
artifact. Every later delta is attributed against it; define the EC-8 cost-bound measurement
protocol here once (same cached universe frame, flag-off vs flag-on CLI scan, evaluation-phase
seconds recorded in the flag ledger) so all levers are measured identically (Performance P1/P4).

### Phase A — Engine Alpha extraction (mechanical, byte-identical)

### 4. Pre-move rulings and parity baseline capture
| | |
|---|---|
| **Domain** | Fowler × Ramírez — Architecture earns its boundaries (P6); make the wrong thing impossible (P4) |
| **Ref** | `refactoring.md` → P6/P8; `quality-backend.md` → P4 |
| **Depends on** | Task 3 |

Settle in writing before any file moves: the boundary rule ("the pure frame→reading chain and its
identity move; plumbing stays") with the three satellites ruled — `_trim_to_period` moves INTO the
engine, `fundamentals/advisory` stays OUT as the one documented flag-gated outward seam, `archive/`
stays behind and summons the facade; the package name cleared against the backend-cwd, tools, and
test namespaces with a standing no-same-name-file rule (Ramírez P4); NO compat shim — one canonical
import path from the first commit (dual module objects would split the settings singleton,
monkeypatches, and pickling); the facade derived empirically from what the ~108 importers actually
use, re-exporting existing objects under existing names (never wrapping — Windows spawn pickles by
qualified name); engine knobs stay physically in `config/settings.py` (the seam ~15 test files +
htf/replay mutate). Capture parity artifacts: shadow_diff output, hermetic seed-recall, ratchet
state, negative corpus, `manifest_hash` (must be IDENTICAL after — hash-neutral or it didn't
happen, Leach P3), scan-metrics evaluation wall-time, and the Task-3 harness report.

### 5. Move the leaf packages: structure, scoring, freeze, stability
| | |
|---|---|
| **Domain** | Fowler — Refactoring is not restructuring; steps small enough nothing breaks (P8) |
| **Ref** | `refactoring.md` → P8/P7 |
| **Depends on** | Task 4 |

Git-mv `core/structure/` + `core/scoring/` (proven leaves), then `core/freeze/` +
`core/pipeline/stability.py`, into `engine_alpha/`, one dependency-ordered commit per package
move, each commit containing ONLY moves + importer rewrites + the structure-coupled test-pin
retargets (invariants glob roots, dotted module lists, docs-sync path strings) — no behavior
edits, no cleanups, battery green per commit. Lazy-import discipline in webapp callers carries
over unchanged (AP-3).

### 6. Move the evaluation chain and close the runtime seams
| | |
|---|---|
| **Domain** | Fowler × Ramírez × Performance — Strangler-free atomic rewrite; frozen subprocess contract; pickling budget |
| **Ref** | `refactoring.md` → P6; `quality-backend.md` → P3; `quality-performance.md` → P4 |
| **Depends on** | Task 5 |

Move `evaluation.py` (with `_trim_to_period` relocated into the engine so the downloads dependency
dies), retarget seed's eval-chain import and the ~108 importers' remaining sites atomically. Add
the two runtime smoke tests in-process pytest cannot see: spawn-pickle round-trip of the eval
callable + skip sentinel in a genuinely spawned child under the new qualified name, and
tools-bootstrap resolution from a decoy cwd (Beck P4). The scan-runner subprocess contract (script
path, cwd, env, one structured stdout line) survives byte-for-byte; engine package root stays
import-light for spawn re-import cost (Performance P4).

### 7. Lockdown and extraction acceptance
| | |
|---|---|
| **Domain** | Hunt × Beck × Ramírez — Automate defences (P2); non-vacuous relocated gates (P6/P1) |
| **Ref** | `security.md` → P2/P5; `quality-testing.md` → P6/P2; `quality-backend.md` → P7 |
| **Depends on** | Task 6 |

Ship the boundary as machine checks: an import-graph allowlist invariant (stdlib, pandas/numpy/
scipy, `config.settings`, itself — nothing from webapp/tools/core-plumbing, no ib_async/sqlalchemy/
yfinance/network libs); zero sys.path lines inside the package (entry points own the path through
the one shared bootstrap); the sealed-dir write guard folded into one shared helper every tool
report passes through; a text-level guard that no webapp file names an engine module by its old
core path; the engine-free-FastAPI-boot subprocess check (import main, inspect loaded modules —
never running lifespan); non-vacuity floors on every relocated glob/list-driven check (minimum
file counts, known names present). Acceptance = the whole frozen battery with ZERO expected-value
changes (only import-path diffs), identical `manifest_hash`, the Task-3 harness report reproduced
byte-for-byte, and evaluation wall-time parity on the same cached frame. No pyproject/pip
packaging — plain repo-root package (Hunt P5/P10).

### Phase B — The lever program (one lever = one identity rotation = one stamped report)

### 8. Flip `LPS_HOLDING_SHELF_ENABLED` (Family 1 core)
| | |
|---|---|
| **Domain** | McKinney × Beck — Evals and regression (P7); governed re-freeze (P10) |
| **Ref** | `quality-llm.md` → P7/P10; `quality-testing.md` → P10 |
| **Depends on** | Task 7 |

The lowest-risk, highest-yield lever: the two-form LPS doctrine's flat holding shelf goes live.
EC-8 flip protocol: ledger Dark-table exit, manifest rotation, strategy_v2 settings block + Reading
Model updated in the same change, pre-measured cost bound. Treat WTS/PBT gains as in-sample —
acceptance evidence is the negative corpus unchanged (CTOS@06-11 upheld), the stage-matched corpus
re-freeze (ONLY `holding-shelf-lps`-tagged pinned misses convert: WTS/DRTS/PBT; operator sign-off
recorded, reseal stays a standalone command never chained into automation — Hunt P9), and the
measured full-universe fire-rate delta. Expected: WTS + PBT convert; MOV/VLO grade at his rails.

### 9. Band-rails: sequence-aware HOLD + deep-event depth cap, then flip (Families 4 + 2)
| | |
|---|---|
| **Domain** | McKinney — Validate/constrain defensively (P2); versioning events (P10) |
| **Ref** | `quality-llm.md` → P2/P10 |
| **Depends on** | Task 8 |

While dark: forgiveness of an earlier below-rail excursion only within a strictly-deeper ordered
chain of individually-qualified events whose FINAL event passes the unconditional never-undercut
rule; window-edge-unresolved spans stay disqualifying; gap-merge precedes forgiveness; above-rail
fail-back untouched. The depth cap lands in ATR units with an explicit non-finite/near-zero-ATR
quarantine (refuse event-typing, fall back to strict behavior). New tunables (cap, chain rules)
enter `config/settings.py` + manifest in the same change (Leach P1). Unit tests transcribed from
the marks, not the code: BODI's Jan→Mar two-step qualifies, its reversed ordering refuses, EGBN's
9.98-ATR excision refuses by pinned magnitude (Beck P1/P3). Then flip `BAND_RAILS_ENABLED` as one
versioning event: manifest rotation + stage-matched re-freeze (BODI `band-vs-excursion`; EGBN stays
`under-investigation` with a stays-dead regression pin on its September-box fire) + full-universe
cost bound (the "last-resort" pool is the COMMON case at universe scale — Performance P3). Expected:
BODI converts at his exact rails; EGBN's over-reach fire dies.

### 10. OVERSHOOT_R window rescope for above-R throwbacks (Family 1)
| | |
|---|---|
| **Domain** | McKinney — Evals and regression (P7) |
| **Ref** | `quality-llm.md` → P7/P2 |
| **Depends on** | Task 8 (shelf flip), Task 2 (raw triple archived) |

Rescale the LPS window-localization denominator for OVERSHOOT_R windows only, to the larger of box
height and a k·ATR floor — k chosen from the archived distribution over marks + fired boxes, never
from the CTOS anecdote alone. Full EC-8 as a NEW dark flag; ATR quarantine as in Task 9;
acceptance includes byte-identity of corpus + shadow restricted to non-OVERSHOOT_R cases (provably
invisible outside its scope). Expected: CTOS converts.

### 11. Shelf length 3→2 (Family 1 tail)
| | |
|---|---|
| **Domain** | McKinney × Beck — Boundary validation (P2); companion negatives (P4/P5) |
| **Ref** | `quality-llm.md` → P2; `quality-testing.md` → P4/P5 |
| **Depends on** | Task 8 |

Before moving the floor, audit every shelf sub-measure at two bars for crash-safety AND
discriminative meaning (flat-or-descending is near-vacuous at n=2). Genuine loosening: ratchet-
gated, ships with a still-rejected two-bar companion case pinned as a regression test. Expected:
VCTR converts.

### 12. Volume contraction 0.85→0.87 (Family 1 volume edge)
| | |
|---|---|
| **Domain** | McKinney — Evals and regression (P7) |
| **Ref** | `quality-llm.md` → P7 |
| **Depends on** | Task 2 (ratio distribution archived), Task 3 |

Move the LPS volume floor only against the archived raw ratio distribution over true positives and
fired boxes (checked against forward returns), with a non-finite-ratio refusal guard on the 50-day
denominator. Manifest key: rotation + docs regen in the same change. Expected: AGCO fires in
window (its SMA50 pincer becomes moot for this batch; the baseline-gate rescope stays a stretch
item gated on measured flicker frequency).

### 13. Election surgery behind dark flags: stale-frame dethronement + rescued-pool arbitration (Family 3)
| | |
|---|---|
| **Domain** | McKinney × Performance — Reproducibility (P4); one trailing pass (P3/P6) |
| **Ref** | `quality-llm.md` → P4/P2; `quality-performance.md` → P3/P6 |
| **Depends on** | Tasks 8–12 landed (highest blast radius goes last) |

Two scoped changes as NEW dark flags with the full EC-8 protocol: (a) a valid pair whose currency
rests solely on the SOS-trim rescue loses election after N consecutive sessions fully above its
buffered R, in favor of a later valid pair price is engaging — N is a manifest knob, the count runs
only over bars at/before the eval bar on the election's own window, deterministic per frame, no
cross-session state, one backward pass over the already-loaded frame (never per-session
re-election); (b) a fully-valid rescued framing that predates every strict candidate competes
instead of dying `rescue_unused` — and the trace stops saying `rescue_unused` for a framing that
competed. Acceptance: full-corpus election regression shows no non-mark boxes changing hands;
election-flap count across walked sessions drops. Expected: MATX converts (with Task 8);
MOV's snapshot flapping stabilizes.

### 14. Program close: final battery, docs, ledger, memory, handoff
| | |
|---|---|
| **Domain** | Carmack (chair) × Leach — the auditable lineage (P3) |
| **Ref** | `quality-postgres.md` → P3; strategy_v2 reading rule |
| **Depends on** | Task 13 |

Final full battery + harness report; verify the rotation ledger tells the whole 5/16→14+/16 story
(every rotation: lever, before/after hash, scoreboard, any re-freeze); confirm strategy_v2's
Reading Model, MAP.md, AGENTS.md paths, and the generated settings block are consistent with the
shipped engine (each lever already updated docs in its own change — this is the sweep, not the
write); write session memory; hand the operator the update_dashboard.bat step and the stretch-lever
decision points (EGBN proximity-aware dead-space, YPF untrimmed-tape dwell, AGCO SMA50 rescope —
each now armed with real margin distributions from Task 2).

---

## Risks & Watchpoints

- **Friedman — ground-truth integrity (P9):** the re-mark loop after each lever must keep the
  "Mark FIRST, peek after" discipline — overlay off during corrections; an edited mark changes the
  fingerprint and forces an explicit re-baseline (Leach). The one failure mode that invalidates the
  whole program is marks drifting toward the engine.
- **Friedman — approval previews (P8/P4):** every re-freeze confirmation previews per-converted-mark
  evidence (stage tag vs lever, fire session/tier/rails); a stage-MISMATCHED conversion is framed
  as an anomaly, never sealed on the happy path. Re-freeze and EC-9 mark graduation never share a
  confirmation flow.
- **McKinney — float boundaries (P4):** several gates operate at one-close resolution; every lever
  spec states rounded-vs-raw comparison and boundary inclusivity, held identical across live,
  shadow, and harness paths.
- **Beck — precision side (P4/P5):** recall marches against ONE sealed negative. Pin killed-probe
  outcomes as regression tests as levers land, and ask the operator to graduate new negatives
  through EC-9 as loosening proceeds — tests cannot manufacture ground truth.
- **Fowler — the two hats (P8):** evaluation.py's known impurities (stderr prints, lazy seams) are
  NOT cleaned during the move. Any test whose expected values "need" adjusting mid-extraction is
  the tripwire that behavior moved.
- **Hunt — no packaging metadata (P5/P10):** engine_alpha never gains pyproject/pip identity; the
  dependency-confusion surface stays closed.
- **Friedman — counterfactuals stay counterfactual (P9):** dark-flag variant tallies live in the
  harness report only; a variant "would fire" never renders in the live chip vocabulary.
- **Saarinen — future distribution view (P4):** if ever built, one recessed dot-strip per gate
  below the coverage table — never a histogram tile grid.
- **Performance — harness cadence (P4):** fired-walks stay session-capped and the variant protocol
  stays linear (baseline + one lever under test); wall-seconds per variant is the standing creep
  alarm.
- **Stretch levers (Families 5/6) are evidence-gated, not scheduled:** dwell rescopes and the SMA50
  pincer wait on the Task-2 margin distributions per the incremental tuning loop. YPF and EGBN are
  the two marks the program consciously leaves for that evidence.

## External Setup Required

No external services, keys, or installs. Operator-gated acts inside the loop:

| # | What | Why | Blocking task |
|---|------|-----|---------------|
| 1 | Operator sign-off on each corpus re-freeze (previewed conversions) | EC-7/EC-9 human gate | Tasks 8, 9 |
| 2 | Operator runs `update_dashboard.bat` after merges | Loading code into the service is the operator's job | 14 |
| 3 | (Recommended) operator graduates fresh negatives via EC-9 as levers loosen | Precision-side ground truth | 8–13 |

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Harness truth: event-window fired-walk + fire-session rails | Beck/McKinney | — |
| 2 | Margin + raw-measure telemetry, ADD-only, proven inert | Leach/McKinney | — |
| 3 | Re-baseline scoreboard + EC-8 cost protocol | Beck | 1 |
| 4 | Pre-move rulings + parity baseline capture | Fowler/Ramírez | 3 |
| 5 | Move leaf packages (structure, scoring, freeze, stability) | Fowler | 4 |
| 6 | Move eval chain + runtime seams (pickle, subprocess, bootstrap) | Fowler/Ramírez/Perf | 5 |
| 7 | Lockdown invariants + extraction acceptance | Hunt/Beck/Ramírez | 6 |
| 8 | Flip holding-shelf LPS (re-freeze WTS/PBT) | McKinney/Beck | 7 |
| 9 | Band-rails HOLD chain + depth cap → flip (BODI; EGBN dies) | McKinney | 8 |
| 10 | OVERSHOOT_R window rescope (CTOS) | McKinney | 8, 2 |
| 11 | Shelf length 3→2 (VCTR) | McKinney/Beck | 8 |
| 12 | Vol contraction 0.85→0.87 (AGCO) | McKinney | 2, 3 |
| 13 | Election surgery: dethronement + rescued-pool arbitration (MATX) | McKinney/Perf | 8–12 |
| 14 | Program close: battery, docs, ledger, memory, handoff | Carmack/Leach | 13 |

## Verdict

The load-bearing decision is sequencing, and it is settled: fix the ruler, then move the engine
without touching it, then turn exactly one knob at a time with a stamped identity per turn. Half
this program's promised gains (MS, NGL, WTS, PBT, BODI, and honest grading for MOV/VLO) come from
a harness fix and two flags that already exist — build those first and the "algorithmic miracle"
shrinks to five scoped detection changes, each with its converting mark named in advance. The
critical domain is McKinney's: every real risk in Phase B is a lookahead, a NaN, or a
nondeterminism hiding inside a plausible-sounding forgiveness rule, and the election surgery in
Task 13 is where the program most resembles the reverted shelf-R failure — keep it last, keep it
flagged, keep the full-corpus regression as its judge. Start at Task 1 tonight; it is engine-free
and unblocks everything. Keep a Beck-shaped gate-runner alongside the build at every step — the
battery that is too slow or too skipped is how a 14/16 quietly becomes a lie.
