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
  text-faint: "#6C7488"
  border-color: "#2F3447"
  border-strong: "#3B4159"
  accent-blue: "#5B8AFF"
  accent-purple: "#9B70F7"
  accent-pink: "#E07AA0"
  accent-yellow: "#D4B85A"
  accent-orange: "#E0A05A"
  success: "#3DD37A"
  danger: "#F26770"
  warning: "#F0BE3C"
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
    backgroundColor: "{colors.accent-blue}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "0.6rem 1.2rem"
  nav-link:
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.85rem"
  nav-link-active:
    backgroundColor: "{colors.accent-blue}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
  score-pill:
    backgroundColor: "{colors.bg-elevated}"
    textColor: "{colors.text-muted}"
    typography: "{typography.mono}"
    rounded: "4px"
    height: "18px"
    padding: "0 6px"
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

Depth comes from a calibrated ramp of dark slate surfaces, not from drop shadows
or glass. Color is spent deliberately — a single interactive blue, a small set
of categorical accents, and a reserved tier palette that carries product meaning.
Numbers are the protagonists, so they are set in tabular figures that hold their
columns and never jitter as values update.

This system explicitly rejects three things. It is **not a gamified retail
broker** (no dopamine mechanics, no celebratory animation, no oversized green
P&L designed to feel good — a research lab must never flatter its own output).
It is **not a generic SaaS dashboard** (no endless identical card grids, no
gradient hero-metric tiles, no uppercase eyebrow kickers above every section).
And it is **not over-designed** (no decorative glassmorphism, no showy motion,
no ornamental gradients between the trader and the data).

**Key Characteristics:**
- Dark "warm slate" surface ramp; depth by tone, not shadow.
- One interactive accent (blue); accents otherwise categorical and rare.
- Reserved tier palette (S/A/B/C) that means something, used nowhere else.
- Tabular numerics everywhere; data alignment is non-negotiable.
- Tactile, confident controls that come alive on interaction.

## 2. Colors

A dark slate foundation with a single interactive blue, a small categorical
accent set, and clear green/amber/red status signaling.

### Primary
- **Signal Blue** (#5B8AFF): The one interactive accent. Active nav, focus
  rings, primary buttons, links, draft-row tint, R-multiple chips. If something
  is clickable-and-important or currently-selected, it carries blue.

### Secondary
- **Categorical Violet** (#9B70F7): Options / OPT asset class, secondary
  category accents. Never a second "primary".
- **Categorical Rose** (#E07AA0): The "setup" action and critical-severity pill.
- **Categorical Gold** (#D4B85A): Notes action, medium-severity pill, partial state.

### Tertiary — The Tier Palette
A reserved four-color ladder that encodes screener tier and appears **only** on
tier identity (badges, the ticker color on a card):
- **Tier S — Amber** (#FF9F43), **Tier A — Violet** (#BB86FC),
  **Tier B — Sky** (#58A6FF), **Tier C — Green** (#3FB950), default grey (#8B949E).

### Neutral
- **Surface ramp** (dark → light): App #1A1D26 → Sidebar #1E2230 → Panel #232735
  → Hover #2A2F3E → Elevated #303547. This ramp *is* the depth system.
- **Ink ramp**: Primary text #E8EAF0, Muted #9AA1B2, Faint #6C7488.
- **Borders**: Hairline #2F3447, Strong #3B4159.

### Status
- **Win/Long Green** (#3DD37A), **Loss/Short Red** (#F26770), **Warning Amber** (#F0BE3C),
  each paired with a ~14%-opacity background tint of its own hue for pills/badges.

### Named Rules
**The One-Accent Rule.** Signal Blue (#5B8AFF) is the *only* interactivity color.
Violet, rose, and gold are categorical labels, not buttons; if you reach for them
to mean "clickable", you're wrong. Blue stays scarce enough to remain a signal.

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

## 4. Elevation

Depth is **tonal, not cast**. The five-step surface ramp (#1A1D26 → #303547) does
the work a shadow stack would in a lighter UI: a panel reads as "above" the app
background because it is a step lighter, a hover state a step lighter still. Drop
shadows are minimal and reserved for genuine overlays (modals) where an element
truly floats above the plane. Glow is a focus/state signal, not a resting decoration.

### Shadow Vocabulary
- **Card rest** (`box-shadow: 0 1px 2px rgba(0,0,0,0.4)`): A near-invisible seam,
  used sparingly; tonal contrast carries most resting depth.
- **Elevated / Modal** (`box-shadow: 0 8px 24px rgba(0,0,0,0.5)`): True overlays only.
- **Accent glow** (`0 0 0 1px accent-blue, 0 0 12px rgba(91,138,255,0.35)`):
  A *state* response — focus rings, active nav — never a resting glow.

### Named Rules
**The Tonal-Depth Rule.** Reach for the next surface step before reaching for a
shadow. If two flat surfaces need separation, change the tone or add a hairline
border (#2F3447); don't drop a shadow.

**The Glow-On-State Rule.** Glow and elevated shadow appear in response to hover,
focus, or float (modals). A surface that glows at rest is over-designed; remove it.

## 5. Components

Controls are **tactile and confident**: low-chrome at rest, decisively
responsive on interaction (lift, tint, border, or glow), never mushy or vague.

### Buttons
- **Shape:** Gently rounded (6px) for standard buttons; pill (9999px) for sidebar action buttons.
- **Primary:** Signal Blue fill, white text, `0.6rem 1.2rem` padding.
- **Trade action:** A blue→violet gradient fill with a matching border and a soft
  blue cast; lifts 1px on hover. The one place a gradient is sanctioned, because it
  marks the single most consequential action.
- **Hover / Focus:** Standard buttons fade opacity; action buttons translate up 1px
  and deepen their cast. Focus shows a 3px Signal-Blue soft ring.

### Chips & Pills
- **Score pill:** Monospace, 18px tall, elevated-surface background, hairline border;
  semantic color variants (visual=sky, market=green, fusion=gold).
- **Status pill:** Pill-radius, 14%-tint background of its status hue with a matching
  6px dot; open=blue, win=green, loss=red, wash=gold.
- **Tier badge:** Carries the reserved tier hue; appears only for tier identity.

### Cards / Containers
- **Corner Style:** 6px (panels/cards), 12px (modals, glass-panel).
- **Background:** Panel #232735 on the app background; hover shifts toward #242837
  with a Signal-Blue border.
- **Shadow Strategy:** Tonal at rest (see Elevation); border-color + faint blue
  shadow on hover.
- **Internal Padding:** 5–8px for dense card headers, 1.5rem for content panels.

### Inputs / Fields
- **Style:** Panel background, hairline border, 6px radius, inherits UI font.
- **Focus:** Border shifts to Signal Blue with a 3px soft-blue ring (`accent-blue-soft`).
- **Inline edit:** Elevated background, solid Signal-Blue border, 2px blue ring —
  the editing state is unmistakable.

### Navigation
- **Style:** Left sidebar, 220px. Links are quiet muted text at rest.
- **States:** Hover lifts text toward white on a 3%-white wash; active link gets a
  Signal-Blue soft background, blue border, and a soft blue shadow — confidently
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
- **Do** keep Signal Blue (#5B8AFF) as the sole interactivity color; build hierarchy with Inter's weight range (The One-Accent / Weight-Not-Family Rules).
- **Do** reserve the S/A/B/C tier hues for tier identity and nothing else (The Tier-Reserve Rule).
- **Do** let controls be confident on interaction — a clear lift, tint, border, or focus ring.

### Don't:
- **Don't** add gamified-broker mechanics: no confetti, no celebratory win animation, no oversized green P&L designed to feel good.
- **Don't** ship the generic-SaaS look: no endless identical card grids, no gradient hero-metric tiles, no uppercase eyebrow kicker above every section.
- **Don't** over-design: no decorative glassmorphism, no heavy/showy motion, no ornamental gradients between the trader and the data.
- **Don't** use gradient text (`background-clip: text` on a gradient). It is decorative and never meaningful; the current `.brand-text` is a legacy exception slated for cleanup, not a pattern to repeat.
- **Don't** borrow a tier or categorical accent to mean "clickable" — that role belongs to Signal Blue alone.
- **Don't** let a surface glow at rest; glow and elevated shadow are state responses (hover/focus/modal) only.
