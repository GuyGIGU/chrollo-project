// The setups rail's one-row header (operator ask 2026-10-02: "add a way to
// search the tickers and split the list into pages of 20 setups"): the count,
// the search, and a compact pager that only shows once there is a second page.
// The search is an <input>, so the marking hotkeys already leave its keystrokes
// alone (isMarkingKeystroke); Escape clears it. Dumb strip — the rail owns the
// query and the page.
function CalibrationRailHeader({ shown, total, query, onQuery, page, pages, onPage }) {
  const filtered = query.trim() !== '';
  return (
    <div className="cal-rail-head">
      <span className="cal-rail-title">
        Setups{total ? ` · ${filtered ? `${shown} of ${total}` : total}` : ''}
      </span>
      <input
        type="search"
        className="cal-rail-search"
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Escape') onQuery(''); }}
        placeholder="Search ticker or label"
        aria-label="Search setups by ticker or label"
      />
      {pages > 1 && (
        <span className="cal-rail-pager" role="group" aria-label="Setup pages">
          <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}
                  aria-label="Previous page">
            ‹
          </button>
          <span className="cal-rail-page" aria-live="polite">{page}/{pages}</span>
          <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}
                  aria-label="Next page">
            ›
          </button>
        </span>
      )}
    </div>
  );
}

export default CalibrationRailHeader;
