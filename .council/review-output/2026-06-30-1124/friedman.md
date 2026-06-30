# Friedman — UX Quality Review (Multi-Universe Screener, 2026-06-30-1124)

## Domain Verdict

From a UX standpoint the multi-universe + drill-down model is **coherent and surgical — keep fixing at the seams, do not rebuild the IA.** The navigation grammar is deliberately right: the universe switcher is positioned as a *context selector reusing the toolbar's tier-pill grammar*, not a third nav tier (`UniverseSwitcher.jsx:3-7`), so switching universes is the same instrument viewed three ways rather than three apps. The drill-down deepens this rather than forking it: it renders the SAME card grid with one quiet lineage header and an explicit "from the US-Stocks scan" hand-off (`ScreenerGrid.jsx:216-238`), so the trader never loses the mental model — they are always reading ranked Wyckoff cards, just scoped. The three prior-review wounds are genuinely closed: `handleUniverseChange` closes any drill-down (`backToGrid()`), resets filters, and resets the page in one atomic transition (`ScreenerGrid.jsx:35-41`); ETF Download/Evaluate are disabled with an explaining tooltip instead of dead no-ops (`ScreenerToolbar.jsx:18-22, 43-57`); and stale-resolve races are token-guarded in both `useScreenerData` (`activeUniverseRef`) and `useDrilldown` (`requestRef`). The `us_stocks`-key/`us_equities`-type split lives entirely backend-side and never surfaces here, so it costs the trader nothing. The residual issues below are all *boundary leaks of the same kind the prior rounds fixed* — screen-state copy that contradicts itself, a freshness stamp that the new "scheduled scan" universes now require, and generic error copy on a fragile data path — i.e. normal hardening of a sound design, not evidence of an IA that needs rethinking. The structural smell is not the navigation model; it is that screen-state messaging is computed in two places (the toolbar count line vs. the grid's `EmptyState`) that can disagree.

---

FINDING:
- Title: Toolbar "N setups matched your constraints" contradicts the grid's empty/never-scanned/loading/error states
- File: webapp/frontend/src/components/ScreenerGrid.jsx:101-113 (toolbar always rendered) + ScreenerToolbar.jsx:35-37 (count line)
- Principle: Principle 2 — Design all five screen states (blank/loading/partial/error/ideal); also Principle 9 — trust is destroyed by inconsistent messaging
- Severity: P2
- What's wrong: The toolbar renders unconditionally and always prints "{matchedCount} setups matched your constraints." When `status` is `never_scanned`, `loading`, `error`, or `empty`, `filteredTickers.length` is 0, so the trader sees "0 setups matched your constraints" sitting directly above the grid's "No scan yet for Sectors + Market" / "Couldn't load this screener" message. The count line claims a scan ran and matched nothing (a filter problem) while the grid correctly says no scan exists or the load failed — two contradictory explanations of the same screen.
- Consequence: On every freshly-switched ETF universe (the common case, since those refresh on a schedule and may have no artifact yet) the trader reads conflicting copy and can't tell whether to loosen a filter, run a scan, or wait for the scheduled one.
- Fix: Suppress or rephrase the matched-count line unless `status === 'ready'`; when no scan/data is present it should either be hidden or echo the grid's actual state rather than asserting a zero match against constraints.

FINDING:
- Title: No data-freshness stamp on the grid — acute now that ETF universes are scheduled-scan-only
- File: webapp/frontend/src/components/ScreenerGrid.jsx:89-204 (no "scanned at" anywhere); ScreenerToolbar.jsx:35-62 (status strip shows cache health, not scan recency)
- Principle: Principle 6 — Missing data-freshness indicators
- Severity: P2
- What's wrong: Nothing on the screener surfaces when the displayed scan was produced. For US Stocks the trader at least drives Download/Evaluate manually so they have a rough sense of recency, but the two ETF universes are explicitly "refreshed by the scheduled daily scan" (`ScreenerGrid.jsx:157-159`) and the trader never triggers them — so they have zero signal whether they're reading today's batch or a three-day-old one. The `MarketDataStatus` strip reports cache *health/coverage*, not *when this scan ran*, and is itself disabled-irrelevant for ETF universes.
- Consequence: A discretionary trader can bridge an ETF setup to TWS/TradingView off a stale scan without any cue the ranks are days old — exactly the "deciding off stale prices" failure the freshness principle warns about, and worse once scans run fully unattended.
- Fix: Surface a visible "scanned at HH:MM · DD MMM" stamp on the grid (the screener payload should already carry a scan timestamp); make it the primary recency cue for the ETF universes where the cache-health strip is muted.

FINDING:
- Title: Generic scan/data-failure copy doesn't name Chrollo's real failure modes
- File: webapp/frontend/src/hooks/useScanRunner.js:138-145 (errorMessageForJob); webapp/frontend/src/components/ScreenerGrid.jsx:153-155 (load-error EmptyState)
- Principle: Principle 2 — Avoid generic error messages
- Severity: P2
- What's wrong: When an evaluation or download stops, the banner reads "Cached evaluation stopped before results were ready." / "The data refresh stopped before the cache was ready." appended with a raw backend `ERROR:` suffix. The load-failure empty state is the generic "Couldn't load this screener. Check the backend is running and try again." Neither names the dominant, *known* Chrollo failure modes — yfinance rate-limiting/429 storms, quarantined-dead tickers, a partial fetch — so the most common real cause is invisible and the recovery ("retry in a minute" vs. "restart backend") is a guess.
- Consequence: When Yahoo throttles the daily refresh (a documented recurring failure), the trader sees a vague "stopped before ready" and re-clicks immediately into the same rate-limit instead of being told to wait, eroding trust in the refresh button.
- Fix: Map the backend's known error signatures (rate-limit/429, partial coverage, quarantine, stale session) to specific actionable copy with the right recovery and wait hint; keep the generic line only as the final fallback.

FINDING:
- Title: Drill-down view has no Esc / keyboard exit and the only "Back" affordance is an arrow glyph
- File: webapp/frontend/src/components/ScreenerGrid.jsx:69-87 (keydown effect handles modal only, gated on activeModalTicker), 220-232 (DrilldownView Back button)
- Principle: Principle 4 — Modal-like content must support a close/escape route; Principle 7 — keyboard for the repetitive loop
- Severity: P3
- What's wrong: The drill-down replaces the whole grid with a scoped view whose only exit is clicking the "← Back" button in the lineage header. The global keydown handler (`ScreenerGrid.jsx:69-87`) early-returns unless `activeModalTicker` is set, so Esc does nothing in the drill-down (when no card modal is open). The card modal supports Esc + arrow cycling; the drill-down, which is the deeper navigation level, supports neither.
- Consequence: A trader who drills ETF→equities and wants out reaches for Esc (which works one level up, in the modal) and nothing happens, breaking the muscle-memory the modal just taught them; the back path is mouse-only.
- Fix: Let Esc trigger `onBack` when a drill-down is open and no card modal is in front; keep the visible "Back" control but stop making it the sole exit.

FINDING:
- Title: Switching universes mid-scan strands the in-flight job against the wrong universe with no warning
- File: webapp/frontend/src/components/ScreenerGrid.jsx:35-41 (handleUniverseChange); useScanRunner.js:48-69 (revealResults/finishJob call fetchScreener(universe) captured at startJob)
- Principle: Principle 3 — never freeze/confuse on input transitions; Principle 2 — partial/transition state
- Severity: P3
- What's wrong: `handleUniverseChange` does not block or acknowledge an active Download/Evaluate. The scan runner closed over the universe at `startJob` time, so a US-Stocks evaluation started, then a switch to an ETF universe, leaves a job whose `revealResults`/`finishJob` fetch and reveal the *old* universe while the switcher shows the new one. The Download/Evaluate buttons are also already disabled for ETF universes, so the trader can't even re-drive the job from where they land.
- Consequence: A trader who switches universes while a scan is still finishing sees the progress/reveal logic operate on a universe they're no longer looking at, with no cue that the running job belongs elsewhere — a confusing transition, though self-correcting on the next manual action.
- Fix: Either disable the universe switcher while a manual scan job is active (with a tooltip naming the running job), or cancel the in-flight job on switch the same way the drill-down is closed. Out of scope for visual treatment — this is the interaction guarantee.

---

No further P1 findings. The five screen states are otherwise present and distinct (`useScreenerData.deriveStatus` separates `never_scanned`/`empty`/`loading`/`error`/`ready`, and the drill-down mirrors them with its own `loading`/`error`/`empty`-with-basis split), structure is not oversimplified, filters stay client-side and live, and ranks carry their why-ranked evidence on the card — so the core triage loop is intact across all three universes and the drill-down.
