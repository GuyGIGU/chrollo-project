# Saarinen — UI Quality Review (2026-06-30-1124)

## Domain Verdict

Visually, the multi-universe UI is **coherent, not fragmenting** — and on my axis that supports the "keep fixing surgically" verdict. The three universes share one card wall, one toolbar, one card component, and one set of CSS tokens; the switcher was *deliberately* built to reuse the toolbar's tier-pill grammar so "selected" reads identically everywhere (`segStyle` mirrors `tierButtonStyle` line-for-line). Nothing about adding a universe dimension fractured the instrument's surface — there is no per-universe hue, no parallel layout, no second card style. The one real visual cost of the `universe_type` seam shows up as a *hierarchy* problem, not a fragmentation one: the most consequential control on the page (the dataset selector) carries the exact same visual weight as a second-order filter chip sitting one row below it, and the brand-new `shallow_history` status renders in the calmest, most ignorable treatment in the status vocabulary despite being an action-needed state. Both are localized token/treatment fixes, not structural rebuild signals. The seam is being closed cleanly on the UI side; my findings are papercuts on a sound surface.

---

FINDING:
- Title: The `shallow_history` / "Rebuild data" status renders as the *quietest* state, under-signaling an action the user must take
- File: webapp/frontend/src/components/ScreenerToolbar.jsx:111-118, 306-312, 263-267, 277-295
- Principle: Reduce noise to reveal hierarchy (#1) + Color communicates / semantic roles (#5)
- Severity: P2
- What's wrong: `shallow_history` matches no branch in `statusColor`, `statusStripStyle`'s text-color test, or `downloadColor`, so it falls through to `var(--text-muted)` grey dot, muted-grey text, and a default Signal-Blue download button — visually identical to the neutral "Checking data..." loading strip and *calmer* than the pink "Repair" state. Yet its label "Rebuild data" is one of the most action-demanding states in the set (the cache is too shallow to trust).
- Consequence: The trader glances at a grey dot and muted text and reads "nothing to do here," exactly when the instrument needs them to rebuild the cache before trusting the scan.
- Fix: Give `shallow_history` an explicit warning-class treatment matching its severity — an amber dot and non-muted text in the strip, and a warning-colored download button — so its visual weight matches "act on me," not "idle."

FINDING:
- Title: The universe switcher — the highest-order context control — shares the exact visual rank of the second-order tier-filter chips
- File: webapp/frontend/src/components/UniverseSwitcher.jsx:60-71; webapp/frontend/src/components/ScreenerToolbar.jsx:321-328
- Principle: Confident hierarchy / reduce noise to reveal hierarchy (#1)
- Severity: P2
- What's wrong: `segStyle` is a deliberate clone of `tierButtonStyle` (same 16px radius, 12px size, blue-fill-when-active, transparent-at-rest). The switcher changes the *entire dataset*; the tier chips one row below merely filter within it. Two controls of completely different consequence are rendered at identical weight, distinguished only by a "Universe:" label and a row gap.
- Consequence: A returning trader can't tell at a glance "which dataset am I looking at" from "which tier filter is on" — the most consequential selector on the page reads as just another chip row.
- Fix: Lift the switcher a tier in the hierarchy without adding a hue — e.g. a heavier resting weight, a slightly larger segment, or seating it in its own panel/segmented-control container — so the dataset context out-ranks the in-grid filters visually.

FINDING:
- Title: Repair-state status borrows Categorical Rose (a label hue) for a status signal, and falls back to Tier-A violet
- File: webapp/frontend/src/components/ScreenerToolbar.jsx:264, 282-284, 309
- Principle: Color communicates / semantic roles (#5) + Tier-Reserve Rule (#3)
- Severity: P2
- What's wrong: `needs_repair` drives both the status dot and the download button to `var(--accent-pink, #bb86fc)`. `--accent-pink` resolves to `#E07AA0` (Categorical Rose — DESIGN reserves it for the "setup" action / critical pill, not a data-status). This adds a fourth status hue outside the green/amber/red status ramp, and the literal fallback `#bb86fc` is Tier-A violet — if the var ever fails to resolve, a *status* element would paint in a reserved tier color, a Tier-Reserve violation.
- Consequence: The repair state reads in a categorical "setup" hue rather than as a graded warning, and a tier hue can leak into a non-tier element, both of which subtly mislead the eye about what the color means.
- Fix: Map `needs_repair` onto the status ramp (warning amber for "fixable," red for "blocked") and drop the `#bb86fc` literal fallback so no tier hue can leak in.

FINDING:
- Title: Fixed-width, ellipsis-clipped status strip can degrade to a colored dot with no word
- File: webapp/frontend/src/components/ScreenerToolbar.jsx:289-295
- Principle: Reduce noise to reveal hierarchy (#1) — chart/strip legibility
- Severity: P3
- What's wrong: `statusStripStyle` pins `maxWidth: 280px` with `overflow: hidden` + `textOverflow: ellipsis` + `whiteSpace: nowrap`. The label is the load-bearing half of the signal; on a narrow action cluster (it `flexWrap`s and competes with two buttons) a longer label like "Provider limited: 12m" or "Stale: 2026-06-28" can ellipse, leaving the trader a colored dot with a truncated word.
- Consequence: In a squeezed layout the trader sees a red/grey dot but can't read *why*, and must hover for the title tooltip to recover the state.
- Fix: Let the strip size to its (short) content rather than capping at 280px, or guarantee the state word survives truncation (truncate any trailing value, never the leading status word).

FINDING:
- Title: Branded Signal-Blue focus ring is absent on the switcher/toolbar buttons (they rely on the UA default outline)
- File: webapp/frontend/src/components/UniverseSwitcher.jsx:29-38; webapp/frontend/src/components/ScreenerToolbar.jsx:138-148, 159-170, 226-234
- Principle: Quality is the accumulation of small corrections — consistent focus states (#9)
- Severity: P3
- What's wrong: These buttons are inline-styled with no `className`, and there is no global `button:focus-visible` rule in index.css — so they show only the browser's default outline, not the 3px Signal-Blue soft ring DESIGN standardizes (and that `.screener-card`, form inputs, `.home-tile` already use). NOT re-raising the prior P1 "missing focus ring," since a UA outline *does* appear and `outline:none` is not set here; this is the narrower consistency gap that the branded ring DESIGN specifies is still missing on these controls.
- Consequence: Keyboard focus on the universe switcher and filter chips looks like a generic browser app rather than the instrument's own focus language — felt as inconsistency by a keyboard user moving between cards (branded ring) and chips (UA ring).
- Fix: Apply the standard 3px Signal-Blue `:focus-visible` ring to these buttons (a shared class or a global `button:focus-visible` token rule) so focus reads in one language across the view.

FINDING:
- Title: Pervasive off-grid spacing across the three components
- File: webapp/frontend/src/components/ScreenerGrid.jsx:93, 224, 268, 342; webapp/frontend/src/components/UniverseSwitcher.jsx:61; webapp/frontend/src/components/ScreenerToolbar.jsx:286, 290
- Principle: Spacing creates meaning — use the scale (#4)
- Severity: P3
- What's wrong: Many gaps/paddings sit off the 4px scale (xs4/sm8/md16/lg24/xl32): grid `gap:14px`, drilldown `gap:14px` vs page `gap:20px`, lineage `gap:10px`/`padding:10px 14px`, segment `padding:5px 14px`, status-strip `gap:7px`, `marginTop:-8px`. The card-wall column gap (14) doesn't match the page vertical rhythm (20), so the grid's internal and external spacing don't share a system.
- Consequence: Individually invisible, but the off-grid values compound across a dense wall as fractional misalignments — the "felt after a few minutes" roughness DESIGN's scale exists to prevent.
- Fix: Snap these to the scale (e.g. 14→16, 10→8, 7→8, 5→4/8) and reconcile the grid gap with the page gap so internal and external rhythm agree.

FINDING:
- Title: 16px (`--radius-lg`) used for pill-shaped toolbar/switcher buttons — neither the 6px standard nor a true pill
- File: webapp/frontend/src/components/ScreenerToolbar.jsx:322, 346, 356, 362; webapp/frontend/src/components/UniverseSwitcher.jsx:62; webapp/frontend/src/components/ScreenerGrid.jsx:276
- Principle: Component consistency / radii (#8)
- Severity: P3
- What's wrong: Every chip-style control (tier, universe, more, reset, tag, drilldown "Back") uses `var(--radius-lg)` = 16px. DESIGN fixes standard buttons at 6px (`radius-sm`) and status/sidebar-action buttons at pill (9999px); 16px is a third radius for the same control family. It is internally consistent across the toolbar+switcher (intentional), so this is system-off-spec, not fresh divergence.
- Consequence: The control family reads slightly "rounder than standard" everywhere it appears — harmless in isolation but a quiet drift from the documented radii vocabulary.
- Fix: Decide whether these are standard buttons (6px) or pills (9999px) and converge on the DESIGN value; if a 16px "chip" radius is genuinely wanted, add it to the radii vocabulary so it's a system value, not an ad hoc one.

---

**Summary: 7 findings — P1: 0, P2: 3, P3: 4.**
