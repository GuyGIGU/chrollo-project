// UI scale — one knob that zooms the whole app via CSS `zoom` on `.app-layout`,
// so the hardcoded-px text and the rem-based spacing grow/shrink *together*.
// It lets the operator size the app to a monitor instead of leaning on native
// browser zoom.
//
// PER MONITOR (operator 2026-10-02: "When using Chrollo on my main monitor the
// scale breaks and the clean 3 Charts per row rule gets ignored"). His two
// screens are 2560x1440 and 1920x1080, both at Windows 100%, and one stored
// value served both. A manual choice is now remembered per screen
// (`chrollo:ui-scale@2560x1440`); a screen with no choice is at 100%. index.html's
// pre-paint script applies the stored choice before React mounts, with no flash
// (uiScale.test.js runs the real script).
//
// ONE CARD SIZE, THE FINVIZ WAY (operator Thu 29/10/2026, his Finviz chart view
// "like finviz ... no matter monitor"). Measured there the same day: every chart is
// 466x219px at 1280, 1920 and 2560 alike, two, four and five to a row, centred, and
// the page is never zoomed to fit. So a card is CARD_PX wide on every screen and a
// wider window shows more of them. Before: always four columns (Wed 28/10/2026),
// stretched to 620px at 2560 and squeezed to 236px in a 1024px window, with an
// auto-fit that zoomed the whole app down in a narrower one.

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
// The card's one width: Finviz's 466px chart with Finviz's 4px gap between them (his
// "Finviz Daily, exactly", Thu 29/10/2026; 460 and 14 that afternoon). Four and three
// gaps are 1876px of the screener's 1882px grid at 1920; 2560 holds five, a 1024px
// window two. ScreenerGrid and HealthBoard build their grids from these two numbers.
export const CARD_PX = 466;
export const CARD_GAP_PX = 4;

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
// `viewportWidth` px (the grid's own auto-fill rule). Under CSS zoom S the app's
// internal coordinate width is viewportWidth / S, so the grid sees
// (viewportWidth / S) - chrome.
export function screenerColumnsAt(scale, viewportWidth) {
  const internalWidth = viewportWidth / scale - GRID_CHROME_PX;
  return Math.max(1, Math.floor((internalWidth + CARD_GAP_PX) / (CARD_PX + CARD_GAP_PX)));
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

// The operator's manual choice for this screen, or null (= 100%).
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

// Back to 100% on this screen.
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
