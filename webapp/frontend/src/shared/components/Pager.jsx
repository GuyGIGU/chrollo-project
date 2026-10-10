import { PAGE_GAP, pageWindow } from '../presentation/pageWindow';

// The one pager (DESIGN.md §5 Pager): the screener grid, the archive table, the
// journal trades, and a compact ‹ n/N › form for the calibration list's header.
// Seven fixed slots (pageWindow), so it never changes width and Next never
// moves. It is dumb: the owner holds the page and clamps it.
export default function Pager({ page, pageCount, onPage, label, compact = false }) {
  if (pageCount <= 1) return null;

  return (
    <div className={compact ? 'pager pager-compact' : 'pager'} role="group" aria-label={label}>
      <button type="button" className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
        {compact ? '‹' : '‹ Prev'}
      </button>
      {compact ? (
        <span className="pager-count" aria-live="polite">{page}/{pageCount}</span>
      ) : (
        pageWindow(page, pageCount).map((entry, index) => (entry === PAGE_GAP ? (
          <span key={`gap-${index}`} className="pager-gap" aria-hidden="true">…</span>
        ) : (
          <button
            key={entry}
            type="button"
            className="btn"
            aria-current={entry === page ? 'page' : undefined}
            onClick={() => onPage(entry)}
          >
            {entry}
          </button>
        )))
      )}
      <button type="button" className="btn" disabled={page >= pageCount} onClick={() => onPage(page + 1)} aria-label="Next page">
        {compact ? '›' : 'Next ›'}
      </button>
    </div>
  );
}
