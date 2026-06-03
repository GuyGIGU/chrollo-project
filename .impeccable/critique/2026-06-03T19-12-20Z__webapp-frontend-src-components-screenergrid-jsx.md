---
target: screener grid
total_score: 26
p0_count: 0
p1_count: 3
timestamp: 2026-06-03T19-12-20Z
slug: webapp-frontend-src-components-screenergrid-jsx
---
# Critique — Screener Grid (`ScreenerGrid.jsx` + card/toolbar surface)

Source + deterministic-detector critique. Live browser inspection skipped: rendering the grid requires the backend with scan data, which is out of scope per project guardrails. No user-visible overlay was produced.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Scan progress + loading/empty states exist; no scan-failure state. |
| 2 | Match System / Real World | 3 | Expert domain language fits the sole user; some setup labels unexplained. |
| 3 | User Control and Freedom | 3 | Reset filters, modal Esc/arrows, pager. Toggles reversible but no explicit undo. |
| 4 | Consistency and Standards | 2 | Ad-hoc radii (5/6/8/12/16px; 8px not a token) and several competing color systems. |
| 5 | Error Prevention | 3 | Scan disabled while running; mostly read-only triage so low surface. |
| 6 | Recognition Rather Than Recall | 3 | Tooltips on pills/tags + tag legend; labeled controls. |
| 7 | Flexibility and Efficiency | 2 | Modal arrow-nav is great, but grid cards aren't keyboard-focusable; no bulk actions. |
| 8 | Aesthetic and Minimalist Design | 2 | Card header + toolbar carry many same-weight elements; high color load. |
| 9 | Error Recovery | 2 | Few surfaced error states; null data shows only a generic loading line. |
| 10 | Help and Documentation | 3 | Tooltips + tag legend are good contextual help. |
| **Total** | | **26/40** | **Acceptable (upper band)** |

## Anti-Patterns Verdict

**Does it look AI-generated? No.** This is clearly hand-built: domain-specific density, a genuine responsive tag-overflow fitter (`fitTags`), a meaningful tier-color system, and tabular numerics. It is not generic-SaaS filler.

**Deterministic scan:** `detect.mjs` returned `[]` on the JSX files. Weak signal (the detector targets HTML markup, not inline-styled JSX), so read as "no gross markers," not a clean bill.

**The one real slop-adjacent tell** is decorative gradients that contradict the anti-references just chosen in PRODUCT.md: the `.brand-text` gradient-text and the three stacked radial glows on `.app-layout`. The 4-up identical-card grid sits *near* the "identical card grid" anti-ref but is saved because each card carries genuinely varying data and a real triage job.

## Overall Impression

A dense, competent instrument that already respects the brand intent — but the **hierarchy inside the card and the color load across the grid** are the two things standing between "acceptable" and "sharp." The single biggest opportunity: make the eye land on **tier + score** first, and quiet the competing color systems so the grid reads calm at four-up.

## What's Working

1. **Real, earned density.** The screener card fits ticker, tier, setup, dual sub-scores, a mini chart, and an auto-fitting tag row into a compact unit without feeling broken. The `fitTags` responsive overflow (`+N` chip) is craft most dashboards skip.
2. **Coherent token system.** Everything is wired to CSS variables; the tier ladder (S/A/B/C) is consistent and meaningful.
3. **Opinionated triage interaction.** Dimming "considered" cards to 50% turns the grid into a live worklist — exactly right for a research lab, and on-brand for "honest instrument."

## Priority Issues

- **[P1] Weak in-card hierarchy.** The header packs ~8 same-weight elements (star, considered checkbox, ticker, tier letter, setup label, earnings chip, "Score N" at 10px, sub-score pills). The score — the primary triage signal — is not visually dominant.
  - *Why it matters:* triage speed depends on the eye landing on rank+score instantly; flat weight forces the user to read every card linearly.
  - *Fix:* promote tier+score to the dominant visual element (size/weight), demote secondary chrome (earnings, sub-pills) to a quieter tier.
  - *Suggested command:* `/impeccable layout`

- **[P1] Too many simultaneous color systems.** Tier hues (4) + tag group tones + score-pill semantics (visual=blue, market=green, fusion=gold) + status + the blue "active" fill on tier AND tag filters. At four-up this is a lot of color competing, fighting both "calm" and the DESIGN.md One-Accent Rule.
  - *Why it matters:* color stops being a signal when everything is colored; the grid reads busy, not calm.
  - *Fix:* pick one carrier of color per zone (e.g. tier owns the card identity; tags go monochrome-with-one-accent; sub-pills lose their hue or share one).
  - *Suggested command:* `/impeccable quieter`

- **[P1] Toolbar option overload.** Filter row (6 tier pills + search) + sort row (2 selects, sort has 6 options) + tag-filter row (N pills) + tag legend, all stacked and always visible. Exceeds the ~7-item working-memory threshold before the user even reaches the grid.
  - *Why it matters:* extraneous cognitive load on every visit; the controls compete with the data they filter.
  - *Fix:* collapse advanced filters (tags, sort) behind a disclosure; keep tier + search always-on.
  - *Suggested command:* `/impeccable distill`

- **[P2] Grid cards aren't keyboard-operable.** Cards are `<div onClick>` with no `tabindex`, role, or focus ring; only the modal supports keyboard (Esc/arrows).
  - *Why it matters:* a power user can't sweep the grid from the keyboard; no visible focus state.
  - *Fix:* make cards real buttons (or add role/tabindex + Enter handler + focus-visible ring).
  - *Suggested command:* `/impeccable harden`

- **[P2] Radius/spacing inconsistency.** Radii in use: 5, 6, 8, 12, 16px and pill — but the token scale is 6/12/16/pill, and 8px isn't a token. Tier pills 16px vs tag pills 12px vs search 8px reads slightly arbitrary.
  - *Why it matters:* small inconsistencies undercut the "precision instrument" feel.
  - *Fix:* snap every radius to the token scale; pick one pill radius for all filter chips.
  - *Suggested command:* `/impeccable polish`

## Persona Red Flags

**Alex (Power User):** No keyboard path through the grid — cards are click-only divs, no focus ring, no Enter-to-open. No bulk action on watchlist/considered (one click per card). The modal's arrow-key paging is the one real accelerator; the grid itself has none.

**Sam (Accessibility-Dependent):** Cards aren't focusable or labeled; a keyboard/SR user can't reach a card's open action. Filter active-state and many tag tones are conveyed by color alone. (User opted "solo, minimal" a11y, so these are noted, not urgent.)

**The Discretionary Trader (project persona):** Sits down to triage a fresh scan fast. Helped by density and the considered-dimming worklist; slowed by the flat in-card hierarchy (must read each card rather than scan rank+score) and the busy toolbar between them and the grid.

## Minor Observations

- `.brand-text` gradient-text and `.app-layout` triple radial glow contradict the "over-designed" anti-reference (P3 cleanup).
- No scan-failure UI; if a scan errors the grid likely just stays on the generic loading line.
- "Run Market Scan Now" is a good verb+object label; keep that voice for new controls.

## Questions to Consider

- What if a card's tier+score were the loud thing and everything else receded — would you triage faster?
- Does the toolbar need every filter visible at once, or only tier + search, with the rest one click away?
- If color were rationed to one carrier per zone, would the grid finally feel "calm" at four-up?
