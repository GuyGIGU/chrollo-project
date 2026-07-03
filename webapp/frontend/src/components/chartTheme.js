// chart-land's single palette + option factory. Every lightweight-charts site
// (mini card, modal, timeframe tabs, market pulse, portfolio position, trade
// drawer) reads its colors HERE, so the card and the modal cannot drift apart
// one literal at a time (the two-greens / four-backgrounds problem). Pure
// literals only — no lightweight-charts import — so Node tests can load it
// (the chart-coupled drawer lives in chartRails.js).
//
// Success/danger are the DESIGN.md tokens (--success / --danger), the canon
// that replaces the GitHub-palette #3fb950/#f85149 twins in JS. Tier colors
// are a different ladder and live in theme.js.

export const CHART_FONT = "'JetBrains Mono', monospace";

export const CHART_COLORS = {
  success: '#3DD37A', // DESIGN.md --success
  danger: '#F26770', // DESIGN.md --danger
  accent: '#5b8aff', // DESIGN.md --accent-blue
  rail: '#2457b8', // R/S box rails (card + modal, by construction)
  innerRail: '#5f8fe6', // inner-box rails
  midRail: 'rgba(139, 148, 158, 0.45)', // dashed box midline
  candle: '#d8dbe5', // whitewashed structure bars
  baseLimb: '#5d6474', // base-limb swing grey
  gold: '#e3b341', // LPS span + trigger line (modal-weight gold)
  goldMuted: '#d4b85a', // LPS bars on dense mini cards; avg-cost / entry lines
};

// Per-surface skins: background/text/grid/border/fontSize. Four deliberate
// surface tints (they sit in different panels), one place to see them all.
const VARIANTS = {
  mini: { background: '#141721', text: '#747c8f', grid: 'rgba(47, 52, 71, 0.13)', border: 'rgba(47, 52, 71, 0.56)', fontSize: 10 },
  modal: { background: '#171922', text: '#8b949e', grid: 'rgba(70, 77, 98, 0.18)', border: '#2f3447', fontSize: 12 },
  position: { background: '#1c1f2a', text: '#7f879a', grid: 'rgba(47, 52, 71, 0.28)', border: '#2f3447', fontSize: 11 },
  trade: { background: '#171a24', text: '#8c94a8', grid: 'rgba(65, 72, 96, 0.26)', border: '#2f3447', fontSize: 11 },
};

// The common createChart skeleton for a variant. Sites spread this and override
// their structural specifics (margins, crosshair mode, interactivity) — but the
// look (background, text, grid, borders, font) comes from one palette.
export const baseChartOptions = (variant, width, height) => {
  const skin = VARIANTS[variant];
  return {
    width,
    height,
    layout: {
      background: { type: 'solid', color: skin.background },
      textColor: skin.text,
      fontFamily: CHART_FONT,
      fontSize: skin.fontSize,
    },
    grid: {
      vertLines: { color: skin.grid },
      horzLines: { color: skin.grid },
    },
    rightPriceScale: { borderColor: skin.border },
    timeScale: { borderColor: skin.border },
  };
};

// Series options for the box-structure rails, keyed by boxRailSpecs' kind.
const railBase = {
  color: CHART_COLORS.rail,
  lineWidth: 2,
  crosshairMarkerVisible: false,
  lastValueVisible: false,
  priceLineVisible: false,
};

export const RAIL_STYLE = {
  rail: railBase,
  mid: { ...railBase, color: CHART_COLORS.midRail, lineWidth: 1, lineStyle: 2 },
  inner: { ...railBase, color: CHART_COLORS.innerRail },
};
