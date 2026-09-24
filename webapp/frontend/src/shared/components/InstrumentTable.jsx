// InstrumentTable — the shared dense-list scaffold the ledger surfaces hand-roll
// (see archive/ArchiveTable + PortfolioTables). It owns ONLY the table chrome:
// the .instrument-well frame, hairline zebra, a controlled sort header, and
// tabular-nums on right-aligned columns. It knows NOTHING about tiers, tags, or
// watchlists — every cell is whatever a column's `render(row)` returns (React
// nodes, never an HTML string), so a new caller is a column-def change, not a
// rewrite. Sort is CONTROLLED (sortBy / sortDir / onSort); the primitive keeps
// no sort state of its own. Callers own their own empty state (early return),
// as ArchiveTable and the Watchlist both do.
//
// columns: [{ key, label, align?, sortable?, render(row) }]
//   align 'right' also switches the cell to tabular-nums (numbers line up).
//   sortable defaults to true; a column with no natural order sets sortable:false.
// rowKey(row): stable React key. rowClassName(row): extra <tr> class (e.g. 'muted').
// onRowClick(row): optional — makes rows clickable + hover-cursored, and gives
//   each clickable row a keyboard path (tab stop + Enter/Space).
// rowClickable(row): optional predicate — when a caller has DEAD rows (no target
//   to open), this keeps the pointer cursor, the mythril lock-on and the handler
//   off them. Without it every row is clickable, as before.
// rowProps(row): optional extra attributes for the <tr> (the hover-glance marks
//   its rows this way). Spread FIRST, so a caller can never shadow the table's
//   own click/keyboard wiring.

// Active column shows the direction; a sortable-but-inactive column shows a faint
// hint so "this sorts" is discoverable before the first click.
function SortIndicator({ active, dir, sortable }) {
  if (active) return <span aria-hidden="true" className="it-sort-arrow">{dir === 'asc' ? '▲' : '▼'}</span>;
  if (sortable) return <span aria-hidden="true" className="it-sort-hint">⇅</span>;
  return null;
}

export default function InstrumentTable({
  columns,
  rows,
  rowKey,
  sortBy,
  sortDir,
  onSort,
  onRowClick,
  rowClickable,
  rowClassName,
  rowProps,
  ariaLabel,
  maxHeight,
}) {
  const clickable = Boolean(onRowClick);
  // A maxHeight makes the WELL itself the scroll container (overflowY:auto), so
  // a sticky thead has something to stick to; .it-scroll scopes the sticky rule.
  const scroll = maxHeight != null;
  return (
    <div
      className={`instrument-well${scroll ? ' it-scroll' : ''}`}
      style={{
        border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
        // Cells never wrap, so a well narrower than the table's min-content
        // would silently cut the rightmost columns — scroll instead of lying.
        overflow: 'hidden', overflowX: 'auto',
        ...(scroll ? { maxHeight, overflowY: 'auto' } : null),
      }}
    >
      <table className="instrument-table" aria-label={ariaLabel}>
        <thead>
          <tr>
            {columns.map((col) => {
              const sortable = col.sortable !== false && Boolean(onSort);
              const active = sortBy === col.key;
              const cls = [sortable ? 'sortable' : '', active ? 'active' : ''].filter(Boolean).join(' ');
              return (
                <th
                  key={col.key}
                  className={cls || undefined}
                  style={{ textAlign: col.align || 'left' }}
                  aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  {sortable ? (
                    // A real <button> so the sort is keyboard-operable (Enter/Space)
                    // while the <th> keeps its columnheader role + aria-sort.
                    <button type="button" className="it-sort" onClick={() => onSort(col.key)}>
                      {col.label}
                      <SortIndicator active={active} dir={sortDir} sortable />
                    </button>
                  ) : (
                    col.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const extra = rowClassName ? rowClassName(row) : '';
            const canClick = clickable && (!rowClickable || rowClickable(row));
            const cls = [canClick ? 'clickable' : '', extra].filter(Boolean).join(' ');
            return (
              <tr
                key={rowKey(row)}
                {...(rowProps ? rowProps(row) : null)}
                className={cls || undefined}
                onClick={canClick ? () => onRowClick(row) : undefined}
                tabIndex={canClick ? 0 : undefined}
                onKeyDown={canClick ? (event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onRowClick(row);
                  }
                } : undefined}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    style={{
                      textAlign: col.align || 'left',
                      fontVariantNumeric: col.align === 'right' ? 'tabular-nums' : undefined,
                      // Numeric columns read as instrument data, not prose (matches
                      // the chart/provenance mono numerics on the same page).
                      fontFamily: col.align === 'right'
                        ? "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
                        : undefined,
                    }}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
