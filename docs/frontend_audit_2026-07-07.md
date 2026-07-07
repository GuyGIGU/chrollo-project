# Chrollo frontend — deep design + technical audit

_Generated 2026-07-07 via impeccable multi-agent audit (9 isolated reviewers -> 60 findings -> 24 clusters -> 22 adversarially verified). Judged as a single-operator desktop instrument at 1536x864; mobile/touch out of scope._

## Overall verdict

Chrollo's frontend is a mature, doctrine-driven instrument, not an AI-slop dashboard: it has a real, enforced design system (tokens, named rules, a documented North Star), engineered consistency (single tier ladder, shared rail drawer, one-owner pollers, leak-free SSE/chart lifecycles), and a genuinely honest posture toward its own confidence (EdgePulse refuses to over-state edge, sign-based P&L color, differentiated empty/stale states). Where it falls short is almost entirely against its OWN stated bars rather than generic best practice — a systemic contrast gap (faint ink and semantic small-text sit below the >=4.5:1 long-session contrast PRODUCT.md commits to, and white-on-accent-blue active states measure 3.22:1), a handful of self-banned or self-conflated color/decoration slips, and secondary-surface keyboard gaps (no modal focus trap/restore, inconsistent Esc). None block the single expert operator, but they undercut the calm-precise-legible instrument the project explicitly promises.

## Does it look AI-generated?

It does NOT read as AI-generated. The tells of machine-made UI are absent: no identical-card monotony (Home commits to named asymmetric grid-areas), no reflexive uppercase-kicker-above-every-section sprawl (kickers appear on only two hero panels), no accent-color rainbow, no marketing copy, no gradient hero tiles as a default, and a real design law (One-Accent, Tier-Reserve, Tabular, Weight-Not-Family) that is actually referenced and mostly obeyed. Copy is trader-native and specific ('restart the backend to enable /engine-edge', 'not in the latest scan', 'no stop recorded'), which reads as domain-authored, not templated. The imperfections here are the opposite of slop — they are a human team's own rules being violated in contained, traceable spots (a shimmer bar, four side-stripe borders, a few raw hex literals), which is what a real codebase under evolution looks like, not a freshly-generated template.

## Per-surface heuristic scores (Nielsen, /40)

| Surface | Score |
|---|---|
| App shell + nav | 32.0/40 |
| Home command-center | 34.0/40 |
| Screener | 29.0/40 |
| Archive | 28.0/40 |
| Portfolio | 30.5/40 |

_(Journal/trades critic hit the schema-retry cap and dropped out; covered by live evidence + cross-cutting auditors.)_

## Technical dimension scores (/4)

| Dimension | Score | Note |
|---|---|---|
| Performance | 3/4 | Genuinely strong runtime hygiene — no SSE/interval leaks, single-owner pollers, memoized heavy list, correct chart teardown. Held back from 4 by a red |
| Theming / tokens | 3/4 | Strongly token-driven and rule-aware; violations are real but localized. One self-acknowledged Tier-Reserve leak (tier-S/B hues reused for HTF phase-s |
| Anti-pattern / slop | 3/4 | Disciplined product-register UI with a real, enforced design system; a few contained violations of its own law (4 self-banned side-stripe borders, one |
| Anti-pattern / slop | 3/4 | The core triage loop (card → open chart → arrow-cycle → Esc) is genuinely excellent keyboard work and the custom tiles are exemplary. Held below 4 by  |

## Systemic patterns

1. Contrast against the project's own >=4.5:1 long-session bar is the dominant systemic theme, appearing in three distinct classes across all surfaces: (1) --text-faint (#6C7488) used as load-bearing labels/values/meta at ~2.96-3.6:1; (2) white on --accent-blue at 3.22:1 on every primary action AND every active/selected filter state — cruelly, the state the operator relies on to know what the grid is showing is the lowest-contrast one; (3) semantic small text (red P&L, blue tickers/links) at 3.7-4.0:1 sub-AA. The token vocabulary to fix it (--text-muted ~6:1, brighter reserved text variants, dark ink on blue fills) already exists.

2. Color-doctrine leakage: the app's own named rules (Tier-Reserve, One-Accent) are broken in contained spots — tier-S amber and tier-B sky repainted for HTF phase-state and active tabs, accent-blue used as resting decoration (Neutral-regime side stripes, info toasts, KPI top rails, reweighting weight-down data), and a scattering of raw hex/rgba semantic literals plus wrong-category fallbacks (--accent-pink falling back to the tier-A hue, success/danger to Tailwind greens/reds, IbkrModeControls greens/reds drifted off the retuned tokens).

3. Secondary-surface keyboard and dialog semantics lag the excellent primary triage loop: no shared Modal focus trap/restore anywhere (Tab escapes behind the scrim, focus orphans on <body>, ConfirmDialog can't accept via Enter), Esc-to-close is inconsistent (one modal disables it, three hand-rolled overlays never bind it), and aria-modal is promised on only one of the dialogs that has no trap.

4. Decoration and idiom drift on meters/tiles/progress bars: ornamental blue->pink gradients + an infinite shimmer sweep, layout-property width animation instead of a compositor transform, and gradient-sheen KPI tiles adjacent to flat ones — small, contained slips toward the 'showy motion / generic hero-tile' anti-references the North Star rejects.

5. Consistency papercuts on a precision surface: tabular-nums missing on the most number-dense streamed tables (portfolio, archive records, chart tooltips) so columns jitter on every tick, and three missing-value glyphs ('-' / '--' / '—') coexist against a documented canonical em-dash, sometimes two on one card.

## Verified findings (18)

### [P2] Faint ink (--text-faint #6C7488) carries real meaning as text and fails the project's own >=4.5:1 long-session bar on all four surfaces · SYSTEMIC

- **Where:** `webapp/frontend/src/index.css:14 (token def; representative usage :2052) — setup name ScreenerCard.jsx:157, rail labels :224, count meta :1881, Open-Book R :1955`
- **Category:** contrast
- **Why it matters:** The single most systemic contrast defect. --text-faint is the naming layer the operator parses repeatedly (section labels, metric names, recency/count meta, R-multiples, setup identity) yet measures ~2.96-3.6:1 — well under the 4.5:1 PRODUCT.md commits to so long dark-room sessions don't strain. Small bold 8-11px doesn't earn WCAG's 3:1 large-text pass.
- **Fix:** Stop using --text-faint for anything meaningful: promote label/value/meta roles to --text-muted (#9AA1B2 ~6:1) or add a --text-label token verified >=4.5:1 against each real surface bg; lift 8px rail labels to >=10px. Reserve raw --text-faint strictly for inert '·' punctuation glyphs.

### [P2] White on --accent-blue sits at 3.22:1 on every primary action and every active filter/pill state · SYSTEMIC

- **Where:** `webapp/frontend/src/utils/archiveTabUtils.js:57 (shared archiveButtonStyle); also ScreenerToolbar.jsx:248/325/353/364, UniverseSwitcher.jsx:56, ScreenerPager.jsx:36, ArchiveHeader.jsx:28, ArchiveTable.jsx:151/245`
- **Category:** contrast
- **Why it matters:** #fff on --accent-blue measures 3.22:1 at 10-13px, below AA and below the project's own bar. The cruel part: the ACTIVE/selected state — the one the operator relies on to know which filter the grid is showing — is the lowest-contrast state on the surface.
- **Fix:** Switch active-pill/button text to near-black ink (#0B1220 on #5B8AFF = ~5.8:1) or darken the fill to a deeper blue token so #fff clears 4.5:1. Apply once in the shared archiveButtonStyle / scanButtonStyle / active-pill styles. One-Accent contract unaffected.

### [P2] Decision-critical semantic small text (red P&L, %change, blue tickers/links) rendered below AA · SYSTEMIC

- **Where:** `webapp/frontend/src/index.css:1949 (.home-ob-pnl 12px) + OpenBookZone.jsx:97/100, .home-wl-chg :1924, .home-bridge :1929, .home-zone-link :1842`
- **Category:** contrast
- **Why it matters:** The exact figures that signal money moving — red '-$9.58 / -0.4%' P&L and clickable blue tickers/links — are colored small at 3.7-4.0:1, sub-AA at 11-12px. Squinting at the losing-money number in a dark room is the wrong place to be dim. (Note: --success green ~6.3:1 and Portfolio #6EA8FF tickers ~5-6:1 already pass — only the RED and the accent-BLUE-as-text actually fail.)
- **Fix:** Introduce slightly brighter danger/blue variants reserved for <14px text (keep current hues for fills/borders); fix the P&L value and %change first. A '13px bold' bump alone won't clear WCAG large-text (needs >=18.66px bold) — the reserved brighter-text variant is the right path.

### [P2] Shared Modal never traps or restores focus — Tab silently escapes behind the scrim, Enter can't accept a confirm · SYSTEMIC

- **Where:** `webapp/frontend/src/components/ui/Modal.jsx:31-65; consumers FeedbackHost ConfirmDialog:47-72, ScreenerModal.jsx:146, TradeDetailDrawer.jsx:155, MarketRegimeDetailModal.jsx:44 (declares aria-modal with no trap)`
- **Category:** focus-management
- **Why it matters:** For form-heavy modals (TradeDetailDrawer entry/stop/qty, AddSetupModal) Tab past the last field jumps to chrome behind the drawer — obscured, no visible caret; on close focus orphans on <body>. ConfirmDialog autofocuses nothing, so Enter can't accept a destructive confirm — the most concrete papercut. MarketRegimeDetailModal's aria-modal='true' is a false a11y promise.
- **Fix:** Centralize in ui/Modal: capture document.activeElement on mount, move focus to shell/initialFocus, wrap Tab within the content node, restore focus on unmount. Route the hand-rolled overlays through ui/Modal. ConfirmDialog should autofocus its safe default (Cancel).

### [P2] Tier S/A/B hues borrowed for non-tier UI (HTF phase-state text, nesting glyph, active timeframe tab) · SYSTEMIC

- **Where:** `webapp/frontend/src/components/ScreenerCard.jsx:191 (Re-accum #ff9f43=tier-S), :192 (Consol #58a6ff=tier-B), :213 (⊂ glyph); ScreenerModal.jsx:55/58 (active tab)`
- **Category:** tier-reserve
- **Why it matters:** The Tier-Reserve Rule reserves S/A/B/C hues for tier identity only. On the always-visible HTF band next to a badge+ticker that already carry the real tier hue, phase-state painted in tier-S amber / tier-B sky reads as a tier cue — and amber no longer uniquely means 'S setup' at a glance. A code comment concedes the borrow.
- **Fix:** Give phase-state its own tokens (--state-reaccum / --state-consol) or fold onto a neutral semantic; use var(--accent-blue) (#5B8AFF, distinct from tier-B #58A6FF) for the active tab — which also corrects a One-Accent slip. Replace the four hardcoded hexes so they can never collide with the tier ladder.

### [P2] Changeable numbers lack tabular-nums, so columns jitter on every SSE/ticker/Prev-Next update · SYSTEMIC

- **Where:** `webapp/frontend/src/components/PortfolioTables.jsx:12 (tdStyle); also .stock-lens-metric strong index.css:922, EquityCurve.jsx:52 tooltip, archive records/tier cards`
- **Category:** named-rule-tabular
- **Why it matters:** The Tabular Rule requires every changeable number to use tabular-nums, yet most numeric cells inherit Inter's proportional figures. Portfolio SSE re-renders and ticker Prev/Next cause cells to shift width and misalign columns frame to frame — the exact 'calm instrument' failure the rule exists to prevent, on the app's most number-dense screens.
- **Fix:** Add fontVariantNumeric:'tabular-nums' to the shared tdStyle, tile/insight value styles, stock-lens-metric strong, the archive Cell/Metric/BreakdownRow value styles, and both recharts tooltip contentStyle objects — ideally one shared numeric-cell style.

### [P2] Type system references fonts it never loads — Inter 800/850 and JetBrains Mono are both absent

- **Where:** `webapp/frontend/src/index.css:1 (@import Inter wght@400;500;600;700 — the only font load); usages fontWeight 850 ScreenerCard.jsx:151, 800 :112/:170`
- **Category:** typography
- **Why it matters:** The screener leans on fontWeight 850 (ticker) and 800 (tier badge, hero score, phase-bin-name) but only 400-700 load — so top-of-hierarchy weights clamp to 700 or render faux-bold and the intended emphasis isn't real, contradicting DESIGN.md's own 400-850 Weight-Not-Family ladder. Separately 'JetBrains Mono' is referenced in ~30+ files and loaded nowhere, silently falling back to Consolas.
- **Fix:** Extend the font load to include weight 800 and map 850 usages to 800; then either add JetBrains Mono (self-hosted) or drop the mono references and standardize tickers/pills on Inter with font-variant-numeric: tabular-nums.

### [P2] Long/Short selector in the position calculator changes nothing — a control that lies

- **Where:** `webapp/frontend/src/components/PositionCalculator.jsx:37 (control); root cause line 12 (Math.abs) + line 23 (useMemo deps omit direction)`
- **Category:** honest-instrument
- **Why it matters:** direction is bound to the select but excluded from the results useMemo deps, and stop distance is Math.abs(entry-stop) — direction-agnostic. A visible control producing no change is corrosive in a tool whose whole premise is an honest instrument, and it silently skips a real safety check (a Long stop must sit below entry, a Short above). The 'SHARES TO BUY' label is also wrong for shorts.
- **Fix:** Either use direction to validate stop side (flag a wrong-side stop) and relabel the output 'Shares to buy/sell', or remove the selector entirely.

### [P2] Daily-P&L tile row duplicates the Account-Summary card directly below it

- **Where:** `webapp/frontend/src/components/PortfolioDailyPnl.jsx:61 (Open P&L) + :50 (Realized Today); duplication partner PortfolioSummary.jsx:86-96`
- **Category:** redundancy
- **Why it matters:** PortfolioDailyPnl renders directly above the Summary card and restates the exact Unrealized/Realized figures (same summaryValue keys, same fmtMoney) one row up — and the redundant top row is the heavier one (22px/850 vs 20px/800), so the most prominent P&L strip is 2/3 duplicative, against Earn-Every-Element and confident hierarchy.
- **Fix:** Collapse to one deliberately-ranked P&L strip: keep the single session-total hero (realized+unrealized, the only net-new figure) and drop the standalone Open/Realized duplicates, or remove the P&L overlap from the Summary card. Commit to one row as the P&L truth.

### [P3] Colored 3px left side-stripe borders on cards/toast/modal — accent-blue used as resting decoration · SYSTEMIC

- **Where:** `webapp/frontend/src/components/MarketPulse.jsx:105; RegimePanel.jsx:67; MarketRegimeDetailModal.jsx:60; components/ui/FeedbackHost.jsx:29 (toast)`
- **Category:** one-accent-decoration
- **Why it matters:** NEUTRAL.tone and toast-info tone both resolve to var(--accent-blue), so in the common Neutral regime both hero cards and info toasts grow a resting Signal-Blue stripe — turning the sole interactivity color into decorative chrome (One-Accent scarcity tension). On RegimePanel/modal the state is already encoded by a dot + colored label, so the stripe is redundant. (Note: this is NOT a DESIGN.md 'absolute ban' — no side-stripe ban exists in the doc; the ban is the generic detector's, so scope the fix to the blue-at-rest case.)
- **Fix:** Remove the accent-blue-at-rest stripe (Neutral regime + info toasts); convey tone via the existing dot or a small trailing chip. Leave the non-blue success/warning/danger stripes as an acceptable tone-coding choice.

### [P3] Semantic colors re-expressed as raw hex/rgba literals and wrong-category fallbacks instead of tokens · SYSTEMIC

- **Where:** `webapp/frontend/src/components/PortfolioStatusBar.jsx:31; IbkrModeControls.jsx:104-116; EquityCurve.jsx:34; RMultipleHistogram.jsx:52-61; ScreenerScanProgress.jsx:83 (--accent-pink,#bb86fc==tier-A); ArchiveReweightingStrip.jsx:59`
- **Category:** token-hygiene
- **Why it matters:** Dozens of sites hand-write danger/blue/warning/success as rgba() literals or fall CSS vars back to foreign hues. Two are wrong-category: --accent-pink falls back to #bb86fc (the tier-A color) and success/danger to Tailwind greens/reds. IbkrModeControls paints CONNECTED/LIVE pills in greens/reds that no longer match the retuned --success/--danger (real, already-manifested drift). Reweighting borrows Signal Blue as a categorical 'weight-down' data label — a clean One-Accent violation.
- **Fix:** Replace literals with color-mix(in srgb, var(--danger) 12%, transparent) or existing -soft tokens; delete foreign fallbacks (tokens always resolve at :root); never fall --accent-pink back to a tier value; color the reweighting delta by sign with --success/--danger, not blue.

### [P3] Escape-to-close is inconsistent: one modal disables it, three hand-rolled overlays never listen · SYSTEMIC

- **Where:** `webapp/frontend/src/components/CalculatorModal.jsx:8 (closeOnEscape={false}); AddSetupModal.jsx:20; ArchiveMaintenanceModals.jsx:7 (ScanHistory) + :53 (Analysis)`
- **Category:** keyboard
- **Why it matters:** The rest of the app (ConfirmDialog, MarketRegimeDetailModal, TradeDetailDrawer, ScreenerModal) closes on Esc, but CalculatorModal explicitly turns it off and the three bespoke archive overlays never bind it — so a keyboard user who opens AddSetup and reconsiders must leave the keyboard to bail, breaking the muscle memory a keyboard-driven instrument establishes.
- **Fix:** Drop closeOnEscape={false} on CalculatorModal, and migrate the three archive overlays onto ui/Modal (they already replicate its backdrop/stopPropagation) so they inherit Esc, or add the window keydown-Escape effect MarketRegimeDetailModal already uses.

### [P3] Ornamental gradients + infinite shimmer sweep on meter/progress fills — showy motion between trader and data · SYSTEMIC

- **Where:** `webapp/frontend/src/components/ScreenerScanProgress.jsx:83 (blue->accent-pink fill) + :88-96 (shimmer, @keyframes index.css:1739); archive/ArchiveCalibrationPanels.jsx:94-96 (two-hue CorrelationBar)`
- **Category:** over-designed
- **Why it matters:** The scan fill is a blue->--accent-pink gradient with a continuous white shimmer; correlation meters fill blue->success / danger->pink. Both map onto the 'showy motion / ornamental gradients' anti-reference: --accent-pink isn't a sanctioned scale color, the gradient direction encodes nothing, and blue->success puts the sole interactivity color on a static data meter.
- **Fix:** Use a solid --accent-blue fill that flips to --success at 100% (the >=100% branch already exists at lines 81-82) and delete the shimmer; make correlation meters a single solid --success (positive) / --danger (negative). Gate any indeterminate motion behind prefers-reduced-motion.

### [P3] Meter/progress fills animate the layout property `width` instead of a compositor transform · SYSTEMIC

- **Where:** `webapp/frontend/src/components/ScreenerScanProgress.jsx:84; archive/ArchiveCalibrationPanels.jsx:99; index.css:531 (.kpi-bar-fill)`
- **Category:** layout-animation
- **Why it matters:** transition: width forces a reflow every frame instead of staying on the compositor, and the project's own DESIGN detector flags layout-property animation. Cost is negligible here (fixed-size, overflow-hidden tracks) but it's the wrong idiom for a tool marketed as calm/precise.
- **Fix:** Animate transform: scaleX(pct) with transform-origin:left (track stays 100% width). Note the fills' border-radius/gradients and shimmer child will need adjustment under scaleX, so it's not perfectly free — mechanical but not zero-effort.

### [P3] Inconsistent missing-value glyph across the app ('-' vs '--' vs '—') against a documented canonical em-dash · SYSTEMIC

- **Where:** `webapp/frontend/src/components/ScoreBreakdown.jsx:5 (formatScore '--'); scoreLabel '-' in ScreenerCard.jsx:9/:125 vs pills :174; format.js:13 EMPTY '—'; ArchiveSummary.jsx:63/74, ArchiveTable.jsx:144`
- **Category:** consistency
- **Why it matters:** An honest instrument should render 'no data' one way, yet a single screener card shows '-' as the hero and '--' in the pills beneath it, and the archive mixes '—'/'-' in one view — all against format.js's own comment calling '—' canonical. Trivial each, but reads as inattention on a precision surface.
- **Fix:** Centralize the one em-dash placeholder ('—') in a shared formatter and route scoreLabel/formatScore/money/pct/bars and the archive summary/table null cells through the existing EMPTY constant.

### [P3] Home mounts two identical live-price pollers and two watchlist fetches for one dataset

- **Where:** `webapp/frontend/src/components/home/WatchlistZone.jsx:41 + ActionCenter.jsx:32-42 (both usePollingInterval /live-prices 60s + useWatchlist)`
- **Category:** duplicate-polling
- **Why it matters:** HomeView renders both ActionCenter and WatchlistZone; each independently calls useWatchlist() (GET /watchlist/ on mount) and polls GET /live-prices every 60s over the same sorted ticker set — byte-identical. This is exactly the redundant-poller pattern useLiveRisk.js's own header documents the app got burned by, plus two watchlist Sets that can silently drift.
- **Fix:** Lift the watchlist and a single live-price poller to one shared owner (AppShell outlet-context, the established single-owner pattern for ibkrStatus/riskFor) and pass prices/watchlist down: one /watchlist fetch, one /live-prices poll, one source of truth.

### [P3] Archive stacks eight equal-weight panels in a flat uniform-gap column — no anchor

- **Where:** `webapp/frontend/src/components/ArchiveTab.jsx:64`
- **Category:** hierarchy
- **Why it matters:** The render stacks header/health, tier cards, two calibration panels, reweighting, equity curve, filters and the records table as interchangeable 20px-gap panels. The North Star explicitly calls flat egalitarian layouts a defect: the eye has no primary artifact to land on and no seam between 'monitor the loop' and 'read the records'.
- **Fix:** Group into 2-3 quiet zones separated by spacing/a hairline (Status: header+health; Research: calibration+reweighting+equity; Records: filters+table) and treat the records table as the visual anchor. Use spacing and weight, not uppercase eyebrow kickers.

### [P3] All explanatory copy is delivered only through native title tooltips

- **Where:** `webapp/frontend/src/components/tooltipText.js:1 (explainTip); sinks ScreenerStockLens.jsx:99/133/162, .phase-bin-control cursor:help index.css:739`
- **Category:** discoverability
- **Why it matters:** explainTip concatenates a 3-sentence what/why/how string straight into the browser title attribute on every metric, tag, pill and phase control. Native title has ~0.5s delay, can't be styled or line-broken, doesn't appear on keyboard focus, and reads as an unformatted wall — so genuinely good documentation is under-delivered, and the phase-bin controls set cursor:help yet the tip never shows on focus.
- **Fix:** Route explainTip through a small custom hover/focus popover (reuse the FeedbackHost portal pattern) rendering What/Why/How as three labeled lines, triggerable by keyboard focus. Keep it lightweight to respect the calm register.

## What is genuinely strong

- One honest source of truth for 'where am I': the active nav highlight derives purely from the URL via NavLink (AppSidebar.jsx:36) feeding the topbar title, so it can never disagree with the route; the rail keeps icon+label together (recognition over recall).
- Full state is URL-addressable and the card carries a complete keyboard model: ?u/?dd/?t survive F5 and Back, and Enter/Space open, W/C toggle watchlist/considered, arrows cycle the modal, Esc closes (ScreenerGrid.jsx:36-116, ScreenerCard.jsx:257-274) — a fast expert sweeps the grid without the tool getting in the way.
- Honest-instrument discipline is real, not decorative: EdgePulse renders n=… instead of a precise edge below its sample-size floor, footnotes 'unbiased, excludes seed · n=N', and only formats byte-parity harness values — the surface actively resists looking more edge-y than the data supports.
- Status visibility is excellent and specific: OpenBookZone separates 'Checking…' / 'Live risk unavailable — retrying' / 'No open positions', price source is labeled IBKR/LIVE/last with a faint stale style, Fresh Setups distinguishes scanning / stale / '0 matched' / 'no scan yet', and PortfolioStatusBar gives specific session-conflict / daily-restart / no-cache Notices — the operator is rarely guessing.
- Consistency is engineered, not hoped for: UniverseSwitcher reuses the toolbar tier-pill styling verbatim, mini-chart and modal share the exact same rail drawer via addBoxRails so card and modal cannot diverge (ScreenerMiniChart.jsx:37), and tierColor is a single hex ladder matched to the --tier-* tokens (theme.js:12-20).
- Exemplary render-lifecycle hygiene with no leaks: useSSE and useScanRunner store their EventSource in a ref and close on unmount/finish/error, every poller runs through visibility-gated usePollingInterval, useLightweightChart pairs createChart/remove in one deps-gated effect, and ScreenerCard is memo'd with stable keys so per-card mini-charts aren't recreated on incidental re-renders.
- Deliberate single-owner poller architecture: useIBKRStatus/useDashboardData/useLiveRisk are mounted once in AppShell and threaded via outlet context, and useLiveRisk explicitly refuses to poll /ibkr/status itself, citing the past three-poller bug (useLiveRisk.js:29-31).
- Genuinely token-driven system with the design law enforced where it counts: a documented single-source tier ladder (index.css:32-36, 'Reserved hues — one source of truth'), and regime/toast tone colors resolve to semantic status tokens rather than --tier-* hues, so the Tier-Reserve Rule is intact and there's no accent sprawl beyond the sanctioned .btn-trade gradient.
- Robust, quiet cross-cutting plumbing: a single ErrorBoundary around the Outlet plus one around lazy modals distinguishing stale-chunk auto-reload from scoped Retry, a module-level toast/confirm store that replaced native alert()/confirm(), and instrument affordances earned for this operator (UI-scale + Auto-fit pre-seeded pre-paint, no reload flash, matching the documented 'denser over bigger' preference).
- The regime detail modal genuinely educates (what/why/how-to-use rows + a plain-English hint per metric + a price-vs-averages visual scale), and the per-setup ArchiveSummary footer is the strongest hierarchy on that surface — a deep six-to-eight panel readout rigorously null-guarded via the shared finiteOrNull/EMPTY family and cleanly chunked into titled cards.
- Honest degradation everywhere: null-guarded formatters and truthful partial states ('No plan', 'No working orders.', the 'n/m priced' partial-quote note), a whole-tab opacity mute when stale plus a 'stale' flag so frozen numbers never read confident — the panels never fabricate a value from missing data.
- Custom interactive tiles are exemplary: ScreenerCard and HomeSetupTile are full role=button, tabIndex=0, Enter/Space, aria-labelled controls with real focus-visible rings, and ScreenerCard's W/C shortcuts use a currentTarget guard so inner toggles don't double-fire — live-region discipline (role=status toasts, role=alert banners) covers the places that must announce.
