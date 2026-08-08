---
name: Chrollo
description: A Wyckoff/VCP setup screener and trading-research lab — an instrument panel for reading market structure.
colors:
  bg-main: "#1A1D26"
  bg-sidebar: "#1E2230"
  bg-panel: "#232735"
  bg-hover: "#2A2F3E"
  bg-elevated: "#303547"
  text-main: "#E8EAF0"
  text-muted: "#9AA1B2"
  text-faint: "#8A93A8"
  border-color: "#384357"
  border-strong: "#4A5470"
  myth: "#4FCFC4"
  myth-ink: "#07211E"
  myth-bright: "#8CEAE0"
  myth-dim: "#39A79E"
  accent-blue: "#5B8AFF"
  accent-purple: "#9B70F7"
  accent-pink: "#E07AA0"
  accent-yellow: "#D4B85A"
  accent-orange: "#E0A05A"
  operator: "#9B70F7"
  trigger: "#E8863C"
  success: "#3DD37A"
  danger: "#DE6E78"
  warning: "#E2B255"
  tier-s: "#FF9F43"
  tier-a: "#BB86FC"
  tier-b: "#58A6FF"
  tier-c: "#3FB950"
typography:
  headline:
    fontFamily: "Inter, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, sans-serif"
    fontSize: "17px"
    fontWeight: 850
    lineHeight: 1
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, sans-serif"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.08em"
  mono:
    fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "normal"
rounded:
  xs: "4px"
  sm: "6px"
  md: "12px"
  lg: "16px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.myth}"
    textColor: "{colors.myth-ink}"
    rounded: "{rounded.sm}"
    padding: "0.6rem 1.2rem"
  nav-link:
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.85rem"
  nav-link-active:
    backgroundColor: "rgba(79, 207, 196, 0.16)"
    textColor: "{colors.myth-bright}"
    rounded: "{rounded.sm}"
  score-pill:
    backgroundColor: "{colors.bg-elevated}"
    textColor: "{colors.text-muted}"
    typography: "{typography.mono}"
    rounded: "4px"
    height: "18px"
    padding: "0 6px"
  # TA-grade panel (build task 12; supersedes the Visual/Market pill pair at
  # the flip — the pills survive only for pre-v2 payloads until retirement).
  # The 0-100 is the lens's single dominant datum: mono/tabular, permanent
  # "/100" scale marker (it must never be misread as the legacy raw score).
  # The chapter strip beneath it keeps EQUAL-width segments in the ruled
  # story order (cause→work→turn→finish→trend, never points-sorted); fill =
  # the engine-resolved earned fraction, so an A/B reweight moves fills,
  # never the layout. Chromatically neutral (accent-blue fills, muted
  # labels); NO chapter or HTF element may wear a tier hue (Tier-Reserve);
  # warnings keep the only hot treatment, as labeled line items with cost.
  ta-grade-panel:
    headline: "{typography.mono} 26px/800 + /100 marker in text-faint 12px"
    strip: "5 equal columns, 5px bars, fill {colors.accent-blue}"
    caveats: "narrativeRead three-state wording, text-faint 9px"
    warnings: "warning tint chips, the panel's only hot hue"
  status-pill:
    textColor: "{colors.text-main}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  input-field:
    backgroundColor: "{colors.bg-panel}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.sm}"
    padding: "0.5rem"
  card-screener:
    backgroundColor: "{colors.bg-panel}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.sm}"
---

# Design System: Chrollo

## 1. Overview

**Creative North Star: "The Instrument Panel"**

Chrollo is a pro's cockpit for reading market structure. The surface stays dark
and quiet so it can be stared at for hours, but the hierarchy is confident:
every screen commits to the one reading that matters most, and every control and
number sits exactly where a returning user expects it. Nothing is decorative for
its own sake. The interface reports; the trader decides.

Depth comes chiefly from a calibrated ramp of dark slate surfaces, reinforced by
a restrained **instrument-framing** layer — mounted bezels and recessed wells that
make each widget read as its own box to focus on — never decorative glass. Color
is spent deliberately — a single interactive accent (**mythril**, a teal-cyan), a
demoted structural blue, a small set of categorical accents, and a reserved tier
palette that carries product meaning. Numbers are the protagonists, so they are
set in tabular figures that hold their columns and never jitter as values update.

This system explicitly rejects three things. It is **not a gamified retail
broker** (no dopamine mechanics, no celebratory animation, no oversized green
P&L designed to feel good — a research lab must never flatter its own output).
It is **not a generic SaaS dashboard** (no endless identical card grids, no
gradient hero-metric tiles, no uppercase eyebrow kickers above every section).
And it is **not over-designed** (no decorative glassmorphism, no showy motion,
no ornamental gradients between the trader and the data).

**Key Characteristics:**
- Dark "warm slate" surface ramp; depth by tone, with a restrained instrument-framing layer (bezel/well) on top.
- One interactive accent — mythril (teal-cyan); blue is demoted to structure/context; other accents categorical and rare.
- Reserved tier palette (S/A/B/C) that means something, used nowhere else.
- Tabular numerics everywhere; data alignment is non-negotiable.
- Tactile, confident controls that come alive on interaction — mythril leads the lock-on.

## 2. Colors

A dark slate foundation with a single interactive accent — **mythril** — a
demoted structural blue, a small categorical accent set, and clear
green/amber/red status signaling.

### Primary — The Active Color
- **Mythril** (#4FCFC4 · ink #07211E · bright #8CEAE0 · dim #39A79E): The one
  interactive accent, a teal-cyan silvery-green. Everything active carries it:
  primary buttons (dark #07211E ink on a mythril fill — never white-on-mythril),
  active nav, focus rings, links, the LIVE dot, selected pills / toggles / tabs /
  pagers, the emphasized data point, and the instrument "lock-on" reticle. If
  something is clickable-and-important or currently-selected, it is mythril.
  Steered teal-cyan (not leaf-green) on purpose so it stays distinct from success
  green (#3DD37A) and tier-C.

### Structure — The Demoted Blue
- **Signal Blue** (#5B8AFF): No longer the interactive color. Blue was so
  pervasive it read as wallpaper ("dark blue feels like background"), so it steps
  back to **structure and context**: informational (not actionable) notices, the
  "open" trade status, Phase-D and chart-line series, the tier-B identity hue.
  Blue narrates; mythril acts. Reaching for blue to mean "click me" is now a
  defect — that role moved to mythril.

### Secondary
- **Categorical Violet** (#9B70F7): Options / OPT asset class, secondary
  category accents. Never a second "primary".
- **Categorical Rose** (#E07AA0): The "setup" category label and critical-severity pill.
- **Categorical Gold** (#D4B85A): Notes label, medium-severity pill, partial state.

### Calibration — Ground Truth & the Buy
Two dedicated semantic roles the calibration workbench (chart, right rail, ledger)
owns. They are **role tokens**, resolved apart from any categorical hue so a
re-tune of one never drags the other.
- **Operator** (`--operator`, #9B70F7): "**this is my mark**" — the single hue for
  operator ground truth wherever it renders: the committed box + rails on the
  chart, the rail's per-setup rows, the ledger atoms. It **resolves to** the
  categorical violet but is a *distinct role* from it: the Options/OPT category
  (raw `--accent-purple`) and **tier-A violet** (`--tier-a` #BB86FC — a lighter,
  cooler violet) must never be misread as an operator mark. Canvas surfaces mirror
  it as `CHART_COLORS.operator` (lightweight-charts needs a concrete hex, not a
  CSS var — the two hold the same value by contract). It is **not** mythril
  (interactivity stays scarce) and **not** green (that's engine agreement).
- **Trigger** (`--trigger`, #E8863C): the operator's **BUY** — the breakout above
  the last LPS bar's High. Its own **warm entry-flag**, deliberately **not**
  mythril, **not** `--success` green (green means engine-agreement, and a green
  "BUY" apes a gamified broker), **not** `--danger`. A burnt orange kept distinct
  from the LPS gold it sits beside on the chart and from `--warning` amber. Canvas
  mirror: `CHART_COLORS.trigger`.

### Tertiary — The Tier Palette
A reserved four-color ladder that encodes screener tier and appears **only** on
tier identity (badges, the ticker color on a card):
- **Tier S — Amber** (#FF9F43), **Tier A — Violet** (#BB86FC),
  **Tier B — Sky** (#58A6FF), **Tier C — Green** (#3FB950), default grey (#8B949E).

### Neutral
- **Surface ramp** (dark → light): App #1A1D26 → Sidebar #1E2230 → Panel #232735
  → Hover #2A2F3E → Elevated #303547. This ramp *is* the depth system.
- **Ink ramp**: Primary text #E8EAF0, Muted #9AA1B2, Faint #8A93A8.
- **Borders**: Hairline #384357, Strong #4A5470.

### Status
- **Win/Long Green** (#3DD37A), **Loss/Short Red** (#DE6E78), **Warning Amber** (#E2B255),
  each paired with a ~14%-opacity background tint of its own hue for pills/badges.
  The red and amber were softened off their original acid values (#F26770 / #F0BE3C)
  to sit calmly on the cool slate base while still clearly reading loss/caution.
  Every tint is mixed from a single channel token (`--{success,danger,warning,operator,trigger}-rgb`)
  so a softened hue can't drift across files: write `rgba(var(--danger-rgb), α)`,
  never a raw copy of the hex.
- **The calm-transient rule.** A self-healing hiccup wears **`--warning`, never
  `--danger`**. Concretely: the calibration chart's `rate_limited` failure (the
  vendor is briefly throttling; the last-good chart stays up) is amber caution,
  not a red alarm — training distrust of a state that fixes itself in seconds is
  a defect. Red is reserved for states the operator must act on.

### Named Rules
**The One-Accent Rule (mythril = action, blue = context).** Mythril (#4FCFC4) is
the *only* interactivity color — active, selected, focused, primary. Blue is
demoted to structure/context and, alongside violet, rose, and gold, is a
label/state color, not a button; if you reach for any of them to mean "clickable",
you're wrong. Mythril stays scarce enough to remain a signal — spent only on what
the trader can act on. (This **reverses** the earlier "Signal Blue is the sole
interactive color" doctrine: blue was everywhere and had stopped signaling.)

**The Tier-Reserve Rule.** The S/A/B/C tier hues are reserved for tier identity.
Never borrow tier amber or tier violet for decoration, charts, or accents — doing
so makes the trader misread rank.

## 3. Typography

**Display / Body / Label Font:** Inter (with `sans-serif` fallback)
**Numeric / Mono Font:** JetBrains Mono (with `ui-monospace, SFMono-Regular, Menlo, Consolas` fallback)

**Character:** One humanist-geometric sans carries the whole UI through weight
contrast (400 → 850), not multiple typefaces. A monospace face is reserved for
compact data pills. Base size is a deliberately small 13px — this is a
dense instrument, not a reading experience.

### Hierarchy
- **Headline** (700, 22px, tabular, -0.01em): The single hero figure on a screen,
  e.g. the P&L value. One per region, never repeated as a template.
- **Title** (850, 17px): Ticker symbols and primary identifiers — the heaviest
  weight in the system, used sparingly to anchor the eye.
- **Body** (400–500, 13px, line-height 1.5): Default UI text and table cells.
- **Label** (600, 10px, 0.08–0.12em, UPPERCASE): Column headers, KPI labels,
  section eyebrows. Reserved for ≤4-word labels — never sentences.
- **Mono / Numeric** (700, 10–12px, tabular): Score and sub-score pills, fill
  inputs; any compact figure that benefits from fixed-width digits.

### Named Rules
**The Tabular Rule.** Every number that can change — prices, R-multiples, P&L,
counts, percentages — uses `font-variant-numeric: tabular-nums`. Columns must
align and digits must not reflow as values update. A jittering number column is
a defect.

**The Weight-Not-Family Rule.** Hierarchy is built from Inter's weight range, not
from adding typefaces. Do not introduce a serif or a second sans for emphasis;
go heavier or larger instead.

## 4. Elevation & Instrument Framing

Depth is **tonal first, framed second**. The five-step surface ramp
(#1A1D26 → #303547) still does most of the work a shadow stack would in a lighter
UI: a panel reads as "above" the app background because it is a step lighter, a
hover state a step lighter still. On top of that ramp sits a **restrained
instrument-framing layer** — the language that makes each widget read as "its own
box to focus on" instead of getting lost in the crowd. Drop shadows beyond that
framing stay reserved for genuine overlays (modals). Glow is a focus/state signal,
not a resting decoration.

### Shadow Vocabulary
- **Bezel** (`.instrument-tile`: `inset 0 1px 0 rgba(255,255,255,0.035), 0 1px 2px rgba(0,0,0,0.45)`):
  a mounted-tile resting depth — quiet top highlight + soft seam so a top-level
  panel reads as mounted in the cockpit.
- **Well** (`.instrument-well`: `inset 0 3px 7px -4px rgba(0,0,0,0.7)` via a
  `pointer-events:none` `::after`): sinks a chart / table / `pre` below the chrome.
- **Elevated / Modal** (`0 8px 24px rgba(0,0,0,0.5)` and deeper): true overlays only.
- **Lock-on** (`0 8px 20px -6px rgba(0,0,0,0.6), 0 0 16px var(--myth-glow)` + 2px lift):
  the hover/focus response on an interactive tile, paired with the mythril reticle.
- **Accent glow** (`0 0 0 1px var(--myth), 0 0 12px var(--myth-glow)`): focus rings
  and active nav — a *state* response, never a resting glow.

### Instrument Framing
A three-word vocabulary (`webapp/frontend/src/index.css`), piloted on the screener
grid and rolled across the surfaces. Compose it; don't paint with it:
- **`.instrument-tile`** — resting bezel on a genuine top-level panel (a home zone,
  a status strip, an analytics panel). Makes it a mounted instrument.
- **`.instrument-well`** — recess a *readout* (chart, data table, code/`pre`) into
  its panel.
- **`.instrument-lockon`** — reserved for a real grid of clickable tiles (the
  screener card and its kin): a mythril corner **reticle** + 2px lift + glow on
  hover/focus, invisible at rest so density is untouched. There is **no**
  attention-dim of the siblings — the earlier `:has()` dim was removed; the hovered
  tile lifts, the rest stay put.

**Restraint is the rule:** frame the few panels that are genuinely their own widget
and the readouts inside them. If everything is bezeled, nothing stands out — that
is the failure mode, not the goal.

### Named Rules
**The Tonal-Depth Rule (softened).** Tone still carries resting depth: reach for the
next surface step or a hairline border (#384357) before a free-floating shadow. The
**only** sanctioned resting shadows are the instrument bezel and well — a deliberate,
uniform framing layer, not per-element decoration.

**The Glow-On-State Rule.** Glow, lift, and the reticle appear in response to hover,
focus, or float (modals). A surface that glows at rest is over-designed; remove it.
(The bezel and well are shadow, not glow — resting depth is fine; resting *glow* is not.)

## 5. Components

Controls are **tactile and confident**: low-chrome at rest, decisively
responsive on interaction (lift, tint, border, or glow), never mushy or vague.

### Buttons
- **Shape:** Gently rounded (6px) for standard buttons; pill (9999px) for sidebar action buttons.
- **Primary:** Mythril fill, dark #07211E ink (never white-on-mythril — it fails
  contrast), `0.6rem 1.2rem` padding. This is the shape of every primary action:
  Evaluate, Download, Connect IBKR, Add Setup, Save, Update Returns, confirm.
- **Hover / Focus:** Standard buttons lift/tint on hover; focus shows a mythril soft
  ring (`--glow-active`).
- **Deprecated:** the old blue→violet gradient "trade action" button (`.btn-trade`
  kit) is unused dead CSS and now off-doctrine (no ornamental gradients; action is
  mythril). Don't revive it — a primary mythril button marks the consequential action.

### Chips & Pills
- **Score pill:** Monospace, 18px tall, elevated-surface background, hairline border;
  semantic color variants (visual=sky, market=green) — these are *data* hues, not
  interactivity.
- **Status pill:** Pill-radius, 14%-tint background of its status hue with a matching
  6px dot; open=blue (a *state*, kept in the demoted structural blue), win=green,
  loss=red, wash=gold.
- **Filter / toggle / tab / pager (selected):** The active state carries **mythril**
  (`--myth-soft` fill, mythril text) — these are controls the trader operates, so
  they follow the action color, not a status hue.
- **Tier badge:** Carries the reserved tier hue; appears only for tier identity.

### Cards / Containers
- **Corner Style:** 6px (panels/cards), 12px (modals, glass-panel).
- **Background:** Panel #232735 on the app background; hover shifts toward #242837
  with a mythril border.
- **Shadow Strategy:** Tonal + a resting instrument bezel (see Elevation);
  border-color + mythril glow on hover. A genuine grid of clickable tiles adds the
  `.instrument-lockon` reticle + lift; standing panels get the bezel only.
- **Internal Padding:** 5–8px for dense card headers, 1.5rem for content panels.

### Inputs / Fields
- **Style:** Panel background, hairline border, 6px radius, inherits UI font.
- **Focus:** Border shifts to mythril with a 3px soft ring (`--myth-soft`).
- **Inline edit:** Elevated background, solid mythril border, 2px mythril ring —
  the editing state is unmistakable.

### Navigation
- **Style:** Left sidebar, 220px. Links are quiet muted text at rest.
- **States:** Hover lifts text toward white on a 3%-white wash; active link gets a
  mythril soft background, mythril border, and a soft mythril shadow — confidently
  "you are here", not subtle.
- **Section labels:** 9px uppercase, faint, wide tracking.

### Signature — The Screener Card
The dense triage unit of the product: a header row (watchlist star, "considered"
checkbox, tier-colored ticker, setup label, score + sub-score pills), a
mini price chart, and a tag row. Cards dim to 50% opacity when marked considered,
so the grid reads as "what's left to review". Density is the point; it must stay
legible at four-up.

## 6. Do's and Don'ts

### Do:
- **Do** convey depth with the surface ramp and hairline borders before reaching for a shadow (The Tonal-Depth Rule).
- **Do** set every changeable number in `tabular-nums` so columns align (The Tabular Rule).
- **Do** keep mythril (#4FCFC4) as the sole interactivity color and blue as structure/context; build hierarchy with Inter's weight range (The One-Accent / Weight-Not-Family Rules).
- **Do** reserve the S/A/B/C tier hues for tier identity and nothing else (The Tier-Reserve Rule).
- **Do** let controls be confident on interaction — a clear lift, tint, border, or focus ring, led by mythril.
- **Do** frame with restraint: bezel the few genuine top-level panels, well the readouts, lock-on only real grids of clickable tiles.

### Don't:
- **Don't** add gamified-broker mechanics: no confetti, no celebratory win animation, no oversized green P&L designed to feel good.
- **Don't** ship the generic-SaaS look: no endless identical card grids, no gradient hero-metric tiles, no uppercase eyebrow kicker above every section.
- **Don't** over-design: no decorative glassmorphism, no heavy/showy motion, no ornamental gradients between the trader and the data.
- **Don't** use gradient text (`background-clip: text` on a gradient). It is decorative and never meaningful; the current `.brand-text` is a legacy exception slated for cleanup, not a pattern to repeat.
- **Don't** borrow a tier, categorical accent, or the demoted structural blue to mean "clickable" — that role belongs to mythril alone.
- **Don't** let a surface *glow* at rest; glow and elevated shadow are state responses (hover/focus/modal) only. The resting instrument bezel/well shadow is the one sanctioned exception (framing, not glow).
