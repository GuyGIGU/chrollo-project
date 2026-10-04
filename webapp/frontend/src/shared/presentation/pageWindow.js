// The pager's slots (DESIGN.md §5 Pager). With more than seven pages it always
// gives exactly seven: the first, the last, the current page and one neighbour
// each side, plus a gap for each hidden run of 2 or more pages. So the pager
// never changes width, Next never moves, and a gap never hides one page (that
// page takes the slot instead). No clamping here: the owner clamps the page.
export const PAGE_GAP = 'gap';
const SLOTS = 7;

export function pageWindow(page, pageCount) {
  if (pageCount <= SLOTS) return Array.from({ length: pageCount }, (_, i) => i + 1);
  if (page <= 4) return [1, 2, 3, 4, 5, PAGE_GAP, pageCount];
  if (page >= pageCount - 3) return [1, PAGE_GAP, pageCount - 4, pageCount - 3, pageCount - 2, pageCount - 1, pageCount];
  return [1, PAGE_GAP, page - 1, page, page + 1, PAGE_GAP, pageCount];
}
