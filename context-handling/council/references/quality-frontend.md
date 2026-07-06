# Frontend Quality Reference — Carmack × Dodds

Philosophy: John Carmack. Specifics: Kent C. Dodds (React Testing Library, Epic React, AHA Programming).
Stack context: **React 19 SPA built with Vite** (no RSC, no Server Components/Actions) / JSX / `lightweight-charts` + `recharts` / FastAPI JSON backend / the project's own "Instrument Panel" design system. NOT Next.js, NOT TypeScript, NOT Tailwind.

Every finding must describe the **concrete cost of getting it wrong** — not just "this is bad practice."
The Pipeline-performance skill covers heavy memoization, list virtualization, bundle size, and chart render cost. **Do not duplicate raw performance findings here.** Focus on correctness, maintainability, testability, and architectural quality. The one exception this doc *owns* is imperative-chart lifecycle (Principle 8), because getting it wrong is a correctness/leak bug, not a micro-optimization.

---

## Principle 1: Duplication is local damage; wrong abstractions are systemic damage

*Carmack: simplicity over cleverness, concrete over abstract.*
*Dodds (AHA Programming): "prefer duplication over the wrong abstraction." — via Sandi Metz.*

Premature abstraction is the most expensive frontend mistake. Dodds: **"If you abstract early, you'll think the function or component is perfect for your use case and so you just bend the code to fit your new use case. This goes on several times until the abstraction is basically your whole application in `if` statements and loops."**

The cost isn't aesthetic — wrong abstractions are terrifying to change because every caller depends on the shape. Duplication is fixable locally; a bad abstraction propagates through every consumer.

### What to check

**Premature component splitting**
- Components split into multiple files when only used in one place. Dodds: "It's WAY easier to maintain it until it needs to be broken up than maintain a pre-mature abstraction." A `ScreenerCard` that reads cleanly top-to-bottom beats six 25-line fragments wired by props.
- Dodds: **"You'll be surprised how simple a big render method can be when you just inline as much as you can."**
- The concrete cost of premature splitting: more files → more props → more prop drilling → pressure to add Context/store → compounding complexity.
- Only split when one of these is concretely true: (a) same UI needed in multiple places (e.g. the mini-chart genuinely reused in card + modal), (b) can't tell which state relates to which JSX, (c) need isolated testing of edge cases, (d) git conflicts are unmanageable.
- Severity: **P3** — unless the splitting has already caused prop drilling that triggered a global store (**P2**)

**Premature hook extraction**
- Custom hooks extracted for "separation of concerns" with a single call site. Apply AHA to hooks: don't extract until reuse is real. Note that Chrollo's hooks (`useScanRunner`, `useScreenerFilters`, `useWatchlist`) earn extraction — they each own a coherent slice of stateful logic with real call sites. A one-off `useFormatTicker` does not.
- Dodds: "Apply the AHA Programming principle and wait until the abstraction/optimization is screaming at you before applying it."
- Exception: context consumer hooks are always appropriate — they enforce the provider boundary.
- Severity: **P3**

**Premature abstraction layers**
- Generic `<DataTable>` components with 15 props when only the archive table and the trade table share two columns. A "config object" prop bag is usually a wrong abstraction in disguise.
- Component "libraries" with one consumer.
- Wrapper components that just forward all props (the `{...rest}` anti-pattern without actual logic).
- Severity: **P3** — unless the abstraction is actively causing bugs due to if-statement branches (**P2**)

---

## Principle 2: Eliminate state that can be derived, then colocate what remains

*Carmack: minimise state — less state means fewer bugs.*
*Dodds: "Don't Sync State. Derive It."*

**This is the highest-alignment point between Carmack and Dodds.** Every piece of stored state that could be computed is a synchronisation bug waiting to happen. Dodds: **"The biggest problem with this is some of that state may fall out of sync with the true component state. It could fall out of sync because we forget to update it for a complex sequence of interactions."**

The fix: calculate during render. `useScreenerFilters` derives `filteredTickers`/`paginatedTickers` from `screenerData` + filter inputs every render — zero sync risk. Dodds: **"We don't need to worry about updating the derived state values because they're simply calculated every render."**

### What to check

**Derivable state stored in useState**
- Any `useState` whose value can be computed from other state or props. This is the #1 frontend correctness bug. A `filteredTickers` copied into state and re-synced when filters change is a guaranteed stale-grid bug; derive it.
- Any `useEffect` that exists solely to synchronise two pieces of state — the "state sync" anti-pattern.
- Props stored in `useState` and synced via `useEffect` — derive from props directly during render instead. (Watch the `ScreenerCard` `watchlisted={watchlist.has(ticker)}` flow: it's derived at render from the `watchlist` Set, which is correct. Copying it into local state would invite drift.)
- Severity: **P1** when the derivable state controls a critical flow (the live trade/risk panel, a position-size calc, an order-staging view). **P2** for screener/archive UI sync bugs.

**State lifted too high**
- State in a top-level store or Context consumed by a single component or subtree. Dodds: "Ask yourself 'do I really need the modal's status (open/closed) state to be in Redux?'" The `activeModalTicker` lives in `ScreenerGrid` — exactly where it's used — not in app-root state.
- The cost: every update to high-lifted state invalidates the entire tree beneath it (the whole 480px-card chart wall), forcing `React.memo`/`useMemo`/`useCallback` everywhere, which Dodds calls **"death by a thousand cuts"** complexity.
- Severity: **P2** when it's causing real re-render cascades across the card wall. **P3** when it's just misplaced but not yet harmful.

**Server/API state treated as UI state**
- FastAPI response data (screener results, archive rows, IBKR live prices) manually copied into `useState` and then mutated alongside UI flags. Dodds: "I would take the data I got from the server and treat it like it was UI state… and this resulted in making *both* more complex."
- Keep the fetched payload (`screenerData`, the archive page) in its own fetch-owning hook and derive view state from it; don't merge "is this row selected" into the row data you got from the backend. SSE-driven data (`useSSE`, scan progress) is server state — own it in one place, render from it.
- Severity: **P2**

**The state escalation framework** (check that the code follows this order):
1. `useState` — for independent local state
2. Lift state up — to the closest common parent when siblings need it
3. Component composition — use `children`/slots to skip intermediate layers
4. `useReducer` — when state elements are interdependent (Dodds: "When one element of your state relies on the value of another element of your state in order to update")
5. React Context — scoped to the relevant subtree, NOT at the app root
6. External store — only for genuinely complex cross-cutting state (there is no global server-cache library here; fetch-owning hooks fill that role)

---

## Principle 3: Validate at the boundary; impossible states unrepresentable

*Carmack: "Use the type system as armour." Here the armour is runtime discipline at the JSON boundary + lint.*
*Dodds: places static analysis at the base of the Testing Trophy — always on, catches whole categories of bugs, costs nearly nothing.*

This is a **JSX** codebase, so there is no compiler watching the FastAPI→React seam. That makes the boundary *more* dangerous, not less: every field that arrives over JSON is `any` until proven otherwise. ESLint (`react-hooks`, exhaustive-deps) is the always-on layer; treat its warnings as errors, not noise. Dodds: "don't dismiss a compilation error or warning just because you think it's impossible."

### What to check

**Unvalidated JSON-boundary reads**
- Code that trusts the backend payload shape blindly: `data.candles.map(...)` with no guard when `candles` can be `undefined` on a thin/failed setup. The mini-chart correctly does `data.candles || []` and `data.volumes || []` everywhere — that defensive read is the pattern. A bare `data.lps_tests.forEach` is a crash waiting for the first setup without an LPS.
- Numbers that may arrive as `null`/empty-string from a partial scan coerced with bare `Number(x)` (→ `NaN` silently). The `finiteNumber` helper (returns `null` unless `Number.isFinite`) is the right guard; flag raw coercions on price/level fields that skip it.
- Severity: **P2** on data the chart/render math depends on (R/S levels, base offsets, R-multiple). **P3** for cosmetic fields.

**Impossible states the model could prevent**
- Independent boolean flags (`isScanning`, `isEvaluating`, `isDownloading`, `scanError`) read in ad-hoc order to decide what to render. The concrete bug: `isScanning: false, scanError: <err>, screenerData: <stale>` renders the stale grid *and* swallows the error depending on which `if` runs first. `ScreenerGrid` already guards `scanError && !isScanning` — verify every such combination is intentional, not accidental.
- Prefer a single `scanPhase`/status value (`'idle' | 'downloading' | 'evaluating' | 'error' | 'ready'`) with convenience booleans **derived** from it, so render logic is a switch on one value.
- Severity: **P2** when the flag combination gates a data-critical view (live trades, order staging). **P3** for simple loading toggles.

**Context without the fail-fast pattern**
- Context created with a `null`/`undefined` default but no consumer hook that throws on misuse. Dodds' pattern: create with no default, export a hook that throws a descriptive error if used outside the provider — incorrect usage crashes immediately with a clear message instead of silently rendering with `undefined`.
- Severity: **P2** — silent `undefined` from a missing provider is hard to trace.

---

## Principle 4: Test behaviour, not implementation

*Carmack: understand what the code does, not how it's structured.*
*Dodds: "The more your tests resemble the way your software is used, the more confidence they can give you."*

The Testing Trophy: Static (ESLint) → Unit (pure functions) → **Integration (the sweet spot)** → E2E (critical paths only). Dodds: **"Write tests. Not too many. Mostly integration."** Be honest about reality here: Chrollo's frontend test layer is intentionally light (ESLint + optional React Testing Library); the engine's correctness is guarded by pytest seed-recall/shadow-harness on the Python side. So the highest-leverage *frontend* tests are a few integration tests over pure transform helpers and the riskiest render paths — not a sprawling component-test suite.

### What to check

**Implementation-detail testing (the core anti-pattern)**
- Tests that assert on internal state or call internal methods rather than rendered output.
- Tests that assert on component structure: `container.querySelector('.internal-class')` or finding a child by component name.
- Tests that use shallow rendering. Dodds: **"With shallow rendering, I can refactor my component's implementation and my tests break. With shallow rendering, I can break my application and my tests say everything's still working."**
- Two-question litmus: (a) Will this break when a real production bug is introduced? (b) Will it survive a backward-compatible refactor? Implementation-detail tests fail both.
- Severity: **P2** — these break on every refactor while giving false confidence.

**Highest-value frontend unit tests: the pure transforms**
- The chart-data helpers are pure and bug-prone — `colorCandles`, `setupIndexes`, `focusSetupRange`, `indexOnOrAfter`, `finiteNumber`. These do off-by-one index math on base/LPS offsets that mirror the engine's own boundary logic; a wrong `baseEnd = len - 1 - forwardBars` silently mis-highlights the box. Test these as plain functions over fixture payloads — they need no DOM.
- Severity: **P2** for missing tests on index/level math that drives what the trader sees.

**Right query priority in Testing Library** (when component tests exist)
1. `getByRole` — top preference. "If you can't, it's possible your UI is inaccessible." The `role="alert"` scan-error banner is queryable this way.
2. `getByLabelText` → 3. `getByPlaceholderText` → 4. `getByText` → 5. `getByDisplayValue` → 6. `getByAltText`/`getByTitle` → 7. `getByTestId` (escape hatch only).
- Severity: **P3** — degrades test quality and hides accessibility gaps.

**Over-mocking**
- Mocking internal hooks/components instead of testing through them. Dodds: "the biggest thing you can do to write more integration tests is to stop mocking so much stuff." Don't mock `useScreenerData` to test `ScreenerGrid` — render with a stubbed fetch at the network boundary (a fake `fetch`/SSE) and let the real hook run.
- The only appropriate mocks: the network boundary (the FastAPI fetch/SSE) and timing.
- Severity: **P2** when mocking hides a real integration bug. **P3** when merely unnecessary.

**Missing tests on critical paths**
- Dodds' heuristic: "What part of your untested codebase would be really bad if it broke?" Here that's the chart-overlay math and anything in the live-trade/risk surface, not the cosmetic cards.
- Severity: **P2** for missing tests on render math the trader relies on. **P3** for stable cosmetic UI.

---

## Principle 5: Composition over configuration

*Carmack: make data flow visible and explicit.*
*Dodds: "Take advantage of component composition" — always before Context, always before external state.*

Dodds' compound-component intuition: think of `<select>` and `<option>` — they don't make sense apart. Composition gives an expressive API without the "prop-ocalypse" of one component taking dozens of config props.

### What to check

**Prop drilling that skipped composition**
- Intermediate components forwarding props they don't use. `ScreenerGrid` hands `ScreenerCard` exactly the props it needs (`data`, `earnings`, `watchlisted`, the toggle callbacks) — before reaching for Context to thread something three levels deep, check whether the parent could pass pre-composed `children`.
- Dodds: "One of the things that really aggravates problems with prop drilling is breaking out your render method into multiple components unnecessarily."
- Severity: **P3** — unless it's already triggered a global store (**P2**)

**Controlled/uncontrolled confusion**
- Components that take a `value` prop but *also* keep internal `useState` for it — unclear who owns the value. This bites hardest on inputs in the position calculator / trade-staging forms, where a fight between props and internal state silently drops a keystroke or a price edit.
- Control-props pattern: if the caller provides the value, defer to them; otherwise manage internally. The component must never fight itself.
- Severity: **P2** when it causes data loss in a numeric input. **P3** for UI-only toggles.

**Slot/children over boolean prop bags**
- A modal or panel that grows `showHeader` / `showFooter` / `variant` flags instead of accepting composed `children`. Flags multiply combinatorially; slots don't.
- Severity: **P3**

---

## Principle 6: Errors are not exceptional — handle them structurally

*Carmack: deploy assertions as tripwires.*
*Dodds: unify error handling through Error Boundaries and status models.*

### What to check

**Error Boundary coverage**
- Chrollo ships a class `ErrorBoundary` (in `components/ErrorBoundary.jsx`) that catches render crashes, shows a fallback instead of a white screen, and even self-heals stale-chunk `ChunkLoadError`s by reloading once. Verify it actually *wraps* the volatile subtrees — the chart wall and any imperative-chart mount are the most likely to throw on a malformed payload.
- The cost of a gap: one bad setup payload throwing inside a card crashes the entire React tree to blank, with no recovery and only a `console.error`.
- Note React's limit: Error Boundaries catch **render-phase** errors, not async/`fetch`/SSE rejections. Those must be caught in the hook and surfaced as state (the `scanError` → `ScanErrorBanner` path is the model). Don't expect the boundary to catch a failed scan.
- Severity: **P1** for no top-level boundary at all. **P2** for missing granular boundaries around the chart wall / live-trade surface.

**Ad-hoc async error handling instead of a status model**
- `{ isLoading, isError, data, error }` as independent values updated by hand. After an error, `isLoading` is false, `data` is stale, `error` is set — and the render silently shows stale data depending on check order. Collapse to one `status` value as the single source of truth; derive booleans from it.
- Severity: **P2** when it gates data-critical UI. **P3** for simple spinners.

**The `response.ok` trap**
- `fetch` only rejects on network failure, **not** on 4xx/5xx. Every call to the FastAPI backend must check `response.ok` (or `response.status`) and throw/branch on failure before `response.json()`. A 500 from a scan endpoint otherwise sails through as a parsed error body treated like data.
- For SSE (`EventSource`/`useSSE`): handle the `error` event explicitly — a dropped scan stream must become `scanError`, not a silent hang on "Loading…".
- Severity: **P2**

**Swallowed errors in the chart effect**
- The mini-chart wraps `createChart`/`setData` in try/catch and flips a `chartError` flag to render a "Chart failed to load" fallback — good. Flag the opposite: an empty `catch {}` that hides a real malformed-payload bug, or a chart effect with no fallback at all that lets one bad series blank the card.
- Severity: **P2** for a silent empty catch on render-critical work. **P3** for a deliberately ignored cleanup error (the `chart.remove()` catch is fine — it's documented "safe to ignore").

---

## Principle 7: Colocate everything — tests, helpers, styles

*Carmack: code you can't see is code you can't reason about.*
*Dodds: "Place code as close to where it's relevant as possible."*

Dodds (quoting Dan Abramov): **"Things that change together should be located as close as reasonable."** The three costs of NOT co-locating: maintainability (files drift out of sync), applicability (people miss related files), ease of use (context-switching between directories).

The orphan-utility problem: **"Later, your component is deleted, but the utility you wrote is out of sight, out of mind and it remains (along with its tests). Over the years, engineers work hard to make sure that the function and its tests continue to run… without even realizing that it's no longer needed at all."**

### What to check

**Test file placement**
- Co-locate tests next to source (`ScreenerMiniChart.jsx` + `ScreenerMiniChart.test.jsx`) rather than in a mirror `__tests__/` tree. The chart-math helpers' tests especially want to sit beside the helper so a future index-math change drags its test along.
- Severity: **P3**

**Helper/utility placement**
- Chrollo already co-locates chart helpers in `chartIndicators` next to the components that consume them — that's the pattern. Flag the inverse: pure transforms shoved into a far-off `utils/` consumed by a single component, or a helper that outlived the only component that used it.
- Dodds: "for heaven's sake, please DELETE THIS ESLINT RULE" — referring to `no-multi-comp`. Co-location means keeping the small `EmptyState`/`ScanErrorBanner` helpers right inside `ScreenerGrid.jsx` where they're used is *correct*, not a smell.
- Severity: **P3**

**Styling placement (design-system aware)**
- Styling here is inline style objects keyed off CSS custom properties from the "Instrument Panel" design system (`var(--text-muted)`, `var(--danger-bg)`, `var(--radius-sm)`). Style decisions defer to `PRODUCT.md` + `DESIGN.md` — they are not a code-quality concern of this doc.
- What *is* a quality concern: hardcoded hex/spacing that bypasses the design tokens and will drift from the system (e.g. a raw `#eb4956` where `var(--danger)` exists). Flag token bypasses, not the styling mechanism.
- Severity: **P3** for placement. **P2** when a hardcoded value diverges from the token it should track and breaks theming consistency.

---

## Principle 8: Imperative chart libraries live inside the effect — create, then destroy

*Carmack: own the lifecycle of every resource you allocate.*
*Dodds: effects are for synchronising with external systems; every effect that creates must clean up.*

`lightweight-charts` is an **imperative** library: `createChart` allocates a canvas, series, and a `ResizeObserver` that React does not know about. Wiring it into the React lifecycle correctly is the single most error-prone thing in this frontend, and the failure mode is a real leak/crash — not a style nit. `recharts`, by contrast, is declarative React; the failure modes there are the ordinary state/prop ones from the earlier principles.

### What to check

**Create-and-destroy must be paired in one effect**
- The mini-chart's effect is the reference pattern: `createChart` on mount, and a cleanup that calls `chart.remove()` and clears the container. Every imperative chart MUST return that cleanup. A `createChart` with no matching `remove()` leaks a canvas + `ResizeObserver` per card; on a 100-card wall with re-scans that compounds into jank and eventually a blank/crashed tab.
- Severity: **P1** — a missing `chart.remove()` cleanup is a guaranteed resource leak.

**Don't re-instantiate the chart every render**
- The effect's dependency array decides how often the chart is torn down and rebuilt. Keyed on `[ticker, data]`, it rebuilds only when the setup or its payload actually changes — correct. Flag an effect that re-creates the chart on *every* render (empty-array omitted, or an unstable inline object/function in deps), or one that puts `createChart` in the render body. Re-instantiating per render destroys the user's chart state and torches performance.
- The dual sin: an effect that *creates* but whose deps cause it to fire repeatedly while the *cleanup* is missing — that's the leak above, but faster.
- Severity: **P2** for needless rebuilds; **P1** if combined with a missing cleanup.

**Stable inputs, or accept the rebuild**
- Passing a freshly-built object/array as the `data` prop on every parent render makes the `[ticker, data]` effect rebuild constantly. Either memoize the payload upstream (it comes straight off `screenerData.chart_data[ticker]`, so it's already stable) or key the effect on the stable identity. Flag inline `data={{...}}` literals feeding a chart effect.
- Severity: **P2**

**Imperative mutation after creation goes through refs, not state**
- Pushing new bars or moving a price line after creation should call series methods (`series.setData`, `series.update`) via a ref to the chart/series — NOT by storing the chart in `useState` (which would trigger renders) and NOT by recreating it. Storing a chart instance in `useState` is a code smell; it belongs in a `useRef`.
- Severity: **P2**

**Declarative `recharts`: keep it in React's world**
- For equity curves, R-multiple histograms, drawdown charts, etc., prefer `recharts` and drive it with derived props — don't reach for imperative escape hatches or manual DOM. The earlier principles (derive don't sync; don't store API data as UI state) cover it.
- Severity: **P3**

---

## Gaps: What This Doc Doesn't Cover

- **Raw performance**: list virtualization of the card wall, memoization strategy, bundle splitting, lazy loading, re-render avoidance, chart render budget. Covered by the **Pipeline-performance skill** (the chart-lifecycle *correctness* in Principle 8 is owned here; the *cost* tuning is not).
- **Accessibility**: Dodds' query hierarchy nudges toward accessible patterns, but this is not an a11y audit. Supplement with axe-core / WCAG.
- **Design-system architecture**: the "Instrument Panel" tokens, theming, typography, and density live in `PRODUCT.md` + `DESIGN.md` and the Karri Saarinen UI doc — design decisions, not code-quality issues.
- **Engine correctness**: lookahead bias, NaN propagation, float-equality, index/window math live on the Python side (Wes McKinney numerical-correctness doc + pytest seed-recall/shadow-harness). The frontend only *renders* those results — but mirror their boundary discipline in the chart-overlay helpers (Principle 4).
- **Animation/transition patterns**: not Dodds' domain.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | State/lifecycle bugs that corrupt data, leak resources, or crash the app | Derivable state controlling the live-trade/risk surface, no top-level Error Boundary, `createChart` with no `chart.remove()` cleanup |
| **P2 — Fix Soon** | Patterns that actively cause bugs or kill velocity | State sync via `useEffect`, API data merged into UI state, unvalidated JSON-boundary reads on render math, boolean-flag combos gating data-critical views, missing `response.ok`/SSE-error handling, controlled/uncontrolled input confusion, needless chart re-instantiation, chart stored in `useState`, hardcoded value diverging from a design token |
| **P3 — Consider** | Hygiene that compounds over time | Premature component splits, single-use hooks, `getByTestId` over `getByRole`, tests in mirror directories, orphaned helpers, declarative `recharts` nits |

### The Overriding Filter

Before writing any finding, apply the Dodds–Carmack synthesis:

1. **Is this state necessary?** If derivable, flag it. (Carmack: eliminate. Dodds: derive.)
2. **Is this abstraction necessary?** If single-use, flag it. (Both: inline until forced.)
3. **Is the boundary validated?** Unguarded JSON reads and ad-hoc boolean status are this codebase's "broken armour." (No compiler — discipline at the seam.)
4. **Do the tests test behaviour?** If asserting on internals — or missing on the chart-overlay math — flag it. (Dodds: test use cases, not code.)
5. **Is every allocated chart cleaned up?** A `createChart` without a paired `remove()` is the signature frontend leak here. (Carmack: own the lifecycle.)
