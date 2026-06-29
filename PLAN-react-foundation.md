# Council Plan: React Foundation Refactor (Lane B)

**Scope:** Lay a reusable React foundation for `webapp/frontend` so future surfaces are compositions, not copies: react-router + a shared AppShell, ONE `useLightweightChart` hook collapsing 5 copy-pasted chart implementations, a small set of UI-kit primitives + a theme/format module, and a best-effort hex→token codemod. **Refactor, not redesign** — preserve behavior and appearance.

**Context:** Plain React 19 + Vite SPA. Navigation is an in-memory `activeTab` string driving an `activeTab === X &&` chain in `App.jsx`/`AppContent.jsx` across 5 tabs (dashboard, options, portfolio, screener, archive). Five lightweight-charts v5 sites repeat the same imperative lifecycle with divergent bodies. `main.jsx` deliberately omits StrictMode (chart canvases can't survive remount). No frontend byte-parity harness — `npm run build` green + per-commit one-hat discipline is the substitute.

**Boundaries:** Frontend only (no Python). No new product features. Do not merge to main. Overlays (modals/drawers) stay overlay state, NOT routes. Panel/StatTile/DataTable built only where a real second consumer exists (AHA).

**Council dispatched:** Dodds (frontend) ✅, Fowler (structure) ✅, Saarinen (UI) ✅, Friedman (UX) ✅. Hunt/Ramírez/Leach/McKinney/Performance — no surface (frontend-only refactor, no auth/backend/data/engine-math/new-perf path); coverage confirmed by exclusion.

---

## Key validated findings (Carmack filter applied)

1. **The chart "config" is the LIFECYCLE, not a god-component.** Dodds + Fowler agree: the only true shared kernel is `createChart → BarSeries → optional volume → optional hl2 SMA → teardown`. Coloring/levels/markers/focus DIVERGE per site and must stay independent pure helpers. Build `useLightweightChart(containerRef, { chartOptions, candles, volumes, onReady })` with an `onReady(chart, candleSeries)` escape hatch. Do NOT lift `chartOptions` into the hook — per-site options (background, autoSize, interactivity) are the chart's identity. **Reject a fat `<CandleChart {...50 props}>`.**
2. **`fmtMoney` is a coincidental duplicate — DO NOT merge.** `tradeTableUtils.fmtMoney` returns a bare number; `portfolioFormat.fmtMoney` prepends `$`/sign/currency. Same name, opposite contract. Merging strips `$` off the trade table. Keep separate.
3. **`tierColor`: 3 inline copies (ScreenerCard/Modal/StockLens) are byte-identical** (`S:#ff9f43`) — safe to fold to one. The `archiveTabUtils` copy diverges (`S:#ff8c00`, adds `D` tier) — reconcile deliberately to DESIGN.md tokens (a 1-shade visual change, flagged).
4. **Canvas colors CANNOT be tokenized.** `var(--…)` does not resolve inside `createChart` (canvas can't read CSS custom properties). The hex→token codemod must EXCLUDE all lightweight-charts option objects. Chart backgrounds stay per-site hex.
5. **Overlays stay overlay state.** Screener modal (Prev/Next + D/W/M), trade drawer, calculator, position chart — putting them in the URL breaks browser Back during triage. Keep local.

---

## Task Sequence

### 1. Router + AppShell via parallel-change (routes render the existing components first)

| | |
|---|---|
| **Domain** | Fowler × Carmack — Refactoring is not restructuring / Strangler Fig (Principle 8) |
| **Ref** | `references/refactoring.md` → P8; cross-ref Dodds quality-frontend P2 |
| **Depends on** | — |

Introduce `react-router-dom` (already installed, v7.18) with one `AppShell` layout route (sidebar + topbar + `<Outlet/>`) and a nested route per tab rendering the **exact existing components unchanged**. `activeTab` becomes derived from the URL; the `activeTab === X &&` chain is deleted only once routes work (never both live in one commit). Index route redirects to `/screener` (today's default); a catch-all redirects unknown URLs to `/screener`.

---

### 2. Preserve cross-cutting state, ErrorBoundary topology, and startNewTrade across routing

| | |
|---|---|
| **Domain** | Dodds × Carmack — State escalation / colocation (Principle 2); Friedman — single-source active-nav |
| **Ref** | `references/quality-frontend.md` → P2; cross-ref `quality-ux.md` active-nav + remount |
| **Depends on** | Task 1 |

Cross-cutting state that outlives any tab (`detailTrade` drawer, `isCalcModalOpen`, `draftRow`, `tradeFilter`, CSV import, `useDashboardData`/`useIBKRStatus`/`useIbkrActions`, and the `useTradeLivePrices`→`TradeRiskAlerts` strip) stays lifted in the shell layout and renders once at the top, surviving navigation. `startNewTrade` becomes `navigate('/dashboard')` + the same `setDraftRow`. Active-nav highlight derives from the route (delete the parallel `activeTab` string). Each volatile route keeps its own inner `ErrorBoundary` + `Suspense` lazy boundary exactly as `AppContent` has today. **Match CURRENT remount behavior** (today `key="screener"`/`key="archive"` remount on tab-leave, so scan state is already discarded on switch — routing must not regress *below* that, and ideally preserves it; verify empirically).

---

### 3. `useLightweightChart` lifecycle hook + thin `<CandleChart>` wrapper

| | |
|---|---|
| **Domain** | Dodds × Carmack — Imperative libs live inside the effect (Principle 8); Fowler — economic refactor (P1) |
| **Ref** | `references/quality-frontend.md` → P8; `references/refactoring.md` → P1 |
| **Depends on** | — (independent of routing; can land in parallel) |

Extract the shared lifecycle into `useLightweightChart(containerRef, { chartOptions, candles, volumes, showVolume, onReady })`: `container.innerHTML='' → createChart → BarSeries → optional HistogramSeries volume → optional hl2 SMA → window resize listener → cleanup (`chart.remove()` + clear container, wrapped in the existing `try/catch`). Never store the chart in `useState`. `<CandleChart>` renders the `<div ref>` plus error/empty fallbacks. The chart is exposed to callers via `onReady(chart, candleSeries)` for site-specific drawing.

---

### 4. Move divergent chart bodies to co-located PURE helpers, pinned with unit tests FIRST

| | |
|---|---|
| **Domain** | Dodds × Carmack — Test behaviour not implementation (Principle 4) + colocate (P7) |
| **Ref** | `references/quality-frontend.md` → P4, P7 |
| **Depends on** | Task 3 |

Lift the off-by-one-prone transforms (`colorCandles`/`colorStructureCandles`, `setupIndexes`, `focusSetupRange`, `visibleRangeFor`, `buildLevelData`, `indexOnOrAfter`, `finiteNumber`) into co-located pure helpers and pin them with `node --test` unit tests over one fixture payload per site BEFORE wiring. Fold the triplicated `finiteNumber`/`indexOnOrAfter` (also in `chartIndicators.js`/`chartPhaseOverlay.js`) to one copy. The R/S phase box keeps using the existing `PhaseRegionPrimitive` (already a clean injectable v5 Series Primitive); levels keep `createPriceLine`.

---

### 5. Migrate the 5 chart sites one commit each, ascending risk, mini-chart last

| | |
|---|---|
| **Domain** | Fowler × Carmack — branch-by-abstraction, one hat per commit (Principle 8); Saarinen — pixel-diff checkpoint |
| **Ref** | `references/refactoring.md` → P8; cross-ref `quality-ui.md` P9 |
| **Depends on** | Tasks 3, 4 |

Order: `TradeSetupChart` → `PortfolioPositionChart` (simplest: candles+volume+lines, no overlay) → `TimeframeMainChart` → `useScreenerModalChart` (phase overlay + structure coloring) → `ScreenerMiniChart` (autoSize, non-interactive, focused logical range, on the perf-critical card wall) LAST. Each is its own commit with `npm run build` green and a visual check of that one surface. **Preserve each site's exact chartOptions** (background hex, fontSize, interactivity) as per-site config — do NOT converge backgrounds (out of scope; canvas can't read tokens anyway).

---

### 6. Theme + format module: fold the 3 identical helpers, rename the coincidental collision

| | |
|---|---|
| **Domain** | Fowler × Carmack — Mysterious Name + Two Hats / byte-parity (Principle 4, P8) |
| **Ref** | `references/refactoring.md` → P4, P8 |
| **Depends on** | — |

Create `theme.js` (one `tierColor` driven by new `--tier-s/a/b/c` tokens; `pnlColor`/`signColor`/`labelColor`/`rMultipleColor`). Point the 3 byte-identical inline `tierColor` copies (ScreenerCard/Modal/StockLens) at it. Reconcile `archiveTabUtils.tierColor` (S `#ff8c00`→token `#FF9F43`, keep its `D` tier) deliberately — flagged 1-shade change. **Do NOT merge the two `fmtMoney`** (different contracts); leave each in place or rename to reveal intent only if low-risk. Verify each replaced call site renders identical hex before deleting the original.

---

### 7. Add `--tier-s/a/b/c` tokens to `index.css :root` (+ DESIGN.md note)

| | |
|---|---|
| **Domain** | Saarinen × Carmack — Color through design tokens / Tier-Reserve Rule (Principle 5) |
| **Ref** | `references/quality-ui.md` → P5 |
| **Depends on** | — (gates Task 6's token references) |

Add `--tier-s: #FF9F43; --tier-a: #BB86FC; --tier-b: #58A6FF; --tier-c: #3FB950;` to `:root` using exact DESIGN.md values, and a `--tier-d` for archive's neutral. The theme module's `tierColor` resolves these. One source of truth so card and modal can never render a different tier shade.

---

### 8. UI-kit primitives — Modal now (proven reuse), Panel/StatTile/DataTable only where a 2nd consumer exists

| | |
|---|---|
| **Domain** | Dodds + Fowler × Carmack — AHA / wrong-abstraction is systemic (Principle 1); Saarinen — surface ramp |
| **Ref** | `references/quality-frontend.md` → P1; `references/refactoring.md` → P6; cross-ref `quality-ui.md` P7 |
| **Depends on** | Task 7 |

Build `Modal` first (overlay + Escape + stopPropagation recurs in PortfolioPositionChart/CalculatorModal/ScreenerModal) with composed `children`/slots — not `showHeader`/`variant` flags — encoding the surface ramp (`--bg-elevated` + elevated shadow + 12px radius). Build `Panel` (resolves `--bg-panel`, used by the existing loading panel + cards) and a `StatTile` ONLY if ≥3 real call sites share it today; otherwise defer and report as follow-up. `DataTable` is deferred unless archive+trade tables genuinely share a shape (likely too divergent — report rather than force). All primitives are dumb/presentational, no data fetching.

---

### 9. Hex→token codemod (best-effort), excluding all canvas option objects

| | |
|---|---|
| **Domain** | Dodds × Carmack — token bypass / colocate styling (Principle 7) |
| **Ref** | `references/quality-frontend.md` → P7 |
| **Depends on** | Tasks 3, 7 |

Replace a hardcoded hex ONLY when it exactly equals a defined `:root` token value (e.g. `#5B8AFF`→`var(--accent-blue)`), scoped to JSX/CSS style values. **Explicitly EXCLUDE** every lightweight-charts `createChart`/series option (backgrounds `#171922`/`#141721`/etc., bar `#d8dbe5`, grid rgba) — `var()` evaluates empty in canvas and blanks the chart. Highest-traffic files first; unmatched hex stays as-is; report what's left.

---

## Risks & Watchpoints

- **Saarinen — pixel-diff checkpoint (P9):** After each chart/primitive migration, eyeball that surface against the pre-refactor build. Only intended deltas (tier shade reconciliation) should move; catch a dropped hairline/padding/radius in the moment. Pair with the `verify`/preview tooling.
- **Friedman — route remounts must not regress in-flight state (P3):** A completed scan grid + applied filters must survive a tab round-trip *at least as well as today*. Verify mounting/unmounting routes doesn't trigger a re-scan or reset filters. Watch during Task 2.
- **Friedman — refresh contract changes deliberately (P9):** Routing makes refresh restore the current view (today it resets to screener). Acceptable and correct, but must be TOTAL — every tab round-trips through refresh to the same place with correct active-nav. No half-state.
- **Dodds — no chart in `useState` / single-mount contract (P8):** The no-StrictMode single-mount assumption and the `try/catch`-wrapped `chart.remove()` must be preserved verbatim in the hook, or the 100-card wall leaks a canvas+ResizeObserver per card.
- **Fowler — `fmtMoney` collision (P4):** Never merge the two `fmtMoney` under one name. A "dedupe" that strips `$` off the trade table is a behavior regression wearing a refactor's hat.

---

## External Setup Required

No external setup required. `react-router-dom@7.18` is already installed in the worktree; all tasks are within the codebase.

---

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Router + AppShell (parallel-change) | Fowler | — |
| 2 | Preserve cross-cutting state / boundaries / startNewTrade | Dodds + Friedman | 1 |
| 3 | `useLightweightChart` hook + `<CandleChart>` | Dodds + Fowler | — |
| 4 | Pure chart helpers + unit tests first | Dodds | 3 |
| 5 | Migrate 5 chart sites, one commit each | Fowler + Saarinen | 3, 4 |
| 6 | Theme/format module (fold 3, rename collision) | Fowler | 7 |
| 7 | `--tier-*` tokens in index.css | Saarinen | — |
| 8 | UI-kit primitives (Modal now, rest if justified) | Dodds + Fowler | 7 |
| 9 | Hex→token codemod (exclude canvas) | Dodds | 3, 7 |

## Verdict

The single most important decision is **refusing the fat `<CandleChart>` config object** — both Dodds and Fowler independently identified that the 5 charts share only a lifecycle, and unifying their divergent bodies (coloring/levels/focus) into one prop-bag would re-couple sites that must stay independent and re-introduce the exact twin-divergence hazard this codebase's fold-pattern exists to kill. The hook owns the lifecycle; sites compose pure helpers. Frontend architecture (Dodds) is the critical domain. **Start with Task 3** (the hook + the simplest two chart migrations) and Task 1 (router) in parallel — they're independent, both low-risk, and each is provable with `npm run build`. The one trap to never trip: blind-merging `fmtMoney` or silently recoloring a tier. One hat per commit, build green at every step.
