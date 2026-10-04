import Pager from '../../../shared/components/Pager';

// The setups rail's one-row header (operator ask 2026-10-02: "add a way to
// search the tickers and split the list into pages of 20 setups"): the count,
// the search, and a compact pager that only shows once there is a second page.
// The search is an <input>, so the marking hotkeys already leave its keystrokes
// alone (isMarkingKeystroke); Escape clears it, and '/' anywhere on the page
// focuses it (app/keyboard/keyMap.js). Dumb strip — the rail owns the query
// and the page.
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
        data-page-search
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Escape') onQuery(''); }}
        placeholder="Search ticker or label"
        aria-label="Search setups by ticker or label"
      />
      <Pager compact page={page} pageCount={pages} onPage={onPage} label="Setup pages" />
    </div>
  );
}

export default CalibrationRailHeader;
