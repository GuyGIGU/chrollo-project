# Project Conventions

Accepted patterns and enforced conventions from council reviews. The council reads this file before every
review to avoid re-flagging resolved decisions.

---

## Accepted Patterns

These are intentional — do not flag as findings.

### AP-1: `us_stocks` key vs `us_equities` universe_type split
**Pattern:** The default universe's `key` is `us_stocks` (API/cache token) while its archive `universe_type` is
`us_equities`; the other two universes use one token for both. Do NOT propose migrating the archive tag to match
the key.
**Origin:** Fowler / Hunt — Council Review 2026-06-30-1124
**Rationale:** Renaming the live archive tag is a live-SQLite migration for cosmetic gain; the boundary leak it
caused is closed by EC-1 instead (the split lives, correctly, only inside `universe.py`).

### AP-2: `fetch_data` cold/incremental/repair state machine
**Pattern:** `core/pipeline/downloads.py` `fetch_data` is a ~70-line lock→scope→fresh?→current?→incremental?→cold
sequence of named `_try_*`/`_*_result` helpers with IO/mutations visible at the helper boundaries. Do NOT
"simplify" or split it further.
**Origin:** Fowler (LEAD) — Council Review 2026-06-30-1124
**Rationale:** It is a well-factored state machine, not a god-function; the sequencing is clear and the state is
contained.

### AP-3: Per-call `Universe` registry build + lazy settings reads
**Pattern:** `core/pipeline/universe.py` rebuilds the registry per call and reads settings at call time (not
module-level attribute reads). Do NOT hoist the registry to a module-level materialization.
**Origin:** universe.py design — Council Review 2026-06-30-1124
**Rationale:** Avoids the config-vs-cwd shadowing trap (the backend cwd shadows the repo-root `config` package).

### AP-4: `yfinance==1.2.1` exact pin
**Pattern:** `requirements.txt` pins yfinance to an exact `==1.2.1`. Never bump it as a "stale dependency" finding.
**Origin:** Hunt — Council Review 2026-06-30-1124
**Rationale:** An unattended scan breaks (and silently archives wrong setups) if a yfinance release changes
Yahoo's scraper / OHLC adjustment — it is a supply-chain + byte-parity control, upgraded only deliberately.

### AP-5: The price-independent fill ledger is a necessary JS↔Python twin
**Pattern:** `summarizeFillLedger` (and the price-independent half of `deriveTradeRow`) stays in
`webapp/frontend/src/utils/tradeTableUtils.js` even though `webapp/backend/services/trade_risk.py`
ports the same ledger. The JS copy backs a WRITE path (the fill-save payload in `useTradeFills` +
inline `position_size` in `useTradeCellEditing`) that a read-only GET cannot serve. Do NOT flag this
as a dual implementation / EC-3 violation — it is a deliberate cross-language twin reconciled by the
parity test (`tests/test_trade_risk.py`).
**Origin:** Fowler / McKinney — Council Review 2026-06-30-1338
**Rationale:** Only the price-DEPENDENT live overlay was centralized; the ledger twin is forced by the write path.

### AP-6: `_js_number(None) == 0.0` in `trade_risk.py` is intentional
**Pattern:** `services/trade_risk.py` maps `None`→`0.0` (mirroring JS `Number(null)`), which differs from
JS `Number(undefined)=NaN` only on a literally key-absent `entry_price`. Do NOT "fix" `infer_direction`
to treat `None` as not-knowable: the router always materializes `entry_price` present-as-None (the
agreeing case), so the current code matches JS on every reachable input, and the proposed fix would
INTRODUCE a divergence on the reachable present-null case.
**Origin:** McKinney — Council Review 2026-06-30-1338
**Rationale:** Parity is correct on the whole reachable input domain; the divergence is unreachable.

### AP-7: The eq_* archive columns' hand-listing is a family-contiguity exception
**Pattern:** `eq_engagement_respect_frac` / `eq_max_excursion_atr` are hand-listed in
`webapp/backend/services/startup.py` `_MIGRATIONS` and `core/archive/writer.py` `_NEW_COLUMNS`
ONLY to keep the eq_* gate-margin family contiguous with its already-listed siblings. Do NOT flag
this as triple registration, and do NOT grow the hand lists for any new column family — the
default for new archive columns is MODEL-ONLY registration (the boot pass and the writer's second
pass derive ALTERs from `SetupArchive.__table__`; the Lane E / Event Map route).
**Origin:** Ramírez — Council Review 2026-07-24-1903 (engine/gap-breach); operator-confirmed 2026-07-25
**Rationale:** A half-listed family misleads more than a documented exception; the note at the
writer list carries the rule forward.

---

## Enforced Conventions

These must be followed — flag violations as findings.

### EC-1: One source for the equities-default scope
**Convention:** Any universe-scoped archive read that defaults to the equities population MUST derive its default
from `core.pipeline.universe.DEFAULT_UNIVERSE_TYPE` (or `default_universe().universe_type`) — never a bare
`"us_equities"` string literal re-typed at the call site.
**Origin:** Fowler / Ramírez — Council Review 2026-06-30-1124
**Principle:** `references/refactoring.md` → P4/P5 (Inconsistent Vocabulary / Shotgun Surgery)

### EC-2: NaN-coerce archive cells at the pandas boundary
**Convention:** When projecting archive rows read via pandas (e.g. `read_sql_query` → `itertuples`), coerce
possibly-missing cells with `pd.isna(...)` (or an explicit `is None` check), NEVER a truthiness test — `bool(np.nan)`
is `True`, so a SQL `NULL` leaks the literal `"nan"` into grouping/identity keys.
**Origin:** McKinney / Beck — Council Review 2026-06-30-1124
**Principle:** `references/quality-llm.md` → P2 (NaN/dtype at the boundary)

### EC-3: Fold twin code paths, never copy
**Convention:** Logic that must agree across call sites (eval-twins, `_weekly_refresh_due`, depth/coverage/scope
predicates) must live in ONE shared implementation that both sites import — not two separately-maintained copies.
**Origin:** Fowler — Council Review 2026-06-30-1124
**Principle:** `references/refactoring.md` → P5 (twin code paths)

### EC-4: A widened identity key must be threaded through EVERY writer
**Convention:** When the archive identity key is widened (e.g. adding `universe_type`), every writer — live
screener, seed, forward-returns/manual — must stamp the new column AND include it in its existence/upsert check,
not just the primary writer.
**Origin:** Leach — Council Review 2026-06-30-1124
**Principle:** `references/quality-postgres.md` → P1/P4 (constraints are assertions; upsert matches the key)

### EC-5: Live open-trade risk is derived once, server-side
**Convention:** The price-dependent live-trade risk overlay (live price, unrealized P&L $/%, R-multiple,
distance-to-stop %/R, stop tone, target distances) is derived ONLY in `webapp/backend/services/trade_risk.py`
(the single source of truth); the frontend consumes it via the `riskFor` accessor. Never re-add a live-risk
computation in JS. R-multiple/`riskDistance` anchor 1R to `planned_stop`→`stop_loss`→None (never fabricated);
distance-to-stop and the stop tone use the CURRENT working `stop_loss` on both sides.
**Origin:** Fowler / McKinney — Council Review 2026-06-30-1338
**Principle:** `references/refactoring.md` → P5 (twin code paths) ; `conventions.md` EC-3

### EC-6: `/live-risk` degrades, never 500s
**Convention:** The read-only `GET /live-risk/` must degrade to null-price rows on any operational failure,
never raise: parse `actions_json` tolerantly (drop non-dict cells), coerce the live price at the boundary,
read only the EXISTING IBKR snapshot (no new connection) and release the DB read before the price fetch.
Programmer errors may still surface (do not blanket-swallow); operational failures log + degrade.
**Origin:** Leach / Ramírez / Hunt — Council Review 2026-06-30-1338
**Principle:** `references/quality-backend.md` → P1 (operational vs programmer errors)

### EC-7: Operator-marks corpus files are immutable test specs
**Convention:** Files under `docs/marks/` are operator ground truth and acceptance specs: grow them
append-only; corrections land only as explicit operator source-upgrades (extraction→operator), never
silent in-place edits; a failing corpus case is fixed in the ENGINE — never by editing a mark, widening
a matcher's date window, or reinterpreting trigger rules. Harnesses consuming a corpus must validate it
loudly (malformed/unrecognized marks fail the run, never skip) and detect unsanctioned edits.
**Origin:** Beck / Leach — Council Plan 2026-07-09-2200 (whole-chart event read); operator-confirmed 2026-07-10
**Principle:** `references/quality-testing.md` → P10 (the test spec is the constraint); `references/quality-postgres.md` → P1

### EC-8: Every new engine flag ships with the full flag protocol in one change
**Convention:** A new engine behavior flag must land in the SAME change as: registration in the frozen
settings manifest (`core/freeze`) AND the dark-flag ledger (`tests/test_invariants.py`); a unit-level
inert test in its home module; one flag-off frozen-fixture pipeline replay asserting equality with the
shadow baseline; and an agreed scan-metrics evaluation-phase cost bound measured before the operator
flips it live. Flag-off must be byte-identical and compute-free.
**Origin:** Beck / Leach / Performance — Council Plan 2026-07-09-2200 (whole-chart event read); operator-confirmed 2026-07-10
**Principle:** `references/quality-testing.md` → P5; `references/quality-postgres.md` → P1; `references/quality-performance.md` → P1

---

### EC-9: Two mark populations, one-way human-gated graduation
**Convention:** The calibration-marks DB (`calibration_marks`, operator-owned) is EDITABLE ground truth —
the operator corrects/hard-deletes his own marks and every edit bumps `revision`; the `docs/marks/`
corpus stays sealed under EC-7. Movement between them is ONLY an explicit, per-mark, operator-confirmed
export (calibration → corpus, carrying provenance) — never a sync, batch export, or startup step; no
tool gets a write path to either population that circumvents this. Every harness report names which
population it scored and stamps a fingerprint of the exact marks set.
**Origin:** Hunt / Leach / Beck / Fowler — Council Plan 2026-07-10-2329 (Calibration at Scale);
operator-confirmed 2026-07-10
**Principle:** `references/security.md` → P9 (assume breach); `references/quality-postgres.md` → P5;
`references/quality-testing.md` → P10

---

### EC-10: The forward grading frame's post-as_of bars are DEADLINES, never engine inputs
**Convention:** Grading a Trigger uses a SECOND frozen basis — `frame_store.freeze_grading_frame` /
`load_grading_frame` — that extends past `as_of` through `frame_end`, addressed by the `<= as_of`
`base_digest` so the two always pair (its `<= as_of` slice MUST reproduce `base_digest`, else it is treated
as unbound and never graded). Those forward bars exist ONLY to locate the engine's fire date relative to the
operator's buy — they are the deadline the grade measures against, and are NEVER fed to the reading/scoring
engine as inputs. The reading engine still sees only `<= as_of` (the no-lookahead invariant is intact), and
the `frame_digest` a mark binds to remains the `<= as_of` frame the operator actually looked at. This
forward-inclusive basis is the load-bearing enabler for a frozen-only, no-vendor-fetch Trigger grade.
**Origin:** McKinney — Council Plan 2026-07-10/2026-07-21 (Calibration at Scale / redesign); built +
operator-confirmed 2026-07-22 (trigger batch, main `136110b`)
**Principle:** `references/quality-postgres.md` → P1 (the frozen basis is an assertion);
`references/quality-testing.md` → P10

---

### EC-11: The Trigger is structurally coupled to the LPS
**Convention:** A calibration Trigger (the operator's buy) is valid ONLY when the setup carries ≥1 LPS event,
and its `trigger_date` is strictly AFTER the last LPS bar. It may otherwise land before, on, or after `as_of`
— the `trigger_date >= as_of` floor was DROPPED 2026-07-22 (the operator often sets an `as_of` already past
the breakout). The assisted Trigger tool snaps level→last-LPS-bar high and date→first breakout bar, is inert
until an LPS exists, and RE-DERIVES whenever the LPS is re-drawn; validity does NOT hard-pin `trigger_price`
to the LPS high (operator flexibility). The single shared judgment lives in `marks_validity._validate_trigger`
(EC-3); any DDL CHECK is fresh-DB-only (SQLite can't retrofit constraints) and must not contradict the shared
validator.
**Origin:** operator-confirmed 2026-07-21 (Trigger = breakout above the last LPS bar's high) + relaxed
2026-07-22 (drop the `as_of` floor); main `136110b`
**Principle:** `references/quality-testing.md` → P10 (the spec is the constraint); `conventions.md` EC-3

---

### EC-12: A committed replay basis must be content-verified at check time
**Convention:** Any committed artifact that carries a replay basis (today: the marks-corpus fixture
parquet — the ONLY in-repo carrier of the sealed drawn bases) must be BOUND to sealed content
evidence and verified where it is consumed: the gate's check recomputes each graduated frame's
content digest against the corpus's sealed `frame_digest`, and the cheap pytest plumbing pins each
frame's bar count to the frozen baseline. A seal that covers the spec but not the data the spec is
graded on is one unsealed link — three seats found it independently.
**Origin:** Leach / Beck / Hunt — Council Review 2026-07-24-1903 (engine/gap-breach);
operator-confirmed 2026-07-25
**Principle:** `references/quality-postgres.md` → P1 (constraints are assertions);
`references/quality-testing.md` → P10; `references/security.md` → P9 (assume breach)

---

### EC-13: Marks-consuming instruments use the ONE validated loader and stamp the exact set scored
**Convention:** Every tool that reads a marks population loads it through the shared validated
loader (`tools.calibration_harness.load_marks` / `load_box_marks`) — a malformed row aborts the
batch naming the offender, never a silent skip — and every report stamps its population name, the
fingerprint of EXACTLY the marks it scored (a filtered run stamps the filtered set), and the engine
manifest hash. No instrument re-implements mark loading, window indexing (`tools.replay.session_pos`),
or frame enrichment (`tools.replay.enrich_marked_frame`).
**Origin:** Fowler / Hunt / McKinney — Council Review 2026-07-24-1903 (engine/gap-breach);
operator-confirmed 2026-07-25
**Principle:** `conventions.md` EC-3 / EC-9; `references/refactoring.md` → P5 (twin code paths)

---

### AP-8: The story-admission read and the archive substrate read are DIFFERENT bases — by design
**Pattern:** The story pool's admission judgment runs on the CANDIDATE window + candidate ATR;
the archived `event_map_*` substrate runs on the ELECTED window + zone ATR. They share ONE reader
but may legally disagree (`elected_pool='story'` with `event_map_story_admitted=0` — YPF is the
live example); the admitting evidence travels separately in `story_admission_profile`. Do NOT
propose "unifying" the two reads, and do NOT treat the substrate profile as the admission record.
**Origin:** Council Review 2026-07-26 (engine/event-map-program) — Friedman/McKinney/Leach finding 2's
underlying design, operator-confirmed 2026-07-26
**Rationale:** The admission must be judged on what the pool actually consulted; the substrate must
describe the elected geometry the TA-score charter grades. Collapsing them falsifies one or the other.

---

### EC-14: Every tool write passes the sealed-output guard
**Convention:** Any file a `tools/` script writes from a user-supplied path (`--json`, `--out`, …)
must be routed through `tools._bootstrap.refuse_sealed_output` BEFORE the file is opened — a
mistyped path must fail loudly, never truncate a sealed spec (`docs/marks/`) or a frozen baseline
(`tests/baselines/`) in place.
**Origin:** Hunt — Council Review 2026-07-24-1903 (engine/gap-breach); operator-confirmed 2026-07-25
**Principle:** `references/security.md` → P7 (deploy assertions as tripwires); `conventions.md` EC-3

---

### EC-15: An executed gating A/B replaces its pre-registration in the decision record — in the same change
**Convention:** When a pre-registered A/B (fire-level, cost, any flip gate) is EXECUTED, every
decision surface that cited the pre-registered expectations — the flag-ledger row first — must be
updated in the SAME change to record the executed outcome, including failed expectations, and to
restate what actually remains open. A ledger row that still reads as "gated on" an A/B that already
ran is a falsified decision record, not a stale doc.
**Origin:** Friedman / Hunt — Council Review 2026-07-26 (engine/event-map-program, finding 1: the
STORY_POOL row still carried "EGBN converts" after the executed A/B proved it false);
operator-confirmed 2026-07-26
**Principle:** `references/quality-ux.md` → P9 (trust is destroyed by single failures);
`references/security.md` → P9

---

### EC-16: Evidence cited by ledger rows and rulings lives in committed paths
**Convention:** The evidence pointers on a flag-ledger row, a ruling record, or any decision doc
must resolve inside the repository (the `docs/` protocol-doc convention — e.g.
`docs/event_map_program_2026-07.md`), never in gitignored scaffolding (`.council/`, root
`PLAN-*.md`). Machine-local captures are distilled into a committed record BEFORE the row cites
them; a pointer that dies on a fresh clone is not an evidence trail.
**Origin:** Hunt / Friedman — Council Review 2026-07-26 (engine/event-map-program, finding 1);
operator-confirmed 2026-07-26
**Principle:** `references/security.md` → P9 (absence of evidence is not evidence of absence)

---

### EC-17: A dark flag's happy path is pinned through the REAL cascade before its flip decision
**Convention:** Every dark engine flag ships (or gains, before its flip is decided) at least one
committed test that drives the feature's ACCEPTANCE path through the real code path — production
values for every other flag, only the flag under test forced on — asserting the feature's
observable outcome end to end (for an election feature: the election happens, with provenance and
evidence fields intact). Builder-in-isolation tests and monkeypatched rung tests do not satisfy
this; the suite must be able to go red if the dark feature silently stops working. Extends EC-8.
**Origin:** Beck — Council Review 2026-07-26 (engine/event-map-program, finding 3: no committed
test elected a story candidate; the production BAND-on/story-on cell was uncovered);
operator-confirmed 2026-07-26
**Principle:** `references/quality-testing.md` → P4/P5 (missing happy path = P1)

---

### EC-18: A ruled judgment predicate has exactly ONE implementation
**Convention:** An operator-ruled judgment (story admission today; any future ruled form) exists
as ONE function in the engine. Research and evidence instruments (census menus, harnesses) that
score "the ruled form" DELEGATE to that function or pin equivalence against it in their check
battery — never a re-typed twin lambda. A re-ruling then re-scores every instrument automatically
instead of silently diverging from the live pool. Sharpens EC-3 for ruled predicates.
**Origin:** Fowler — Council Review 2026-07-26 (engine/event-map-program, finding 7: census Form A
was a character-for-character twin of `story_admission`); operator-confirmed 2026-07-26
**Principle:** `conventions.md` EC-3; `references/refactoring.md` → P5

---

### EC-19: Closed-set archive label columns get the universe_type treatment
**Convention:** Any archive column documented as a closed set (`elected_pool` today) is enforced
three ways: a model-level CHECK constraint (guards every fresh create_all database; SQLite cannot
retrofit), a write-time assertion at the single stamping point (guards the live DB — e.g.
`bricks._pool_label`), and an archive-layer test proving an illegal label cannot land. A comment
saying "closed set" is not enforcement.
**Origin:** Leach — Council Review 2026-07-26 (engine/event-map-program, finding 8);
operator-confirmed 2026-07-26
**Principle:** `references/quality-postgres.md` → P1 (constraints are assertions)

---

### EC-20: A telemetry lane never widens the blast radius of the path it observes
**Convention:** Measure-only passengers (refusal telemetry, probes, shadow reads) get their own
containment at EVERY layer they ride: per-item in the worker (degrade to empty output + a loud
dedicated counter the nightly print surfaces), operational-error coverage across their whole DB
span (ensure DDL + probes + commit, duplicate-tolerant like the established siblings), and ordering
that puts the paying artifact first. Programmer errors inside the lane still surface — via the
counter in production, via the raise in tests/census. "Never touches the scan" is an operational
property, not just a data property.
**Origin:** Ramírez / McKinney / Leach — Council Review 2026-07-26-2156 (engine/near-miss-lane,
findings 2/5/6: three seats found the same class at three layers); operator-delegated 2026-07-26
**Principle:** `references/quality-backend.md` → P1 (deliberate crash boundaries);
`references/quality-postgres.md` → P2

### EC-21: A passenger on a shared job never owns the job's status
**Convention:** When telemetry rides a books-of-record job (the forward-returns maturation run
today), the passenger's call is wrapped in its own narrow logged catch at the seam — the shared
run's recorded status reflects the paying customer only, and the passenger's failure prints
distinctly. A false "failed" on a health surface is a trust defect, not a conservative default.
**Origin:** Ramírez / Leach — Council Review 2026-07-26-2156 (finding 6); operator-delegated
2026-07-26
**Principle:** `references/quality-postgres.md` → P2 (the job record must tell the truth)

### EC-22: Every value in a closed-set label column has a committed producing test
**Convention:** EC-19 proves an illegal label cannot land; this adds the mirror: each LEGAL value
of a closed-set column (pool, failing_leg, elected_pool, …) has a committed test in which the real
producer actually emits it end-to-end — or the vocabulary is explicitly narrowed. A CHECK whose
value is unreachable is an advertised capability the system does not have (the near-miss lane
shipped with rescued/band unreachable behind a pool-blind dedup key and stayed green).
**Origin:** McKinney / Fowler / Beck — Council Review 2026-07-26-2156 (finding 1);
operator-delegated 2026-07-26
**Principle:** `conventions.md` EC-19; `references/quality-testing.md` → P4/P5

### EC-23: Columns forming one fact are written as one unit in every branch
**Convention:** When two columns state one fact (triggered/trigger_date today; any stamped
value+date or value+source pair), every branch that writes one writes both — the paired value on
the affirmative branch, NULL on the negative — so no code path can half-flip the pair into a
contradiction (`triggered=0` with a stale date). Mirrors the fires' pair-coherent write.
**Origin:** Leach — Council Review 2026-07-26-2156 (finding 7); operator-delegated 2026-07-26
**Principle:** `references/quality-postgres.md` → P1 (constraints are assertions)

---

### EC-24: A staleness budget counts only sessions the provider could have supplied
**Convention:** Freshness/staleness arithmetic that bounds a tolerance (session lag, retry
budgets) must discount sessions PROVEN absent upstream (the `absent_sessions` ledger) — the
budget measures our lag against what exists, not against a calendar ideal. Without the discount
the tolerance is consumed by exactly the event it exists to survive: a provider-lost Friday would
have expired the `session_lag` state at 16:31 ET the same day it shipped, when the expected
session rolled forward.
**Origin:** Council Review 2026-07-27-1732 (provider-lost-session hardening, ledger redesign);
operator-delegated 2026-08-04
**Principle:** `references/quality-postgres.md` → P2 (the record must tell the truth)

### EC-25: Cooldowns are keyed on the thing they describe, never on the wall clock
**Convention:** A "don't retry what we already learned" guard is keyed to the FACT it records
(the absent session; the unchanged symbol set), not to elapsed time. A wall-clock window is dead
exactly when it is needed — measured repeats were ~24h apart and a lost Friday spans ~72h to
Monday's close — and it silently re-arms on schedules nobody chose. A new fact (a newly completed
session, an operator Refresh) gets a fresh attempt by construction, not by timer expiry.
**Origin:** Council Review 2026-07-27-1732 (the failed-cold-fetch cooldown was redesigned into the
session-keyed `absent_sessions` ledger); operator-delegated 2026-08-04
**Principle:** `docs/decisions.md` → Tested-DEAD 2026-07-27 (the wall-clock variant, refuted at
design time); `references/quality-postgres.md` → P1

### EC-26: Published payload fields are derived at the publisher, never echoed defaults
**Convention:** A field on a health/status payload is computed at the boundary that publishes it
(or by a caller that provably computed it) — never accepted as a parameter default most call
sites silently leave unset. `weekly_refresh_due` shipped as accepted-but-never-computed: 5/7
callers passed nothing, the payload never emitted it, and the Refresh button no-op'd without a
trace. A default that travels the wire as data is a lie on the only surface the operator sees.
**Origin:** Council Review 2026-07-27-1732 (the silent-Refresh defect); operator-delegated
2026-08-04
**Principle:** `references/quality-ux.md` → P9 (trust is destroyed by single failures);
`conventions.md` EC-21

### EC-27: A conjunctive guard's tests must assert WHICH condition refused
**Convention:** A test battery for a guard of the form `A and B and C` must distinguish which leg
refused (distinct sentinel, counter, or message per leg), not merely that the guard refused. A
conjunctive guard can stay green while the wrong leg fires — the repair dropout_guard shipped with
a denominator bug that made the manual "Repair N" path issue ZERO batches 100% of the time, and
every existing test passed because they all tripped the guard through another leg. Complements
EC-22: every legal value producible, every refusing leg distinguishable.
**Origin:** adversarial review + Council Review 2026-07-27-1732 (the repair-guard denominator P1);
operator-delegated 2026-08-04
**Principle:** `references/quality-testing.md` → P4/P5

---

### EC-28: The wire carries verdicts, never rules
**Convention:** No scoring cap, threshold, fire-rule, or chapter-membership may be re-declared in
frontend JS. Every judgment (which chips fired, the grade, chapter subtotals, tier) crosses the
wire already resolved by the engine; the frontend keeps only presentational lookups (labels,
tones, ordering, copy). If a surface needs a number that isn't on the wire, the fix is a backend
serialization addition — never a client computation. Operator's framing: "rules are carried by
the engine itself; the purpose of this layer is to grade the passing stocks."
**Origin:** Council Plan 2026-08-06-1038 (TA grade — the seven-copies disease: caps/fire-rules/
vol-z thresholds duplicated across setupScoreMath.js and friends, rs/uptrend caps already
drifted stale); operator-confirmed 2026-08-08
**Principle:** `conventions.md` EC-3/EC-5 (one source of truth, server-side derivation);
`references/refactoring.md` → P5 (twin code paths)

### EC-29: Baselines recapture only at a flip/seam commit
**Convention:** Shadow-pipeline, seed-recall, marks-corpus, and fold-parity baselines may be
recaptured ONLY in an explicit flip/seam task with committed evidence (EC-15/EC-16); a baseline
recapture appearing in any other diff is treated as masking a regression and rejected. The
regression ground truth is the operator's two signals — a stock he deems high quality
disappearing or getting demoted, and calibrated-list (Guided List) stocks no longer firing — and
a mid-build reseal silently destroys the second signal's meaning.
**Origin:** Council Plan 2026-08-06-1038 (TA grade — Carmack watchpoint: mid-build baseline
recapture is one of the two cheat temptations); operator-confirmed 2026-08-08
**Principle:** `conventions.md` EC-7/EC-15; `references/quality-testing.md` → P10 (the test spec
is the constraint)

---

### EC-30: A column-family producer rides EVERY writer, enforced by a guard that names each writer
**Convention:** When a family of archive columns gets a producer extraction (the `*_archive_values`
splats), EVERY writer of that table — live, seed, manual, and any future route — takes the splat in
the same change, and the guard suite asserts the producer's presence PER WRITER (the AST-guard
pattern), never "at least somewhere." A writer left to a raw model pass bypasses the family's
serialization, scrubbing, and closed-set refusals — the exact half-conversion that shipped a
guaranteed flag-on crash on the manual route with the whole suite green. Sharpens EC-4 from
"columns thread through every writer" to "the PRODUCER threads through every writer."
**Origin:** Leach / Fowler / Ramírez / Hunt — Council Review 2026-08-08-1808 (TA-grade build,
finding 1: four seats independently; reproduced `sqlite3.ProgrammingError` binding a raw list);
operator-delegated 2026-08-08
**Principle:** `references/quality-postgres.md` → P1; `conventions.md` EC-4/EC-19

### EC-31: A bug-tripwire asserts the operand the pipeline guarantees, and speaks on every output mode
**Convention:** An instrument's "this is a BUG" check (exit codes, violation banners) must compare
the quantity the pipeline actually promises invariant — never a downstream transform that may
legitimately reorder (the A/B ranked the post-warning headline; per-row multiplicative factors are
not affine, so the tripwire was one weight-setting away from crying bug on correct behavior). And
its verdict prints on EVERY output mode, `--json` included — an operator reads words, not exit
codes, and a silent alarm on the evidence path is no alarm.
**Origin:** McKinney / Friedman — Council Review 2026-08-08-1808 (finding 2);
operator-delegated 2026-08-08
**Principle:** `references/quality-llm.md` → P7; `references/quality-ux.md` → P9

### EC-32: An EC-17 cascade carries at least one input-tied assertion, mutation-checked once
**Convention:** A dark feature's EC-17 acceptance test must include ≥1 assertion that derives the
feature's outcome from the row's OWN inputs (e.g. the grade equals the sum of the row's term
points) — bounds, key-presence, and self-consistency identities all pass trivially on an
input-blind implementation (chapters summing to raw×k holds at zero). Prove the assertion's teeth
ONCE with a mutation probe (feed the seam an empty/wrong input; the suite must go red) before
trusting the cascade. Extends EC-17.
**Origin:** Beck — Council Review 2026-08-08-1808 (finding 3, mutation-proven);
operator-delegated 2026-08-08
**Principle:** `references/quality-testing.md` → P1/P6; `conventions.md` EC-17

### EC-33: Reserved vocabularies are derived from ONE tuple; flag-off leak checks derive from the archive extraction
**Convention:** A settled result/wire vocabulary lives in exactly one registry tuple; every
consumer (routing maps, tripwire filters, serializers) DERIVES membership from it — a hand-re-typed
subset silently mis-routes the next addition. A flag's OFF-state leak check additionally asserts
through the writers' own extraction (`*_archive_values(...)` all-None on the gated subset), because
the archive splats unconditionally: that form covers every current AND future family field by
construction, where a prefix filter goes stale the day a field family is added. Extends EC-8.
**Origin:** Beck / Fowler — Council Review 2026-08-08-1808 (finding 4: the two-prefix filter was
blind to six field families; `_grade_family` re-typed five names); operator-delegated 2026-08-08
**Principle:** `references/refactoring.md` → P4/P5; `conventions.md` EC-8

### EC-34: Every rule KIND in a declarative rule engine ships one wrong-side refusal case
**Convention:** A declarative rule interpreter (tag fire-rules today) is tested with one PRESENT,
FINITE, wrong-side case per rule KIND — just-under for fraction thresholds, at-threshold for
strict comparisons, wrong-label for eq, falsy for flags — asserting the id ABSENT. Producible-only
batteries (EC-22) prove every rule CAN fire; without the refusing side, "fire whenever the fact is
present" mutations stay green and the judgment surface degrades to noise. One case per KIND, not
per rule (Beck composability). Extends EC-22/EC-27 to rule engines.
**Origin:** Beck — Council Review 2026-08-08-1808 (finding 14: no committed row ever sat on the
refusing side of gt/lt or a non-demoted fraction); operator-delegated 2026-08-08
**Principle:** `references/quality-testing.md` → P5; `conventions.md` EC-22/EC-27

### EC-35: Path guards normalize before comparing — Windows ignores case
**Convention:** Any guard comparing filesystem paths (the sealed-output refusal, future
allow/deny-lists) normalizes BOTH sides with `os.path.normcase` + `os.path.realpath` before the
prefix check. Chrollo deploys on NTFS: a case-sensitive `startswith` let `docs/Marks/…` open the
real sealed directory — the exact mistyped-path scenario the guard exists for.
**Origin:** Hunt — Council Review 2026-08-08-1808 (finding 15); operator-delegated 2026-08-08
**Principle:** `references/security.md` → P7; `conventions.md` EC-14

### EC-36: Operator playbooks are executable from the doc alone
**Convention:** A committed operator playbook (flip checklists, runbooks) names the exact
interpreter ONCE at the top (this machine's bare `python` is a documented trap) and gives every
step a copy-runnable committed command — prose like "re-run the capture" is not a step. Every
pointer resolves in the repo (EC-16), including the instruments: a cost bound cited by a checklist
must be reproducible by a COMMITTED tool, not a machine-local harness. Promises about signal
surfaces (badges, banners) state when they light in reality, not aspiration — a signal already lit
before the event it claims to announce is a cry-wolf.
**Origin:** Friedman / Hunt / Beck — Council Review 2026-08-08-1808 (finding 10);
operator-delegated 2026-08-08
**Principle:** `references/quality-ux.md` → P2/P9; `conventions.md` EC-16

---

### EC-37: A stored pin is copied verbatim from the displayed artifact's identity — never clock-derived
**Convention:** When a UI action persists a reference to something the operator was looking at (a
watchlist save's pinned setup today; any future "what I saw when I acted" record), the identity
columns are copied VERBATIM from the displayed payload's own identity — never recomputed from any
clock at write time. Chrollo runs three clocks that disagree by design: `scan_date` is the scan
machine's LOCAL civil date (`core/pipeline/scan_job.py`), the scheduler fires on
`America/New_York`, and server stamps are UTC — so "match today's date to the scan row" is provably
wrong in definable windows (UTC trails local 00:00–03:00 local; a post-close run at ~22:30 local can
stamp the following day; the ET↔Israel offset moves twice a year). Artifact-sourced identity is
deterministic and DST-proof by construction, and it answers the calendar edges for free: a weekend
save pins Friday's scan because Friday's scan is what is on screen. Timestamps may be stored for
display/audit, but never as a join or grouping key. Generalizes the ReadVerdict precedent
(`scan_identity` keyed verbatim to the payload).
**Origin:** McKinney / Ramírez / Leach / Hunt — Council Plan 2026-08-09-2257 (Finviz UI/UX program,
watchlist date-tagging: four seats independently refused clock-derived pinning);
operator-confirmed 2026-08-09
**Principle:** `references/quality-llm.md` → P4 (pin the inputs, record the identity);
`references/quality-backend.md` → P3; `conventions.md` EC-26 (derived at the publisher, never echoed)

---

### AP-9: `can_archive=False` is THE archive block — the evaluate/archive split is load-bearing
**Pattern:** The `session_lag` health state deliberately splits `can_evaluate=True` from
`can_archive=False`: a panel one session behind is readable but must NEVER be archived, and the
archive path's ONLY gate is `can_archive`, enforced at the archive layer and pinned by
`tests/test_archive_reliability.py`. Do NOT "simplify" the pair into one boolean, and do NOT add
a second, parallel archive gate (a belt-and-suspenders twin lets the load-bearing one rot
unobserved). New consumers of panel readability key on `can_evaluate`; anything that PERSISTS
keys on `can_archive`.
**Origin:** Council Review 2026-07-27-1732 (provider-lost-session hardening); operator-delegated
2026-08-04
**Rationale:** Readable-but-never-archivable is the entire safety contract of `session_lag`;
merging the flags or duplicating the gate both destroy it silently.

---

### EC-38: A chart surface renders ONE artifact — overlay fields and candles never cross sources
**Convention:** Any surface that draws engine-read material (rails, LPS spans, structure
coloring, boxes) renders it ONLY against the exact candle arrays that shipped in the SAME
artifact — the scan row wholesale, or nothing. Fresh-cache candles are always a CLEAN chart; no
code path may merge overlay fields from one source onto candles from another, because overlay
geometry is index-arithmetic against the candle array it was computed with (a one-bar window
difference silently draws every rail and span on the wrong bars). The pane/card data contract is
atomic: one source per surface, chosen before render, never field-level mixing
(`resolvePaneData` / `cardPlan` are the reference implementations, node-pinned).
**Origin:** Watchlist-page build + Council Review 2026-08-17-1435; operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-28 (the wire carries verdicts); `references/quality-llm.md` →
P4 (pin the inputs)

### EC-39: A batched wire route resolves through its single-item sibling's exact function
**Convention:** When a resource has both a single-item route and a batched route (the candle
envelope + the card-grid batch today), BOTH resolve each item through the SAME shared function —
batching may group the reads, never re-implement the walk. A re-typed batch loop is a twin that
silently diverges on the degrade legs: the shipped one broke at first membership while the
single walk continued past failed reads, so one ticker got two different verdicts on one page.
Parameters that shape resolution (the EC-37 pin) must reach the batch too, or the batch is
resolving on half the identity. Sharpens EC-3/EC-18 for wire routes.
**Origin:** Council Review 2026-08-17-1435, finding 5 (four seats independently) + finding 6;
operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-3/EC-18/EC-37; `references/quality-backend.md` → P6

### EC-40: Every asked-for item gets a recorded outcome, and retry copy is wired
**Convention:** A client batch handler stamps a terminal cell for EVERY name it asked about —
including names the server declined to echo — in the same merge that lands the response; an
unanswered name must terminate in a rendered verdict, never re-join the fetch plan (the shipped
gap was an unbounded request loop armed by any legacy-cased stored row). Error-status entries
always have a real retry trigger (mount revalidate, selection), and any UI copy naming a
recovery gesture ("reselect to retry") is backed by a code path that actually re-issues the
request — copy and mechanism are verified together, not written separately.
**Origin:** Council Review 2026-08-17-1435, findings 1+3 (Friedman/Dodds/Hunt independently);
operator-delegated 2026-08-17
**Principle:** `references/quality-frontend.md` → P6 (errors are structural);
`references/quality-ux.md` → P9 (misleading copy is a trust event)

### EC-41: Client caches of server artifacts serve-stale-then-revalidate, keyed by generation
**Convention:** A module-level client store caching a server artifact (scan payloads, candle
envelopes, batch cells) is never write-once: ready entries keep serving while calls issue
background revalidates (a route mount and a selection are revalidation triggers), and the cache
key records every parameter the value was derived from (the pin universe). The arrival path
compares a cheap GENERATION stamp (cache_last_modified / last bar / verdict) and keeps the OLD
object reference when nothing moved — reference identity is the frontend's rebuild currency, so
a no-change revalidate must rebuild zero charts, and a real change must replace the reference so
everything downstream rebuilds deliberately.
**Origin:** Council Review 2026-08-17-1435, findings 4+11 (Dodds + Performance);
operator-delegated 2026-08-17
**Principle:** `references/quality-frontend.md` → P2 (managed cache contract);
`references/quality-performance.md` → P6 (allocate deliberately)

### EC-42: Ledger rows are trued up at BUILD END, not task time
**Convention:** In a multi-task change, every earlier task's flag-ledger row, program-doc
claim, and forward promise ("lands with Task N", "nothing consults this yet") is
RE-VERIFIED against the later tasks before the change is offered for commit; a snapshot a
sibling task already falsified is treated exactly as EC-15 treats an executed A/B's stale
pre-registration. The species build shipped its preset row claiming "nothing consults the
flag yet" while Task 8 in the same change-set wired the lane, and citing the clock-10 MAN
diagnosis that Task 10's executed capture had already corrected — the flip's primary
decision surface, falsified twice in one diff.
**Origin:** Friedman — Council Review 2026-08-17-2120 (power-play species build,
finding 1, P1); operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-15/EC-16; `references/quality-ux.md` → P9

### EC-43: An evidence instrument enters a shared read through the SAME mechanism and a DERIVED key set
**Convention:** When an instrument (census, harness, A/B) replays a read the live lane
also runs, both enter through the same override/save-restore core, and any preset/key-set
the lane consumes as a declared dict is DERIVED by the instrument from that dict — never
re-typed. Extends EC-18 from the ruled predicate to the run harness: the census entered
the species election through `flag_capture` while the lane used `window_override`, with a
hand-typed two-key copy of the preset — three drift channels on the exact evidence the
clock ruling reads (`flag_capture` now delegates to `window_override`).
**Origin:** Fowler — Council Review 2026-08-17-2120 (finding 9);
operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-3/EC-18/EC-33; `references/refactoring.md` → P5

### EC-44: A new operator ground-truth corpus joins the sealed set in the commit that CREATES it
**Convention:** Any new hand-curated operator artifact (marks corpus, ruling record) is
added to `tools._bootstrap`'s sealed set — as a directory or an explicit file entry —
in the same commit that creates the artifact, with the EC-35 case-variant refusal test
alongside. A committed readme promising "no tool has a write path into this file" is not
enforcement: the power-play corpus (and its two docs-root siblings) sat outside the guard
while every guarded tool's `--out` could truncate them during the ruling loop that feeds
them.
**Origin:** Hunt — Council Review 2026-08-17-2120 (finding 10);
operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-7/EC-14/EC-35; `references/security.md` → P7

### EC-45: Replay arithmetic derives from the AS-OF state; a hindsight value needs a stamped divergence
**Convention:** Any instrument that dates or evaluates historical decisions ("when could
the engine first have seen this") derives every input from the state the pipeline held ON
that day — never from a frame-final value — or, where the hindsight form is deliberately
kept, stamps each affected row so downstream analysis can partition. The census dated
first-legal-looks from the hindsight-final AR (the full reaction window's argmin) while
the live walk sees the running argmin; the bias was arithmetically zero at the default
clock and opened at exactly the short clocks under study — the cross-clock comparison the
ruling reads. Extends EC-10's frozen-basis discipline from grading frames to instrument
arithmetic.
**Origin:** McKinney — Council Review 2026-08-17-2120 (finding 4);
operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-10; `references/quality-llm.md` → P3

### EC-46: Census/evidence instruments write sidecars only — never the archive
**Convention:** A research/evidence instrument (`tools/` census, harness, sheet builder)
has NO write path into `setup_archive` or any books-of-record table: its output is a
sidecar file routed through `refuse_sealed_output`, stamped with the engine manifest hash
and the exact population fingerprint it scored. Backfilling instrument output into the
archive is the "archive stays pure" red line — replay evidence rides sidecars, always.
**Origin:** species program Tasks 3/10 design, ratified at Council Review 2026-08-17-2120;
operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-9/EC-13/EC-14; the TA-grade "no backfill EVER" ruling

### EC-47: Every half of an advisory lane carries its OWN attempted-vs-populated pair
**Convention:** A measure-only lane's counter block distinguishes "never attempted" from
"attempted, none populated" SEPARATELY for each independent half the lane runs (each flag,
each provider surface) — one pair for the whole lane lets a 0-of-N silence hide on the
uncounted half, which is the exact class the counters exist to alarm on (the post-pass
shipped with fundamentals counted and the RS-line half entirely dark). Failures inside a
half print a per-item stderr line. Sharpens EC-20's "loud dedicated counter" to per-half
pairs.
**Origin:** Ramírez — Council Review 2026-08-17-2120 (finding R3, below-cap);
operator-delegated 2026-08-17
**Principle:** `conventions.md` EC-20/EC-26; `references/quality-backend.md` → P7

---

### AP-10: Declared window presets through the ONE scoped override
**Pattern:** A differently-clocked or differently-flagged read enters the engine through
`htf.window_override` with a DECLARED settings dict (`HTF_WEEKLY_WINDOWS`,
`HTF_MONTHLY_WINDOWS`, `POWER_PLAY_WINDOWS`) — never a forked collector, a hand-threaded
parameter, or a per-call setattr patch. `tools.replay.flag_capture` is a thin
validate-first wrapper delegating to the same core. Do NOT flag the setattr save/restore
mechanism as a smell, propose threading window parameters through call signatures, or
re-introduce a second save/restore core.
**Origin:** species program Task 1 §D + Council Review 2026-08-17-2120 (finding 9's fold);
operator-delegated 2026-08-17
**Rationale:** The detectors read settings lazily at call time by design (the cwd-shadowing
constraint, AP-3); one scoped override is the only mechanism that moves every consulting
site coherently, and the declared dict is what keeps multi-name clocks (the import-time
copy trap) moving together.

### EC-48: A correction to a ruled mechanism lands whole — fix + re-derived evidence + trued rulings in ONE change
**Convention:** A CORRECTION (a change making an existing ruled mechanism compute what its ruling
already says it should — a bug fix, an as-of repair, an EC-45 violation) is never parked as a
branch: it lands in ONE change carrying (1) the fix with a regression battery pinning the corrected
behavior, (2) re-derivation of every evidence artifact the affected rulings cite (old headline vs
new headline stated side by side), (3) EC-15 true-up of every ruling row and program-doc claim the
re-derivation touches, and (4) a decisions.md "evidence re-derivation" row. **The presumption of
continuity:** the ruling STANDS by default; the operator re-rules BEFORE merge only when the
re-derived evidence crosses the ruling's own recorded acceptance condition. A correction lands or
dies within seven days of its confirming review — "proposal branch" is abolished as a resting
state. Distinct from a NEW LEVER (which changes what the engine believes and keeps the full EC-8
A/B road).
**Origin:** Friedman / McKinney — Council Review 2026-08-22-2250 (the first_legal_look fix parked
as `proposal/first-legal-look-fix` because no lane existed for its case); operator-delegated
2026-08-22 ("Take the lead on this one, if you think its good then push and flip")
**Principle:** `conventions.md` EC-15/EC-45; `references/quality-ux.md` → P9

### EC-49: A live-only cost bound is measured by ONE named trial scan with pre-agreed revert
**Convention:** When EC-8's pre-flip cost bound cannot be measured while a lane is dark (the cost
instrument only reports with the flag on), the bound is obtained by a TRIAL FLIP: one named nightly
scan with the flag on, the cost recorded to a committed sidecar, and one-word revert semantics
agreed in the flag-ledger row beforehand. Codifies the species preset's ad-hoc exception
(2026-08-19) so each future lane stops re-negotiating it or stalling dark on an unmeetable gate
(the trace-export flag's state since 2026-08-04).
**Origin:** Friedman — Council Review 2026-08-22-2250 (finding 10: the chicken-and-egg documented
twice, codified nowhere); operator-delegated 2026-08-22
**Principle:** `conventions.md` EC-8

### EC-50: Parked work and open questions exist only WITH a register/queue row in the same change
**Convention:** A park is legal only when the same change lands its `docs/pattern_register.md` row
(owner-or-kill-by); an open question owed to the operator lands its `docs/asks.md` line in the
change that creates it; a ruling received in chat lands its decisions.md row AND closes its ask row
in the same session. A branch, stash, or question older than its row's kill-by is a red condition,
not a parking space — the flag ledger's "flipped, deleted, or re-dated with a written reason, never
silently carried" applied to everything parked.
**Origin:** Friedman / Hunt — Council Review 2026-08-22-2250 (findings 4/7/12: the three
first_legal_look questions lived only in an unmerged branch's commit message; a chat ruling took
three weeks of forensics to reconstruct; a park named an owner that does not exist);
operator-delegated 2026-08-22
**Principle:** `conventions.md` EC-15/EC-16/EC-42

### EC-51: A baseline is captured at the SAME tree the seam commit carries
**Convention:** A commit that rotates a declared epoch (`engine_config_version`, a manifest hash, any
sealed stamp) recaptures **in that same commit** every baseline whose stamp it invalidates. A capture
taken at one tree and committed at another is not a baseline — its provenance stamp names a tree that
was never committed, so every intermediate commit reports a drift that never happened and a bisect
through the seam lands on the wrong culprit. If a capture must be taken early, the seam commit
re-takes it before landing; the recapture's diff is stated in the commit message.
**Origin:** Beck — Council Review 2026-08-30 (finding 5: the reader-pin baseline was stamped with the
pre-rotation epoch and carried a bisect artifact); operator-delegated 2026-08-31
**Principle:** `conventions.md` EC-29 — EC-29 rules WHEN a recapture is permitted; this rules that the
recapture and the seam ship as one commit.

### EC-52: A writer that feeds a seal pins its line terminator explicitly
**Convention:** Every tool writing a sealed, pinned or hashed artifact passes an explicit
`newline="\n"` (or its library equivalent), and any digest computed over serialized text pins the
terminator in the same function. Never rely on the platform default, and never lean on a
`.gitattributes` rule to normalize afterwards — the bytes are hashed before git ever sees them.
**Origin:** Hunt — Council Review 2026-08-30 (P3 sweep, folded into finding 5's fix: the pin captures
wrote CRLF against an LF `.gitattributes` pin); operator-delegated 2026-08-31
**Rationale:** Second sighting of one defect class. On 2026-08-25 `frame_digest` sealed the OPERATING
SYSTEM — `to_csv` defaults `lineterminator` to `os.linesep`, so identical frames hashed differently on
Windows and Linux and CI could never pass off-Windows (decisions.md 2026-08-25). A platform default
inside a seal is a portability bug that is invisible on the platform that wrote it.

### EC-53: Cited evidence is tracked in the change that cites it — force-added if ignored
**Convention:** When a ledger row, ruling or decision record cites an evidence file, that file becomes
**tracked in the same change** — including `git add -f` when it lives under a broad ignore rule (an
`output/` sidecar, a `*.parquet` fixture). Because `decisions.md` is append-only, a rotted pointer can
never be repaired by editing the row: the evidence must come to the pointer, not the reverse.
**Origin:** Friedman — Council Review 2026-08-30 (finding 2: three census sidecars cited by ruling rows
existed only in the author's worktree); operator-delegated 2026-08-31
**Principle:** `conventions.md` EC-16 — this names the mechanism EC-16 needs when the evidence path is
ignored by default.

### EC-54: A rescue lane's admission legs fail CLOSED on missing input
**Convention:** When a default-off lane opens a door that a standing rule keeps shut, every leg of its
admission test refuses on missing or non-finite input — a NaN moving average, an absent history
window, a frame too short to compute the leg. The guard is written as *affirmatively qualified*
(`admits = finite(x) and x >= floor`), never as *not disqualified*, and the refusal carries a named
reason so a census can count it.
**Origin:** McKinney — Council Review 2026-08-30 (sweep item 15: the bottoming-base lane's seeding half
admitted a NaN-`sma200` frame); operator-delegated 2026-08-31
**Rationale:** A rescue lane exists to admit charts the base rule refuses, which is precisely the code
path where fail-open is invisible — it admits more, and admitting more is what the lane is *for*.

### EC-55: A closed set asserts at its stamping point, not only at the column
**Convention:** A closed-set label gets its write-time assertion in the **producing module, beside the
tuple that declares the set** — not only in the archive column's CHECK. The CHECK is the last line of
defence and fires at commit time, far from the code that minted the value; the producer's assertion
names the offending value at the moment it is invented, in the stack frame that invented it.
**Origin:** Leach — Council Review 2026-08-30 (finding 11: `inner_position` reached the archive CHECK
with no assertion at the `select_inner_box` stamping point); operator-delegated 2026-08-31
**Principle:** `conventions.md` EC-19/EC-22/EC-33 — those three assume a stamping point exists; this
requires it.

### EC-56: The same-app guard is DEFAULT-ON at the middleware, with no exemption list
**Convention:** Cross-origin containment has two layers. `require_same_app` stays the opt-in header
guard a route declares. Underneath it, `middleware/same_app.SameAppOriginGuard` runs for **every**
request and refuses anything a browser attests came from another page (`Sec-Fetch-Site` / `Origin`,
which page JS cannot forge). Do NOT add a per-path exemption to that middleware, and do NOT reach for
the header dependency as the *only* protection on a new route — `EventSource` cannot send a header,
so an SSE route can never carry it. A new mutating or streaming route is guarded the moment it is
registered; `tests/test_service_boot.py` walks every registered route and proves it.
**Origin:** Hunt × Ramírez — Council Review 2026-09-07 (finding 3: the opt-in guard had reached 15 of
85 routes; 28 mutating or streaming routes were open, including all four IBKR control routes)
**Rationale:** An opt-in guard is only ever on the routes someone remembered, and the one it could
never reach was the most expensive endpoint in the app. Default-on has no rot surface; an exemption
list is that rot surface reintroduced.

---

### AP-11: The species story-form dark lane is the protocol working — not a version smell
**Pattern:** `POWER_PLAY_STORY_FORM_ENABLED` sits dark with banked EGBN/PKE acceptance evidence
while its graduation into the paying read waits for its own A/B program (Pattern Register row 5).
Do NOT flag the dark flag, the scoped species election, or the two named ruled forms consulted in
priority order as parallel versions or EC-3 twins: McKinney's census verified ONE admission seam,
ONE implementation per ruled form (EC-18), the O(1) prefilter deriving from the same predicates,
and a test pinning the paying read's blindness to the form by name.
**Origin:** McKinney — Council Review 2026-08-22-2250 (finding 4); operator-delegated 2026-08-22
**Rationale:** The refused flip (a3397a5) removed a graduation, not code; measure-first dark lanes
with banked evidence are the intake design's normal state, not debt.

### AP-12: The archive serializers speak both verdict vocabularies forever
**Pattern:** `SetupOut`, the watchlist snapshot readers, and the concordance surface serve BOTH the
legacy `score`/`tier` family and the `ta_grade` family, and the live writers keep stamping
`score` (NOT NULL model contract; computationally free) after the 2026-08-23 legacy-path
retirement. Do NOT propose removing the legacy columns/fields from archive-facing serializers or
writers: pre-flip rows are NULL-graded forever (no backfill EVER), so the books of record must
speak both vocabularies for the life of the archive; `min_score` keeps raw-sum semantics forever
beside `min_ta_grade` (two filters over two populations, ruled).
**Origin:** Ramírez / Leach — Council Review 2026-08-22-2250 (the wire map + the archive ruling);
operator-delegated 2026-08-22
**Rationale:** Display retired; history did not. The one system READS with one verdict and
REMEMBERS with both.

### AP-13: A daily-clock ruling is scoped by pinning its flag in the window presets
**Pattern:** A lane ruled on the daily clock is bounded by pinning its flag `False` inside
`HTF_WEEKLY_WINDOWS` / `HTF_MONTHLY_WINDOWS` — the declared window presets, i.e. AP-10's one scoped
override — rather than by inventing rescaled thresholds for clocks the operator never ruled on. Do
NOT flag those `False` entries as dead config, as a missing weekly implementation, or as duplication
of the settings default: they ARE the ruling's boundary, written where the override mechanism already
lives. `BOTTOMING_BASE_LANE_ENABLED` is the first instance.
**Origin:** McKinney — Council Review 2026-08-30 (finding 13's fix: the bottoming-base lane's 50-day
reclaim is a daily-bar ruling); operator-delegated 2026-08-31
**Rationale:** The alternative is worse in both directions — letting a daily-calibrated rescue run on
weekly bars silently invents an unruled threshold, and hard-coding a weekly variant invents a second
one. A preset pin says "not ruled here" in the only place that can enforce it.
