import InstrumentTable from '../../../shared/components/InstrumentTable';
import { fx, fmtSignedPctFrac } from '../../../shared/formatting/format.js';
import { dayShort } from '../../../shared/setup/fundamentalsSheetRead.js';
import { tierColor, signColor } from '../../../shared/presentation/theme';

// The existing sortable ledger primitive, with one compact row per saved ticker.
export default function WatchlistTable({ rows, sort, onSort, selected, onSelect, onRemove, liked, onLike, anchorProps, priceErr }) {
  const columns = [
    { key: 'ticker', label: 'Ticker', render: (row) => (
      <span className="wl-ledger-ticker" style={{ color: row.in_scan ? tierColor(row.tier) : undefined }}>{row.ticker}</span>
    ) },
    { key: 'added', label: 'Added', render: (row) => <time dateTime={row.added || undefined}>{dayShort(row.added)}</time> },
    { key: 'setup', label: 'Setup', render: (row) => (
      <span className="wl-setup-label" title={row.saved_setup ? 'Setup in the saved scan' : 'Latest scan setup; no saved setup available'}>
        {row.saved_setup || row.setup || '—'}
      </span>
    ) },
    { key: 'tier', label: 'Tier', render: (row) => <span style={{ color: tierColor(row.tier) }}>{row.tier || '—'}</span> },
    { key: 'grade', label: 'TA / 100', align: 'right', render: (row) => fx(row.grade, 0) },
    { key: 'price', label: 'Last', align: 'right', render: (row) => <span className={priceErr ? 'stale' : undefined}>{fx(row.price)}</span> },
    { key: 'saved_price', label: 'Saved price', align: 'right', render: (row) => fx(row.saved_price) },
    { key: 'vs_saved', label: 'vs saved %', align: 'right', render: (row) => (
      <span className={`wl-return-cell${row.vs_saved > 0 ? ' positive' : row.vs_saved < 0 ? ' negative' : ''}`}
        style={{ color: signColor(row.vs_saved) }}>{fmtSignedPctFrac(row.vs_saved)}</span>
    ) },
    { key: 'rs_rating', label: 'RS', align: 'right', render: (row) => fx(row.rs_rating, 0) },
    { key: 'market_cap', label: 'Cap ($B)', align: 'right', render: (row) => fx(row.market_cap == null ? null : row.market_cap / 1e9, 1) },
    { key: 'sector', label: 'Sector', render: (row) => <span className="wl-ledger-text" title={row.sector || ''}>{row.sector || '—'}</span> },
    { key: 'industry', label: 'Industry', render: (row) => <span className="wl-ledger-text wl-industry" title={row.industry || ''}>{row.industry || '—'}</span> },
    { key: 'in_scan', label: 'In scan', sortable: false, render: (row) => <span className={row.in_scan ? 'wl-in-scan' : 'wl-off-scan'}>{row.in_scan ? 'Yes' : 'No'}</span> },
    { key: 'liked', label: 'Liked', sortable: false, align: 'center', render: (row) => (
      <button type="button" className="wl-row-action" aria-label={`Like ${row.ticker}`} aria-pressed={liked.has(row.ticker)}
        onClick={(event) => { event.stopPropagation(); onLike(row.ticker); }}><span aria-hidden="true">{liked.has(row.ticker) ? '♥' : '♡'}</span></button>
    ) },
    { key: 'remove', label: '', sortable: false, align: 'center', render: (row) => (
      <button type="button" className="row-remove" aria-label={`Remove ${row.ticker} from watchlist`}
        onClick={(event) => { event.stopPropagation(); onRemove(row.ticker); }}>×</button>
    ) },
  ];
  return (
    <div className="wl-ledger">
      <InstrumentTable columns={columns} rows={rows} rowKey={(row) => row.ticker}
        sortBy={sort.by} sortDir={sort.dir} onSort={onSort} onRowClick={(row) => onSelect(row.ticker)}
        rowProps={(row) => ({ ...anchorProps(row.ticker, row.ticker, row.ticker),
          'data-ticker': row.ticker, 'aria-current': row.ticker === selected || undefined })}
        rowClassName={(row) => row.ticker === selected ? 'wl-row-selected' : ''}
        ariaLabel="Watchlist tickers" maxHeight="calc(100dvh / var(--ui-scale, 1) - 240px)" />
    </div>
  );
}
