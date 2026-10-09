// Which screener card the arrows and J/K move focus to (item 7). Pure, so
// node --test pins it; useCardKeyboard does the DOM side (reads the focused
// card and the grid's real column count, then moves focus).

export const CARD_KEYS = { ArrowRight: 'next', ArrowLeft: 'prev', ArrowDown: 'down', ArrowUp: 'up', j: 'next', k: 'prev' };
// W, L, Enter and Space are deliberately absent: they stay the focused card's own keys (ScreenerCard).
export function cardMove(key) {
  const k = typeof key === 'string' && key.length === 1 ? key.toLowerCase() : key;
  return Object.hasOwn(CARD_KEYS, k) ? CARD_KEYS[k] : null;
}

// Next focused card in a grid `columns` wide holding `count` cards. index -1 = no card focused yet:
// land on `firstVisible` (the first card on screen). Left/right/J/K step one card and stop at the ends
// (no wrap); up/down move a row; down into a short last row lands on its last card.
export function nextCardIndex(move, index, count, columns, firstVisible = 0) {
  if (!count) return null;
  const last = count - 1;
  if (index < 0) return Math.min(Math.max(firstVisible, 0), last);
  const cols = columns >= 1 ? Math.floor(columns) : 1;
  if (move === 'next') return Math.min(index + 1, last);
  if (move === 'prev') return Math.max(index - 1, 0);
  if (move === 'up') return index - cols >= 0 ? index - cols : index;
  if (move === 'down') {
    if (index + cols <= last) return index + cols;
    const lastRowStart = Math.floor(last / cols) * cols;
    return index < lastRowStart ? last : index;
  }
  return null;
}

// Column count from the resolved computed `grid-template-columns` (e.g. '618px 618px 618px').
// Read from the layout, not predicted from the viewport (uiScale), so the drill-down, the
// scrollbar and the zoom are all already in it.
export function gridColumnCount(template) {
  const tracks = String(template ?? '').trim().split(/\s+/).filter((t) => t && t !== 'none');
  return Math.max(1, tracks.length);
}
