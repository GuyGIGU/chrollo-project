// The app's ONE list of keys: what the '?' sheet (app/components/KeyCheatSheet.jsx)
// shows. The handlers live with their pages; keyMap.test.js pins the calibration,
// card and big-chart sections to their vocabularies: a key handled there without
// a row here, or a row for a letter (on the cards, any key) nothing handles, fails
// the suite. The Everywhere and Watchlist rows are not pinned.
//
// Rows are { keys: [...event.key names], does }. A section with `routes` shows
// only on those pages ('/' is Home itself, any other route also covers what is
// under it); 'Everywhere' always shows. Escape is deliberately not a global row:
// it means a different thing in each dialog and page.
export const KEY_SECTIONS = [
  {
    id: 'global',
    title: 'Everywhere',
    rows: [
      { keys: ['?'], does: 'Show or hide this list of keys' },
      { keys: ['/'], does: 'Jump to the search box (Screener, Archive, Calibration)' },
    ],
  },
  {
    id: 'cards',
    title: 'Screener cards',
    routes: ['/screener'],
    rows: [
      { keys: ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'], does: 'Move between the cards' },
      { keys: ['j', 'k'], does: 'Next / previous card' },
      { keys: ['Enter', ' '], does: 'Open the big chart for the card' },
      { keys: ['w'], does: 'Add to / remove from the watchlist' },
      { keys: ['l'], does: 'Like / unlike the setup' },
    ],
  },
  {
    // Every page that opens a big chart: Home's peeks and replays, the Screener,
    // the Archive. T needs only the ticker, so it works in all of them.
    id: 'lens',
    title: 'Big chart',
    routes: ['/', '/home', '/screener', '/archive'],
    rows: [
      { keys: ['t'], does: 'Open it on TradingView (new tab)' },
      { keys: ['Escape'], does: 'Close the big chart' },
    ],
  },
  {
    // Stepping and the star/heart are the Screener grid's: only it hands the lens a list and its lists.
    id: 'lens-screener',
    title: 'Big chart on the Screener',
    routes: ['/screener'],
    rows: [
      { keys: ['ArrowLeft', 'ArrowUp'], does: 'Previous setup' },
      { keys: ['ArrowRight', 'ArrowDown'], does: 'Next setup' },
      { keys: ['w'], does: 'Add to / remove from the watchlist' },
      { keys: ['l'], does: 'Like / unlike the setup' },
    ],
  },
  {
    id: 'watchlist',
    title: 'Watchlist',
    routes: ['/watchlist'],
    rows: [
      { keys: ['ArrowUp', 'ArrowDown'], does: 'Previous / next name' },
    ],
  },
  {
    id: 'calibration',
    title: 'Calibration',
    routes: ['/calibration'],
    rows: [
      { keys: ['ArrowUp', 'ArrowDown'], does: 'Previous / next setup in the list' },
      { keys: ['r'], does: 'Mark the resistance rail' },
      { keys: ['s'], does: 'Mark the support rail' },
      { keys: ['x'], does: 'Mark the box span' },
      { keys: ['c'], does: 'Mark a Phase C' },
      { keys: ['l'], does: 'Mark an LPS' },
      { keys: ['t'], does: 'Mark a spring test' },
      { keys: ['o'], does: 'Mark an SOS' },
      { keys: ['m'], does: 'Mark a mini consolidation' },
      { keys: ['u'], does: 'Mark the Last Supper' },
      { keys: ['b'], does: 'Mark the buy' },
      { keys: ['e'], does: "Show / hide the engine's read" },
      { keys: ['Enter'], does: 'Save the marks' },
      { keys: ['Escape'], does: 'Put the marking tool down' },
    ],
  },
];

const LABELS = { ArrowLeft: '←', ArrowRight: '→', ArrowUp: '↑', ArrowDown: '↓', Escape: 'Esc', ' ': 'Space' };

// How a key reads on its key cap: arrows as glyphs, letters upper-case, named keys as named.
export function keyLabel(key) {
  if (Object.hasOwn(LABELS, key)) return LABELS[key];
  return key.length === 1 ? key.toUpperCase() : key;
}

const onRoute = (pathname, route) => (route === '/' ? pathname === '/' : pathname.startsWith(route));

// 'Everywhere' plus the sections for the page at `pathname`.
export function keySectionsFor(pathname) {
  const path = String(pathname || '');
  return KEY_SECTIONS.filter((s) => !s.routes || s.routes.some((route) => onRoute(path, route)));
}
