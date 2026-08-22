# Saarinen (UI) — One-Verdict + Instrument-Panel Coherence Review
Run: 2026-08-22-2250 · main @ dd4c0ab · code-reading pass (JSX/CSS + payload tracing), no server booted

Lane question: does the operator SEE one verdict? Short answer: **the lens does; the ranking and
every small score-print around it do not.** The wire carries BOTH verdict systems on every v2 row
(`score` = legacy raw points, `ta_grade` = the 0-100, `tier` = derived from ta_grade since the
2026-08-09 flip — verified in `engine_alpha/evaluation.py:717-729` and `output/dashboard.py:223,356`),
and the frontend still spends the legacy number in four places and, worse, ranks the whole grid by it.

Verdict-surface inventory (verified, for the census):
- **Screener card face** — tier only. Clean.
- **Lens (SetupStoryPanel)** — ta_grade /100 protagonist; legacy Visual/Market pills only for
  pre-v2 payloads, documented dual-epoch. Clean.
- **Tag chips** — `tagResolver.js` dual-epoch by the `fired_tags` presence switch, EC-28-clean.
- **Watchlist 3-pane page** — tier hue only, no score. Clean.
- **Calibration workbench** — concordance grades (`fired · tier`), a different axis, one system. Clean.
- **PowerPlayRegister** — margin-note chrome per its ruling. Clean.
- **The leaks** — grid rank order, sort menu, cockpit chips, watchlist manager column, weekly
  review, hover glance, archive table: findings 1-5 below.

---

FINDING:
- Title: The grid's rank order is the retired score; the badges on it are the grade
- File: webapp/frontend/src/hooks/useScreenerFilters.js:137 (order consumed as-is), origin core/pipeline/screener.py:327 + output/dashboard.py:471-474 (order = legacy `Score` desc), label webapp/frontend/src/components/ScreenerToolbar.jsx:217
- Principle: Context brief question 1 (one verdict); quality-ui.md Overriding Filter 1; EC-28 spirit (the ranking judgment should arrive resolved by the ONE live system)
- Severity: P1
- What's wrong: The default "Score (high to low)" sort passes `ordered_tickers` through untouched, and that order is the pipeline's sort on the LEGACY raw score — while the tier badge on each card and the 0-100 in the lens derive from `ta_grade`. The two sums differ structurally (normalization, warning multipliers, demoted market terms), so nothing guarantees the order respects the tier ladder.
- Consequence: On the primary triage surface, top-left-is-best is computed by the system the operator retired; a Tier-A card can legally sit above a Tier-S one and no visible number explains why (the card face prints no score). This is the operator's "competing versions" disease made spatial — the rank truth and the badge truth come from different engines.
- Fix: Rank by the grade at the pipeline seam (a flip-seam ruling for the legacy-retirement program — ranking changes what he sees first, so it needs the operator's go, not a client re-sort). Until then the grid is silently bi-truthed.

FINDING:
- Title: "Visual score" / "Market score" sorts re-rank the live grid through the frozen legacy remnant
- File: webapp/frontend/src/hooks/useScreenerFilters.js:140-141,149-150 + webapp/frontend/src/components/ScreenerToolbar.jsx:216-223
- Principle: EC-28 (a client-computed judgment re-orders the surface); AGENTS.md — setupScoreMath.js is frozen, "retires with the legacy path"
- Severity: P2
- What's wrong: Two sort options compute the legacy Visual/Market split client-side via `deriveScoreBreakdown(sub_scores)`. On v2 payloads those numbers render NOWHERE anymore (the lens shows chapters), so the option re-orders the grid by invisible arithmetic from the retired epoch.
- Consequence: The operator picks a sort and receives an ordering justified by numbers no surface can show him — a hidden second truth — and the sort path is a live consumer that blocks the staged retirement of setupScoreMath.js.
- Fix: Replace with grade/chapter sorts served from fields already on the wire (ta_grade, chapter points), or delete the two options in the retirement change; never extend the remnant.

FINDING:
- Title: The "Relative strength" sort is a dead control — every row compares 0 to 0
- File: webapp/frontend/src/hooks/useScreenerFilters.js:144; config/settings.py:884 (SCORE_RS_BONUS = 0 since 2026-07-25)
- Principle: EC-26 spirit (a control that no-ops without a trace lies on the only surface the operator sees); quality-ux P9 via EC-15's falsified-record logic
- Severity: P2
- What's wrong: The sorter keys on `sub_scores.rs_bonus`, which has been weight-0 for a month — `_ramp(…, 0)` emits 0.0 on every row, so the comparator is constant and the stable sort silently keeps the legacy-score order.
- Consequence: An offered ranking that provably does nothing; the operator believes he re-ranked by RS and is still looking at the default order. Dead-knob debris (the demoted rs term) surfacing as UI.
- Fix: Remove the option, or key it on the archived raw RS measure if RS ordering is genuinely wanted — an explicit decision, not a silent no-op.

FINDING:
- Title: The legacy raw score prints unlabeled beside grade-derived tiers on four live surfaces
- File: webapp/frontend/src/components/home/ActionCenter.jsx:170; components/ScreenerWatchlistPanel.jsx:112-117; components/WeeklyReview.jsx:158; components/ui/HoverGlass.jsx:108-117 (fed by components/glanceResolvers.js:25-30)
- Principle: DESIGN.md §components/setup-story-panel — the /100 marker exists because the grade "must never be misread as the legacy raw score"; utils/scoreFormat.js's own incommensurability rule; quality-ui P2 (scale/label hierarchy)
- Severity: P2
- What's wrong: The cockpit's Fresh-S-tier chips, the watchlist manager's "Score" column, the weekly-review ledger, and the hover-glance header all print `data.score` — legacy raw points — with no scale marker, beside a tier letter that was derived from `ta_grade`. One click deeper the lens prints a different number for the same setup, suffixed /100.
- Consequence: Two unlabeled numbers on two incommensurable scales for one setup, one click apart. The cockpit chip literally annotates a grade-derived "S" with the raw-score figure that did not produce it — the exact misread the /100 doctrine was written to prevent, on the surfaces that lack the marker.
- Fix: On v2 rows show the grade (with its /100 or a "grade" label) and reserve the raw number for pre-v2 rows with an epoch tell; where a surface's payload lacks `ta_grade` (the weekly-review save ledger), that is a backend serialization addition per EC-28 — never a client fallback, and never coalesced (scoreFormat.js forbids it).

FINDING:
- Title: Archive table's Score column crosses the epoch seam with no per-row tell
- File: webapp/frontend/src/components/archive/ArchiveTable.jsx:22-23,147 (contrast: components/archive/ArchiveTierCards.jsx:31 already carries the epoch warning as a tooltip)
- Principle: quality-ui P2 (same semantic element must mean one thing across a view); the ArchiveTierCards tooltip's own stated rule ("tier and score mean different things across the seam")
- Severity: P3
- What's wrong: The books-of-record table prints tier + raw score for every row and sorts on Score; for post-flip rows the letter came from ta_grade, so the number beside it is not its source, and no row-level marker says which epoch a row belongs to — the caveat lives only on the tier cards above.
- Consequence: Sorting the ledger by Score interleaves epochs whose ranked-by number differs from the shown number; a per-epoch read requires knowledge the table withholds.
- Fix: Add a nullable grade column (dash pre-v2, per scoreFormat's two-column rule) or a per-row epoch marker; keep the scales in separate columns, never merged.

FINDING:
- Title: Off-ramp raw colors on card and lens chrome
- File: webapp/frontend/src/components/ScreenerCard.jsx:19,52,126,353; components/watchlist/WatchlistCardGrid.jsx:71; components/ScreenerModal.jsx:83
- Principle: quality-ui P5 (token leaks); DESIGN.md §Neutral — "This ramp *is* the depth system"
- Severity: P3
- What's wrong: Card-header scrims use `rgba(20,23,33,…)` (#141721 — darker than the ramp's darkest step), the modal toolbar sits on `#202330` (between the sidebar and panel steps), and the PassButton's idle grey `#6b6b7a` is outside the ink ramp. The scrim value is hand-twinned across ScreenerCard and WatchlistCardGrid.
- Consequence: Surfaces below/between the ramp are un-tunable drift points in a system whose depth IS the ramp; the twinned scrim can diverge the next time either card is touched.
- Fix: Promote the header scrim to one named token (or an existing ramp step at opacity) and take the idle grey from the ink ramp; point both card files at the same token.

FINDING:
- Title: Mythril — the active color itself — has no channel token, so its rgb triple is hand-copied
- File: webapp/frontend/src/index.css:36-43 (token block); hand-copies at components/ScreenerCard.jsx:238,340, components/watchlist/WatchlistCardGrid.jsx:34, components/IbkrModeControls.jsx:132, components/tradeDetail/tradePlanDrawerStyles.js:157 (chartTheme.js:26 is exempt — canvas needs concrete hex by contract)
- Principle: DESIGN.md §Status — "every tint is mixed from a single channel token … so a softened hue can't drift across files"; quality-ui P5
- Severity: P3
- What's wrong: The doctrine gives success/danger/warning/operator/trigger their `--*-rgb` channel tokens but not mythril; five JS sites hand-mix `rgba(79,207,196, α)` at ad hoc alphas (0.35/0.45/0.65) outside the named --myth-soft/glow/wash steps.
- Consequence: Mythril was already re-steered once (off leaf-green); the next tune leaves stale hover borders and disabled fills scattered through JS — precisely the drift class the channel-token rule was written against, on the system's most meaningful color.
- Fix: Add `--myth-rgb` and route the JS alphas through it (or snap the ad hoc alphas onto the existing named steps).

FINDING:
- Title: The ticker changes typeface between the card and the lens
- File: webapp/frontend/src/components/ScreenerModal.jsx:92 (JetBrains Mono 22) vs components/ScreenerCard.jsx:144 (Inter 850/19)
- Principle: DESIGN.md §Typography — Title (Inter 850) is for "ticker symbols and primary identifiers"; mono is reserved for compact figures; quality-ui P2 (inconsistent type treatment of the same element)
- Severity: P3
- What's wrong: The lens toolbar sets the ticker in the mono face at 22px while every other surface (card, glance, watchlist rail) sets tickers in Inter 850.
- Consequence: The system's heaviest identity element swaps families across the most-used click-through — the subliminal "assembled from parts" inconsistency, at the pair the operator stares at most.
- Fix: Set the modal ticker in Inter 850 like its siblings; keep mono for the price beside it.

---

Density note (lane item 3, not deep-dived): nothing found violating denser-over-bigger in code —
the lens takes the full viewport minus a 12px scrim (deliberately annotated as such), card chart
heights clamp at 180-240px, and the watchlist/manager tables ride the dense InstrumentTable
primitive. No oversized hero elements introduced since the last pass.
