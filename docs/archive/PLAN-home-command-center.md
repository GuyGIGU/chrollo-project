**Plan written to:** `PLAN-home-command-center.md`

---

# Council Plan: Home Command-Center

**Scope:** A new index-route orient surface — regime spine + Fresh Setups + Watchlist + Open Book + an honest engine-edge pulse — composed mostly from existing components, plus one read-only edge endpoint. "Dashboard" trade-journal renames to "Journal".
**Context:** Chrollo is a React 19 + Vite SPA over a FastAPI/SQLite backend. The app currently lands in the screener grid; there is no orient surface. ~70% of this is assembly/IA of well-built components (regime banner, screener cards, watchlist panel, live-position machinery, equity curve); ~30% is net-new (Home route + layout, a derived today's-scan aggregation, the edge-pulse tile + its endpoint).
**Boundaries:** No engine-math change, no new DB tables/columns, no order placement (read-only), no tile-configurator / charting workspace / alerts stream. Never touch the WIP files (`core/structure/metrics.py`, `tests/test_market_structure.py`, `tools/l2_staircase_audit.py`, `tools/l2_staircase_render.py`, `tools/fidelity/l2/`).
**Council dispatched:** All 9 returned recommendations — Security (Hunt), Structure (Fowler), Frontend (Dodds), Backend (Ramírez), Data-Integrity (Leach), Performance, Numerical (McKinney), UI (Saarinen), UX (Friedman). Leach returned "no schema recommendations" (read-only feature) but contributed the read-pattern guidance folded into Task 3.

---

## Task Sequence

### 1. Home route shell + visual hierarchy scaffold

| | |
|---|---|
| **Domain** | Saarinen × Carmack — Tonal depth is a system (quality-ui Principle 3) + Spacing creates meaning (Principle 4) |
| **Ref** | `references/quality-ui.md` → P3, P4 |
| **Depends on** | — |

Add a thin `HomeRoute` as the new index (replacing the `/screener` redirect), following the existing `src/routes/` per-surface idiom — lazy view, `Suspense`, zero fetch logic in the route. Lay out the surface as a **tonal spine** (regime full-bleed, one surface step lighter, more vertical air) above a **1+3 hierarchy** (three zones differentiated by internal rhythm, not chrome) with the edge pulse as a quiet baseline footnote; encode hierarchy with the xl/lg/sm spacing ladder. Cross-ref: Fowler (thin composition shell) and Friedman (action-first IA) also informed this — see Risks.

---

### 2. Per-zone data foundation: status hooks + error isolation + visibility-gated polling

| | |
|---|---|
| **Domain** | Dodds × Carmack — Model async state as one status; Error Boundaries are structural (quality-frontend P3, P6) |
| **Ref** | `references/quality-frontend.md` → P3, P6; cross-ref Performance |
| **Depends on** | — |

Establish the scaffolding every zone plugs into: each zone owns its **own** fetch hook exposing a single `status` enum (`loading/ready/empty/error`) — no monolithic `useHomeData` — wrapped in its **own** `ErrorBoundary` with a local async-error state, so one dead source degrades only its zone. Extract one shared `usePollingInterval` that gates on `document.visibilityState` (the gap Dodds found: SSE hooks already pause on hidden tab, the `setInterval` ones don't) and route every Home poll through it so a backgrounded tab stops polling and resumes with an explicit refresh. Per-zone skeletons match each zone's final shape (no full-page spinner, no reflow).

---

### 3. Engine-edge endpoint (read-only service wrap)

| | |
|---|---|
| **Domain** | Ramírez × Carmack — Thin route over pure core; never block the event loop (quality-backend P1, P2, P3, P5) |
| **Ref** | `references/quality-backend.md` → P1–P5; cross-ref Leach, Hunt, Performance |
| **Depends on** | — |

Add one read-only `GET` endpoint whose route is a one-liner calling a new `services/engine_edge.py` function: load archive rows via the existing read-only loader (`core/backtest/loader.py`, opens `mode=ro`), call `build_edge_report(df, source_basis="screener")`, return a **Pydantic `response_model` that carries the bias-safety contract verbatim** (`unbiased`, `contaminated_input`, `n_unbiased`, `headline_mfe_median: float | None`, `by_tier`). Run it as plain `def` (threadpool — the whole-archive load + pandas pass is CPU/IO-bound), select only the edge-math columns, count `n` over the **NULL-excluded** (backfilled) rows so low-n is honest, coerce non-finite floats to `None`, treat empty/missing archive as the operational "n=0" state (everything else crashes to a clean 500 — no traceback/path leak), read any config lazily (cwd-shadow trap), and **cache the result on a scan-cadence signature that also moves when forward-returns mature**. Cross-ref: Leach (project columns, `WHERE source='screener'`, read-only autocommit), Hunt (param validation, no raw SQL), Performance (single grouped pass) all folded here.

---

### 4. Regime spine zone

| | |
|---|---|
| **Domain** | UI (Saarinen) × Carmack — One-Accent & Tier-Reserve Rules (quality-ui P3) |
| **Ref** | `references/quality-ui.md` → P3; cross-ref UX, Frontend |
| **Depends on** | 1, 2 |

Render the regime as the dominant spine by reusing `MarketRegimeBanner` fed from `screenerData.market_context` (the same single `/screener-data/` fetch that drives Fresh Setups — Fowler: share the source, never two scan fetches), with detail-on-demand via the existing modal. Regime risk-on/off and breadth use the **status ramp (green/amber/red), never tier hues**; a stale/unavailable regime shows a neutral last-known state, never a misleading fresh reading.

---

### 5. Fresh Setups zone

| | |
|---|---|
| **Domain** | Dodds × Carmack — Derive, don't store; AHA on component reuse (quality-frontend P1, P2) |
| **Ref** | `references/quality-frontend.md` → P1, P2; cross-ref UX (screen states), Performance (chart cap) |
| **Depends on** | 1, 2 |

Add a `useTodaysScan` hook that **derives** tier counts + the top 3-4 setups (a pure `useMemo` over the already-fetched `ordered_tickers`/`chart_data` + `scan-status/latest`; never copy top-N into state). Render the top cards via a thin `HomeSetupTile` reusing `ScreenerMiniChart` (don't fork `ScreenerCard` with a `variant` flag) and **cap lightweight-charts instances at 3-4 with deterministic disposal**. Three visually-distinct states driven off an always-visible "scanned at HH:MM" stamp — **"no scan today" vs "scan ran, 0 matched" vs "scan stale"** — plus a partial-coverage note ("scanned 480/512") so a half-fetched universe isn't read as a quiet day; one clear "Open the grid" handoff.

---

### 6. Watchlist zone

| | |
|---|---|
| **Domain** | Friedman × Carmack — Single-purpose handoffs; per-source staleness (quality-ux P4, P6) |
| **Ref** | `references/quality-ux.md` → P4, P6; cross-ref Frontend (modal reuse) |
| **Depends on** | 1, 2 |

Reuse `useWatchlist` + live prices to show each curated name with price/%-change and a **near-trigger flag** (within the agreed threshold). Click opens a chart-peek using the existing `ScreenerModal` (Home owns `peekTicker` locally; feed `chart_data[ticker]`; guard the render when a watchlist name has no setup in today's scan) with a **separate, distinctly-labeled "Bridge to TWS/TV" action in the modal's `footer` slot** — never overload one click to both peek and bridge. Live numbers that go stale (poll fail / was-hidden) **visibly mark themselves stale**, not silently current; empty watchlist shows an add-names CTA.

---

### 7. Open Book zone

| | |
|---|---|
| **Domain** | Friedman × Carmack — Action-first attention ordering (quality-ux P6) + calm P&L (Saarinen quality-ui P2) |
| **Ref** | `references/quality-ux.md` → P6; cross-ref UI (calm P&L), Frontend (local snapshot ownership) |
| **Depends on** | 1, 2 |

Own `usePortfolioSnapshot` **locally inside this zone** (don't hoist the IBKR stream into the shell for one consumer); show each position's live P&L / R / distance-to-stop with **calm styling** (status-hue ink only, identical visual weight for up and down days — no oversized or celebratory P&L). A position at/through its stop carries a single restrained risk flag that **out-ranks top-down reading order** (open risk is the most urgent read). Stale price → last-known marked stale (never blank/zero/crash); no positions → quiet empty; a named error state if the IBKR session is held elsewhere, still showing the "Open Portfolio" handoff.

---

### 8. Engine-Edge Pulse tile

| | |
|---|---|
| **Domain** | McKinney × Carmack — Three-state None/thin/has-data; no UI-side recompute (quality-llm P2, P4, P7) |
| **Ref** | `references/quality-llm.md` → P2, P4, P7; cross-ref UI (footnote styling), UX (honest low-n) |
| **Depends on** | 2, 3 |

Bind the tile to the bias-safe `headline` block (never `overall`) and honor its provenance flags; surface `n_unbiased` as the sample size. Three distinct states per figure: **has-data / thin (n below an explicit floor → "n=4, not enough data") / empty (`None` → "—", never `0.0%`)**. Format-only the source float (no UI recompute, no averaging tier medians, no blending elapsed vs fixed windows — byte-parity with the harness), label it honestly as a **median elapsed-window MFE** with confirmed units, and render it as a **quiet baseline footnote strip** (inline figure+label pairs, mono/tabular, faint honesty cues — never a boxed hero-metric tile); each shown figure can drill to its cohort.

---

### 9. Nav rename: Dashboard → Journal (label-only)

| | |
|---|---|
| **Domain** | Fowler × Carmack — Two Hats + the economic test (refactoring P1, P8) |
| **Ref** | `references/refactoring.md` → P1, P8; cross-ref UX (mental model) |
| **Depends on** | — |

Change the user-facing nav label and the topbar `tabFromPath`/`activeTab` map from "Dashboard" to "Journal"; **leave the route path, `DashboardRoute`, `useDashboardData`, and `/dashboard` navigation intact** (renaming them is cross-file churn that buys nothing this week and risks the New-Trade flow that navigates to `/dashboard`). Make Home's distinct purpose self-evident on arrival so the trader reads "new orient surface added," not "my dashboard moved"; a one-time dismissable inline pointer is acceptable, a coachmark takeover is not.

---

### 10. Visual + interaction polish pass (impeccable)

| | |
|---|---|
| **Domain** | Saarinen × Friedman × Carmack — Component consistency + honest instrument (quality-ui P8, quality-ux P9) |
| **Ref** | `references/quality-ui.md` → P8; `references/quality-ux.md` → P9 |
| **Depends on** | 4, 5, 6, 7, 8 |

Final pass once the zones exist: reconcile the reused components to **one density grammar** (shared 6px radius, hairline, pill heights, label vocabulary — the inline cards should look pixel-identical to the grid's), **lock `tabular-nums`** on every live figure so columns hold under polling, hold the **One-Accent + Tier-Reserve** rules across the whole surface (blue only on affordances; tier hues only on tier identity; charts themed to ink-ramp + status hues), keep elevation tonal with glow/shadow reserved for the peek modal and hover/focus, and verify the action-first attention precedence (open-risk → at-trigger → fresh S/A) reads correctly. Run via the `impeccable` skill (`critique` then `polish`).

---

## Risks & Watchpoints

- **Ramírez — cache invalidation signature:** the scan-cadence cache must move when **forward-returns mature overnight**, not just on `(max_id, row_count)` (that tuple is blind to in-place value updates). A naive signature serves yesterday's edge after the nightly backfill. Watch when wiring Task 3's cache.
- **Leach — composite `(source, tier)` index:** as the archive grows, the edge read is a full scan. The scan-cadence cache (Task 3) is the primary defense; the index is a faster-but-additive DDL on the existing table — strictly a schema touch, so **confirm before adding** (see External Setup). Likely unnecessary at current size.
- **Friedman — staleness feeds the risk flag:** the Open-Book near-stop flag (Task 7) is only trustworthy if its price is known-fresh (Task 6/2 staleness). Build the per-source staleness signal before relying on the action-first flag. Pair with a UX check when wiring Task 7.
- **Hunt — keep the route off the broker surface:** the edge endpoint must live in a read-only router, never one that touches IBKR/orders. Single-user localhost CORS stays as-is.
- **Ramírez — config cwd-shadow trap:** any setting in Task 3 read lazily (`load_core_settings()`), never a module-level root-config import, or the service crashes on boot while tests stay green. Prefer keeping the endpoint config-free.
- **IBKR single-session constraint:** Open Book's snapshot can fail if TradingView holds the session — surface a named "IBKR session in use" error and degrade, don't blank.
- **WIP-file hard constraint:** none of these tasks touch `metrics.py` / `l2_staircase_*` / `tools/fidelity/l2/` — keep it that way; the rename (Task 9) must not churn into those surfaces.

---

## External Setup Required

| # | What | Why | Blocking task |
|---|------|-----|---------------|
| 1 | **Decision only:** confirm whether adding a composite `(source, tier)` index to `setup_archive` is in scope under "no schema change" | Task 3's edge read scans the archive; the index speeds it but is a DDL on the existing table | Task 3 (non-blocking — cache covers it; index is an optimization) |

No external accounts, API keys, or service config required — all tasks are in-codebase.

---

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Home route shell + visual hierarchy scaffold | Saarinen | — |
| 2 | Per-zone data foundation (status hooks, error isolation, visibility polling) | Dodds | — |
| 3 | Engine-edge endpoint (read-only service wrap) | Ramírez | — |
| 4 | Regime spine zone | Saarinen | 1, 2 |
| 5 | Fresh Setups zone | Dodds | 1, 2 |
| 6 | Watchlist zone | Friedman | 1, 2 |
| 7 | Open Book zone | Friedman | 1, 2 |
| 8 | Engine-Edge Pulse tile | McKinney | 2, 3 |
| 9 | Nav rename Dashboard → Journal (label-only) | Fowler | — |
| 10 | Visual + interaction polish pass (impeccable) | Saarinen × Friedman | 4–8 |

## Verdict

The single most important decision in this plan is **per-zone independence** — it shows up in five seats' recommendations because it's the architectural spine of the whole surface: own hooks, own status enum, own error boundary, own skeleton, isolated render. Get that foundation (Task 2) right and the command-center degrades gracefully on the exact mornings the trader most needs it; get it wrong and one throttled feed blanks everything. **Start with Tasks 1–3 in parallel** (shell, data foundation, endpoint — all independent), then build the four zones onto that foundation, then polish. The highest-stakes *correctness* seat is McKinney's edge pulse (Task 8): every pitfall lives in the display layer, and a flattering low-n number quietly poisons trust in the engine — so honor the three-state None/thin/has-data discipline religiously. Tasks 3–8 (backend endpoint + zones) are cleanly parallelizable across worktrees once 1 and 2 land.
