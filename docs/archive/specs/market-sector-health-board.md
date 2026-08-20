# Spec: Market & Sector Health Board

**Date:** 2026-06-30
**Status:** Confirmed (engine-grounded by the state-taxonomy audit — see `docs/health_board_state_audit.md`)

## Objective

Turn the two non-equity universe tabs (Sectors + Market, Commodities + ETFs) from empty strict-screener grids into always-on **health boards**: a looser structural read of *every* member — including the broad-market indices — that classifies each into a position-in-cycle **state** and surfaces the ones at a decision point first. A market index resting on support after a pullback is not a rejected setup; it is a signal about which equities to look at next.

## Context

The three universes run the same engine, but the equity-momentum screener fires **zero** setups on broad ETFs/indices (Sectors: 13 evaluated → 0; Commodities: 29 → 0), so both grids render nothing. The firing chain rejects exactly the members a health read wants: SPY/QQQ are skipped as benchmarks; the baseline gate requires an uptrending stock; the crash/extension filters drop fallen and broken-out members. The structure machinery (box detector, traversal/equilibrium metrics, trend template, drawdown, the Finviz-faithful card) is reusable, but today it only produces its fields for *firing* tickers.

This read is **additive and flag-gated** and must never perturb the US-Stocks (`us_equities`) engine output, which is locked by the `shadow_diff` and `seed_recall` byte-parity gates (a concurrent engine session owns those baselines). The actionable "what to hunt" pool already exists — the US-Stocks firing scan — and the existing ETF→related-equities drill-down already intersects with it, so this feature adds only the top-down context.

## State taxonomy (v1)

Every member is classified into exactly one state, ordered by decision-proximity:

1. **near_resistance** — coiled just under the box ceiling R (pre-breakout).
2. **post_breakout_markup** — an established base with price now above R (coarse "broke out"; not a confirmed continuation setup).
3. **near_support** — pressed against the box floor S (sitting on support).
4. **consolidating** — a worked two-sided box, price inside the rails (with or without a completed LPS).
5. **trending** — a clean directional move with no established base.
6. **deep_correction** — a large drawdown from the recent high; fallen well below its base.
7. **no_structure** — no readable base and nothing else actionable.

## Scope

### In scope
- A looser read that runs on **every** member of both non-equity universes, including SPY/QQQ as first-class members, bypassing the uptrend/VCP firing gates.
- Classify each member into exactly one taxonomy state.
- The two tabs render all members full-time using the existing card (chart + box overlay), re-framed as a *health read* — no setup/score/trigger/"buy" language — each tagged with its state.
- Order the board decision-point-first (near-rail / just-broke-out surface first; dormant last).
- Reuse the existing ETF→related-equities drill-down as the bridge to actionable equities.
- A setting that gates the whole read path; when off, behaviour is unchanged.

### Out of scope
- **Refined post-breakout** continuation detection (re-anchored base + fresh LPS above the old range) — deferred to the L2 event-reader / HTF re-accum track.
- **Detecting a base forming below the 200-day trend** — the box substrate refuses below-SMA200, so such members read as `deep_correction` in v1 (candidate future enhancement).
- The compact Home cockpit "Market & Sector Health" strip — deferred to a fast-follow spec.
- Wiring reads into scoring/edge/archive; alerts; new data feeds; real-time refresh.
- Any change to the US-Stocks screener behaviour.

### Non-goals
- Not a trade-signal generator. States are context, never a recommendation to buy or sell.

## Stories

### Story 1: Full-time, state-classified read of every sector, index & commodity

**When** I open a health-board tab, **I want to** see every member classified by where it sits in its cycle, with the interesting ones first, **so I can** read market/sector/commodity health at a glance.

**Acceptance Criteria:**

Given a universe whose latest scan fired zero tradeable setups
When I open that universe's tab
Then I see a card for every evaluated member, each tagged with exactly one taxonomy state

Given the Sectors+Market universe
When I open its tab
Then SPY and QQQ appear as first-class members with their own state

Given a board of classified members
When it renders
Then members at a decision point (near a rail / just broke out) appear before dormant ones (trending / deep correction / no structure)

Given a member that has fallen well below its recent high
When it is classified
Then it reads as a correction, not dropped as "no structure"

Given a member sitting in a worked box that has not yet formed a completed LPS
When it is classified
Then it reads as consolidating, not as "no structure"

Given any member card on a health board
When it renders
Then it shows no setup score, tier, trigger price, or buy-action language

Given the latest scheduled scan is a few bars old
When I read a member's state
Then the board presents as an end-of-scan read, not a real-time feed (a very fresh move may take a few sessions to re-label)

### Story 2: Bridge from a context instrument to actionable equities

**When** I see a sector or commodity at an interesting spot, **I want to** jump to the related US stocks that are setting up, **so I can** act on the top-down read.

**Acceptance Criteria:**

Given a sector or commodity member on a health board
When I open its drill-down
Then I see the related US-Stock setups from the current US-Stocks firing scan

Given a member with a curated mapping but no related stocks firing today
When I open its drill-down
Then I see a "mapped, none firing today" state distinct from "no curated mapping"

Given a member with no curated mapping and no sector-ETF lineage
When I open its drill-down
Then I see a "no curated mapping yet" state rather than an error or a blank grid

### Story 3: The health read never perturbs the engine

**When** the health read is enabled, **I want to** be certain it changes nothing about the US-Stocks screener or engine output, **so I can** trust the screener and its regression gates.

**Acceptance Criteria:**

Given the health-read setting is off
When any scan runs
Then the Sectors/Commodities tabs behave exactly as today and US-Stocks is unchanged

Given the health-read setting is on
When `tools.shadow_diff --check` and `core.archive.seed_recall --check` run
Then both report no canonical drift (us_equities output byte-identical)

Given the health read classifies any member
When it derives that member's state
Then it recomputes every classifying measure for that member and never reads a value produced only for firing setups

Given the health read runs
When it completes
Then it writes nothing to the setup archive, scoring, or edge metrics

## Boundaries

### ✅ Always
- Keep `python -m tools.shadow_diff --check` and `python -m core.archive.seed_recall --check` green after every change.
- Gate the entire read path behind a setting, default off, until the operator has eyeballed the boards.
- Recompute every classifying measure per member (drawdown/trend/box) — never read a state off fields produced only for firing tickers.
- Classify drawdown first, then attempt the box read; derive equities-default scope from `DEFAULT_UNIVERSE_TYPE` (EC-1); fold shared logic, never copy (EC-3).

### ⚠️ Ask first
- Relaxing the below-SMA200 box-substrate refusal for the health path (an engine change to shared box primitives).
- Changing any US-Stocks firing gate/threshold; adding a new backend endpoint vs extending the per-universe route.
- Persisting any health read (new archive columns/tables) or changing the scheduled-scan cadence.
- Building the Home strip (separate, deferred spec).

### 🚫 Never
- Modify `_run_eval_chain` / `_evaluate_ticker` / `_resolve_structure_context` / the baseline/crash/extension gates in a way that drifts `us_equities` output.
- Reuse the firing structure read such that an LPS-less worked base is labeled "no structure."
- Build any v1 state on the measure-only L2 reader (`PUZZLE_SCORE_ENABLED`) or HTF re-accum — coarse `price > R` is the honest post-breakout flag.
- Present a health read as a buy/sell signal; wire it into the archive/scoring/edge; open a broker connection; bump the `yfinance==1.2.1` pin (AP-4).

## Success Metrics

- The Sectors+Market tab renders all 15 members (incl. SPY/QQQ) and the Commodities tab all ~29 members full-time, where both show 0 today.
- Every member carries exactly one state label; decision-point members appear before dormant ones.
- With the flag on, `shadow_diff --check` and `seed_recall --check` both report zero drift.
- From a sector/commodity member, the related firing US-Stock candidates are reachable in ≤1 click.

## Assumptions

- (confirmed) Tabs-only in this spec; Home strip deferred; reuse the existing card and drill-down.
- (audit-confirmed) The classifier is a **separate** read path over the box detector (`find_outer_box`/`detect_boxes`) + standalone metrics (traversal/equilibrium/staircase) + freshly recomputed drawdown (`dist_52w_high_pct`) and trend posture — **not** `read_structure` reused (its LPS requirement would collapse LPS-less bases).
- (audit-confirmed) Box-derived states apply only to above-SMA200 members with a worked base; below-SMA200 fallen members read as `deep_correction`.
- (audit-confirmed) `post_breakout_markup` is the coarse "price above the established box R" flag (the extension comparison without the veto); refined continuation deferred.
- (unconfirmed) SPY/QQQ render as first-class members while remaining regime benchmarks (dual role).
- (unconfirmed) Boards refresh on the nightly `--all-universes` scan; the anti-lookahead edge offset means a fresh move can lag its label by a few sessions.

---

*After implementing, compare results against each acceptance criterion above and list any unmet requirements.*
