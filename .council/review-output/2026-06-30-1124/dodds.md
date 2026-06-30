# Kent C. Dodds — Frontend Quality Review (2026-06-30-1124)

## Domain Verdict

**The universe-switching frontend architecture is SOUND — keep fixing surgically; do NOT refactor toward a unified fetch/status machine.** The `universe` key is a single source of truth held in the URL (`?u=`), threaded as a plain prop into `useScreenerData`, `useScanRunner`, and the grid — there is no hidden universe state to fall out of sync. Each fetch concern owns exactly one coherent slice: `useScreenerData` owns the per-universe payload cache + status, `useDrilldown` owns the drill-down fetch, `useScanRunner` owns the SSE job lifecycle. The two prior-flagged seams are now genuinely closed and the fixes are well-constructed: `useScreenerData` keys its cache by universe and gates `setStatus` behind an `activeUniverseRef` so a late response can only write the (keyed, safe) cache and never stamp a stale status onto the visible universe; `useDrilldown` was correctly extracted into a status-mirroring hook with a request-token staleness guard, killing the prior twin fetch path. Crucially, these three hooks deliberately do NOT share a status enum, and that is the *right* call by AHA Programming — they have different status vocabularies (`never_scanned`/`empty`/`ready` vs `loading`/`empty`/`error` vs job phases) and forcing them into one "universe fetch machine" abstraction would be the wrong abstraction propagating through every consumer. The seam is leaky at the *Python* boundary (cache write, archive scope, episode identity), but the *React* boundary is now clean and convergent. That said, the latest round left the drill-down hook's unmount guard inert and the filter-reset fix only half-applied — both surgical, neither structural.

---

FINDING:
- Title: `useDrilldown` unmount guard is inert — `mountedRef` is force-set true on every render with no cleanup
- File: webapp/frontend/src/hooks/useDrilldown.js:41 (and 16, 24, 29)
- Principle: Imperative resource lifecycle / effects clean up what they create (Principle 8) + boundary discipline (Principle 3)
- Severity: P2
- What's wrong: `if (typeof window !== 'undefined') mountedRef.current = true;` runs in the render body every render and unconditionally re-asserts `true`; there is no `useEffect` cleanup that ever sets it to `false`, so the `!mountedRef.current` checks in the `.then`/`.catch` handlers can never short-circuit on a real unmount.
- Consequence: A drill-down fetch that resolves after the grid unmounts (universe nav away, route change mid-flight) calls `setDrilldown` on a dead component — a React "set state on unmounted component" warning and a wasted render path that the guard was written specifically to prevent.
- Fix: Replace the render-body assignment with a `useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, [])` exactly as `useScreenerData` already does, so the flag actually flips false on teardown.

FINDING:
- Title: Universe switch leaks `tierFilter` and `searchTerm` — prior filter-persistence fix only half-applied
- File: webapp/frontend/src/components/ScreenerGrid.jsx:35-41 (with hooks/useScreenerFilters.js:51-56)
- Principle: Make impossible/misleading states unrepresentable (Principle 3) — boolean/filter combo gating a data view
- Severity: P2
- What's wrong: `handleUniverseChange` calls `filters.resetFilters()`, but `resetFilters` only clears `setupFilter`/`tagFilter`/`sortBy`/`currentPage` — it does NOT reset `tierFilter` or `searchTerm`, the exact two the prior review (#8) named ("a stale WATCHLIST tier filter applies to the new universe"). A user on tier `S`/`WATCHLIST` or with a typed search carries it into a universe where it matches nothing.
- Consequence: A freshly-populated universe renders "No setups match the current filters" (or, on WATCHLIST tier, an empty watchlist panel) and reads as broken, re-opening the bug the last round was meant to close.
- Fix: Have the universe-switch path clear tier and search too (reset to `ALL`/empty) — either widen `resetFilters` to cover them or add explicit `setTierFilter('ALL')`/`setSearchTerm('')` calls in `handleUniverseChange`.

FINDING:
- Title: `useScreenerData` keeps the per-universe payload in both `useState` and a parallel `useRef` mirror
- File: webapp/frontend/src/hooks/useScreenerData.js:19,26,56-57,96
- Principle: Eliminate state that can be derived; don't sync two copies (Principle 2)
- Severity: P3
- What's wrong: The payload cache is held simultaneously in `byUniverse` (state) and `cacheRef` (ref), written together on every fetch (`cacheRef.current = {...}; setByUniverse(cacheRef.current)`). The ref exists only for synchronous reads inside the fetch callback, but it duplicates the state's identity and any future write that updates one without the other silently desyncs the cache.
- Consequence: Low today (writes are paired), but it's a two-source-of-truth seam that will bite the next person who adds a cache-eviction or invalidation path and updates only one copy.
- Fix: Either drop `byUniverse` state and trigger re-render via a small version counter while reading the ref, or drop the ref and read latest state through the functional-updater form — keep one authoritative copy of the cache.

FINDING:
- Title: Earnings negative-cache (`requestedRef`) never clears across universe switches
- File: webapp/frontend/src/hooks/useScreenerData.js:23,78-94
- Principle: Server/API state lifecycle tied to the wrong scope (Principle 2)
- Severity: P3
- What's wrong: `requestedRef` (the "already asked the backend" set) and `earningsByTicker` are not scoped to or reset on `universe` change, unlike the payload cache which is keyed by universe. A ticker that appears in two universes is fetched once and the first universe's earnings row is reused.
- Consequence: Minor and arguably fine (earnings are ticker-intrinsic, not universe-specific), but the asymmetry — payload is universe-keyed, earnings is global — is the kind of inconsistency that invites a future "why is this stale" hunt; worth a one-line comment documenting the intentional global scope if not a reset.
- Fix: Add a short comment asserting earnings are deliberately universe-agnostic (ticker-intrinsic), or key/reset the earnings caches by universe to match the payload cache's discipline.
