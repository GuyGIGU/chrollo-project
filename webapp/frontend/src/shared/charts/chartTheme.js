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
  danger: '#DE6E78', // DESIGN.md --danger
  accent: '#5b8aff', // DESIGN.md --accent-blue
  // Lifted Thu 16/10/2026 ("make the colors pop up more"): the rails from a navy that sank into the
  // canvas to a clear blue, the gold warmer and brighter, the bars a step whiter. Card and modal
  // alike, by construction.
  rail: '#3B7BFF', // R/S box rails (card + modal, by construction)
  innerRail: '#86B0FF', // inner-box rails
  midRail: 'rgba(150, 160, 182, 0.5)', // dashed box midline
  candle: '#E6E9F2', // whitewashed structure bars
  baseLimb: '#6E7689', // base-limb swing grey
  gold: '#F5C84B', // LPS span + trigger line (modal-weight gold)
  goldMuted: '#d4b85a', // LPS bars on dense mini cards; avg-cost / entry lines
  marking: '#4FCFC4', // calibration draft IN PROGRESS (--myth — the ACTIVE color)
  markingWash: 'rgba(79, 207, 196, 0.12)', // marking at 12% — the hovered-bar band while a tool is armed
  operator: '#9B70F7', // COMMITTED operator marks — canvas mirror of CSS --operator (calibration ground truth; never an engine-read color)
  trigger: '#E8863C', // operator BUY glyph: the LPS-high breakout entry — canvas mirror of CSS --trigger; warm, distinct from LPS gold
  asOfLine: 'rgba(148, 158, 178, 0.55)', // faint vertical divider at the as-of session (observed <= as-of | forward > as-of); neutral, never a rail color
  indexUp: '#5fb882', // market-strip index bars, green/red by direction (Finviz convention)
  indexDown: '#ee6352',
  sma50: '#f0a35e', // 50-day moving-average overlay
  sma200: '#7c8cf8', // 200-day moving-average overlay
};

// Per-surface skins: background/text/grid/border/fontSize. Four deliberate
// surface tints (they sit in different panels), one place to see them all.
const VARIANTS = {
  mini: { background: '#141721', text: '#747c8f', grid: 'rgba(47, 52, 71, 0.13)', border: 'rgba(47, 52, 71, 0.56)', fontSize: 10 },
  // The lens's canvas (Thu 16/10/2026): a step deeper than the page, brighter axis ink, a cool grid.
  modal: { background: '#12141C', text: '#A3ACBF', grid: 'rgba(98, 110, 140, 0.16)', border: '#363C50', fontSize: 12 },
  position: { background: '#1c1f2a', text: '#7f879a', grid: 'rgba(47, 52, 71, 0.28)', border: '#2f3447', fontSize: 11 },
  trade: { background: '#171a24', text: '#8c94a8', grid: 'rgba(65, 72, 96, 0.26)', border: '#2f3447', fontSize: 11 },
  // The lens's PAPER skin (Thu 16/10/2026): a white chart like Finviz's, dark ink, a faint grid. Chosen in
  // place of 'modal' when the canvas sits inside a shell wearing data-skin="paper" (lensSkinOf).
  paper: { background: '#FFFFFF', text: '#5B6475', grid: 'rgba(20, 24, 31, 0.08)', border: '#C9CFDA', fontSize: 12 },
};

// Which skin a canvas is drawn under: 'paper' inside a lens shell that wears it, else null (the dark skin).
// Read off the DOM so a chart in the Watchlist page, outside the lens, never follows the lens's choice.
export const lensSkinOf = (container) =>
  (container && typeof container.closest === 'function' && container.closest('[data-skin="paper"]') ? 'paper' : null);

// The structure bars' colour under a skin: whitewashed on the dark skin, ink on paper. One colour up and down,
// his OHLC bars: green/red for an afternoon on Thu 29/10/2026 was never his ask ("why are the ohlc bars green
// and red i never asked you for that") and came off the same night.
export const lensBarOptions = (container) => {
  const color = lensSkinOf(container) === 'paper' ? '#1F2430' : CHART_COLORS.candle;
  return { upColor: color, downColor: color, thinBars: false };
};

// The hl2 SMA-20's colour under a skin: the teal reads on the dark skin only.
export const lensSmaOptions = (container) => (lensSkinOf(container) === 'paper' ? { color: 'rgba(23, 143, 134, 0.85)' } : {});

// A variant's raw surface tints, for shells that must MATCH a chart's skin
// (the calibration pane states render on the modal surface by construction —
// never by hand-copied hex literals).
export const surfaceOf = (variant) => VARIANTS[variant];

// The common createChart skeleton for a variant. Sites spread this and override
// their structural specifics (margins, crosshair mode, interactivity) — but the
// look (background, text, grid, borders, font) comes from one palette.
export const baseChartOptions = (variant, width, height, container = null) => {
  const skin = VARIANTS[variant === 'modal' && lensSkinOf(container) === 'paper' ? 'paper' : variant];
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
