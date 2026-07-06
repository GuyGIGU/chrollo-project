# UI Quality Reference — Carmack × Saarinen

Philosophy: John Carmack. Specifics: Karri Saarinen (Linear, Airbnb DLS) + Steve Schoger (Refactoring UI) as supplementary.
Stack context: React 19 + Vite SPA (`webapp/frontend/`). The styling source of truth is the **Chrollo design system — `PRODUCT.md` + `DESIGN.md` at the repo root**, managed via the `impeccable` skill. North Star: **"The Instrument Panel"** — a dark, quiet, data-dense reading-room **chart wall** of screener cards. Charts via `lightweight-charts` + `recharts`. Inter (UI) + JetBrains Mono (numerics). A discretionary trader stares at it for hours to triage scan output.

Every finding must describe the **concrete visual consequence** — not just "this doesn't follow the system."
When Carmack and Saarinen independently converge on a principle, it earns its place here.

**Scope boundary:** This doc covers visual design quality: hierarchy, typography, color, spacing, elevation, motion, chart legibility, and component consistency. It does NOT cover: scanning/triage workflows and information architecture (separate domain — quality-ux.md), accessibility (PRODUCT.md sets a single-user ≥4.5:1 body-contrast bar, not audited here), or the `core/` engine. **When this doc and `DESIGN.md` disagree, `DESIGN.md` wins** — it is the project's law; this doc is the lens for spotting drift from it.

---

## Principle 1: Reduce noise to reveal hierarchy — the instrument reports, the trader decides

*Carmack: "The best code is no code. The second best is simple code." Every unnecessary element is a potential source of confusion.*
*Saarinen: "Just from a visual standpoint, these tools had a lot of noise, and it was hard to understand the important things." He wrote a Chrome extension at Airbnb to "reduce some of the information overload of JIRA, and tone down and improve some of the visuals for better hierarchy."*

Both converge on elimination as the path to clarity. Carmack eliminates code because every line is a liability. Saarinen eliminates visual noise because every decorative element competes with content. Chrollo's first design principle says it directly: "Signal over chrome. The data is the product. UI recedes so structure, score, and tags read instantly; decoration that doesn't aid the read is debt." On a screener card the protagonists are the tier-colored ticker, the score pills, the mini-chart, and the why-ranked tags — the 220px sidebar and section chrome must recede behind them.

### What to check

**Chrome competing with content**
- Does the 220px sidebar, header, or filter bar visually overpower the card wall? Per `DESIGN.md`, nav links are "quiet muted text at rest" (`text-muted` #9AA1B2). Chrome should use the muted ink ramp and lighter weight; the card content gets the visual priority.
- Are borders, dividers, or background fills creating noise between elements that spacing or a surface step could separate instead? Schoger: "Use fewer borders." Chrollo's depth is **tonal** — reach for the surface ramp (#1A1D26 → #303547) before a hairline, and a hairline (#2F3447) before a heavier line.
- Severity: **P2** for chrome that competes with content. **P1** if noise makes it hard to identify the primary signal (ticker, tier, score) on a card or the scan grid.

**Decorative elements in the instrument**
- `PRODUCT.md` rejects three looks outright: gamified-broker dopamine (confetti, celebratory win animation, oversized feel-good green P&L), generic-SaaS (gradient hero-metric tiles, uppercase eyebrow kickers, endless identical card grids), and over-design (decorative glassmorphism, ornamental gradients between trader and data). Saarinen: "For me, work is serious… I want [my tools] to be good. I want them to be professional." A research lab must never flatter its own output.
- Severity: **P3** for decoration that doesn't interfere. **P2** if decoration takes space from data or — worse — biases the trader's read of a result (a celebratory green-glow on a winner is a P2 here, not a nicety).

**Alignment inconsistencies**
- Saarinen's team spent dedicated time "aligning labels, icons, and buttons, both vertically and horizontally." The payoff is "something you'll feel after a few minutes." On a four-up card grid, check: is the watchlist star vertically centered with the ticker? Do the score/sub-score pills sit on a consistent baseline across cards? Do tag chips wrap to a predictable grid rather than ragged rows?
- Severity: **P3** for minor drift. **P2** for visible misalignment between primary card elements repeated across the wall (it compounds at scale).

---

## Principle 2: Typography is the primary hierarchy tool — and numbers are the protagonists

*Carmack: "The structure of the code should make the intended behavior obvious." Type structure should make the information hierarchy obvious.*
*Saarinen: "90% of UI is text." His Linear type system uses two groups (Body and Title) with a few sizes plus weight variations.*

Chrollo builds its entire hierarchy from **one humanist sans (Inter) across a weight range (400 → 850)** plus a monospace face reserved for compact data pills — see `DESIGN.md` §3. The named "Weight-Not-Family Rule" forbids adding a serif or second sans for emphasis; go heavier or larger instead. Schoger agrees: "A common mistake… is relying too much on font size to control your hierarchy." The levers are size, **weight**, and color/contrast — in combination.

### What to check

**Size as the only hierarchy lever**
- Is primary-vs-secondary expressed only through size? On the dark surface, de-emphasize secondary text with the ink ramp (Muted #9AA1B2, Faint #6C7488), not just a smaller px. Check: do card metadata (earnings chip, distance-to-stop, timestamps) drop to muted/faint color as well as size?
- Severity: **P2** for hierarchy on size alone. **P3** if readable but could be clearer.

**Too many type styles**
- `DESIGN.md` defines exactly five roles: Headline (700/22), Title (850/17), Body (400/13), Label (600/10 uppercase), Mono (700/10–12). That is the whole vocabulary. If a view introduces a sixth treatment, or renders the same element (e.g. a score pill) differently in the screener vs the archive, the system frays.
- Severity: **P3** for proliferation. **P2** for the same element styled inconsistently across views (screener vs archive vs journal).

**Monospace + tabular figures for every changeable number**
- This is Chrollo's named **Tabular Rule**: every number that can change — price, R-multiple, P&L, score, count, percentage — uses `font-variant-numeric: tabular-nums` so columns hold and digits don't reflow as values update. A jittering number column is a defect, full stop. JetBrains Mono is reserved for compact data pills (score/sub-score, fill inputs). Check score pills and any live-updating P&L: monospace, tabular, fixed width.
- Severity: **P2** for changeable numerics not set tabular (visible jitter on update). **P3** for prose figures that would merely read cleaner in mono.

**Label dominance over data**
- Schoger: "Labels are a last resort… the data should always dominate visually." `DESIGN.md` reserves the Label style (10px, uppercase, wide tracking) for ≤4-word headers, never sentences. A card that renders "Score:" heavier than the number inverts the hierarchy. Where format makes content self-evident (a tier-colored ticker, an R-chip), omit the label.
- Severity: **P2** for labels dominating their values in dense views. **P3** for labels that could be dropped entirely.

---

## Principle 3: Dark theme is a system, not an inversion — depth is tonal, not cast

*Carmack: "Don't build on assumptions you can't verify." Hand-picking hex values assumes perceptual correctness intuition can't provide.*
*Saarinen: "Karri mostly worked with opacities of black and white during his explorations, which… helped me understand the relationship he had in mind between the elements and their respective elevation and hierarchy."*

Chrollo's depth system is its named **Tonal-Depth Rule**: a five-step surface ramp does the work a shadow stack would in a light UI. App #1A1D26 → Sidebar #1E2230 → Panel #232735 → Hover #2A2F3E → Elevated #303547 — *that ramp is the depth system.* A panel reads as "above" the app because it is a step lighter; a hover state a step lighter still. Reach for the next surface step before reaching for a shadow.

### What to check

**Pure black backgrounds**
- The darkest Chrollo surface is App #1A1D26 — a warm slate, never #000000. Schoger: "Avoid pure black… Saturate dark greys with a cool hue." Pure black over-contrasts text and reads as a void. Check: any `#000`/`rgba(0,0,0,…)` used as a *surface* (as opposed to a shadow color)?
- Severity: **P2** for near-black primary surfaces off the ramp.

**No elevation hierarchy between surfaces**
- Cards sit on Panel #232735 over the App #1A1D26 background; hover shifts toward #242837 with a Signal-Blue border. Modals/glass-panels step up to Elevated and 12px corners. Without these steps, overlapping surfaces blend and spatial relationships collapse. Check: do dropdowns, modals, and the timeframe chart modal (TimeframeMainChart) use a lighter surface than the wall behind them?
- Schoger: "Close elements should still be lighter and distant elements darker — even in a dark UI."
- Severity: **P1** for a modal indistinguishable from the surface behind it. **P2** for missing intermediate steps (a card that doesn't separate from the app background).

**Harsh borders in dark theme**
- Chrollo borders are hairline #2F3447 / strong #3B4159, used sparingly; tonal contrast carries most resting depth. Opaque heavy borders create a wireframe "cage." Where a line is needed on varied surfaces, a semi-transparent white overlay (e.g. `rgba(255,255,255,0.06)`, as the live EarningsChip already uses for its neutral state) adapts to the background rather than fighting it.
- Severity: **P3** for harsh borders on secondary elements. **P2** if borders dominate the field and cage the content.

**Accent overuse — the One-Accent Rule**
- This is Chrollo's strictest color law: **Signal Blue (#5B8AFF) is the only interactivity color.** Active nav, focus rings, primary buttons, links, R-chips. The categorical accents (violet/rose/gold) are *labels*, not buttons. If you reach for a categorical hue to mean "clickable," you are wrong, and blue stops reading as a signal. Check: is blue scarce and reserved for primary/active, or sprayed across every interactive element?
- Severity: **P2** for accent overuse that flattens hierarchy. **P2 also** for a categorical/tier hue used to imply clickability (it misleads the eye).

**The Tier-Reserve Rule**
- The S/A/B/C tier ladder (Amber #FF9F43, Violet #BB86FC, Sky #58A6FF, Green #3FB950) is reserved for **tier identity only** — the ticker color and tier badge on a card. Borrowing tier amber or tier violet for a chart series, a decoration, or an unrelated accent makes the trader misread rank. Check chart palettes and chips for tier-hue leakage.
- Severity: **P2** for tier hues escaping tier identity (a real misread risk, not cosmetic).

**Semantic colors that strain against the slate**
- Status hues (Green #3DD37A, Red #F26770, Amber #F0BE3C) each pair with a ~14%-opacity tint of their own hue for pills. Fully saturated reds/greens on dark slate create hot spots that pull the eye disproportionately — exactly what a calm, hours-long instrument must avoid. Check: are status pills using the tinted-background pattern, or raw full-saturation fills?
- Severity: **P2** for full-saturation semantic fills on the dark surface. **P3** for minor saturation tuning.

---

## Principle 4: Spacing creates meaning — use the scale, let proximity group

*Carmack: "State is the enemy." Every spacing value outside the system is ad hoc state that makes the layout harder to reason about.*
*Saarinen: "The grid 8, and the 24 spacing, generally affected our type styles. I think spacing often goes with the typography."*

Chrollo's scale is defined in `DESIGN.md`: xs 4 / sm 8 / md 16 / lg 24 / xl 32, on a 4px base. Every margin, padding, and gap should come from it, and the *relationships* between values communicate grouping: tight within a group, loose between groups.

### What to check

**Arbitrary spacing values**
- Are inline styles and CSS using the scale, or off-grid one-offs (13px here, 17px there)? All spacing should be a multiple of 4. The card components carry a lot of inline `padding`/`gap` numbers — check them against xs/sm/md/lg/xl.
- Severity: **P3** for occasional off-grid values. **P2** for no discernible system across components.

**Spacing not communicating grouping**
- Schoger: "Increase spacing between groups and reduce spacing within groups to leverage Gestalt proximity." On a card, the gap between the score pills should be tighter than the gap between the header row and the mini-chart, which should be tighter than the gap between cards. Check: do the header cluster, chart, and tag row read as three groups, or one undifferentiated stack?
- Severity: **P2** for uniform spacing that makes card regions ambiguous. **P3** for minor proximity issues.

**Density without system**
- Chrollo's design principle 4: "Be dense where density informs… and empty where it doesn't." `DESIGN.md` calls for 5–8px padding on dense card headers and 1.5rem on content panels. The signature screener card must stay legible at four-up — dense, not cramped. If rows touch or lack breathing room within a cell, density is accidental, not designed.
- Severity: **P2** for cramped density that hurts scanability at four-up. **P3** for inconsistent density across similar cards.

**Line-heights not grid-aligned**
- `DESIGN.md` fixes Title at line-height 1, Body at 1.5, Label/Mono at 1. When line-heights drift off these, text blocks create fractional offsets that compound across the wall. Check that custom components don't override these with arbitrary values.
- Severity: **P3** — a refinement that compounds across the whole grid.

---

## Principle 5: Color communicates — drive everything through the design tokens

*Carmack: "Use the type system to prove absence of flaw classes." A named token system eliminates the class of bug where the same conceptual color is specified differently in different places.*
*Saarinen: Linear's tokens are grouped (Bg, Label, Control) with variations. "When designing, I write 'bg base' for default background, 'label base' for default text."*

Chrollo's tokens live in `DESIGN.md` and are exposed to the frontend as CSS custom properties (the live `EarningsChip` already references `var(--warning)`, `var(--warning-bg)`, `var(--text-muted)`). Every color in the UI should trace back to a named token — surface ramp, ink ramp, accent, status, tier — so a single edit propagates and drift is impossible.

### What to check

**Raw hex/RGB instead of tokens**
- Are color values hardcoded in JSX/CSS, or do they reference the CSS variables? This is a real, present leak: `ScreenerCard.jsx`'s `tierColor()` returns literal `'#ff9f43'`/`'#bb86fc'`/… instead of `var(--tier-s)`/`var(--tier-a)`. Those literals must match `DESIGN.md` exactly or the tier ladder silently diverges. Prefer token references; if a JS lookup is unavoidable, it should read the same custom properties.
- Severity: **P2** for widespread raw color with no token discipline (especially tier/status colors, where drift causes misreads). **P3** for an otherwise-tokenized system with occasional literals.

**No semantic color roles**
- Chrollo separates roles cleanly: surface ramp (backgrounds), ink ramp (text/icons), Signal Blue (interactive), status (green/amber/red), tier (identity only). Check: is the same value reused across roles (e.g. a text color doubling as a border or a status fill)? That collapses the role structure that keeps the instrument legible.
- Severity: **P2** for no role separation. **P3** if roles exist but aren't consistently applied.

**Inconsistent color for the same meaning**
- Does "muted secondary text," "panel surface," or "loss/short red" use different values in different components? The card, the archive row, and the journal should all render a loss in the same #F26770 + 14% tint. This is the subliminal inconsistency Saarinen's alignment work targets — felt, not consciously seen. Check the same semantic element across screener / archive / journal.
- Severity: **P2** for visible inconsistency in semantic colors across views. **P3** for minor shade variation.

---

## Principle 6: Motion confirms action — never decorate, never delay, never celebrate

*Carmack: "Latency is always a bug." Every millisecond of unnecessary delay degrades the experience.*
*Saarinen: "Almost everyone said that they hate when these tools are slow… what if we can build a tool that is never slow?" Linear's standard hover transition is 150ms.*

Chrollo's design principle 5 — "Built for long sessions" — makes motion **optional and never load-bearing**, and `PRODUCT.md` bans celebratory animation outright (no confetti, no win-flash). Animation here exists only to confirm a state change (a card marked "considered" dimming to 50%, a panel opening, a star toggling) — not to impress, and never to make the trader *feel good* about a result.

### What to check

**Animations that delay interaction**
- Can the trader act on the destination before the transition finishes? If the timeframe chart modal slides for 300ms and blocks clicks until done, that's a bug. Keep micro-interactions 100–200ms, view transitions ≤300ms, and non-blocking.
- Severity: **P1** for animation blocking input. **P2** for >300ms on frequent interactions (card hover, star toggle, considered-dim).

**Inconsistent timing**
- Saarinen's team chased a bug where "one of the buttons darkened instantly… rather than fading out over 150 milliseconds." `DESIGN.md` specifies hover lifts and a 1px translate on action buttons; those should share one duration. Check: do card hover, nav hover, and pill hover all fade on the same curve, or does one snap while its neighbor fades?
- Severity: **P3** for minor drift. **P2** if the inconsistency is visible on one view (one card animates, the adjacent one snaps).

**No animation on meaningful state changes — but never gratuitous motion**
- The "considered" dim-to-50% and the watchlist-star toggle are state changes that benefit from a brief, subtle transition for continuity. But absence of animation is always better than bad animation, and `PRODUCT.md` is explicit: no heavy or showy motion between the trader and the data. Never add motion just to satisfy this check.
- Severity: **P3** — and the bias is toward *less* motion here, not more.

**Optimistic UI for safe local actions**
- The watchlist star and "considered" checkbox are safe, predictable toggles persisted to the SQLite `watchlist`/archive tables. They should update the card immediately and reconcile with the FastAPI write in the background, not show a spinner on each click. A round-trip on a one-bit toggle is needless latency in a fast triage loop.
- Severity: **P2** for safe toggles that show a loading state. **P3** for minor delay on infrequent actions.

---

## Principle 7: Elevation is a system — and in this UI it is mostly tonal

*Carmack: "Assertions catch assumption violations." A defined elevation system asserts which elements sit above which — violations are immediately visible.*
*Saarinen: Linear defines four shadow levels — Low (buttons) → Float (modals). Elevation is calculated through background lightness: background → foreground → panels → dialogs → modals.*

`DESIGN.md` §4 codifies this for Chrollo: depth is **tonal, not cast.** The shadow vocabulary is tiny and intentional — Card-rest a near-invisible `0 1px 2px rgba(0,0,0,0.4)` seam used sparingly, Elevated/Modal `0 8px 24px rgba(0,0,0,0.5)` for true overlays only, and an Accent glow that is a *state* response (focus/active nav), never a resting decoration. The named **Glow-On-State Rule**: a surface that glows at rest is over-designed — remove it.

### What to check

**Ad hoc shadows off the vocabulary**
- Are box-shadows invented per component, or drawn from the three defined values? Check: do all genuine overlays (modal, dropdown, popover) use the single Elevated shadow, and do resting cards rely on tone + hairline rather than their own shadow?
- Severity: **P3** for no system. **P2** if components at the same elevation carry different shadows.

**Dark-theme elevation without surface differentiation**
- A shadow alone can't lift an overlay on this dark slate — if the timeframe modal shares the card's Panel surface, no shadow will make it float. Elevated elements must step up the surface ramp (toward #303547) *and* take the Elevated shadow.
- Severity: **P1** for an overlay indistinguishable from the wall behind it. **P2** for a dropdown/popover that doesn't clearly float.

**Glow at rest**
- A resting blue glow on a card or pill violates the Glow-On-State Rule and reads as over-design. Glow belongs to hover/focus/active only.
- Severity: **P2** for resting glow on primary surfaces. **P3** on secondary elements.

---

## Principle 8: Component consistency is systematic — and the system is deliberately light

*Carmack: "The single most effective strategy for defect reduction is code reduction." Shared tokens and components reduce the surface area for visual bugs.*
*Saarinen: "There is no design system team, no councils, no meetings… We have a system which has colors, type, icons and components. It feels very simple and light but still useful. Like a good tool."*

This matches Chrollo exactly: a solo project whose system is `PRODUCT.md` + `DESIGN.md` plus a set of shared React components (ScreenerCard, SetupTags, ScoreBreakdown, status/score pills) and CSS custom properties — not a 200-page doc. The system lives in the tokens and the shared components; consistency means every card, pill, and chip is built from them.

### What to check

**Component visual inconsistency**
- Do buttons, inputs, cards, pills, and chips look the same across screener / archive / journal? `DESIGN.md` fixes the radii — 6px for panels/cards and standard buttons, 12px for modals, pill for status/sidebar-action buttons. If a button is 4px here and 8px there, the instrument feels assembled from parts. Check the same component type across views.
- Severity: **P2** for visible inconsistency in core components (cards, score pills, buttons). **P3** for secondary elements.

**Tokens not actually consumed**
- Are the `DESIGN.md` values exposed as CSS custom properties and read everywhere, or duplicated as literals across components (see the `tierColor()` leak in Principle 5)? The system should be definable once and consumed by every component.
- Severity: **P2** for widespread literal duplication of system values. **P3** for partial adoption.

**One-off implementations of a repeated pattern**
- A pattern that appears many times (the score pill, the setup-tag chip, the status pill) should have one implementation. If the score pill is re-styled inline in three places, they will drift. Check for duplicated chip/pill styling that should be a shared component.
- Severity: **P3** — maintenance concern, P2 only once it produces visible inconsistency.

---

## Principle 9: Quality is the accumulation of small corrections — fix visual debt in the moment

*Carmack: "If a mistake is possible, it will eventually happen." Quality is maintained by finding and fixing mistakes, not by preventing them.*
*Saarinen: "Quality doesn't happen on its own, you need to push for it." Over 1,000 small fixes in two years, each 30 minutes or less. "You start noticing patterns and common pitfalls while building stuff, so fewer of these papercuts ship."*

For a solo trader-developer this is the operative principle: notice when a card's spacing is off, when a tier color doesn't match `DESIGN.md`, when a number column jitters — and fix it in the moment. The `impeccable` skill exists to run these passes; the memory record shows the screener climbing from a 26→29/40 critique exactly this way.

### What to check

**Visible layout shifts**
- Does any interaction make the grid jump? Saarinen's team fixed a case where "the issue composer height changed when adding a line." On the card wall, watch: does marking a card "considered" (dim to 50%) reflow its neighbors? Does a tag row wrapping to a second line shove the chart? Does live P&L widening shift columns (this is exactly why P&L must be tabular)?
- Severity: **P1** for shifts on primary triage interactions (considered, star, hover). **P2** for shifts on secondary ones.

**Inconsistent hover/focus states**
- Do all interactive elements (card, star, checkbox, nav link, pill, button) have visible hover and focus, and do they respond consistently? `DESIGN.md` standardizes a 3px Signal-Blue soft focus ring. Hover every interactive element on a view — do they all respond, and the same way?
- Severity: **P2** for interactive elements with no hover/focus. **P3** for inconsistent treatments.

**Pixel-level polish issues**
- Ticker or setup-label truncation without ellipsis, a chart canvas overflowing its card, tag chips touching the card edge with no padding, an unexpected scrollbar on the wall. Each is individually P3, but 5+ on one view signals systematic neglect — the difference between "rough" and "instrument-grade."
- Severity: **P3** individually. Note the count.

---

## Principle 10: Know your gaps — what this doc is weaker on

*Carmack: epistemic humility — you can't fix what you don't know is broken.*
*Saarinen: his published body of work is narrower than other experts in this system — a practitioner who ships, not a prolific author. Many decisions are observable in Linear but never explicitly discussed.*

### Areas this doc is weaker on (supplement from other sources)

- **Chart legibility specifics.** `lightweight-charts` and `recharts` carry most of Chrollo's information, yet Saarinen has not published chart-design guidance. Theme both libraries off the design tokens — slate background, ink-ramp axes/gridlines kept faint, status green/red for up/down candles, and **never** a tier or categorical hue for a series (Tier-Reserve Rule). Mini-chart legibility at four-up density is a first-principles problem this doc can only point at.
- **Accessibility.** `PRODUCT.md` sets a single-user ≥4.5:1 body-contrast bar and notes win/loss currently lean on red/green hue alone — acceptable for the sole user, pair hue with shape/text if Chrollo ever gains others. No formal WCAG audit here.
- **Responsive density.** The card wall is a responsive reading-room grid (four-up → fewer-up), but specific breakpoint behavior for the dense card is a judgment call; supplement with quality-ux.md.
- **Data-viz statistics.** Forward-return distributions, edge stats strips, and confidence displays for the engine-validation work need domain-specific charting guidance beyond this doc.
- **Iconography & easing curves.** Icon weight/grid and the exact easing for the standard ~150ms transition are not specified in `DESIGN.md`; decide from first principles (ease-out is the safe default) and keep them consistent once chosen.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Trader cannot parse the view, spatial relationships are broken, or interaction is blocked | Modal/overlay indistinguishable from the card wall, signal unreadable due to contrast, animation blocking input, layout shift on a triage interaction (considered/star/hover) |
| **P2 — Fix Soon** | Hierarchy degraded, system broken, or the instrument feels rough | Chrome competing with cards, accent/tier hue used as "clickable" (misread risk), raw color literals diverging from `DESIGN.md`, no surface-step elevation, changeable numbers not tabular, full-saturation status fills, labels dominating data, celebratory motion |
| **P3 — Consider** | Polish, systematization, refinement | Off-grid spacing, a sixth type style, minor alignment drift, missing hover state, pixel overflow/truncation, hover-timing drift, mono not used for an incidental figure |

### The Overriding Filter

Before writing any finding, apply the Saarinen-Carmack synthesis through Chrollo's own law (`PRODUCT.md` + `DESIGN.md`):

1. **Can the trader immediately identify what matters on this view?** Confident hierarchy is required; a flat, egalitarian layout is a defect, not neutrality. If hierarchy is flat or noisy, flag it.
2. **Is color/spacing/typography driven by the tokens or ad hoc?** If a value is arbitrary or a literal that should be `var(--…)`, flag it.
3. **Does the dark surface feel like a calibrated ramp or a void?** If elevation is missing, a surface is near-black off-ramp, or an overlay floats without tonal grounding, flag it.
4. **Does every element earn its place?** Decoration that doesn't aid the read is debt; a border that a surface step could replace is noise. Flag it.
5. **Is the quality consistent across screener / archive / journal?** If one view is instrument-grade and another is rough, flag it — quality is 1,000 small fixes.
6. **Would this feel fast, and does it stay an honest instrument?** If motion delays interaction *or* celebrates/inflates a result, flag it. The interface reports; the trader decides.
