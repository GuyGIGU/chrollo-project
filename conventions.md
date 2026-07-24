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

### EC-14: Every tool write passes the sealed-output guard
**Convention:** Any file a `tools/` script writes from a user-supplied path (`--json`, `--out`, …)
must be routed through `tools._bootstrap.refuse_sealed_output` BEFORE the file is opened — a
mistyped path must fail loudly, never truncate a sealed spec (`docs/marks/`) or a frozen baseline
(`tests/baselines/`) in place.
**Origin:** Hunt — Council Review 2026-07-24-1903 (engine/gap-breach); operator-confirmed 2026-07-25
**Principle:** `references/security.md` → P7 (deploy assertions as tripwires); `conventions.md` EC-3
