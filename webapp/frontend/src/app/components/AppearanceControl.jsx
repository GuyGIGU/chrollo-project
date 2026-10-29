import { useEffect, useRef, useState } from 'react';
import { SlidersIcon } from '../../shared/components/NavIcons';
import {
  SCALE_STEPS,
  DEFAULT_SCALE,
  screenerColumnsAt,
  monitorId,
  readStoredScale,
  persistScale,
  clearStoredScale,
  applyScale,
} from '../appearance/uiScale';

const readViewport = () =>
  (typeof document !== 'undefined' && document.documentElement.clientWidth) || 1920;

// A top-nav action that opens a small popover to size the whole app via CSS `zoom`
// (--ui-scale on .app-layout). Self-contained: it owns the scale state and applies
// it to the document root — index.html's pre-paint script sets the initial value
// so there is no flash on reload. The scale is PER SCREEN (operator 2026-10-02):
// a manual step is remembered for the screen it was chosen on; a screen with no
// choice is at 100% (the cards keep one size, Thu 29/10/2026), and moving the
// window to the other monitor re-reads that monitor's choice.
function AppearanceControl() {
  const [open, setOpen] = useState(false);
  const [monitor, setMonitor] = useState(monitorId);
  const [override, setOverride] = useState(() => readStoredScale(monitorId()));
  const [viewport, setViewport] = useState(readViewport);
  const anchorRef = useRef(null);
  const scale = override ?? DEFAULT_SCALE;

  useEffect(() => {
    applyScale(scale);
  }, [scale]);

  // A resize, a move to the other monitor, or a return to the window: re-read
  // which screen we are on, its width, and its remembered choice. `focus` covers
  // a window dragged across without resizing, which fires no resize at all.
  useEffect(() => {
    const sync = () => {
      const id = monitorId();
      setMonitor(id);
      setOverride(readStoredScale(id));
      setViewport(readViewport());
    };
    const screenApi = typeof window !== 'undefined' ? window.screen : null;
    window.addEventListener('resize', sync);
    window.addEventListener('focus', sync);
    screenApi?.addEventListener?.('change', sync);
    return () => {
      window.removeEventListener('resize', sync);
      window.removeEventListener('focus', sync);
      screenApi?.removeEventListener?.('change', sync);
    };
  }, []);

  const choose = (next) => {
    persistScale(next, monitor);
    setOverride(next);
  };
  const reset = () => {
    clearStoredScale(monitor);
    setOverride(null);
  };

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
    if (next != null) choose(next);
  };
  const cols = screenerColumnsAt(scale, viewport);

  return (
    <div className="appearance-anchor" ref={anchorRef}>
      <button
        type="button"
        className={`topnav-action${open ? ' topnav-action-primary' : ''}`}
        onClick={() => setOpen((prev) => !prev)}
        title="Scale — size the app to your screen"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="Scale"
      >
        <SlidersIcon className="topnav-icon" />
      </button>

      {open && (
        <div className="appearance-popover" role="dialog" aria-label="Scale">
          <div className="appearance-popover-title">Scale</div>

          <div className="appearance-stepper">
            <button type="button" onClick={() => stepBy(-1)} disabled={idx <= 0} aria-label="Smaller">
              −
            </button>
            <span className="appearance-value">
              {Math.round(scale * 100)}%
            </span>
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
            <button type="button" className="appearance-primary" onClick={reset} disabled={override == null}>
              Reset to 100%
            </button>
          </div>

          <div className="appearance-hint">
            Remembered for this screen ({monitor.replace('x', '×')}). Keep browser zoom at 100% (Ctrl+0).
          </div>
        </div>
      )}
    </div>
  );
}

export default AppearanceControl;
