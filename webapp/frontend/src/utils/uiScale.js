// UI scale — one knob that zooms the whole app via CSS `zoom` on `.app-layout`,
// so the hardcoded-px text and the rem-based spacing grow/shrink *together*.
// It lets the operator size the app to a scaled monitor (e.g. Windows 125% ->
// 1536x864 effective viewport) instead of leaning on native browser zoom.
//
// The auto-fit heuristic mirrors the real layout. Keep these constants in sync
// with ScreenerGrid.jsx (the full-bleed grid wrapper's side padding + the card
// min-width + gap) and the app's scrollbar width. A small drift only nudges the
// heuristic by ~one step, which the stepper corrects — but keep them honest. The
// same math is duplicated in index.html's pre-paint script (so the saved/first-
// run scale applies before React mounts, with no flash); update both together.

export const STORAGE_KEY = 'chrollo:ui-scale';

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
  return Math.max(1, cols);
}

// "Smart" pick: the least shrink (largest scale <= 1) that still reaches the most
// screener columns achievable without shrinking past the smallest step. Density
// is a shrink, so auto-fit never enlarges past 1 — zooming in is a manual call.
export function computeAutoFitScale(viewportWidth) {
  const candidates = SCALE_STEPS.filter((s) => s <= 1);
  const maxCols = Math.max(...candidates.map((s) => screenerColumnsAt(s, viewportWidth)));
  return candidates
    .filter((s) => screenerColumnsAt(s, viewportWidth) === maxCols)
    .reduce((a, b) => Math.max(a, b));
}

export function readStoredScale() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw == null ? null : clampScale(raw);
  } catch {
    return null;
  }
}

export function persistScale(scale) {
  try {
    localStorage.setItem(STORAGE_KEY, String(scale));
  } catch {
    /* private mode / storage disabled — scale still applies for the session */
  }
}

export function applyScale(scale) {
  document.documentElement.style.setProperty('--ui-scale', String(scale));
}
