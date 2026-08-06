# Backlog — started-but-unfinished work (survey 2026-07-21)

Living checklist of work that **was started and then stalled/forgotten**, produced by a full
sweep of every unmerged branch, the PLAN/spec docs, the tracking docs (flag ledger, quality
doctrine, knob audit), the council outputs, and auto-memory. Every candidate was cross-checked
against `origin/main` (`merge-base` + `git grep`), so anything quietly completed or renamed was
filtered out — see [False alarms](#false-alarms-verified-not-open) at the bottom.

Excludes: work already merged, work actively in progress, and forward-roadmap items never started.

Ranked most-worth-resuming first. Tick items as they land or are formally killed.

---

## 1 · Built, tested, then left unmerged (the forgotten heavyweights)

All are stale-based and will **not** merge clean — each needs a re-port onto today's `main`.

- [ ] **Signal-edge backtest framework** — `wip/signal-edge-backtest` (ca8863a, last touched 2026-07-13; 1 ahead / 182 behind).
  Deflated-Sharpe + event-study + exit-sim modules, a 247-line DSR/CAR harness, **92 tests**, and the 2026-07-07 edge read. Commit body literally says *"parked."* Its one flagged analytical gap (a null model) has since shipped on `main` (`core/backtest/null_model.py`), so the blocker is cleared.
  **Next:** review the 3 core modules → rebase (conflicts on `tools/backtest_engine.py`) → rewire to consume `null_model.py` → merge or formally discard.
- [ ] **TA Score v2 — the 0-100 Technical Analysis Score** — `engine/ta-score-v2` (tip 47d6ade, 2026-07-02; 2 ahead / 224 behind).
  The locked-design "ONE visual grade" rework; ~2 of ~11 phases built. **Stranded on the pre-extraction layout** (edits `core/scoring/` which is now `engine_alpha/scoring/`). Design specs are on `main` (`specs/ta-score-*.md`).
  **Next:** rebuild from a fresh branch off `main`; finish P1/P3/P3.5 tag-folds, tier-invariance tests (P4), `TIER_*_STRUCT` recalibration (P5), A/B harness (P6), FE single-source cutover (P6.5), then an operator A/B-eyeball flip.
- [ ] **Council P2 follow-up fixes** — `worktree-council-p2-followups` (20fe178, 2026-06-30; pushed, never merged; 1 ahead / 253 behind).
  Bundles 6 "Fix Soon" findings + pinning tests. **Two are confirmed still-live defects on `main`:**
  - ⚠️ `webapp/frontend/src/hooks/useDrilldown.js:41` re-sets `mountedRef.current = true` in the render body → the unmount cleanup guard is defeated.
  - ⚠️ ScreenerGrid keeps a **stale tier/search filter when the universe switches** (`resetFilters` clears only setup/tag/sort/page).
  Also #5 archive episode-cache scoped by `universe_type`, #6 `data_freshness` per-symbol `.loc` vectorization, #4 fold the two `_weekly_refresh_due` copies. **Skip #3** (split-probe inf — already superseded on `main` by `98a23ac`).
  **Next:** cherry-pick #4–#8 onto `main`, re-test, council-review, merge.
- [ ] **Server-side stop/target alert sweep** — `codex/backend-hardening` (d46c96f, 2026-06-23; 1 ahead / **331 behind**).
  Trade-Lifecycle Layer-C: live-quote sweep firing stop/target proximity + breach alerts via webhook, scheduler-wired behind `TRADE_ALERTS_ENABLED`, market-hours gated, with tests. All target files verified **absent** from `main`. **Only this slice is salvageable** — the rest of the branch (edge-report tool, generic backend guards) is superseded.
  **Next:** re-port `services/trade_alerts.py` + `live_quotes.py` + `notify.py` + the scheduler job onto `main`'s current `trade_risk.py`; bring the 4 tests forward; flip `TRADE_ALERTS_ENABLED` only after operator review. Depends on the §6 webhook (below).
- [ ] **Last Supper definition + event-geometry doc** — `docs/last-supper-definition` (d9e4e2d, 2026-07-14; 1 ahead / 98 behind).
  Three over-extension measures are **live in `main` code but undocumented** — a standing violation of the "update `strategy_alpha.md` in the same change" rule. Pure doc catch-up; the branch targets the pre-rename `strategy_v2.md`, so it must be re-applied by hand onto `strategy_alpha.md`. **No code change.**

## 2 · Owed follow-ups on features already live (small, quality/safety)

- [x] **Cause-before-effect veto regression net** (PLAN Tasks 9–11) — **SHIPPED 2026-07-21** (uncommitted on `engine/solve-the-engine`; tools/tests + one backend chip, engine byte-identical, no manifest rotation):
  - [x] Task 9: MIDD bidirectional bite-proof — `tools/cause_veto_corpus.py` + `tests/baselines/cause_veto_corpus.parquet` + `tests/test_cause_veto_bite.py` (veto ON rejects / OFF fires @ MIDD 2026-07-17; 6/6 green).
  - [x] Task 10a: `tools/doctrine_audit.py` refusal-seam — a `cause_absent` veto-drop reads from the engine's own trace as an expected non-election, not a coverage hole (fixed the gate going red on the pre-load payload: 13 refusals → 6 vetoed + 7 stale-payload holes that clear on a fresh scan).
  - [x] Task 11: `vetoed_cause_absent` in `tools/agreement.py` OUTCOMES + `grade_mark(vetoed=)` + `tally`; `calibration_harness.grade_one` per-variant detection; backend chip `kind:"vetoed"`.
  - [ ] Task 10b (inverse "elected box has a matured cause" invariant) — **DEFERRED, measure-first:** every simple geometric form false-positives (39/221 legit payload setups sit >0.25 box-heights above their climax; re-accumulation breaks to new highs). Needs a macro-bridge-provenance design, not a geometry gate.
  - [ ] P3 #6: kill the duplicate macro-bridge zigzag compute (surface `resolve_phase_a`'s raw abstention into `cause_maturity`) or accept the measured +0.4% cost.
- [ ] **TrustedHost middleware missing** (2026-07-11 review watchpoint). The `require_same_app` header guard is defeatable by DNS rebinding; verified no `TrustedHost`/`allowed_hosts` anywhere in `webapp/backend`. **One line, app-wide** (`TrustedHostMiddleware(allowed_hosts=localhost/127.0.0.1)`).
- [ ] **Hidden scoring weights not lifted to `settings.py`**. Hardcoded `0.4/0.4/0.2` and `0.40/0.35/0.25` weights inside `engine_alpha/structure/box_primitives.py:148` and `metrics.py:156,237` — invisible to the knob audit, outside the freeze manifest. Small, self-contained (ROADMAP fold #8).

## 3 · Diagnosed or planned, build not started *(lower priority — never actually begun)*

- [ ] **EGBN high-shelf / above-R LPS detector** — EGBN misses because its LPS closes ride *above* R (a high-tight-flag shelf) which `find_lps` rejects as `terminal_low` (~85% of the miss). Distinct above-R form, same family as the live holding-shelf LPS. Optional span-aware occupancy sub-measure enters report-only (measure-first). **Do NOT touch the box-election respect gate to chase EGBN.**
- [ ] **`atr_squeeze` ADR-relative rebase** — the untouched twin of the shipped `box_tightness` rebase; flat low-ADR names still win `SCORE_ATR_SQUEEZE` unfairly. Measure-first, grade-not-veto.
- [ ] **Dark-flag consumption waves** — substrate for `ELECTION_STABILITY` and Lane-C (`FUNDAMENTALS`/`RS_LINE`/`SECTOR_RANKING`) is built + tested + default-off + manifest-registered, but the score/enrichment wire-up was never scheduled. **Kill-by dates approaching (09-15 / 09-30).**
- [ ] **Event Map display layer (Tasks 12–15)** — engine substrate (Tasks 1–11) done; nothing reaches the chart yet. Task 12 Last Supper wave outcome-typing; Task 13 overlay payload into `chart_data`; Task 14 lightweight-charts marker collection; Task 15 detail-lens event list. Flag `EVENT_MAP_ENABLED` still dark. Includes the open **KLAC spring-test third-LPS-form** ruling (needs operator marks).
- [ ] **Plain-name rename migration** — operator-locked mapping (`traversal→Equilibrium`, `bin_a..d→Phase A..D`, `pip→Phase A`) never executed; those identifiers are still pervasive in `engine_alpha/`. Large mechanical change + 2 open naming decisions (Stale-Support-Reject naming; whether `LPS_RESCUE_MAX_ADVANCE_BOX` should exist).

## 4 · Waiting on an operator decision (not agent-resumable)

- [ ] **`AR_FIRST_REACTION_ENABLED` flip** — substrate live measure-only; blocker (the `bin_a` archive-seam guard) **now exists** after the climax-anchor fix (6e83007). Needs an A/B re-run + flip/kill call (kill-by 2026-08-15). *(The `engine/ar-first-reaction` branch holds only an older raw-bar prototype superseded on `main` — do not resurrect; this is a decision, not a build.)*
- [ ] **QUALITY_DOCTRINE §6 operator last-mile** — 5 operator-only deploy actions still unchecked. Until `ALERT_WEBHOOK_URL` is set on the NSSM service, **every watchdog alert dies silently in a log file** (also gates the trade-alert sweep above). Plus: re-register Forward-Returns + Daily-Backup OS tasks as S4U, set the `$Mirror` off-disk backup dest, run the first restore drill.
- [ ] **Calibration footguns held for your call** — (a) `frame_digest NOT NULL` DDL rebuild on the non-regenerable marks DB (`webapp/backend/models.py:245`); (b) `agreement.py` `span_overlap` symmetric-Jaccard deflation (likely already resolved by the concordance reframe `a5a0e63` — confirm); (c) three marking-page footguns: Edit re-stamps a mark's provenance across sessions, a parse-failed successful POST reported as failure, auto-enter-edit makes drawing box B mutate box A.

## Cleanup
- [ ] **Stray untracked file** `tools/fidelity/full_package/BBVA.png` — a leftover 196 KB diagnostic render (from `tools/full_package_render.py`). Delete or gitignore.

---

## False alarms (verified NOT open)

Cross-checked against `origin/main` — **do not chase these**:

- **`engine/band-rails-flip`** — the cap+flip is **live and merged**. `main` has `BAND_RAILS_ENABLED = True`, an ATR-basis cap (`BAND_EVENT_MAX_DEPTH_ATR = 5.0`, replacing the branch's `BAND_EVENT_MAX_DEPTH_BOX = 2.0`), and the module renamed to `engine_alpha/structure/rail_qualification.py`. Branch superseded → **deletable**.
- **`claude/nervous-goldstine-5c7d81` perf batch** — all 3 commits are folded into `main` (twin `68b42bf` is an ancestor). **Deletable.**
- **UI-scale control** and **WP-F frontend folds** — memory flagged both *"likely LOST,"* but they're **present on `main`** (`utils/uiScale.js`, `hooks/screenerStore.js`, `/screener-summary/`). Memory notes were stale (corrected 2026-07-21).
- **`wip/audit-tool-tweaks`** and the rest of **`codex/backend-hardening`** — superseded by the post-reorg codebase (imports the pre-rename `core.*` namespace; `phase_a_pip_diff.py` was deleted from `main`). Re-implementation, not a resumable slice; low value.
- **Solve-the-Engine program**, **band-rails**, **calibration Task 15**, **stretch levers** — complete/merged or intentionally evidence-gated, not forgotten.

## Branches safe to prune once confirmed
`engine/band-rails-flip` · `claude/nervous-goldstine-5c7d81` · `wip/audit-tool-tweaks` (local + remote where present). Keep `wip/signal-edge-backtest`, `engine/ta-score-v2`, `worktree-council-p2-followups`, `codex/backend-hardening`, `docs/last-supper-definition` until their salvageable slices are re-ported (items above).

---

## Added 2026-08-05 (Surface-the-Read council review, finding 9)

- **Fold the cascade-summarizer copies onto `trace_export.terminal_verdict`** — the census /
  evidence tools still carry three independent re-derivations of the "which stage killed the
  furthest candidate" judgment. Fold them onto the one function (or pin equivalence in a check
  battery) before the next consumer lands; until then an evidence report and the operator-facing
  exported trace can tell different stories about the same cascade. The function's docstring
  names this debt.
- **Hoist one shared family-splat helper** when the NEXT archive column family arrives — the
  get → NaN-scrub → INTEGER-coerce loop now has four copies (event_map, election_trace,
  strategy_read, plus htf's older bool variant). Ownership of names/types stays per-module;
  only the mechanics fold (review finding, fowler seat).
