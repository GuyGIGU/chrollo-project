import { useEffect } from 'react';
import { cardMove, gridColumnCount, nextCardIndex } from '../model/cardNavigation';
import { isPageKeystroke } from '../../../shared/navigation/keyboardGuard';

// Arrows / J / K move DOM focus across the screener cards; the focused card's own Enter/Space/W/L then act.
// The index comes from DOM focus each press (no React state), so a filter or page change cannot leave it stale.
export default function useCardKeyboard(rootRef) {
  useEffect(() => {
    const onKey = (event) => {
      const move = cardMove(event.key);
      if (!move || !isPageKeystroke(event)) return;   // typing, a modifier, or ANY dialog (the lens included)
      const grid = rootRef.current?.querySelector('.screener-grid');   // main grid or drill-down, never both
      // Evaluate dims the results and makes them inert: focus() would be a no-op, so leave the keys alone.
      if (!grid || grid.closest('[inert]')) return;
      const cards = [...grid.querySelectorAll(':scope > .screener-card[tabindex="0"]')];
      if (!cards.length) return;
      const current = cards.indexOf(document.activeElement?.closest?.('.screener-card'));
      const columns = gridColumnCount(getComputedStyle(grid).gridTemplateColumns);
      const target = nextCardIndex(move, current, cards.length, columns, firstVisibleIndex(cards));
      event.preventDefault();   // arrows never scroll the page here; the page follows the ring
      cards[target].focus({ preventScroll: true });
      cards[target].scrollIntoView({ block: 'nearest' });   // instant: Chromium won't animate under CSS zoom
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [rootRef]);
}

// The first card whose bottom edge is below the top of the scrolling pane: where the first key lands
// when no card is focused yet, so it never jumps the page back to the top-left card.
function firstVisibleIndex(cards) {
  const top = document.querySelector('.content-scroll')?.getBoundingClientRect().top ?? 0;
  const i = cards.findIndex((c) => c.getBoundingClientRect().bottom > top);
  return i < 0 ? 0 : i;
}
