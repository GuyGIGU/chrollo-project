import { DEFAULT_UNIVERSE } from '../hooks/useScreenerData';

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

export default function UniverseSwitcher({ universe = DEFAULT_UNIVERSE, onChange }) {
  return (
    <div style={wrapStyle} role="group" aria-label="Screener universe">
      <span style={labelStyle}>Universe:</span>
      {UNIVERSES.map(({ key, label }) => {
        const active = key === universe;
        return (
          <button
            key={key}
            type="button"
            onClick={() => !active && onChange?.(key)}
            aria-pressed={active}
            style={segStyle(active)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

const wrapStyle = {
  display: 'flex',
  gap: '8px',
  alignItems: 'center',
  flexWrap: 'wrap',
};

const labelStyle = {
  fontSize: '12px',
  color: 'var(--text-muted)',
  fontWeight: 500,
  marginRight: '4px',
};

// Mirrors ScreenerToolbar's tierButtonStyle so "selected" reads identically
// across the toolbar and the switcher.
const segStyle = (active) => ({
  padding: '5px 14px',
  borderRadius: 'var(--radius-lg)',
  border: '1px solid',
  borderColor: active ? 'var(--accent-blue)' : 'var(--border-color)',
  background: active ? 'var(--accent-blue)' : 'transparent',
  color: active ? '#fff' : 'var(--text-main)',
  cursor: active ? 'default' : 'pointer',
  fontWeight: active ? 600 : 500,
  fontSize: '12px',
  fontFamily: 'inherit',
});
