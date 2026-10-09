# Project Conventions

Accepted patterns and enforced conventions from council reviews. The council reads this file before every
review to avoid re-flagging resolved decisions.

Each entry's full original text (origin, reasoning, examples) is kept verbatim under its ID in
[conventions-archive.md](conventions-archive.md) (not read by runs). "(merged from X)" marks a rule folded into a related entry.

## Accepted Patterns

These are intentional — do not flag as findings.

### AP-1: `us_stocks` key vs `us_equities` universe_type split
**Pattern:** The default universe's `key` is `us_stocks` (API/cache token) while its archive `universe_type` is `us_equities`. Do NOT propose migrating the archive tag to match the key; the split lives only inside `universe/descriptor.py` (EC-1).

### AP-2: `fetch_data` cold/incremental/repair state machine
**Pattern:** `core/pipeline/market_data/downloads.py` `fetch_data` is a lock→scope→fresh?→current?→incremental?→cold sequence of named `_try_*`/`_*_result` helpers. Do NOT "simplify" or split it further.

### AP-3: Per-call `Universe` registry build + lazy settings reads
**Pattern:** `core/pipeline/universe/descriptor.py` rebuilds the registry per call and reads settings at call time. Do NOT hoist the registry to module level.

### AP-4: `yfinance==1.2.1` exact pin
**Pattern:** `requirements.txt` pins yfinance to an exact `==1.2.1` — upgraded only deliberately. Never bump it as a "stale dependency" finding.

### AP-5: The price-independent fill ledger is a necessary JS↔Python twin
**Pattern:** `summarizeFillLedger` (and the price-independent half of `deriveTradeRow`) stays in `tradeTableUtils.js` beside its port in `domains/trading/risk.py`, because the JS copy backs a WRITE path. Do NOT flag it as an EC-3 twin; `tests/contracts/test_trade_risk.py` pins parity.

### AP-6: `_js_number(None) == 0.0` in `domains/trading/risk.py` is intentional
**Pattern:** `None`→`0.0` mirrors JS `Number(null)`, and the router always materializes `entry_price` present-as-None, so the code matches JS on every reachable input. Do NOT "fix" `infer_direction` to treat `None` as not-knowable.

### AP-7: The eq_* archive columns' hand-listing is a family-contiguity exception
**Pattern:** `eq_engagement_respect_frac` / `eq_max_excursion_atr` are hand-listed in `_MIGRATIONS` and `_NEW_COLUMNS` ONLY to keep the eq_* family contiguous. Do NOT flag this as triple registration, and do NOT grow the hand lists: new archive columns are MODEL-ONLY registration.

### AP-8: The story-admission read and the archive substrate read are DIFFERENT bases — by design
**Pattern:** Story admission is judged on the CANDIDATE window + candidate ATR; the archived `event_map_*` substrate on the ELECTED window + zone ATR. They may legally disagree (the admitting evidence rides `story_admission_profile`). Do NOT propose unifying the two reads or treat the substrate as the admission record.

### AP-9: `can_archive=False` is THE archive block — the evaluate/archive split is load-bearing
**Pattern:** `session_lag` splits `can_evaluate=True` from `can_archive=False`; `can_archive` is the archive path's ONLY gate (pinned by `tests/backend/test_archive_reliability.py`). Do NOT merge the pair into one boolean or add a second, parallel archive gate. Readers key on `can_evaluate`; anything that PERSISTS keys on `can_archive`.

### AP-10: Declared window presets through the ONE scoped override
**Pattern:** A differently-clocked or -flagged read enters via `htf.window_override` with a DECLARED settings dict (`HTF_WEEKLY_WINDOWS`, `HTF_MONTHLY_WINDOWS`); `replay.flag_capture` delegates to it. Do NOT flag the setattr save/restore, thread window parameters through signatures, or add a second core. (merged from AP-13) Pinning a daily-clock lane's flag `False` in those presets (first: `BOTTOMING_BASE_LANE_ENABLED`) is the ruling's boundary — not dead config, a missing weekly version or duplication.

### AP-11: The species story-form dark lane is the protocol working — not a version smell
**Pattern:** `POWER_PLAY_STORY_FORM_ENABLED` sits dark with banked EGBN/PKE evidence until its own A/B (Pattern Register row 5). Do NOT flag the dark flag, its scoped use by the contraction rescue lane (`CONTRACTION_RESCUE_ENABLED`, its only consumer since the species lane was deleted 2026-09-19), or the two ruled forms consulted in priority order as parallel versions or EC-3 twins.

### AP-12: The archive serializers speak both verdict vocabularies forever
**Pattern:** `SetupOut`, the watchlist snapshot readers and the concordance surface serve BOTH the legacy `score`/`tier` family and `ta_grade`, and live writers keep stamping `score`. Do NOT propose removing the legacy fields from archive-facing serializers or writers (no backfill EVER); `min_score` keeps raw-sum semantics beside `min_ta_grade`.

## Enforced Conventions

These must be followed — flag violations as findings.

### EC-1: One source for the equities-default scope
**Convention:** A universe-scoped archive read that defaults to the equities population derives that default from `core.pipeline.universe.DEFAULT_UNIVERSE_TYPE` (or `default_universe().universe_type`) — never a re-typed `"us_equities"` literal.

### EC-2: NaN-coerce archive cells at the pandas boundary
**Convention:** Coerce possibly-missing cells of pandas-read archive rows with `pd.isna(...)` (or `is None`), NEVER a truthiness test — `bool(np.nan)` is `True`.

### EC-3: Fold twin code paths, never copy
**Convention:** Logic that must agree across call sites (eval-twins, `_weekly_refresh_due`, depth/coverage/scope predicates) lives in ONE shared implementation both sites import. (merged from EC-39) A batched route resolves each item through its single-item route's SAME function (batching groups reads, never re-walks), with the same resolution parameters (the EC-37 pin).

### EC-4: A widened identity key must be threaded through EVERY writer
**Convention:** A widened archive identity key (e.g. `universe_type`) is stamped AND included in the existence/upsert check by every writer — live screener, seed, forward-returns/manual. (merged from EC-30) A column family's producer (the `*_archive_values` splats) reaches EVERY writer in the same change, and the guard suite asserts it PER WRITER.

### EC-5: Live open-trade risk is derived once, server-side
**Convention:** The price-dependent live-risk overlay (price, unrealized P&L, R-multiple, stop distance/tone, targets) is derived ONLY in `domains/trading/risk.py`, read via `riskFor` — never in JS. 1R anchors to `planned_stop`→`stop_loss`→None (never fabricated); stop distance and tone use the CURRENT `stop_loss`.

### EC-6: `/live-risk` degrades, never 500s
**Convention:** `GET /live-risk/` degrades to null-price rows on any operational failure (logged): tolerant `actions_json` parsing, price coerced at the boundary, only the EXISTING IBKR snapshot, DB read released before the price fetch. Programmer errors still surface.

### EC-7: A failing case is fixed in the ENGINE, never by editing the mark
**Convention:** `docs/marks/` is operator ground truth. A failing corpus case is fixed in the ENGINE — never by editing a mark, widening a matcher's date window or reinterpreting trigger rules. Harnesses fail loudly on malformed marks, never skip. He may redraw a chart (EC-9); an agent never edits a mark to make a test pass.

### EC-8: Every new engine flag ships with the full flag protocol in one change
**Convention:** A new engine flag lands in ONE change with: registration in `engine_alpha/freeze/manifest.py` and `docs/flag_ledger.md`, a unit inert test, a flag-off frozen-fixture replay equal to the shadow baseline, and an agreed cost bound measured before the flip. Flag-off is byte-identical and compute-free. (merged from EC-49) A bound measurable only with the flag on comes from ONE named trial-flip scan (cost in a committed sidecar, revert agreed in the ledger row first).

### EC-9: The population follows the operator; the VERDICTS are what stay pinned
**Convention:** The `calibration_marks` DB (operator-owned, editable) is THE population; `docs/marks/` is its regenerated projection, and `marks_corpus --check` FAILS on a mismatch with a live DB (no DB is not drift). A verdict is pinned to one drawing (`setup_digest`): unchanged → a hit that stops firing or a miss that starts FAILS; redrawn or new → re-measured, unreadable ones enter as `NEW_MARK_STAGE`, pinned and reported for his review; deleted → it leaves with its `STAGE_TAGS` excuse. Reports stamp population and fingerprint; no tool writes the calibration DB.

### EC-10: The forward grading frame's post-as_of bars are DEADLINES, never engine inputs
**Convention:** Trigger grading uses a second frozen basis (`freeze_grading_frame`/`load_grading_frame`) through `frame_end`, bound to `base_digest` (its `<= as_of` slice MUST reproduce it, else ungraded). Its forward bars only locate the fire date; the reading engine sees only `<= as_of`. (merged from EC-45) Any instrument that dates or evaluates historical decisions derives every input from the pipeline's state ON that day, never a frame-final value, or stamps each row where hindsight is deliberately kept.

### EC-11: The Trigger is structurally coupled to the LPS
**Convention:** A Trigger is valid ONLY with ≥1 LPS event and `trigger_date` strictly after the last LPS bar (before, on or after `as_of`). The assisted tool snaps to the last LPS bar's high and first breakout bar, is inert without an LPS and re-derives on redraw; `trigger_price` is not hard-pinned. One judgment: `marks_validity._validate_trigger`; no DDL CHECK may contradict it.

### EC-12: A committed replay basis must be content-verified at check time
**Convention:** An artifact carrying a replay basis (the marks-corpus fixture parquet) is verified where consumed: the gate recomputes each graduated frame's content digest against the sealed `frame_digest`, and pytest pins each frame's bar count.

### EC-13: Marks-consuming instruments use the ONE validated loader and stamp the exact set scored
**Convention:** Marks load only via `calibration_harness.load_marks`/`load_box_marks` (a malformed row aborts, named); reports stamp population, the fingerprint of EXACTLY the marks scored, and the manifest hash. Never re-implement mark loading, `replay.session_pos` or `replay.enrich_marked_frame`.

### EC-14: Every tool write passes the sealed-output guard
**Convention:** A `tools/` write to a user-supplied path (`--json`, `--out`) passes `tools._bootstrap.refuse_sealed_output` BEFORE the file opens — never truncating `docs/marks/` or `tests/baselines/`. (merged from EC-35) This and any path allow/deny check normalize BOTH sides with `os.path.normcase` + `os.path.realpath` first. (merged from EC-44) A new operator ground-truth artifact joins the sealed set in the commit that creates it, with a case-variant refusal test.

### EC-15: An executed gating A/B replaces its pre-registration in the decision record — in the same change
**Convention:** When a pre-registered A/B is EXECUTED, every surface citing it (the flag-ledger row first) records the outcome, failed expectations included, and what stays open — in the SAME change. (merged from EC-42) A multi-task change re-verifies earlier tasks' ledger rows, doc claims and forward promises against the later tasks before it is offered for commit.

### EC-16: Evidence cited by ledger rows and rulings lives in committed paths
**Convention:** Evidence cited by ledger rows, rulings and decision docs resolves inside the repo (`docs/`), never in `.council/` or root `PLAN-*.md`; local captures are distilled into a committed record first. (merged from EC-53) A cited file is tracked in the same change, `git add -f` if ignored (`decisions.md` is append-only).

### EC-17: A dark flag's happy path is pinned through the REAL cascade before its flip decision
**Convention:** Before its flip is decided, every dark flag has ≥1 committed test driving its ACCEPTANCE path through the real code (production values for other flags, only it forced on), asserting the outcome end to end; isolated or monkeypatched tests do not count. (merged from EC-32) It holds ≥1 assertion derived from the row's OWN inputs, its teeth proven once by a mutation probe.

### EC-18: A ruled judgment predicate has exactly ONE implementation
**Convention:** An operator-ruled judgment is ONE engine function; instruments scoring "the ruled form" delegate to it or pin equivalence against it — never a re-typed twin. (merged from EC-43) An instrument replaying a live-lane read enters through the same override core and DERIVES any preset/key-set from the lane's declared dict.

### EC-19: Closed-set archive label columns get the universe_type treatment
**Convention:** A closed-set label column (`elected_pool`, …) gets a model CHECK, a write-time assertion at its stamping point (e.g. `bricks._pool_label`) and a test that an illegal label cannot land. (merged from EC-22) Each LEGAL value has a committed test in which the real producer emits it, or the vocabulary is narrowed. (merged from EC-55) The assertion sits in the producing module beside the tuple declaring the set, not only in the CHECK.

### EC-20: A telemetry lane never widens the blast radius of the path it observes
**Convention:** Measure-only passengers (telemetry, probes, shadow reads) are contained at EVERY layer: per-item degrade plus a loud dedicated counter, operational-error coverage over their whole DB span, the paying artifact first; programmer errors still surface. (merged from EC-21) On a shared books-of-record job the passenger gets its own narrow logged catch; the run's status reflects the paying customer only, and its failure prints distinctly. (merged from EC-47) Counters separate "never attempted" from "attempted, none populated" for each independent half; per-item failures print to stderr.

### EC-23: Columns forming one fact are written as one unit in every branch
**Convention:** When two columns state one fact (triggered/trigger_date; any value+date or value+source pair), every branch that writes one writes both — the value on the affirmative branch, NULL on the negative.

### EC-24: A staleness budget counts only sessions the provider could have supplied
**Convention:** Staleness arithmetic that bounds a tolerance (session lag, retry budgets) discounts sessions PROVEN absent upstream (the `absent_sessions` ledger).

### EC-25: Cooldowns are keyed on the thing they describe, never on the wall clock
**Convention:** A "don't retry what we learned" guard is keyed to the FACT it records (the absent session, the unchanged symbol set), never to elapsed time; a new fact (a completed session, an operator Refresh) gets a fresh attempt.

### EC-26: Published payload fields are derived at the publisher, never echoed defaults
**Convention:** A health/status payload field is computed where it is published (or by a caller that provably computed it), never taken from a parameter default most call sites leave unset.

### EC-27: A conjunctive guard's tests must assert WHICH condition refused
**Convention:** Tests of a guard `A and B and C` show WHICH leg refused (a distinct sentinel, counter or message per leg). (merged from EC-34) A declarative rule engine gets one PRESENT, FINITE, wrong-side case per rule KIND (just-under, at-threshold, wrong-label, falsy) asserting the id ABSENT.

### EC-28: The wire carries verdicts, never rules
**Convention:** No scoring cap, threshold, fire-rule or chapter-membership is re-declared in frontend JS; judgments cross the wire resolved and the frontend keeps presentational lookups only. A missing number is a backend serialization addition, never a client computation.

### EC-29: Baselines recapture only at a flip/seam commit
**Convention:** Shadow-pipeline, seed-recall, marks-corpus and fold-parity baselines are recaptured ONLY in an explicit flip/seam task with committed evidence; a recapture in any other diff is rejected as masking a regression. (merged from EC-51) A commit that rotates a declared epoch recaptures, in that same commit, every baseline whose stamp it invalidates (an early capture is re-taken; its diff goes in the commit message).

### EC-31: A bug-tripwire asserts the operand the pipeline guarantees, and speaks on every output mode
**Convention:** A "this is a BUG" check compares the quantity the pipeline promises invariant, never a transform that may legitimately reorder, and its verdict prints on EVERY output mode, `--json` included.

### EC-33: Reserved vocabularies are derived from ONE tuple; flag-off leak checks derive from the archive extraction
**Convention:** A settled vocabulary lives in one registry tuple that every consumer derives from. A flag's OFF-state leak check asserts through the writers' own extraction (`*_archive_values(...)` all-None on the gated subset), not a prefix filter.

### EC-36: Operator playbooks are executable from the doc alone
**Convention:** A committed playbook names the exact interpreter once at the top and gives every step a copy-runnable committed command; every pointer and instrument resolves in the repo; signals are promised as they really light.

### EC-37: A stored pin is copied verbatim from the displayed artifact's identity — never clock-derived
**Convention:** A UI action persisting what the operator was looking at (a watchlist pin) copies identity VERBATIM from the displayed payload, never recomputed from a clock. Timestamps are for display/audit, never a join or grouping key.

### EC-38: A chart surface renders ONE artifact — overlay fields and candles never cross sources
**Convention:** Engine-read overlays (rails, LPS spans, structure coloring, boxes) render only on the candles shipped in the SAME artifact — the scan row wholesale, or nothing; fresh-cache candles are a CLEAN chart (`resolvePaneData`/`cardPlan` are the reference).

### EC-40: Every asked-for item gets a recorded outcome, and retry copy is wired
**Convention:** A client batch handler stamps a terminal cell for EVERY name it asked about, echoed or not, in the same merge; an unanswered name never re-joins the fetch plan. Error entries have a real retry trigger, and copy naming a recovery gesture is backed by code that re-issues the request.

### EC-41: Client caches of server artifacts serve-stale-then-revalidate, keyed by generation
**Convention:** A client cache of a server artifact serves ready entries while revalidating in the background (mount, selection); its key holds every parameter the value derives from; arrival compares a GENERATION stamp and keeps the old reference when nothing moved, replacing it on a real change.

### EC-46: Census/evidence instruments write sidecars only — never the archive
**Convention:** A research/evidence instrument never writes `setup_archive` or any books-of-record table; its output is a sidecar through `refuse_sealed_output`, stamped with the manifest hash and population fingerprint.

### EC-48: A correction to a ruled mechanism lands whole — fix + re-derived evidence + trued rulings in ONE change
**Convention:** A CORRECTION (a ruled mechanism made to compute what its ruling says) is never parked: ONE change carries the fix + regression battery, re-derived cited evidence (old vs new headline), the EC-15 true-up and a decisions.md "evidence re-derivation" row. The ruling STANDS unless the evidence crosses its recorded acceptance condition (then he re-rules before merge); it lands or dies within seven days of its confirming review. A NEW LEVER keeps the EC-8 A/B road.

### EC-50: Parked work and open questions exist only WITH a register/queue row in the same change
**Convention:** A park lands its `docs/pattern_register.md` row (owner-or-kill-by) in the same change; a question for the operator lands its `docs/asks.md` line; a chat ruling lands its decisions.md row and closes its ask in the same session. Past kill-by is a red condition.

### EC-52: A writer that feeds a seal pins its line terminator explicitly
**Convention:** A tool writing a sealed, pinned or hashed artifact passes an explicit `newline="\n"` (or equivalent), and a text digest pins the terminator in the same function — never the platform default or `.gitattributes`.

### EC-54: A rescue lane's admission legs fail CLOSED on missing input
**Convention:** When a default-off lane opens a door a standing rule keeps shut, every admission leg refuses missing or non-finite input — written as `admits = finite(x) and x >= floor`, never as not-disqualified — with a named, countable refusal reason.

### EC-56: The same-app guard is DEFAULT-ON at the middleware, with no PATH exemption
**Convention:** `middleware/same_app.SameAppOriginGuard` checks EVERY request (`Sec-Fetch-Site`/`Origin`); `require_same_app` stays opt-in. No per-path exemption and never the header guard alone (`EventSource` cannot send it); the one carve-out is method-keyed (CORS `OPTIONS`); `tests/backend/test_service_boot.py` proves every route. Never hand the browser a cross-origin subresource URL: serve it relative via the `vite.config.js` proxy; never trust `same-site`.

### EC-57: Assert on sealed bases; disclose live drift as a ruling row
**Convention:** Gates ASSERT only on sealed bases (marks ratchet, shadow fixture, junk corpus, reader pin). Live or fleet drift is never asserted and never silently passed: it is DISCLOSED in a dated sidecar with its population fingerprint, as a ruling row for the operator — it may block a ruling, never a build.

### EC-58: A page the operator approves from states every choice it rests on and what it measured
**Convention:** An approval page (the approval pack and anything like it) lists every OURS default and every recorded-but-unbuilt ruling it rests on, each with its docs/decisions.md row date, and stamps the drawings' fingerprint and the engine version it measured; a part pasted in from another run (a night file) is refused or flagged when its stamp differs.
**Scope:** tools/calibration/approval_pack.py, aronson, patterson
**Origin:** Council review 2026-10-09 of the two-eyes reader branch (.council/reviews/2026-10-09-two-eyes-reader-branch.md, findings 4 and 7)
**Anchor:** tools/calibration/approval_pack.py
**Approved:** 2026-10-09 — the user said: "yes to both, then fix them all"

## Observed Failures (F) — historical evidence, never a rule

### F-1: A memory consolidation changed three rules while shortening them
**Failure:** The 2026-09-29 trim of this file reworded every rule to one line, and three came out saying something different from what was ruled: EC-50 ("owner-or-kill-by" became "owner, kill-by"), EC-48 (the seven-day deadline lost "of its confirming review") and EC-45 ("dates or evaluates" became "dating"). The author's own read of all 70 originals passed them; a second, blind reader caught them. Restored 2026-09-30.
**Scope:** conventions.md, conventions-archive.md
**Origin:** Council review 2026-09-30 of commit 2e70c79 (.council/reviews/2026-09-30-memory-trim.md)
**Evidence:** .council/runs/2026-09-30-131416-review/verify-1.md:8
**Verdict:** CONFIRMED
**Anchor:** conventions.md
**Approved:** 2026-09-30 — the user said: "yes to both, fix all four"

### F-2: A "the old night never loads the new reader" guard that only imported modules missed a run-time import
**Failure:** The two-eyes branch kept the new reader out of the old nightly scan's imports, and its leak guard checked only what loads at import. The engine version stamp imported `engine_alpha.two_eyes.method_numbers` inside `collect_manifest`, which ran the package door and loaded all 14 stage modules on every night with the switch off; the guard stayed green. Future check: a leak guard also CALLS the nightly entry points (the version stamp), not just imports them.
**Scope:** engine_alpha/freeze/manifest.py, tests/archive/test_archive_second_reader.py
**Origin:** Council review 2026-10-09 of the two-eyes reader branch (.council/reviews/2026-10-09-two-eyes-reader-branch.md, finding 1)
**Evidence:** .council/runs/2026-10-09-193545-review/verify-1.md:5
**Verdict:** CONFIRMED
**Anchor:** engine_alpha/freeze/manifest.py
**Approved:** 2026-10-09 — the user said: "yes to both, then fix them all"

## Proposed

## Rejected
- "A basis change is a migration" · 2026-09-01 · declined when EC-57 was ruled in; basis changes stay a case-by-case judgment and no convention binds them.
