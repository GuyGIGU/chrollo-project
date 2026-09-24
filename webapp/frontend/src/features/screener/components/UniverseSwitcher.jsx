import { DEFAULT_UNIVERSE } from '../hooks/useScreenerData';
import { UNIVERSES } from '../../../shared/presentation/universeSwitcherData';

// The three screeners are one instrument viewed through three universes — the
// switcher is a context selector, NOT a third nav tier. It reuses the toolbar's
// tier-pill grammar exactly (Signal Blue marks the active segment only; the
// universes are told apart by their label and the data on screen, never by a
// per-universe hue, which would break the blue=interactive contract).
// UNIVERSES + the universe helpers live in ./universeSwitcherData so this file
// only exports the component (keeps React Fast Refresh working).
export default function UniverseSwitcher({ universe = DEFAULT_UNIVERSE, onChange, showLabel = true }) {
  return (
    <div style={wrapStyle} role="group" aria-label="Screener universe">
      {showLabel && <span style={labelStyle}>Universe:</span>}
      {UNIVERSES.map(({ key, label }) => {
        const active = key === universe;
        return (
          <button
            key={key}
            type="button"
            className="focus-ring"
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
  borderColor: active ? 'var(--accent-active)' : 'var(--border-color)',
  background: active ? 'var(--accent-active)' : 'transparent',
  color: active ? 'var(--myth-ink)' : 'var(--text-main)',
  cursor: active ? 'default' : 'pointer',
  fontWeight: active ? 600 : 500,
  fontSize: '12px',
  fontFamily: 'inherit',
});
