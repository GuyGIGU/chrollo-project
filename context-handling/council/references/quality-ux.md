# UX Quality Reference — Carmack × Friedman

Philosophy: John Carmack. Specifics: Vitaly Friedman (Smashing Magazine, Smart Interface Design Patterns, Design Patterns for data-dense interfaces).
Stack context: React 19 + Vite SPA / FastAPI + Pydantic backend / SQLite (archive, watchlist) + parquet market-data cache / yfinance + IBKR. The project's own "Instrument Panel" design system (`PRODUCT.md` + `DESIGN.md`) — calm dark theme, JetBrains Mono for numerals. `lightweight-charts` + `recharts`. The user is a single discretionary trader (Minervini-VCP + Qullamaggie style) who uses the screener as an *idea source* and triages ranked setups by eyeballing card-level signals, then bridges grid → TWS / TradingView for the real decision.

Every finding must describe the **concrete UX consequence** — not just "this could be better."
When Carmack and Friedman independently converge on a principle, it earns its place here.

**Scope boundary:** This doc covers UX patterns, information architecture, and interaction design for the screener / archive / trade-journal surfaces. It does NOT cover: accessibility/a11y (the project has a single known user and no formal WCAG target — `PRODUCT.md` documents what's deliberately deferred), visual design aesthetics (Karri Saarinen's Instrument-Panel doc owns those), engine correctness, security, or backend concerns. Where accessibility intersects UX patterns (hit targets, keyboard alternatives), it's noted but not deeply audited.

---

## Principle 1: Structure complexity — don't destroy the trader's read by simplifying it away

*Carmack: "The best code is no code. The second best is simple code." But Carmack never advocates removing necessary complexity — he advocates structuring it so its behavior is obvious.*
*Friedman: "Don't destroy user value by oversimplification." And: "'Efficient' is not always simple and 'simple' is not always efficient." His thesis across 15+ years: "Complex UIs don't have to be complicated."*

Both converge on the same distinction: unnecessary complexity must be eliminated, but necessary complexity must be structured, not hidden. A Wyckoff/VCP screener is a data-dense analytical tool; the trader relies on specific structural detail — tier, score, the why-ranked tags, the card mini-chart — to triage a scan in seconds. Stripping that away to make the grid "clean" actively harms the one person who needs it. The job is to make the structural fingerprint navigable, not to pretend a setup is a single number.

### What to check

**Oversimplified cards that hide the structural read**
- Are the signals the trader actually triages on (score breakdown, the `SetupTags` why-ranked chips, traversal/LPS evidence, the mini-chart) hidden behind a click when they're needed to decide attend-vs-skip? `PRODUCT.md` is explicit: the job-to-be-done is *fast, trustworthy triage* on the grid itself. Forcing a modal open per card to see why a setup ranked breaks the core loop.
- Does the card assume the trader wants a verdict when they actually need the components? A lone tier badge with no visible structure tags is a summary masquerading as a decision. Friedman: "Life is complex, and the tools we design must match the complexities of the real world."
- Severity: **P1** if the trader cannot triage (compare tier/score/structure across cards) without leaving the grid. **P2** if secondary evidence (full score breakdown, HTF context) takes excessive clicks.

**No density controls on the scan grid**
- A scan can return 100+ cards. Does the grid offer density modes? Friedman teaches three levels: low (large text, extra spacing, progressive disclosure), medium (regular size, more cards per row, shortcuts), high (small text, heavy data, customization, filters). A single fixed density forces the daily power-user into a layout meant for a first look — or buries a newcomer in a wall of `JetBrains Mono` numerals.
- Severity: **P3** for a single-user research lab at this stage. **P2** if the trader is regularly fighting the grid to fit a full scan on screen.

**Feature parity destroyed on narrow viewports**
- The screener is described as a responsive reading-room chart wall. Friedman's position: a narrow-viewport version of a data-dense interface should be a different experience, not a shrunk desktop one — "features they heavily rely on don't have to work or look exactly the same." An archive table that just scrolls horizontally on a laptop split-screen is a failure; consider stacked card rows or a column-priority collapse.
- Severity: **P2** for the archive/trade tables that become unusable when narrowed. **P3** for surfaces the trader only ever opens full-width.

---

## Principle 2: Design all five screen states — blank, loading, partial, error, ideal

*Carmack: "If a mistake is possible, it will eventually happen."*
*Friedman credits Scott Hurff's UI Stack: "Every screen you interact with has multiple personalities: blank state, loading state, partial state, error state and ideal state." His practice: "I often start exploring errors and recovery flows early because they often leave users frustrated and disappointed."*

Both treat failure as a first-class concern. This matters acutely here because the data path is *fragile by nature*: yfinance throttles and returns empties, tickers get quarantined as dead, IBKR sessions conflict (single-session-per-username with TradingView), and scans increasingly run **unattended on a schedule**. A component that only looks right with a full clean scan is incomplete — it will meet empty results, a half-fetched universe, a 429 storm, and a dead session in production.

### What to check

**Missing blank/empty states**
- What does the trader see when a scan returns zero qualifying setups, or before the first scan of the day, or when the watchlist is empty? A blank grid with no guidance reads as "broken," not "nothing qualified today." Friedman: "Design sets of filters, templates and empty states." An empty state should say what this view shows, *why* it's empty (no setups passed the gates today vs. scan not yet run), and the next action (run scan / loosen a filter / open the archive instead).
- Severity: **P1** for primary views (screener grid, archive) with no empty state. **P2** for secondary panels (watchlist, IBKR account).

**Full-page loading takeover during a scan**
- A full-universe scan is a multi-stage, CPU-bound pipeline that runs for tens of seconds. The existing `ScreenerScanProgress` already does the right thing — a phase label, a percent, a determinate bar, and a tail of pipeline log lines — *without* locking the rest of the app. Friedman: "Avoid an entire page takeover; lazy-load content panes or use inline loading." For multi-stage work, show stages (fetch → detect → score → rank), not one indeterminate spinner. Skeleton cards beat a spinner for the grid because the layout is predictable.
- Severity: **P1** for any 10s+ operation with no progress signal. **P2** for a full-page spinner that blocks reviewing already-loaded results.

**No partial state handling**
- Scans are inherently partial: some tickers fetch, some 429, some are quarantined. If the fetch-health layer degrades, does the grid render the setups that *did* compute and flag the gap ("scanned 480 / 512 — 32 skipped, data unavailable"), or does one failed fetch blank the whole run? The `ErrorBoundary` component should isolate an independent panel (a broken mini-chart, a failed IBKR enrich) so it doesn't take down the grid. Friedman: "When the page is sparsely populated, our job is to prevent people from getting discouraged."
- Severity: **P1** if a single failed fetch or one bad card crashes the whole view. **P2** for missing error isolation on independent panels.

**Generic error messages**
- Friedman: "Avoid generic error messages: they are often main blockers." A data-source failure must say what went wrong, whose fault it is, and the recovery. "Something went wrong" is a dead end; "Yahoo rate-limited the scan — 47 tickers deferred, retry in a minute" or "IBKR session in use (TradingView open?) — close it and reconnect" is actionable. These are real Chrollo failure modes; name them.
- Severity: **P2** for generic errors on the scan / fetch / IBKR paths. **P3** for secondary flows.

---

## Principle 3: Never freeze the interface on a single input

*Carmack: "State is the enemy. Mutable shared state is the root of most bugs." Applied to UI: state transitions that lock the interface create cascading frustration.*
*Friedman: "Every time we freeze the UI on a single input, we actively slow down our customers in expressing their intent." His strongest filter-design principle.*

Both keep systems responsive. When the trader narrows a scan — tier, score floor, structure-tag filter, sector — the interface must stay interactive while the grid re-filters. Locking it forces a serial workflow (one filter, wait, one filter, wait) when the intent is a compound preference expressed fast: "tier-1 LPS setups above score X in this sector."

### What to check

**Filters that lock during re-filter**
- When the trader applies a screener/archive filter, do the controls stay live while the grid updates? Friedman's pattern: "matching results update asynchronously, while the filters always remain accessible and at the same place." Anti-pattern: the toolbar greys out or becomes unclickable while cards re-render. Prefer dimming the *results* and keeping the controls hot. Re-filtering an already-loaded scan is client-side and should be instant — never round-trip a re-scan just to apply a tier filter.
- Severity: **P1** if the trader must wait for each filter to resolve before applying the next. **P2** if filters stay live but the whole layout reflows on every change.

**Auto-scroll / jump on selection**
- Does opening a card's detail, starring a watchlist item, or paging the grid yank the scroll position? Friedman documents the configurator anti-pattern: "a stubborn scrolling fight against the auto-scroll." If starring a card re-sorts the grid and the trader loses their place mid-triage, they have to re-orient after every action.
- Severity: **P2** for any interaction that moves scroll position without the trader asking.

**No optimistic UI for known-safe local actions**
- Starring a setup to the watchlist (`watchlist` SQLite table), toggling a tag filter, hiding a card — these are predictable, local, reversible. Friedman endorses "optimistic actions where we assume access by default and reduce perceived latency." Carmack's corollary: if it succeeds 99.9% of the time, render success immediately and roll back the rare write failure. Don't make the star wait for the SQLite write to confirm.
- Severity: **P3** — polish, but it compounds across a long triage session.

---

## Principle 4: Progressive disclosure needs visible triggers and hard limits

*Carmack: "The structure of the code should make the intended behavior obvious." Applied to interfaces: hidden information should be obviously hidden — the trader should know it exists before revealing it.*
*Friedman: "The accordion is probably the most established workhorse in responsive design." But with constraints: visible triggers, clear icons, the whole bar clickable, and a maximum of three nesting levels.*

Both demand that structure communicates intent. Progressive disclosure fails when the trader doesn't know there's more to see (a collapsed score breakdown with no affordance), or when nesting gets so deep they lose orientation (HTF context inside box diagnostics inside a card detail).

### What to check

**Hidden evidence with no visible trigger**
- Is load-bearing structure — the full score breakdown, the descent-tail/traversal diagnostics, HTF re-accum context — hidden behind an interaction with no indicator it exists? The `SetupTags` row already handles this well: it measures available width and renders a `+N` overflow chip with the hidden tag labels in its tooltip, so the trader knows more tags exist and can read them on hover. Every disclosure point needs that kind of affordance — an expand chevron, a "+N more" with a count, a labeled section.
- Severity: **P1** if the trader misses critical structure because nothing signals it's there. **P2** for supplementary detail with weak triggers.

**Nesting deeper than three levels**
- Friedman's hard limit: beyond three sublevels "usually is a warning sign that the navigation could be simplified." A card → detail modal → tab → nested collapsible → nested-again diagnostic loses everyone but the author. Each level needs distinct typographic contrast.
- Severity: **P2** for nesting beyond three levels without visual differentiation per level. **P3** for deep nesting only the owner ever reaches.

**Modals used for non-blocking content**
- Friedman's default: "Use a non-blocking dialog by default." Reserve modals for deliberate friction — a destructive archive purge, a maintenance confirm. They should not host informational content the trader wants to compare against the grid behind them. The setup-detail / chart-lens surfaces are review tools, not interrupts; a modal that traps the trader away from the scan breaks the triage rhythm. Every modal must support a close button, ESC, and click-outside.
- Severity: **P2** for modals hosting non-blocking review content. **P1** for any modal with no escape route.

**Dual-function triggers**
- Friedman warns against overloading an element so a single click both navigates AND expands. A card whose body both opens the TradingView/TWS bridge and expands an inline detail on the same tap forces the trader to guess which fires. Separate the affordances.
- Severity: **P2** for elements with ambiguous dual functions.

---

## Principle 5: Disabled controls are a dead end — keep actions accessible

*Carmack: "Assertions catch assumption violations before they become exploitable." A runtime assertion tells the developer exactly what's wrong. A disabled button tells the trader nothing.*
*Friedman: Disabled buttons are "a disastrous design pattern." Two failure modes: users who "sit and wait patiently" assuming it's loading, and users who hit "a wall" and guess which input unlocks it.*

Both: when something is wrong, say what's wrong. Carmack's assertions fail loudly with a specific message; Friedman's accessible buttons fail loudly with a specific reason. Disabling a control and leaving the trader to guess is the UI equivalent of swallowing an exception.

### What to check

**Disabled action buttons — only flag when genuinely confusing**
- Friedman's "always enabled, validate on click" stance is opinionated and not mainstream. **Do not flag disabled buttons** when the blocker is self-evident — e.g. a "Run scan" button disabled while a scan is already running, or a "Connect IBKR" button disabled with a visible "session in use" note right beside it. Those are reasonable.
- **Do flag** disabled controls when the blocker isn't visible: a "Scan" disabled for an opaque reason, or a submit greyed out on a multi-field form (the position-size / add-setup forms) with no hint about which field blocks it.
- The one universally-correct case: disabling a button immediately after click to prevent double submission of a write that hits IBKR or mutates the archive — paired with a loading indicator.
- Severity: **P2** for disabled buttons on multi-field forms where the blocker isn't obvious. Not a finding for simple, contextually clear cases.

**Inline validation that blocks input**
- Validation that fires before the trader finishes typing (a ticker symbol, a date range, a stop price) creates friction. The "Reward Early, Punish Late" pattern is sound: validate the instant they're *correcting* a known error; wait while they edit a valid field.
- Severity: **P2** for validation firing mid-keystroke. Not a finding for standard on-blur / on-submit validation.

**No validation override path**
- Friedman's most distinctive form note: provide a way past inline validation. If the position calculator flags a risk parameter as unusual but the trader knows their intent, there should be a "use anyway" path rather than a hard block.
- Severity: **P3** — a maturity feature that prevents edge-case abandonment.

---

## Principle 6: The dashboard must create understanding and drive action

*Carmack: "If you can't measure it, you can't improve it." A dashboard that displays numbers without enabling action is decoration.*
*Friedman: "Dashboards shouldn't just display data, but create an understanding of that data." And: "Dashboard value is measured by the useful actions it prompts."*

Both: instruments exist to serve a purpose. This is the engine-validation north star in UI form — the archive analytics (forward returns, tier hit-rates, R-multiple distribution) exist to answer "what edge does this engine actually have?" Charts that don't connect to a decision are logging without alerting.

### What to check

**Metrics without context or next step**
- Does every number on the dashboard / archive analytics connect to something the trader can do? "87 setups archived" is trivia. "12 tier-1 setups today — review grid" or "tier-1 forward win-rate 54% over N trades — open the cohort" drives the loop. Friedman: "Communicate one message per chart." The watchlist and scan-status strips should each point somewhere.
- Severity: **P2** for metrics with no action path. **P1** if the primary dashboard shows data that connects to no workflow.

**No drill-down from summary to setups**
- Can the trader go from an aggregate to the underlying setups? Friedman teaches "data drill-downs" as a standard building block. A tier card reading "3 tier-1 this scan" should open that filtered slice; an archive cohort bar should expand into its constituent rows with their forward outcomes.
- Severity: **P2** for summary metrics that can't expand into their underlying data.

**Chart-type mismatches**
- Friedman: "Avoid pie/donut charts when users compare." For the archive's R-multiple histogram, equity / drawdown curves, and tier comparisons, bars / lines / tables (the current `recharts` choices) outperform circular charts. Mini-card structure is best served by the `lightweight-charts` price view, not a decorative gauge. Reach for the FT Visual Vocabulary when unsure.
- Severity: **P3** for merely-suboptimal chart choices. **P2** if a chart actively misleads (e.g. a circular chart for multi-category comparison).

**Missing data-freshness indicators**
- When was this scan run? Is the archive showing yesterday's batch? Forward returns update on a schedule — are they current? A trader deciding off stale prices needs to know they're stale, especially once scans run unattended. Friedman lists freshness indicators as a standard dashboard feature; surface a visible "scanned at HH:MM" / "data as of" stamp.
- Severity: **P2** for time-sensitive views with no last-updated stamp.

---

## Principle 7: Respect the trader's expertise — design for one expert who is sometimes new

*Carmack: "Understand before opining." He never writes tools that assume their user is stupid — they expose power and expect competence.*
*Friedman: Design for three expertise levels — low (progressive disclosure, large text, spacing), medium (regular density, shortcuts), high (small text, heavy data, customization, filters). "In complex environments, users often need access to specific details or raw data."*

Both respect the user. The Chrollo trader *is* the expert — Wyckoff/VCP fluent, the decision-maker, never the tool (`PRODUCT.md`). The interface should expose structure and power, not hand-hold. But "expert at trading" doesn't mean "remembers every tag's exact definition six weeks later," so context stays reachable on demand.

### What to check

**Patronizing the expert**
- Does the interface dumb down what the trader relies on — hiding raw structure behind reassuring summaries, or gating a power view behind a beginner flow? The brand is *honest instrument, never a salesman*: no celebratory framing, no oversimplified verdicts that flatten the structural read. Friedman: design so density and detail are available, not forced off.
- Severity: **P3** at this single-user stage. **P2** if the trader is routinely fighting the UI to surface detail it already has.

**Onboarding that blocks the product**
- Friedman: "Anything that keeps users away from using the product is an unnecessary distraction. Tutorials and walkthroughs are often dismissed almost instinctively." Never block the grid with a full-page coachmark tour. For a single expert user, prefer contextual hints (a tag's definition on hover, as `SetupTags` already does via title tooltips) over a multi-step walkthrough. "Shorten the time to relevance."
- Severity: **P1** for a blocking onboarding overlay. **P2** for dismissable multi-step tours that delay the scan.

**No keyboard shortcuts for the triage loop**
- Friedman treats shortcuts as a first-class power-user pattern. The core loop is repetitive — next/prev card, star to watchlist, open detail, open the TWS/TradingView bridge, page the grid. Keys for those cut real friction in a long session without affecting anyone else.
- Severity: **P3** — an enhancement, not a defect.

---

## Principle 8: Structured controls beat free-form input — the trader thinks in setups, not queries

*Carmack: "Don't build on assumptions you can't verify." A free-text search-everything box assumes the trader can articulate precisely what they want as a string — an unverifiable assumption.*
*Friedman: "Conversational and free-form input is a very slow way of helping users express intent. Usability tests show users get lost in editing, reviewing, typing, and re-typing." The burden of articulating intent should not fall on the user when structured controls would be faster.*

Both: don't force the trader to formulate intent from scratch when typed scope can be a structured control. Chrollo has **no LLM** — the engine is fully deterministic — so this is not about chatbots; it's about how the trader narrows a scan and reaches a setup. A bare "search…" field is slower than tier / score / structure-tag / sector selectors that map directly to how the trader thinks.

### What to check

**Free-text where structured filters would be faster**
- Is the primary way to narrow a scan a free-text box, when tier toggles, a score slider, structure-tag chips, and a sector picker would be both faster and self-documenting? Friedman's framework: scoping/filtering, presets, templates. Free text is fine as a *ticker jump* ("type a symbol to find it"); it's the wrong primary tool for "show me the setups that matter today."
- Severity: **P2** if the main triage filter is free-text for something a selector should do. **P3** if free text exists alongside structured controls.

**The blank-input problem**
- Friedman: "To many, an empty text box is remarkably scary. It says 'ask me anything', but users don't know what to ask or in what format." Any free-form input (a ticker search, a filter expression) needs scaffolding: recent symbols, example syntax, or the active universe shown. A bare field with a "Search…" placeholder and no scope is a small UX failure.
- Severity: **P2** for free-form inputs with no guidance. **P1** if it's the first thing a new session lands on with nothing else actionable.

**Dense output as an undifferentiated wall**
- Friedman: output "must drive people to insights, faster." A scan result or a setup detail with internal structure (ranked tags, evidence per Wyckoff event, score sub-components) should be *structured* — forced ranking so the strongest signal reads first, collapsible diagnostics, the price chart for the geometry — not a flat dump of every field at equal weight. This mirrors the design principle *confident hierarchy*.
- Severity: **P2** for structured content rendered flat and equal.

**Refinement that forces a full re-scan**
- Friedman calls refinement "usually the most painful part of the experience." Tweaking what's shown (sort order, which tag groups are visible, density) should be a UI control acting on the loaded scan — knobs, toggles, sort headers — not a reason to re-run the whole pipeline. Re-scanning the universe just to re-sort is the round-trip to avoid.
- Severity: **P3** for missing refinement controls. **P2** if the trader must re-scan to achieve what a client-side control should do.

**Engine actions without guardrails**
- The engine never trades — IBKR is read-only context — but write actions still exist: archive purges/re-seeds, watchlist edits, maintenance jobs. Friedman: "Building guardrails, permissions and approval flows is critical." A destructive archive operation must *preview* what it will do (how many rows, which cohort) before it runs — not just "Are you sure?"
- Severity: **P1** for destructive archive/data actions with no confirmation. **P2** for confirmations that don't preview the consequence.

---

## Principle 9: Trust compounds slowly and is destroyed by a single failure

*Carmack: "If a mistake is possible, it will eventually happen." His whole error philosophy: design for the failure case, because it will arrive.*
*Friedman: "Every time a user discovers a mistake, it's a small betrayal of trust. Mistakes are expensive — each betrayal chips away at the carefully orchestrated relationship with the user."*

Both: failure is inevitable, and the asymmetry between building and destroying trust is brutal. The screener exists to be *a daily idea source the trader trusts* (`PRODUCT.md`). One confidently-wrong rank — a tier-1 badge on a setup the trader's eye immediately rejects — taxes every future rank. So the interface must build trust proactively (show the reasoning) and degrade honestly (never inflate).

### What to check

**No visible reasoning behind a rank**
- Can the trader see *why* a setup ranked where it did? This is the why-ranked tag system's entire job — the `SetupTags` chips and the score breakdown turn an opaque tier into "ranked here because: worked equilibrium, graded LPS shape, touch-volume." A bare "tier 1, score 87" with no surfaced structure is a black box that erodes trust; the visible evidence is what lets the trader's eye confirm or override the engine. The engine is a deterministic instrument — its reasoning *can* always be shown.
- Severity: **P1** for ranks with no surfaced evidence. **P2** for evidence that exists in the archive payload but isn't rendered on the card.

**Inconsistent numbers across views**
- Friedman: "Once they've had this experience, they perceive the feature as 'broken' in general and ignore it altogether in future sessions." A score that shows 87 on the card and 85 in the detail, or a tier that differs between grid and archive, doesn't just confuse — it permanently breaks trust in *every* score. This is a real risk wherever the live `_evaluate_ticker` path and the archived value can drift; the eval-twins fold and seed-recall `--fresh` re-eval exist precisely to keep card and stored values byte-identical. The UI must never display two different numbers for the same underlying read.
- Severity: **P1** for the same datum showing differently across views. This is a trust-destruction event, not a rounding nit.

**No confidence / quality signal on a rank**
- Not all setups are equally clean. Friedman teaches showing agreement/quality so users can calibrate. A traversal-density grade, an LPS-shape quality, or a simple data-quality flag (thin history, recently un-quarantined ticker) lets the trader weight a rank instead of treating every tier-1 as equal. The honest-instrument brand demands this.
- Severity: **P3** for missing quality signals. **P2** given the product positions itself on analytical rigor.

**Engine output indistinguishable from the trader's own annotations**
- The trader's curated watchlist stars, journal notes, and manual tags coexist with engine-derived ranks and tags. Friedman: "Signal and label" machine-derived content so it works alongside human-curated content. Not because engine output is less trustworthy — but because the trader evaluates "the engine flagged this" and "I starred this" differently.
- Severity: **P3** — a transparency enhancement that builds trust over time.

---

## Principle 10: Know your gaps — what this doc is weaker on

*Carmack: epistemic humility — you can't fix what you don't know is broken.*
*Friedman: openly shares his curricula and admits when topics are emerging vs. mature (form design).*

### Areas this doc is weaker on (supplement from other sources)

- **Accessibility/a11y**: `PRODUCT.md` documents a deliberate non-target — a single known user, no formal WCAG goal, body contrast ≥4.5:1 and motion kept non-essential as hygiene, with a noted future risk that win/loss leans on red/green hue. This doc does not audit screen-reader compatibility, focus management, or ARIA. If Chrollo ever gains other users, pair hue with shape/text.
- **Data-visualization depth**: Friedman teaches honest chart selection but is not a viz specialist. For the statistical surfaces — forward-return distributions, R-multiple histograms, confidence on the engine's edge — supplement with Tufte and domain-specific viz guidance. Chart *legibility and theming* (`lightweight-charts` / `recharts` against the dark Instrument-Panel theme) is owned by the UI-quality doc.
- **Animation and micro-interactions**: the brand mandates calm, optional, never load-bearing motion (the scan shimmer/pulse is decorative and tolerable). Friedman curates rather than authors detailed motion specs (timing, easing); supplement if motion ever becomes functional.
- **Design-system architecture**: this doc audits UX patterns, not how the Instrument-Panel system is built. Token structure, CSS-variable theming, and component composition live in `DESIGN.md` and Karri Saarinen's UI doc.
- **Loading states for very long unattended jobs**: Friedman's published guidance on multi-minute progress is limited. His general principles (no page takeover, skeletons, staged progress) apply to a full-universe scan, but observability for *unattended* scheduled scans — where no human is watching the bar — is an automation-roadmap concern, not pure UX.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Trader cannot triage, is actively misled, or trust is destroyed | Structure hidden behind clicks, no empty state on grid/archive, full-page scan lockout, one failed fetch blanks the view, destructive archive action with no confirm, rank with no surfaced evidence, same datum differs across views, blocking onboarding overlay |
| **P2 — Fix Soon** | Friction is unnecessary or the loop is inefficient | Filters that lock during re-filter, generic data-source errors, modals for review content, free-text where selectors belong, no drill-down to setups, metrics with no action path, no scan-freshness stamp, dense output rendered flat |
| **P3 — Consider** | Polish, consistency, maturity | Missing density controls, no triage keyboard shortcuts, no validation override, no quality/confidence signal on ranks, engine vs. trader content unlabeled, suboptimal chart types, no client-side refinement controls |

### The Overriding Filter

Before writing any finding, apply the Friedman-Carmack synthesis:

1. **Can the trader triage from this view?** If structure is hidden or the grid blocks action, flag it. (Both: structure should make intended behavior obvious.)
2. **Does the interface freeze on input?** If any single filter or action locks the UI, flag it. (Both: minimize blocking state.)
3. **Are all five screen states designed?** If blank, loading, partial, or error states are missing — and the data path *will* fail (yfinance, IBKR, quarantine) — flag it. (Both: failure will happen; design for it.)
4. **Is complexity structured or stripped?** If load-bearing structure was removed to "clean up" the card, flag it. (Both: eliminate unnecessary complexity, structure necessary complexity.)
5. **Does the trader know why it ranked?** If a rank lacks surfaced evidence, a control is disabled without explanation, or a number appears without context, flag it. (Both: the instrument must communicate what it's doing and why.)
6. **Is the interface honest about uncertainty?** If a rank is presented with false confidence, or data freshness/quality is obscured, flag it. (Both: epistemic honesty is non-negotiable — and the engine-validation north star.)
