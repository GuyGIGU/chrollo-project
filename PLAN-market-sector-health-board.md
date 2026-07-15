**Plan written to:** `PLAN-market-sector-health-board.md`

---

# Council Plan: Market & Sector Health Board (v1 — tabs)

**Scope:** Turn the two non-equity universe tabs (Sectors+Market, Commodities+ETFs) from empty strict-screener grids into always-on **health boards** — a looser, flag-gated structural read that classifies every member (incl. SPY/QQQ) into one of 7 position-in-cycle states, renders all members full-time via the reused card, sorted decision-proximity-first, with the existing ETF→equity drill-down as the actionable bridge.
**Context:** The equity firing chain fires 0 setups on broad ETFs (Sectors 13→0, Commodities 29→0), so the grids are empty. The classifier is a **separate, additive read path** over the public `core.structure` box detector + standalone metrics + recomputed drawdown/trend — it never touches the byte-parity-locked `us_equities` firing chain. Grounded by `specs/market-sector-health-board.md` + `docs/health_board_state_audit.md`.
**Boundaries (out of scope):** Home cockpit strip; refined post-breakout continuation; below-SMA200 base detection; any archive/scoring/edge write; any US-Stocks screener change; any broker action; a `yfinance` bump.
**Council dispatched (9/9):** Hunt (2 recs, low surface), Fowler (6), Dodds (7), Ramírez (6), Leach (4, DB-veto), Performance (6, "don't over-engineer"), McKinney (8, highest-stakes), Saarinen (5), Friedman (8). All returned recommendations; no unresolved cross-domain conflicts (only clean lane handoffs).

---

## Task Sequence

### 1. Byte-parity prep: fold `dist_52w_high_pct` into a shared pure helper

| | |
|---|---|
| **Domain** | Fowler × Carmack — Fold twin code paths, never copy (refactoring.md → EC-3 / Principle 2 + Two Hats §Principle 8) |
| **Ref** | `references/refactoring.md` → Principle 2 |
| **Depends on** | — |

The drawdown number the classifier needs is today inlined mid-function in `_relative_strength_context` (`evaluation.py:300-305`), reachable only after the firing gates. Lift it into a named pure helper both the firing path and the classifier call. Ship this as its OWN commit, proven byte-identical by `shadow_diff --check` + `seed_recall --check` BEFORE any health code lands on top — this is the only change that touches locked code, and that ordering is the whole safety story. Cross-ref: McKinney (single consistent drawdown basis).

---

### 2. Classifier module + state model + precedence ladder

| | |
|---|---|
| **Domain** | Fowler × Carmack — Missing boundaries / Primitive Obsession (refactoring.md → Principle 6 + Principle 5) |
| **Ref** | `references/refactoring.md` → Principle 6 |
| **Depends on** | Task 1 |

Create a new sibling module `core/pipeline/health_board.py` (the firing chain changes for calibration reasons and is locked; the classifier changes for taxonomy reasons and is flag-gated — different reasons, separate files). Expose a pure `classify_member(df) -> MemberHealth`; model the closed 7-state set as a `HealthState` enum (its order encodes the decision-proximity sort) and each read as a small `MemberHealth` dataclass. Reuse the box detector + standalone metrics **only through the existing public `core.structure` API** — never import `_resolve_structure_context`/`_structure_to_boxes` (they carry firing-chain gates) and don't invent a new shared fold-layer for one caller. Cross-ref: Ramírez (pure decision fn split from the write effect).

---

### 3. Per-state numerical derivation contract

| | |
|---|---|
| **Domain** | McKinney × Carmack — Lookahead / NaN-at-boundary / determinism (quality-llm.md → Principles 1, 2, 4, 7, 10) — HIGHEST-STAKES SEAT |
| **Ref** | `references/quality-llm.md` → Principles 1–10 |
| **Depends on** | Task 2 |

The classifier must be correct by construction: evaluate every measure on the SAME as-of bar the box detector uses (`df[:-STRUCTURE_EDGE_SKIP_BARS]`, i.e. `df[-6]`), never `df.iloc[-1]`, so a state never leads its geometry (the board is end-of-scan, not real-time). Guard box-position `(Close−S)/(R−S)` against zero/NaN/inf at the source (route a degenerate/empty box to the drawdown/no-structure branch, never a poisoned ratio). Express "near a rail" in scale-invariant fraction-of-box / ATR units (reuse the calibrated zone constants), never absolute price; keep `post_breakout_markup` the pure `Close > R` coarse flag. Use tolerance inequalities (never `==` on adjusted closes) and a **stable** decision-proximity sort with an explicit final tiebreaker (ticker). Cross-ref: Performance (compute the box + metrics once per member, branch all states off that single read).

---

### 4. Precedence ladder totality + frame isolation + flag + orchestration branch

| | |
|---|---|
| **Domain** | McKinney × Carmack — Determinism / copy-vs-view (quality-llm.md → Principle 7) + Fowler (visible orchestration, lazy settings) |
| **Ref** | `references/quality-llm.md` → Principle 7 ; `references/refactoring.md` → Principle 1 (Global Data) |
| **Depends on** | Task 2 (uses Task 1) |

Encode ONE ordered, exhaustive, non-overlapping precedence ladder — **drawdown first** (`dist_52w_high_pct` below threshold → `deep_correction`, which also absorbs the below-SMA200 cohort the box substrate refuses), then valid-box split into the four box states, then `trending`, then `no_structure` as the total fallback — so every member gets exactly one state and the empty-box conflation (no-structure vs LPS-less base vs below-SMA200) is broken. Enrich only an explicit `.copy()` of each member frame (never a view / the cached parquet slice) and mutate no shared state. Wire the read as a **visible per-universe branch in `run_scan_and_export`** (not a hidden hook in `run_screener`/`_evaluate_frames`), gated by one **lazily-read** `HEALTH_BOARD_ENABLED` (default OFF; read at call time — AP-3 config-vs-cwd trap); flag-OFF must be a literal early skip so the code path is not entered at all (byte-identical by construction). Reuse the already-fetched `ticker_frames` + the existing ProcessPool; drawdown/SMA200 short-circuit keeps the anchor walk off fallen members.

---

### 5. Health payload builder + artifact contract

| | |
|---|---|
| **Domain** | Leach × Carmack — Versioned data contract / atomic write (quality-postgres.md → Principles 5, 6, 2) — Cross-ref: Fowler (no twin of `_extract_chart_data`), Hunt (JSON-safe + per-member isolation) |
| **Ref** | `references/quality-postgres.md` → Principles 5, 6 |
| **Depends on** | Tasks 3, 4 |

Write a dedicated `build_health_payload(members, data)` (do NOT parameterize/twin `_extract_chart_data`, which reads only firing `results_df`) that emits a distinct `health_board` section into the **same per-universe artifact**, keyed by member: `{candles, volumes, R, S (nullable), state, sort fields}`. It rides the SINGLE existing atomic tmp-then-`os.replace` write (build the full payload in memory, write once — no second append pass); every value passes through the existing `_json_safe` chokepoint; each member is classified inside its own `try/except` so one unreadable member degrades to `no_structure`/skipped, never tears the artifact; assert each emitted member carries exactly one valid closed-set state. Additive + back-compatible: an absent section (flag-off / older file) must still parse. No archive/DB write — nothing reaches `writer.py`/`seed.py`; the state strings share one definition with the reader.

---

### 6. Serve path: extend `/screener-data/` + `HealthMember` contract

| | |
|---|---|
| **Domain** | Ramírez × Carmack — Thin routes / validate at the boundary (quality-backend.md → Principles 3, 4) — Cross-ref: Hunt (closed-set params), Performance (off-loop) |
| **Ref** | `references/quality-backend.md` → Principles 3, 4 |
| **Depends on** | Task 5 |

Extend the existing `GET /screener-data/?universe=` to pass the `health` key straight through (no new route, no new endpoint, no on-the-fly classification — the route stays a pure pass-through of the cached parsed artifact and never touches the event loop). Define a `HealthMember` Pydantic projection with `state: Literal[<7 taxonomy names>]` and `R/S: float | None`, carrying **no score/tier/trigger/setup field** — the "no buy language" AC enforced at the type layer. Flag-off / missing-section serves the health key absent (operational absence → frontend renders today's empty), riding the existing `never_scanned`/`ready` status discipline; do NOT swallow a malformed block behind `except: return {}` (a classifier bug should surface, not silently blank the board). Ideally add zero new request params; any future toggle/filter is a closed-set enum validated at the edge (Hunt).

---

### 7. Frontend data plumbing + render branch

| | |
|---|---|
| **Domain** | Dodds × Carmack — Own server state in one place / validate at the boundary (quality-frontend.md → Principles 2, 3) |
| **Ref** | `references/quality-frontend.md` → Principles 2, 3 |
| **Depends on** | Task 6 |

`useScreenerData` already fetches the whole per-universe payload — expose the new section by reading `byUniverse[universe]?.health_board` off the single fetch-owned cache (no second fetch hook, no second `useState`); do NOT merge health rows into `chart_data`/`ordered_tickers`/`deriveStatus` (that would perturb the firing status/empty logic). In `ScreenerGrid`, add a THIRD render branch (`etfUniverse && healthEnabled` → a colocated `HealthBoard` presentational component) — leave the firing grid JSX literally unchanged so US-Stocks stays byte-identical. Validate the section at the JSON boundary (`health_board?.members || []`, unknown state → fallback, absent → existing empty grid), under the existing `ErrorBoundary`. Keep the ETF drill-down wiring exactly as-is.

---

### 8. `ScreenerCard` health variant + the state chip

| | |
|---|---|
| **Domain** | Dodds (composition) × Saarinen (visual) × Carmack — Composition over configuration / Reduce noise to reveal hierarchy (quality-frontend.md → Principle 5 ; quality-ui.md → Principles 1, 3) |
| **Ref** | `references/quality-frontend.md` → Principle 5 ; `references/quality-ui.md` → Principle 1 |
| **Depends on** | Task 7 |

Add a single narrow `health` variant prop to `ScreenerCard` that render-branches the setup UI away (no score/tier/`setup`/trigger/`ScoreBreakdownPills`, skip the tag row) — a real render branch, NOT a CSS-hidden wrapper (which would still read `data.score`/`tier` that don't exist) and NOT a forked card (which would drift the shared chart lifecycle). Fill the vacated verdict slot with ONE neutral **state chip** (the card's single new protagonist) reusing an existing type role + matching the existing chip metrics; render the ticker in neutral `--text-main` (no tier hue) — the absence of the tier-colored ticker is itself the honest "context, not a ranked setup" tell. Re-balance the header so nothing jumps between the firing and health tabs. The mini-chart + box overlay stay identical.

---

### 9. State→sort selector + comparator unit test

| | |
|---|---|
| **Domain** | Dodds × Carmack — Derive, don't store / test behaviour not implementation (quality-frontend.md → Principles 2, 4) — Cross-ref: McKinney (stable sort) |
| **Ref** | `references/quality-frontend.md` → Principles 2, 4 |
| **Depends on** | Task 7 |

Put the decision-proximity ordering in one pure `sortHealthMembers(healthBoard)` selector computed in `useMemo` every render — never store the sorted list or per-member label in state, and never recompute the state on the frontend (the engine is the single source of the classification; the FE only orders + renders). Colocate a unit test for the comparator: full 7-bucket order, the `near_resistance`/`near_support` rail-distance tie-break direction, `post_breakout_markup` freshest-first, and an unknown/missing state landing in the correct fallback bucket.

---

### 10. Board framing, state bands, freshness stamp + copy register

| | |
|---|---|
| **Domain** | Friedman (UX) × Saarinen (visual) × Carmack — Attention direction / honest instrument (quality-ux.md → Principles 1, 6, 8, 9 ; quality-ui.md → Principles 2, 5) |
| **Ref** | `references/quality-ux.md` → Principles 1, 8, 9 |
| **Depends on** | Tasks 8, 9 |

Add a persistent board-mode header (same quiet register as the existing ETF breadth note) that names the view as a health READ, states the decision-proximity sort logic, and pre-empts the setup-model reflex — before the eye hits the first card. Make the sort **visible** as labeled state-band sections with counts ("Near resistance · 4", "Deep correction · 11") so the whole universe's shape reads at a glance. State labels use the taxonomy's human words with hover definitions; enforce **positional-not-imperative copy everywhere** ("sitting on support," never "buy zone" — the hardest AC). Add an "as-of-last-scan · HH:MM" freshness stamp plus a plain, boring labeling-latency note ("a fresh move may take a few sessions to show"). Visual: a two-tone attention ramp (decision-point emphasized, dormant recessed) — zero hue on state, no per-state rainbow, no green/red; keep the state chip the loudest element (quiet or drop the colored setup-tag row).

---

### 11. Screen states: degraded / stale / partial / pre-scan / short-history

| | |
|---|---|
| **Domain** | Friedman × Carmack — Design all five screen states (quality-ux.md → Principle 2) — Cross-ref: Dodds (boundary validation) |
| **Ref** | `references/quality-ux.md` → Principle 2 |
| **Depends on** | Task 10 |

The board removes "empty grid" but not the fragile yfinance path. Render the members that DID classify and flag the gap honestly ("29 members · 5 unavailable this scan") — a partial fetch must never blank or silently shrink the board. Give the two ETF tabs a pre-first-scan message in health-read language (not setup language). A member that fetched but has too little history to classify (<200 bars) belongs in an explicit "can't read yet" bucket, never silently dropped or mislabeled `no_structure`.

---

### 12. Drill-down bridge polish

| | |
|---|---|
| **Domain** | Friedman × Carmack — Blank/partial state design / don't yank the user's place (quality-ux.md → Principles 2, 3) — Cross-ref: Dodds (reuse existing wiring) |
| **Ref** | `references/quality-ux.md` → Principles 2, 3 |
| **Depends on** | Task 8 |

Preserve and strengthen the two distinct "nothing here" cases in plain words — "No XLE member stocks set up in today's scan" (market quiet, a meaningful read) vs "No curated stock mapping for XLE yet" (a coverage gap) — since they demand opposite next actions. Returning from a drill-down must restore the board's scroll position and state band (the board is long; losing place taxes the whole top-down→bottom-up→back loop). Reuse the existing `useDrilldown` wiring; add no new drill state.

---

### 13. Verification sweep + operator eyeball → flag flip

| | |
|---|---|
| **Domain** | McKinney/Hunt × Carmack — the classifier path has its own tripwire (quality-llm.md → Principle 7 ; security.md → Principle 9) |
| **Ref** | `references/quality-llm.md` → Principle 7 |
| **Depends on** | Tasks 1–12 |

Every step stays gated on `shadow_diff --check` + `seed_recall --check` + `pytest -q` green (flag-OFF byte-identical is the contract). The byte-parity gates cover ONLY `us_equities` — they do NOT watch the classifier's own output, so add classifier unit tests on synthetic frames (each state, precedence totality/exclusivity, the zero/NaN/inf guards, frame isolation, the "exactly one valid state" assertion) plus the FE sort test (Task 9). Then run the two ETF boards with the flag ON, operator eyeballs the states against the charts (the measure→render→eyeball loop), and only then flip `HEALTH_BOARD_ENABLED` on for real.

---

## Risks & Watchpoints

- **Performance — don't over-engineer for absent scale:** ~44 members, offline scan. Do NOT add batching/caching/incremental-rescan/anchor-walk memoization. The looser path widens the above-SMA200 cohort that reaches the anchor walk, but the SMA200 gate bounds it — accept it, don't re-architect.
- **McKinney/Performance — never use the L2 measure-only readers** (`assemble_box_narrative`/`read_box_events`/`measure_resistance_events`) for any v1 state: they're `PUZZLE_SCORE_ENABLED`-gated, wired downstream of the LPS/extension gates (so they read garbage for exactly the broken-out cohort), and the heaviest primitive. Coarse `Close > R` is the honest flag.
- **McKinney/Hunt — the classifier output is unguarded by shadow/seed.** Those prove only `us_equities` is untouched. The one-valid-state assertion + classifier unit tests are the ONLY tripwire on the health path — treat them as load-bearing, not optional.
- **Fowler — the fold-out (Task 1) must ship & prove green FIRST**, alone, before the feature builds on it. Folding shared pure primitives is right; entangling the two paths (importing firing-chain helpers) is the byte-parity risk to avoid.
- **Friedman/Saarinen — cognitive load across ~29 members:** the state-band grouping (Task 10) is the primary load-reducer. Whether health cards need a compact density variant (vs the 480px reading-room card) is an open build decision — decide during Task 8, don't force reading-room cards for the whole universe if it makes the board an endless scroll.
- **Leach/Hunt — hold the DB line:** if any instinct arises to "just persist the states in a column/table," that's out of scope and would drag soft-state predicates into every calibration/recall query. Artifact JSON only.

---

## External Setup Required

No external setup required. All tasks can be implemented within the codebase (no API keys, no service signups, no new data feed — the classifier reads the already-cached OHLC).

---

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Fold `dist_52w_high_pct` into a shared pure helper (own byte-parity commit) | Fowler×McKinney | — |
| 2 | Classifier module + `HealthState` enum / `MemberHealth` + reuse public API | Fowler | 1 |
| 3 | Per-state numerical derivation contract (as-of bar, guards, scale-invariant) | McKinney | 2 |
| 4 | Precedence ladder + frame isolation + flag + orchestration branch | McKinney/Fowler/Ramírez | 2 |
| 5 | Health payload builder + artifact contract (atomic, additive, JSON-safe) | Leach/Fowler/Hunt | 3, 4 |
| 6 | Serve path: extend `/screener-data/` + `HealthMember` Pydantic contract | Ramírez/Hunt | 5 |
| 7 | Frontend data plumbing + third render branch | Dodds | 6 |
| 8 | `ScreenerCard` health variant + neutral state chip | Dodds/Saarinen | 7 |
| 9 | State→sort selector + comparator unit test | Dodds/McKinney | 7 |
| 10 | Board framing, state bands, freshness stamp, copy register | Friedman/Saarinen | 8, 9 |
| 11 | Screen states: degraded/stale/partial/pre-scan/short-history | Friedman/Dodds | 10 |
| 12 | Drill-down bridge polish | Friedman/Dodds | 8 |
| 13 | Verification sweep + operator eyeball → flag flip | McKinney/Hunt | 1–12 |

## Verdict

The single most important architectural decision is the **separation line**: the classifier is a new, pure, flag-gated module reading only the *public* `core.structure` API, wired as a *visible branch* in `run_scan_and_export` — never inside the firing chain. Get that boundary right and byte-parity is safe by construction; blur it (import a `_resolve_*` helper "to save work," or graft the read into `run_screener`) and you reopen the one risk the whole spec exists to close. **McKinney's seat is the critical one** — the classifier is new engine math, and its correctness is guarded by nothing but its own tests (shadow/seed only prove `us_equities` is untouched). Start at Task 1 (the fold-out, proven green alone), because it's the only edit to locked code and everything else stacks on it. Tasks 1–6 are the real feature (engine → artifact → serve); 7–12 are a mostly-mechanical reuse of surfaces that already exist (the drill-down is essentially already built); 13 is the eyeball-gated flip. This is a surgical, additive build — the council's dominant note across every seat was *restraint*: reuse the card, reuse the route, reuse the drill-down, spend no new color, add no new scale machinery, and never let the health path near the firing bytes.
