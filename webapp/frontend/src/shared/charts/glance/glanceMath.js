// The hover-glance's pure arithmetic: its status vocabulary and where the glass
// lands. Kept in a plain .js module (never the .jsx shell) for two reasons — it
// is the only part of a hover surface this repo can actually test (there is no
// DOM runner; timing and feel are named manual gates), and exporting constants
// from a .jsx file trips react-refresh/only-export-components.

// The ONE status tuple (EC-33): every consumer derives from this, nobody mints
// a parallel vocabulary. EC-27 — each refusing leg stays distinguishable:
// `pending` (asked, waiting), `empty` (asked, answered "nothing to show"), and
// `error` (asked, the ask failed) must never collapse into one another.
export const GLANCE_STATUSES = ['closed', 'pending', 'ready', 'empty', 'error'];

export const isGlanceStatus = (value) => GLANCE_STATUSES.includes(value);

// What one pointer sample means, given what the glass is already doing. The
// hover is driven by WHERE THE CURSOR IS rather than by enter/leave events (see
// useHoverGlance's header for why), which makes this the whole decision — so it
// lives here, pure and tested, instead of as branches inside a listener.
//   'none'  — the cursor is still on whatever we already answered for
//   'arm'   — a new anchor and nothing up yet: wait out the intent delay
//   'swap'  — a new anchor while the glass is up: retarget with no delay
//   'close' — no anchor under the cursor
// `current` is deliberately compared to `next` FIRST: a stationary pointer
// sends a move event per frame, and re-arming on each one would mean the glass
// never opens at all.
export function glanceAction({ current = null, next = null, open = false } = {}) {
  const from = current ?? null;
  const to = next ?? null;
  if (to === from) return 'none';
  if (!to) return 'close';
  return open ? 'swap' : 'arm';
}

// The glass, in INTERNAL css px (the app's own coordinate system, see below).
export const GLANCE_WIDTH = 380;
export const GLANCE_HEIGHT = 250;
const EDGE_MARGIN = 8;
// Far enough that the glass never sits under the pointer itself (it would still
// be harmless — the glass is pointerEvents:none — but a chart under your own
// cursor reads as a misplaced overlay), close enough to stay one glance away.
const CURSOR_GAP = 16;

// Where to put the glass: BESIDE THE CURSOR (operator 2026-09-02, "can you make
// them appear near the location of my cursor instead of static"). It used to be
// placed against the row's ticker cell, so on a wide table the chart opened far
// from where the operator was actually looking — and in the same spot for every
// row, which is the "static" he means.
//
// THE ZOOM TRAP: `.app-layout` carries `zoom: var(--ui-scale)` (0.85–1.30), and
// the glass renders INSIDE that subtree. Pointer coordinates (like
// getBoundingClientRect) answer in SCREEN px — already multiplied by the scale —
// but a position:fixed child of a zoomed subtree resolves its own top/left in
// the subtree's PRE-ZOOM px. So every screen-space input — the cursor point and
// the viewport box — is divided by the scale exactly once, and the result is in
// the units `style.top/left` actually speak. At scale 1 this is the identity,
// which is precisely why an untested version of this function would look
// correct on the operator's machine and land in the wrong place for anyone
// zoomed in.
//
// Preferred quadrant is down-and-right of the cursor, the way a tooltip sits;
// each axis flips independently when the glass would cross the viewport edge,
// then clamps. Both flips are computed from the SAME point, so a cursor in the
// bottom-right corner gets the glass up-and-left and never under itself.
// Pure: no DOM reads, no side effects.
export function glancePlacement({
  pointer,
  viewport,
  scale = 1,
  width = GLANCE_WIDTH,
  height = GLANCE_HEIGHT,
}) {
  const s = Number(scale);
  const safeScale = Number.isFinite(s) && s > 0 ? s : 1;
  if (!pointer || !viewport) return null;

  const x = Number(pointer.x) / safeScale;
  const y = Number(pointer.y) / safeScale;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;

  const viewW = viewport.width / safeScale;
  const viewH = viewport.height / safeScale;

  const side = x + CURSOR_GAP + width <= viewW - EDGE_MARGIN ? 'right' : 'left';
  const vertical = y + CURSOR_GAP + height <= viewH - EDGE_MARGIN ? 'below' : 'above';

  const rawX = side === 'right' ? x + CURSOR_GAP : x - CURSOR_GAP - width;
  const rawY = vertical === 'below' ? y + CURSOR_GAP : y - CURSOR_GAP - height;

  return {
    side,
    vertical,
    left: clamp(rawX, EDGE_MARGIN, Math.max(EDGE_MARGIN, viewW - width - EDGE_MARGIN)),
    top: clamp(rawY, EDGE_MARGIN, Math.max(EDGE_MARGIN, viewH - height - EDGE_MARGIN)),
  };
}

function clamp(value, low, high) {
  if (!Number.isFinite(value)) return low;
  return Math.min(Math.max(value, low), high);
}

// The chart is torn down and rebuilt whenever this key changes
// (ScreenerMiniChart keys its chart on `[ticker, data]` object identity), so it
// must be keyed on the CONTENT the payload came from, never the payload object:
// the screener store swaps `chart_data` for a fresh object on every landed
// fetch — including the one every hook mount fires — so an identity-keyed
// chart would rebuild itself mid-hover with no new scan at all.
export const glanceChartKey = (ticker, stamp) => `${ticker || '?'}|${stamp || 'none'}`;
