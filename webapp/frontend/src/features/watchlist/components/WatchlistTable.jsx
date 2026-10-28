import InstrumentTable from '../../../shared/components/InstrumentTable';
import { fx, fmtPctFrac, fmtSignedPctFrac } from '../../../shared/formatting/format.js';
import { signColor } from '../../../shared/presentation/theme';
import { BEST_GAIN_COLUMNS } from '../presentation/watchlistTable';

// Why a measured cell is a dash, by the wire's status word.
const GAIN_GAPS = {
  no_pin: 'Saved without a scan: no day to measure from',
  no_bar_since_scan: 'Nothing has traded since the saved scan yet',
  no_cache: 'Price history is being rewritten; try again shortly',
  unknown_ticker: 'No price history for this ticker',
  no_drawable_bars: 'No usable price history for this ticker',
};

// The save's UTC audit stamp in the operator's own clock, as his sheet's Time Added.
const addedLabel = (iso) => {
  if (!iso) return '—';
  const when = new Date(/[zZ+]/.test(iso.slice(10)) ? iso : `${iso}Z`);
  if (Number.isNaN(when.getTime())) return '—';
  const pad = (n) => String(n).padStart(2, '0');
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())} `
    + `${pad(when.getHours())}:${pad(when.getMinutes())}:${pad(when.getSeconds())}`;
};

const dayMonth = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

const earningsCell = (row) => (row.earnings == null ? '—' : (
  <span className={row.earnings_this_week ? 'wl-earn-week' : undefined}
    title={`Next report ${row.earnings}${row.earnings_confirmed === false ? ' (estimated)' : ''}${row.earnings_this_week ? ': this week' : ''}`}>
    {dayMonth(row.earnings)}{row.earnings_confirmed === false ? '?' : ''} · {row.earnings_days}d</span>
));

// Each sector fund keeps one hue, as the tiles on his sheet.
const ETF_HUES = { XLK: 270, XLV: 0, XLF: 210, XLY: 30, XLP: 95, XLC: 190, XLI: 45, XLE: 150, XLU: 60, XLRE: 320, XLB: 15 };
const sectorCell = (row) => (row.sector_etf == null ? '—' : (
  <span className="wl-etf" style={{ '--etf-hue': ETF_HUES[row.sector_etf] ?? 220 }} title={row.sector || row.sector_etf}>
    {row.sector_etf}</span>
));

const returnCell = (value, title) => (
  <span className={`wl-return-cell${value > 0 ? ' positive' : value < 0 ? ' negative' : ''}`}
    style={{ color: signColor(value) }} title={title}>{fmtSignedPctFrac(value, 2)}</span>
);
const gapTitle = (row, value) => (value == null ? GAIN_GAPS[row.gain_status] : undefined);

// The other best-gain windows ride the 30-day cell's hover, so the list fits the screen.
const otherWindows = (row) => BEST_GAIN_COLUMNS.filter(({ days }) => days !== 30)
  .map(({ key, days }) => `${days == null ? 'Since add' : `${days} days`}: ${fmtSignedPctFrac(row[key], 2)}`).join(' · ');

// One week's list in his sheet's column order. This week's rows take his L/S
// and the remove button; a past week is read-only and offers Carry over.
export default function WatchlistTable({ rows, sort, onSort, selected, onSelect, onRemove, onMark, onCarry,
  pastWeek, thisWeek, anchorProps, priceErr }) {
  const stop = (event) => event.stopPropagation();
  const columns = [
    { key: 'side', label: 'Side', align: 'center', render: (row) => (pastWeek
      ? <span className={`wl-side wl-side-${row.side}`}>{row.side}</span>
      : <select className={`wl-side wl-side-${row.side}`} value={row.side} title="Long or short"
        aria-label={`${row.ticker}: long or short`} onClick={stop}
        onChange={(event) => onMark(row.ticker, { side: event.target.value })}>
        <option value="L">L</option><option value="S">S</option></select>
    ) },
    { key: 'ticker', label: 'Ticker', render: (row) => <span className="wl-ledger-ticker">{row.ticker}</span> },
    { key: 'change', label: '% Change', align: 'right', render: (row) => (
      <span className={priceErr ? 'stale' : undefined} style={{ color: signColor(row.change) }}
        title={row.change == null ? gapTitle(row, null) : undefined}>{fmtSignedPctFrac(row.change, 2)}</span>
    ) },
    { key: 'diff_since_add', align: 'right',
      label: <span title="Latest quote against the high of the day before the add">% Diff since add</span>,
      render: (row) => returnCell(row.diff_since_add, gapTitle(row, row.diff_since_add)) },
    { key: 'best_30d', align: 'right',
      label: <span title="Best high in the first 30 days after the add, against the high of the day before the add; hover a cell for the other windows">
        % Diff best 30 days</span>,
      render: (row) => returnCell(row.best_30d, gapTitle(row, row.best_30d) || otherWindows(row)) },
    { key: 'market_cap', label: 'Mkt cap $B', align: 'right',
      render: (row) => <span className="wl-cap">{fx(row.market_cap == null ? null : row.market_cap / 1e9, 1)}</span> },
    { key: 'off_52w_high', align: 'right',
      label: <span title="How far the last close sits under the 52-week high">52W distance</span>,
      render: (row) => <span title={gapTitle(row, row.off_52w_high)}>{fmtPctFrac(row.off_52w_high, 2)}</span> },
    { key: 'earnings', label: 'Next earnings', render: earningsCell },
    { key: 'sector', label: 'Sector', align: 'center', render: sectorCell },
    { key: 'industry', label: 'Industry', render: (row) => <span className="wl-ledger-text" title={row.industry || undefined}>{row.industry || '—'}</span> },
    { key: 'added', label: 'Date', render: (row) => <time className="wl-added" dateTime={row.added || undefined}>{addedLabel(row.added)}</time> },
    { key: 'action', label: '', sortable: false, align: 'center', render: (row) => (pastWeek
      ? <button type="button" className="btn btn-sm" disabled={thisWeek.has(row.ticker)}
        title={thisWeek.has(row.ticker) ? 'Already on this week’s list' : 'Add to this week’s list'}
        onClick={(event) => { stop(event); onCarry(row); }}>{thisWeek.has(row.ticker) ? 'This week' : 'Carry over'}</button>
      : <button type="button" className="row-remove" aria-label={`Remove ${row.ticker} from the watchlist`}
        onClick={(event) => { stop(event); onRemove(row.ticker); }}>×</button>
    ) },
  ];
  return (
    <div className="wl-ledger">
      <InstrumentTable columns={columns} rows={rows} rowKey={(row) => row.ticker}
        sortBy={sort.by} sortDir={sort.dir} onSort={onSort} onRowClick={(row) => onSelect(row.ticker)}
        rowProps={(row) => ({ ...anchorProps(row.ticker, row.ticker, row.ticker),
          'data-ticker': row.ticker, 'aria-current': row.ticker === selected || undefined })}
        rowClassName={(row) => (row.ticker === selected ? 'wl-row-selected' : '')}
        ariaLabel="Watchlist tickers" maxHeight="calc(100dvh / var(--ui-scale, 1) - 240px)" />
    </div>
  );
}
