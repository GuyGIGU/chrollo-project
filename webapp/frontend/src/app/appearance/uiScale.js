// UI scale — one knob that zooms the whole app via CSS `zoom` on `.app-layout`,
// so the hardcoded-px text and the rem-based spacing grow/shrink *together*.
// It lets the operator size the app to a monitor instead of leaning on native
// browser zoom.
//
// PER MONITOR (operator 2026-10-02: "When using Chrollo on my main monitor the
// scale breaks and the clean 3 Charts per row rule gets ignored"). His two
// screens are 2560x1440 and 1920x1080, both at Windows 100%, and one stored
// value served both. A manual choice is now remembered per screen
// (`chrollo:ui-scale@2560x1440`); a screen with no choice runs auto-fit against
// its own viewport, live, and nothing auto is ever saved. The grid itself never
// shows more than MAX_CARD_COLS cards per row (ScreenerGrid / HealthBoard /
// .wl-card-grid cap their tracks at a third of the width), so a wide screen
// gets three BIGGER cards, never a fourth or fifth.
//
// The auto-fit heuristic mirrors the real layout. Keep these constants in sync
// with ScreenerGrid.jsx (the full-bleed grid wrapper's side padding + the card
// min-width + gap) and the app's scrollbar width. The same math is duplicated in
// index.html's pre-paint script (so the scale applies before React mounts, with
// no flash); update both together — uiScale.test.js runs the real script.

// One key per screen. Until 2026-10-02 every screen shared the single key
// 'chrollo:ui-scale'; it is no longer read — its one value served both monitors.
export const STORAGE_KEY_PREFIX = 'chrollo:ui-scale@';

// Discrete steps, 85%–130% in 5% increments (operator chose finer steps). Stays
// inside the desktop layout so the 760/1200px breakpoints never fire.
export const SCALE_STEPS = [0.85, 0.9, 0.95, 1, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3];
export const DEFAULT_SCALE = 1;

// Horizontal chrome flanking the screener grid, in internal CSS px. The screener
// is full-bleed: ScreenerGrid's wrapper cancels the content-scroll side padding
// (margin: 0 -2rem) and re-adds 1rem each side, so the only horizontal chrome is
// that 2rem of wrapper padding (32px) plus the 6px overlay scrollbar. The old
// 86px app rail is gone — it became a horizontal top nav that costs height, not
// width — so it no longer belongs in this budget.
export const GRID_CHROME_PX = 32 + 6;
export const CARD_MIN_PX = 480; // mirrored by ScreenerGrid/HealthBoard gridStyle and .wl-card-grid
export const CARD_GAP_PX = 14;  // ScreenerGrid gap
// "The clean 3 charts per row rule" (operator 2026-10-02) — the grids cap their
// tracks at a third of the width, so this is a ceiling, never a target.
export const MAX_CARD_COLS = 3;

// Snap an arbitrary value to the nearest allowed step (defensive against a
// stale/garbage stored value).
export function clampScale(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return DEFAULT_SCALE;
  return SCALE_STEPS.reduce(
    (best, step) => (Math.abs(step - n) < Math.abs(best - n) ? step : best),
    SCALE_STEPS[0],
  );
}

// How many screener cards fit per row at a given scale for a browser viewport of
// `viewportWidth` px. Under CSS zoom S the app's internal coordinate width is
// viewportWidth / S, so the grid sees (viewportWidth / S) - chrome.
export function screenerColumnsAt(scale, viewportWidth) {
  const internalWidth = viewportWidth / scale - GRID_CHROME_PX;
  const cols = Math.floor((internalWidth + CARD_GAP_PX) / (CARD_MIN_PX + CARD_GAP_PX));
  return Math.min(MAX_CARD_COLS, Math.max(1, cols));
}

// "Smart" pick: the least shrink (largest scale <= 1) that still reaches the most
// screener columns achievable without shrinking past the smallest step. Density
// is a shrink, so auto-fit never enlarges past 1 — zooming in is a manual call.
// With the three-card ceiling this is 100% on any screen at least ~1506px wide.
export function computeAutoFitScale(viewportWidth) {
  const candidates = SCALE_STEPS.filter((s) => s <= 1);
  const maxCols = Math.max(...candidates.map((s) => screenerColumnsAt(s, viewportWidth)));
  return candidates
    .filter((s) => screenerColumnsAt(s, viewportWidth) === maxCols)
    .reduce((a, b) => Math.max(a, b));
}

// Which physical screen the window is on. `screen` reports the CSS size of the
// screen the window currently sits on, and Chrome updates it when the window is
// dragged to another monitor.
export function monitorId(screenLike = globalThis.screen) {
  const width = Number(screenLike?.width);
  const height = Number(screenLike?.height);
  if (!(width > 0) || !(height > 0)) return 'default';
  return `${Math.round(width)}x${Math.round(height)}`;
}

export const storageKeyFor = (id) => `${STORAGE_KEY_PREFIX}${id}`;

// The operator's manual choice for this screen, or null (= auto-fit).
export function readStoredScale(id = monitorId()) {
  try {
    const raw = localStorage.getItem(storageKeyFor(id));
    return raw == null ? null : clampScale(raw);
  } catch {
    return null;
  }
}

export function persistScale(scale, id = monitorId()) {
  try {
    localStorage.setItem(storageKeyFor(id), String(scale));
  } catch {
    /* private mode / storage disabled — scale still applies for the session */
  }
}

// Back to auto-fit on this screen.
export function clearStoredScale(id = monitorId()) {
  try {
    localStorage.removeItem(storageKeyFor(id));
  } catch {
    /* nothing stored, nothing to clear */
  }
}

export function applyScale(scale) {
  document.documentElement.style.setProperty('--ui-scale', String(scale));
}
