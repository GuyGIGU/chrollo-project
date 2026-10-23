# Finviz workflow review and Chrollo structure pass

Reviewed 2026-10-23. Source changes are in `codex/engineering-quality`, alongside
the earlier quality and shortlisting work, merged into main on 24 October; deployment
remains the operator's `update_dashboard.bat`.

## Finding

The most useful Finviz pattern for Chrollo is **one filtered result set, several
ways to inspect it**. Finviz exposes overview, technical, performance, chart and
snapshot views under the same screener. Its help emphasizes information density,
fast navigation and saved filter presets. These address the operator's stated
problem: finding and shortlisting setups.
Sources: [public screener](https://finviz.com/screener/stocks?v=111),
[screener help](https://finviz.com/help/screener).

This is a reconstruction of public product behavior, with an independent Chrollo
implementation. Finviz's server code, ranking internals, data infrastructure and
authenticated workflows were not available for inspection.

## What the public pages establish

| Observed pattern | Evidence | Chrollo application |
|---|---|---|
| Separate filter categories, a visible result count and a reset action when filtered | [USA-filtered overview](https://finviz.com/screener/stocks?v=111&f=geo_usa) | Keep the current visible query summary and removable chips. Add filters only when their data and daily use justify them. |
| A view change preserves the filter: the USA chart link retains `f=geo_usa` while changing `v=111` to `v=211` | [USA chart view](https://finviz.com/screener/stocks?f=geo_usa&v=211) | Charts and Table use the same selected ticker list and URL state. |
| Different views emphasize different comparisons | [technical view](https://finviz.com/screener/stocks?v=171), [snapshot view](https://finviz.com/screener/stocks?v=341) | Compare key setup facts in a dense table; open the existing lens for the structural story. |
| Filter combinations can be saved as presets | [official screener help](https://finviz.com/help/screener) | Named saved views are the next useful extension of Chrollo's existing bookmarkable URLs. |
| Maps and groups provide market context | [maps help](https://finviz.com/help/maps), [groups](https://finviz.com/groups) | Build on the existing sector health board and stock drill-down. A second market-map implementation is lower priority. |

Finviz also advertises advanced filters, interactive multi-layout charts,
screener notifications and exports in its [Elite description](https://finviz.com/elite).
Those are documented capabilities, not authenticated behavior verified in this
review. Their presence does not establish which infrastructure or algorithms
Finviz uses.

The REA runtime attempt launched an owned temporary Edge instance, navigated to
the public screener and waited for its body. It reached a verification page titled
"Just a moment...", rather than the screener. No challenge was completed. The
owned process was terminated. Runtime evidence:
`ev_12de0e69b9c6de2c3c85bd2df56331f9e88eb7ea1939a8b4ecb7eb2596f11cad`.
The product findings above come from accessible public pages and official help;
the runtime attempt proves only that access limitation.

## Built in this pass

- A Charts/Table switch in the result summary. `?view=table` survives reload and
  copied URLs. Charts remains the default.
- Both presentations consume the same filtered, sorted, paginated ticker list.
  Switching keeps the current query and page; Clear filters keeps the selected
  presentation. Neither presentation changes engine ranking.
- The table compares tier, TA grade, setup, scan price, trigger, RS and base days.
  Missing measurements remain dashes. A missing TA grade never falls back to the
  legacy raw score. Scan price is labeled explicitly, without implying a live quote.
- Table hearts and stars use the existing save paths. Stars carry the displayed
  scan identity, just like the cards and lens.
- A ticker opens the existing lens. Next/Prev follow the full filtered list;
  closing returns focus to its ticker. Arrow navigation also works in the table.
- Horizontal scrolling stays inside the comparison region on narrow screens.

The real frontend review used the already-running backend read-only. It showed
six liked setups among 269 charts from the 22 October scan. No real shortlist,
scan, trade or broker action was performed. Save behavior was exercised only
against the browser suite's synthetic API.

## File-structure findings and cleanup

The repo's top-level domain split already has clear ownership: `engine_alpha`
reads and judges, `core` coordinates and archives, `webapp` presents, `tools`
contains instruments, and `tests` protects behavior. The audit found no generic
`utils`, `helpers`, `common` or `misc` source modules. Existing compatibility
paths have documented consumers in [architecture.md](architecture.md).

Two concrete ownership issues were corrected:

| Responsibility | Canonical location after this pass | Why |
|---|---|---|
| React subscription to the shared scan cache | [shared/hooks/useScreenerData.js](../webapp/frontend/src/shared/hooks/useScreenerData.js) | Home and Screener both use it. The shared hook now sits beside its shared store; Home no longer imports this hook from the Screener feature. |
| Pure result selection, tag projection and display sorting | [screener/model/screenerResults.js](../webapp/frontend/src/features/screener/model/screenerResults.js) | Removed from the React hook into its feature's model layer. Selection can be tested directly without React or a browser. |
| Comparison table | [ScreenerResultsTable.jsx](../webapp/frontend/src/features/screener/components/ScreenerResultsTable.jsx) | Feature-owned presentation; no duplicated selection, network state or scoring logic. |

All current callers were repointed; the moved hook has no compatibility wrapper.
Historical migration records retain their historical paths. The frontend import
guard now detects cycles of any length and rejects shared production code that
imports a feature. Previously it detected only mutually importing feature pairs.

The largest modules still warrant responsibility reviews: archive `writer.py`,
calibration `router.py`, scan lifecycle and market-data coordination. Size alone
does not justify a split. The next backend cleanup should separate calibration
chart retrieval/replay from mark writes and box corrections, with its existing
frame provenance, write guards and patch-sensitive tests preserved. Startup DB
initialization and archive transaction ownership remain the separate work listed
in [the dependable-daily plan](dependable_daily_2026-10.md).

## Next adaptations, in order

1. **Named saved views.** Save the canonical universe/filter/sort/presentation
   query under an operator name. Restore it without retaining an open lens or
   drill-down. Distinguish a saved query from a frozen shortlist or scan snapshot.
2. **Export the selected results.** Export the whole matching set, not just the
   visible page, with scan identity, measurement units and missing values intact.
   This would make the handoff to the operator's other tools easier to inspect.
3. **Faster context inspection.** Reuse the existing chart/lens and glance
   infrastructure; preserve focus and scroll while examining candidates. Measure
   shortlist time before adding another charting library or a separate workspace.
4. **Freshness and review history.** Make service health, scan completeness and
   each symbol's session coverage distinguishable. Preserve the exact reviewed
   artifact and show what changed since that review.

Finviz supplies workflow ideas, not evidence for changing Chrollo's structural
rules or score weights. Preference evaluation still needs the operator's positive
and negative examples, held-out cases and archived outcomes.

## Verification

- The current branch has 609 JavaScript tests, including pure selection and import
  ownership checks; obsolete card-grid cases were retired with that interface.
- 20 browser checks cover the production frontend build with synthetic APIs.
  New cases cover presentation switching, reload, keyboard/lens focus, shortlist
  persistence and scan identity, null numbers and narrow-screen scrolling.
- Frontend lint and the isolated worktree production build pass.
- 13 Python architecture/pointer tests pass: moved-module paths, production/tool
  import boundaries and evidence pointers. The explicit pointer audit also passes.
- The backend was never booted or restarted. No engine or scoring code changed.

## Operator Watchlist redesign

The operator's 23 October reference calls for a compact ticker list. The
dedicated Watchlist filter and manager have moved off the Screener; stars on
cards, the comparison table and the lens still save to the Watchlist tab. An
old `?tier=WATCHLIST` bookmark reads as All rather than a hidden empty subset.

The Watchlist tab now reuses `InstrumentTable` for a dense sortable ledger:
Added date, setup, tier, TA grade, last quote, saved price, percentage versus
saved price, RS, market cap in billions, sector, industry, scan membership,
heart and removal. Newest saves appear first, including off-scan names. Search,
sticky headers, banded rows and restrained return colors follow the reference's
layout. The current-scan tier/grade remain distinct from saved facts.

Five optional active-save response fields quote the original stored snapshot:
`saved_setup`, `saved_price`, `saved_market_cap`, `saved_sector`, `saved_industry`.
They require no migration, vendor fetch or re-pin. Missing, malformed or unsupported
snapshots stay null. Current quotes are compared with the stored scan price;
this is a price comparison, not an executed trade return or the reference's
historical maximum-return windows. Those 60/30/14/7/2-day windows and the reference's
custom ready/top/side controls are outside this presentation change.

Daily/weekly/monthly charts, the engine-overlay toggle and candle retry now open
from a row in a dialog, with Prev/Next, keyboard navigation and return focus.
Hover previews, historical review/replay, likes and removal with Undo remain.
The removed card wall's batch cache and obsolete selection/style code were
removed with it. The general backend candle endpoints remain available.

The navigation grows from a 52px to a 60px minimum height; tab text, icons and
padding grow slightly. Responsive wrapping remains covered by browser checks.
An existing quote-loading delay was fixed: membership arriving after mount now
triggers a quote fetch immediately, with older responses ignored after a newer
request or membership change.

The actual frontend review loaded the existing 16 saved tickers and inspected
the TEVA D/W/M chart without a real list or broker mutation. The running backend
still uses its previous response shape, so newly exposed saved facts remain
dashes in this preview until integration and the operator's ordinary update.
Producing tests exercise the new fields against stored snapshots in a throwaway
database. Verification includes 52 watchlist/API contract tests, plus the frontend
tests and browser checks above. No service was restarted.

### Review fixes (23 October)

The pass's code review named three UI bugs; each fix has a check that fails without it:

- **Undo during a removal still saving.** Undo used the star's toggle, which drops a
  click while that ticker has a write in flight, so the ticker stayed removed.
  `restoreWatchlist` waits for the removal to settle and saves again unless a failed
  removal already restored it (`watchlistStore.test.js`; the held-DELETE browser case).
- **Alt+arrows.** The Watchlist chart dialog and the screener lens took every arrow,
  so Alt+Left / Alt+Right (the browser's Back / Forward) stepped the chart instead.
  Both now leave keys with Ctrl, Alt or Meta to the browser (`hasCommandModifier`).
- **Clipping at 130% UI scale.** The dialog renders inside `.app-layout`'s `zoom`, so
  its `96vw` / `82dvh` grew by the scale; they are now divided by `--ui-scale`, as
  `.app-layout`'s own height is (`uiScale.test.js` pins the rule; the browser case
  measures the dialog inside the window).
