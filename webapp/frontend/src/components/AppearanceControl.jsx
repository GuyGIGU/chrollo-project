import { useEffect, useRef, useState } from 'react';
import { SlidersIcon } from './NavIcons';
import {
  SCALE_STEPS,
  DEFAULT_SCALE,
  computeAutoFitScale,
  screenerColumnsAt,
  readStoredScale,
  persistScale,
  applyScale,
} from '../utils/uiScale';

const readViewport = () =>
  (typeof document !== 'undefined' && document.documentElement.clientWidth) || 1536;

// A rail action that opens a small popover to size the whole app via CSS `zoom`
// (--ui-scale on .app-layout). Self-contained: it owns the scale state, applies
// it to the document root, and persists it — index.html's pre-paint script sets
// the initial value so there is no flash on reload. Auto-fit picks the least
// shrink that unlocks another screener column, which is the operator's real
// goal on a scaled monitor (more cards per row).
function AppearanceControl() {
  const [open, setOpen] = useState(false);
  const [scale, setScale] = useState(() => readStoredScale() ?? DEFAULT_SCALE);
  const [viewport, setViewport] = useState(readViewport);
  const anchorRef = useRef(null);

  // Keep the document var + storage in lockstep with state on every change.
  useEffect(() => {
    applyScale(scale);
    persistScale(scale);
  }, [scale]);

  // Track viewport width so the cards-per-row readout and auto-fit stay honest.
  useEffect(() => {
    const onResize = () => setViewport(readViewport());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Dismiss on outside click or Escape.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => {
      if (anchorRef.current && !anchorRef.current.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const idx = SCALE_STEPS.indexOf(scale);
  const stepBy = (delta) => {
    const next = SCALE_STEPS[Math.min(SCALE_STEPS.length - 1, Math.max(0, idx + delta))];
    if (next != null) setScale(next);
  };
  const cols = screenerColumnsAt(scale, viewport);

  return (
    <div className="appearance-anchor" ref={anchorRef}>
      <button
        type="button"
        className={`rail-action${open ? ' rail-action-primary' : ''}`}
        onClick={() => setOpen((prev) => !prev)}
        title="Scale — size the app to your screen"
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <SlidersIcon className="rail-icon" />
        <span className="rail-label">Scale</span>
      </button>

      {open && (
        <div className="appearance-popover" role="dialog" aria-label="Scale">
          <div className="appearance-popover-title">Scale</div>

          <div className="appearance-stepper">
            <button type="button" onClick={() => stepBy(-1)} disabled={idx <= 0} aria-label="Smaller">
              −
            </button>
            <span className="appearance-value">{Math.round(scale * 100)}%</span>
            <button
              type="button"
              onClick={() => stepBy(1)}
              disabled={idx >= SCALE_STEPS.length - 1}
              aria-label="Larger"
            >
              +
            </button>
          </div>

          <div className="appearance-cols">
            Screener: ~{cols} card{cols === 1 ? '' : 's'} per row
          </div>

          <div className="appearance-actions">
            <button
              type="button"
              className="appearance-primary"
              onClick={() => setScale(computeAutoFitScale(readViewport()))}
              title="Pick the densest comfortable scale for this window"
            >
              Auto-fit
            </button>
            <button type="button" onClick={() => setScale(DEFAULT_SCALE)}>
              Reset
            </button>
          </div>

          <div className="appearance-hint">
            Keep browser zoom at 100% (Ctrl+0) and use this to size the app to your monitor.
          </div>
        </div>
      )}
    </div>
  );
}

export default AppearanceControl;
