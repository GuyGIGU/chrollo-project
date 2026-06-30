# Spec: Home Command-Center

**Date:** 2026-06-29
**Status:** Confirmed

## Objective

Give Chrollo a single **orient surface** — the first thing the trader sees when they
open the app — that answers "what is the state of my world right now?" before they dive
into any one view. It composes the market regime, today's fresh scan, the curated
watchlist, and the open book into one calm pane, plus an honest read of the engine's
measured edge. Today the app drops the user mid-task into the screener grid; there is no
place to take stock first.

## Context

The pieces exist but are scattered: regime lives atop the screener, live-position P&L and
risk machinery live in Portfolio, the watchlist is a screener side-panel, and the engine's
forward-return edge is computed in the backend but surfaced nowhere. The current
"Dashboard" route is a backward-looking **trade-journal** page (equity curve + win/loss
tiles), not an orient surface. This feature is mostly **assembly + information
architecture** over existing, well-built parts; the only net-new data is a small
read-only endpoint serving the engine's headline edge. The full competitive analysis and
IA rationale live in [`docs/cockpit/teardown.md`](../docs/cockpit/teardown.md). The
project's design law is `PRODUCT.md` + `DESIGN.md` ("The Instrument Panel": calm,
confident hierarchy, signal over chrome, honest instrument — never a salesman).

## Scope

### In scope
- A new **Home** surface that becomes the app's landing/index route.
- Four content zones in a confident top-down hierarchy: **Regime** (spine), **Fresh
  Setups**, **Watchlist**, **Open Book**, plus an **Engine-Edge Pulse** footnote.
- Renaming the existing "Dashboard" trade-journal route/nav label to **"Journal"**.
- A small read-only backend endpoint serving the engine's headline edge for the pulse tile.

### Out of scope
- A user-configurable / drag-and-drop dashboard (regions are curated, not configurable).
- A charting workspace or drawing tools (deep charting bridges out to TradingView/TWS).
- An alerts/event stream (a future zone; deliberately omitted from this layout).
- A full edge-explorer surface (the pulse is a read-only summary, not a research view).
- Any change to engine scoring or structure math.

### Non-goals
- Does not optimize for novelty or "engagement" — it optimizes for fast, calm orientation.
- Does not replace Portfolio, Screener, or Journal; it links into them.

## Stories

### Story 1: Land on the command-center and orient

**When** I open Chrollo to start a review session, **I want to** land on one surface that
shows the regime, fresh scan, watchlist, and open book together, **so I can** decide where
to focus before diving in.

**Acceptance Criteria:**

Given I open the app at its root address
When the app loads
Then I land on the Home command-center, with the Screener reachable in one click from the nav.

Given I am on Home
When the surface renders
Then I see all four zones (Regime, Fresh Setups, Watchlist, Open Book) plus the edge pulse, with the regime reading visually dominant at the top.

Given I previously navigated to the trade-journal page
When I look at the navigation
Then it is labeled "Journal" (not "Dashboard"), and its content is unchanged.

Given one data source for a single zone is slow or fails to load
When the surface renders
Then the other zones still render, and the affected zone shows its own loading or error state without blanking the page.

Given the browser tab is hidden / backgrounded
When time passes
Then live-price polling pauses, and resumes when the tab becomes visible again.

### Story 2: Read the market regime first

**When** I sit down in an uncertain tape, **I want to** see the regime weather as the first
thing on the surface, **so I can** calibrate whether to take new setups today.

**Acceptance Criteria:**

Given the regime has been evaluated
When Home renders
Then the current regime state (risk posture / trend / breadth) is shown prominently at the top of the surface.

Given I want more detail on the regime
When I open the regime detail
Then I see the breakdown behind the current reading without leaving Home.

Given regime data is unavailable or stale
When Home renders
Then the regime zone shows a neutral "unavailable" or clearly-labeled last-known state, never a misleading fresh-looking reading.

### Story 3: Triage today's scan at a glance

**When** a fresh scan has run, **I want to** see how many setups it found by tier and a few
top names, **so I can** decide whether it's worth opening the full grid.

**Acceptance Criteria:**

Given a scan has completed
When I view the Fresh Setups zone
Then I see when the scan ran and a count of setups by tier (S/A/B/C).

Given there are qualifying setups
When I view the zone
Then I see the top few setups inline and a clear path to the full Screener grid.

Given no scan has run yet, or the latest scan is stale
When I view the zone
Then I see a clearly-labeled "no recent scan" state rather than empty or stale-looking content.

Given the latest scan matched zero setups
When I view the zone
Then I see a quiet "no setups matched" empty state, not a filler placeholder.

### Story 4: Check my watchlist status

**When** I'm tracking a curated shortlist, **I want to** see each name's live move and
whether it's near its trigger, **so I can** spot which of my names is acting and jump to a
closer look.

**Acceptance Criteria:**

Given I have names on my watchlist
When I view the Watchlist zone
Then I see each name with its live price and change, with figures aligned in fixed-width columns.

Given a watchlisted name is near its trigger level
When I view the zone
Then that name is visibly flagged as near-trigger.

Given I want a closer look at a watchlisted name
When I select it
Then a chart peek opens in place, with an action to bridge out to the external charting/broker view.

Given my watchlist is empty
When I view the zone
Then I see a short explanation and a clear way to add names, not a blank panel.

### Story 5: Watch my open book

**When** I have open positions, **I want to** see live P&L, R-multiple, and distance-to-stop
with any risk flags, **so I can** catch anything needing attention without opening Portfolio.

**Acceptance Criteria:**

Given I have open positions
When I view the Open Book zone
Then each position shows live P&L, R-multiple, and distance-to-stop, with P&L reported calmly (no oversized or celebratory styling).

Given a position has moved near its stop
When I view the zone
Then it carries a risk flag, and a path to the full Portfolio view is available.

Given I have no open positions
When I view the zone
Then I see a quiet "no open trades" state.

Given a live price cannot be fetched for a position
When I view the zone
Then it shows the last-known value marked as stale rather than a blank, zero, or crash.

### Story 6: Gauge the engine's edge honestly

**When** I want a quick read on whether the engine actually carries an edge, **I want to**
see a small honest summary by tier, **so I can** keep the "what edge does this have?"
question in view without leaving Home.

**Acceptance Criteria:**

Given the engine has enough archived setups with measured outcomes
When I view the Engine-Edge Pulse
Then I see the headline forward-return edge by tier with the sample size, labeled plainly and without celebratory framing.

Given the displayed edge is computed
When I view the pulse
Then it is based on the unbiased (live-screener) population and never includes seed-gallery / cherry-picked outcomes.

Given there are not yet enough measured outcomes
When I view the pulse
Then it shows a clear "not enough data yet" state rather than a misleadingly precise number.

## Boundaries

### ✅ Always
- Reuse the existing regime, screener-card, watchlist, live-position, and equity-curve building blocks rather than reimplementing them.
- Conform to `DESIGN.md` (tonal depth before shadow, one interactive accent, tabular numerics, the reserved tier palette) and `PRODUCT.md`'s anti-references.
- Render each zone's loading/empty/error independently so one failing data source never blanks the surface.
- After changes, build the frontend and run the existing test suite; verify the surface renders with no console errors.

### ⚠️ Ask first
- The response shape of the new edge endpoint (confirm before finalizing).
- Adding any new global state/context, new polling beyond reusing the existing cadence, or any new third-party UI library.
- Changing the existing live-poll interval or the regime/scan data contracts.

### 🚫 Never
- Modify the owner's in-progress files: `core/structure/metrics.py`, `tests/test_market_structure.py`, `tools/l2_staircase_audit.py`, `tools/l2_staircase_render.py`, `tools/fidelity/l2/`.
- Add gamified or celebratory mechanics (confetti, win animations, oversized green P&L) or let the surface flatter its own output.
- Place orders or execute trades from the cockpit — it is read-only context.
- Borrow a tier or categorical hue to signal "clickable", or build a tile-configurator.
- Change engine scoring or structure math to serve the UI.

## Success Metrics

- From app open, the trader can read regime + scan + watchlist + book state on one surface with **zero navigation** away.
- Killing any single zone's data source leaves the other zones rendering (independent degradation verified).
- Frontend build passes and existing frontend tests stay green; Home renders with no console errors.
- The edge pulse only ever shows the unbiased population with a stated `n`; it shows the "not enough data" state rather than a contaminated or low-`n` number.

## Assumptions

- (confirmed) Home is the index route; "Dashboard" → "Journal"; edge pulse ships in v1 with a small backend endpoint.
- (confirmed) Watchlist click = chart peek + bridge-out; reuse existing live-poll cadence and pause when the tab is hidden; top 3–4 setup cards inline; alerts zone deferred.
- (unconfirmed) The edge pulse surfaces the existing headline edge (elapsed-window MFE / win-rate by tier, screener source basis). Override if a different metric is wanted.
- (unconfirmed) "Near trigger" is defined as price within ~2% of the trigger level. Override with a preferred threshold.

---

*After implementing, compare results against each acceptance criterion above and list any unmet requirements.*
