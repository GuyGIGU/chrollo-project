// The top nav links back to a surface's last address (operator 2026-10-03, 'never lose your place').
// Session memory only; the tab you are on points at where you are now (the memory is written after
// render and can be one address behind).
const lastSearch = new Map();

export function rememberPlace(pathname, search) { lastSearch.set(pathname, search); }

export function placeFor(to, location) {
  if (to === location.pathname) return `${to}${location.search}`;
  return `${to}${lastSearch.get(to) ?? ''}`;
}

// A plain click on the tab he is on has nowhere to go. Followed anyway, the router REPLACED the
// entry with no state, which dropped the drill-down's Back tag (review 2026-10-04). A modified
// or middle click is left to the browser: it opens the page in a new tab.
export function goesNowhere(event, to, location) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  return placeFor(to, location) === `${location.pathname}${location.search}`;
}
