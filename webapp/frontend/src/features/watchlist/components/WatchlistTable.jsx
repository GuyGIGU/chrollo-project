import InstrumentTable from '../../../shared/components/InstrumentTable';
import { fx, fmtPctFrac, fmtSignedPctFrac } from '../../../shared/formatting/format.js';
import { tierColor, signColor } from '../../../shared/presentation/theme';
import { BEST_GAIN_COLUMNS, READY_MARKS, nextReady } from '../presentation/watchlistTable';

// Why a measured cell is a dash, by the wire's status word.
const GAIN_GAPS = {
  no_pin: 'Saved without a scan: no day to measure from',
  no_bar_since_scan: 'Nothing has traded since the saved scan yet',
  no_cache: 'Price history is being rewritten; try again shortly',
  unknown_ticker: 'No price history for this ticker',
  no_drawable_bars: 'No usable price history for this ticker',
};
const READY_TITLES = ['Watching', '✓ A valid LPS: take it when it triggers', '✓✓ Top candidate this week'];

// The save's UTC audit stamp in the operator's own clock, as his sheet's Time Added.
const addedLabel = (iso) => {
  if (!iso) return '—';
  const when = new Date(/[zZ+]/.test(iso.slice(10)) ? iso : `${iso}Z`);
  if (Number.isNaN(when.getTime())) return '—';
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(when.getDate())}/${pad(when.getMonth() + 1)} ${pad(when.getHours())}:${pad(when.getMinutes())}`;
};

const dayMonth = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

// The move still needed to the trigger; Triggered once the quote is over it.
const triggerCell = (row) => {
  if (row.trigger == null) return <span title="No trigger: not in tonight's scan nor in the save">—</span>;
  const source = row.trigger_saved ? ' (as saved; tonight’s scan dropped it)' : '';
  if (row.triggered) {
    return <span className="wl-trig wl-trig-fired" title={`Over the trigger ${fx(row.trigger, 2)}${source}`}>Triggered</span>;
  }
  return (
    <span className={`wl-trig${row.near_trigger ? ' wl-trig-near' : ''}${row.trigger_saved ? ' wl-trig-saved' : ''}`}
      title={`Needs ${fmtSignedPctFrac(row.to_trigger, 2)} to reach the trigger ${fx(row.trigger, 2)}${source}`}>
      {fmtPctFrac(row.to_trigger, 1)}</span>
  );
};

const earningsCell = (row) => (row.earnings == null ? '—' : (
  <span className={row.earnings_this_week ? 'wl-earn-week' : undefined}
    title={`Next report ${row.earnings}${row.earnings_confirmed === false ? ' (estimated)' : ''}${row.earnings_this_week ? ': this week' : ''}`}>
    {dayMonth(row.earnings)}{row.earnings_confirmed === false ? '?' : ''} · {row.earnings_days}d</span>
));

// A name with its rank chip; the top quarter of the ranking reads as leading.
const rankedCell = (name, rank, of, leading, what) => (
  <span className="wl-ranked" title={name ? `${name}${rank == null ? ': not ranked' : `: #${rank} of ${of} ${what} by the median RS of their stocks${leading ? ', leading (top quarter)' : ''}`}` : ''}>
    <span className="wl-ledger-text">{name || '—'}</span>
    {rank != null && <span className={`wl-rank${leading ? ' wl-rank-lead' : ''}`}>{rank}/{of}</span>}
  </span>
);

const rsCell = (row) => (row.rs == null ? '—' : (
  <span className={row.place === 1 ? 'wl-leader' : undefined}
    title={`RS rating ${fx(row.rs, 0)}; #${row.place} of ${row.place_of} in ${row.industry} by RS${row.place === 1 ? ': the group’s leader' : ''}`}>
    {fx(row.rs, 0)} <span className="wl-place">#{row.place}/{row.place_of}</span></span>
));

const returnCell = (value, title) => (
  <span className={`wl-return-cell${value > 0 ? ' positive' : value < 0 ? ' negative' : ''}`}
    style={{ color: signColor(value) }} title={title}>{fmtSignedPctFrac(value, 2)}</span>
);
const gapTitle = (row, value) => (value == null ? GAIN_GAPS[row.gain_status] : undefined);

// One week's list in his sheet's column order. This week's rows take his marks
// (L/S, ✓/✓✓) and the remove button; a past week is read-only and offers Carry over.
export default function WatchlistTable({ rows, sort, onSort, selected, onSelect, onRemove, onMark, onCarry,
  pastWeek, thisWeek, anchorProps, priceErr }) {
  const stop = (event) => event.stopPropagation();
  const gainColumns = pastWeek ? BEST_GAIN_COLUMNS : BEST_GAIN_COLUMNS.filter((column) => column.days === 30);
  const columns = [
    { key: 'side', label: 'Type', align: 'center', render: (row) => (pastWeek
      ? <span className={`wl-side wl-side-${row.side}`}>{row.side}</span>
      : <button type="button" className={`wl-side wl-side-${row.side}`} title="Long or short: click to switch"
        aria-label={`${row.ticker}: ${row.side === 'S' ? 'short' : 'long'}, switch`}
        onClick={(event) => { stop(event); onMark(row.ticker, { side: row.side === 'L' ? 'S' : 'L' }); }}>{row.side}</button>
    ) },
    { key: 'ticker', label: 'Ticker', render: (row) => (
      <span className="wl-ledger-ticker" style={{ color: row.in_scan ? tierColor(row.tier) : undefined }}>{row.ticker}</span>
    ) },
    { key: 'ready', label: 'Ready', align: 'center', render: (row) => (pastWeek
      ? <span className="wl-ready" title={READY_TITLES[row.ready]}>{READY_MARKS[row.ready]}</span>
      : <button type="button" className="wl-ready" data-ready={row.ready} title={`${READY_TITLES[row.ready]}. Click for the next mark`}
        aria-label={`${row.ticker}: ${READY_TITLES[row.ready]}, change`}
        onClick={(event) => { stop(event); onMark(row.ticker, { ready: nextReady(row.ready) }); }}>
        {READY_MARKS[row.ready] || <span aria-hidden="true" className="wl-ready-empty">○</span>}</button>
    ) },
    { key: 'tier', label: 'Tier', render: (row) => (
      <span style={{ color: tierColor(row.tier) }} title={row.grade == null ? 'Not in the latest scan' : `Chart score ${fx(row.grade, 0)} / 100`}>
        {row.tier || '—'}</span>
    ) },
    { key: 'to_trigger', align: 'right',
      label: <span title="The move the latest quote still needs to reach the trigger">To trigger</span>,
      render: triggerCell },
    { key: 'change', label: 'Change %', align: 'right', render: (row) => (
      <span className={priceErr ? 'stale' : undefined} style={{ color: signColor(row.change) }}
        title={row.change == null ? gapTitle(row, null) : undefined}>{fmtSignedPctFrac(row.change, 2)}</span>
    ) },
    { key: 'diff_since_add', align: 'right',
      label: <span title="Latest quote against the high of the day before the add">% Diff since add</span>,
      render: (row) => returnCell(row.diff_since_add, gapTitle(row, row.diff_since_add)) },
    ...gainColumns.map(({ key, days }) => ({
      key, align: 'right',
      label: <span title={`Best high ${days == null ? 'since the add' : `in the first ${days} days after the add`}, against the high of the day before the add`}>
        {days == null ? '% Best since add' : `% Best ${days}d`}</span>,
      render: (row) => returnCell(row[key], gapTitle(row, row[key])),
    })),
    { key: 'market_cap', label: 'Cap $B', align: 'right', render: (row) => fx(row.market_cap == null ? null : row.market_cap / 1e9, 1) },
    { key: 'off_52w_high', align: 'right',
      label: <span title="How far the last close sits under the 52-week high">52W dist.</span>,
      render: (row) => <span title={gapTitle(row, row.off_52w_high)}>{fmtPctFrac(row.off_52w_high, 1)}</span> },
    { key: 'earnings', label: 'Earnings', render: earningsCell },
    { key: 'sector', label: 'Sector', render: (row) => rankedCell(row.sector, row.sector_rank, row.sector_of, row.sector_leading, 'sectors') },
    { key: 'industry', label: 'Group', render: (row) => rankedCell(row.industry, row.group_rank, row.group_of, row.group_leading, 'groups') },
    { key: 'rs', align: 'right', label: <span title="RS rating, and the stock’s place in its group by RS (#1 = the group’s leader)">RS · in group</span>,
      render: rsCell },
    { key: 'added', label: 'Added', render: (row) => <time dateTime={row.added || undefined}>{addedLabel(row.added)}</time> },
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
        rowClassName={(row) => [row.ticker === selected ? 'wl-row-selected' : '', row.ready === 2 ? 'wl-row-top' : '']
          .filter(Boolean).join(' ')}
        ariaLabel="Watchlist tickers" maxHeight="calc(100dvh / var(--ui-scale, 1) - 240px)" />
    </div>
  );
}
