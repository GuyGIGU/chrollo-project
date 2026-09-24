// The three screeners are one instrument viewed through three universes — the
// switcher is a context selector, NOT a third nav tier. It reuses the toolbar's
// tier-pill grammar exactly (Signal Blue marks the active segment only; the
// universes are told apart by their label and the data on screen, never by a
// per-universe hue, which would break the blue=interactive contract).
export const UNIVERSES = [
  { key: 'us_stocks', label: 'US Stocks', etf: false },
  { key: 'us_sectors', label: 'Sectors + Market', etf: true },
  { key: 'commodities_etf', label: 'Commodities + ETFs', etf: true },
];

export function universeLabel(key) {
  return (UNIVERSES.find(u => u.key === key) || UNIVERSES[0]).label;
}

export function isEtfUniverse(key) {
  return !!(UNIVERSES.find(u => u.key === key) || {}).etf;
}
