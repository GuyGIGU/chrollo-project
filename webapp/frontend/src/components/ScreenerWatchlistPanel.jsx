import { useMemo, useState } from 'react';
import InstrumentTable from './ui/InstrumentTable';
import { buildWatchlistRows, sortWatchlistRows } from '../utils/watchlistTable';
import { fixed } from '../utils/archiveTabUtils';
import { tierColor } from '../theme';
import { confirmDialog } from './ui/feedback';

// The watchlist manager: every starred name as a dense, sortable ledger row —
// the ones live in today's scan carry their tier/score/setup, the rest read as a
// coherent muted "no live setup" row (roughly half a real watchlist). Replaces
// the old chip list; the in-scan setups still show as full chart cards in the
// grid above, so this is the manage-and-triage view, not a second chart wall.
function ScreenerWatchlistPanel({ watchlist, screenerData, isScanning, onToggleWatchlist }) {
  // Sort lives in the caller (controlled), not inside the table primitive.
  const [sort, setSort] = useState({ by: 'tier', dir: 'asc' });

  // Derive the rows every render — never store them, or a star toggle / rescan
  // leaves a stale grid.
  const rows = useMemo(
    () => sortWatchlistRows(buildWatchlistRows(watchlist, screenerData), sort.by, sort.dir),
    [watchlist, screenerData, sort],
  );

  if (isScanning) return null;

  if (!watchlist || watchlist.size === 0) {
    return (
      <div style={emptyStyle}>
        No names on your watchlist yet. Star a setup (the ☆ on a screener card) to add it here.
      </div>
    );
  }

  const onSort = (key) =>
    setSort((current) =>
      current.by === key
        ? { by: key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        : { by: key, dir: key === 'score' ? 'desc' : 'asc' });

  const inScanCount = rows.filter((row) => row.in_scan).length;

  // In-scan names can be re-starred from their card, so removal is frictionless;
  // an off-scan name has no card to re-add it from, so guard that (irreversible)
  // removal with a confirm.
  const removeName = async (ticker, inScan) => {
    if (!inScan) {
      const ok = await confirmDialog({
        title: 'Remove from watchlist?',
        message: `${ticker} has no setup in today's scan, so it can only be re-added when it next appears in the screener. Remove it anyway?`,
        confirmLabel: 'Remove',
        cancelLabel: 'Keep',
        danger: true,
      });
      if (!ok) return;
    }
    onToggleWatchlist(ticker);
  };

  const columns = [
    {
      key: 'ticker',
      label: 'Ticker',
      align: 'left',
      render: (row) => (
        <span style={{ color: row.in_scan ? tierColor(row.tier) : 'var(--text-muted)', fontWeight: 700 }}>
          {row.ticker}
        </span>
      ),
    },
    {
      key: 'tier',
      label: 'Tier',
      align: 'left',
      render: (row) =>
        row.in_scan ? <span style={{ color: tierColor(row.tier), fontWeight: 600 }}>{row.tier}</span> : '—',
    },
    {
      key: 'score',
      label: 'Score',
      align: 'right',
      render: (row) => fixed(row.score, 0),
    },
    {
      key: 'setup',
      label: 'Setup',
      align: 'left',
      render: (row) => row.setup || '—',
    },
    {
      key: 'in_scan',
      label: 'In scan',
      align: 'center',
      sortable: false,
      render: (row) =>
        row.in_scan
          ? <span style={{ color: 'var(--success)', fontWeight: 600 }}>Yes</span>
          : <span style={{ color: 'var(--text-muted)' }}>No</span>,
    },
    {
      key: 'remove',
      label: '',
      align: 'center',
      sortable: false,
      render: (row) => (
        <button
          type="button"
          className="row-remove"
          title={`Remove ${row.ticker} from watchlist`}
          aria-label={`Remove ${row.ticker} from watchlist`}
          onClick={(event) => {
            event.stopPropagation();
            removeName(row.ticker, row.in_scan);
          }}
        >
          ×
        </button>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={captionStyle}>
        Watchlist — {watchlist.size} {watchlist.size === 1 ? 'name' : 'names'} · {inScanCount} with a live setup
      </div>
      <InstrumentTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.ticker}
        sortBy={sort.by}
        sortDir={sort.dir}
        onSort={onSort}
        rowClassName={(row) => (row.in_scan ? '' : 'muted')}
        ariaLabel="Watchlist"
      />
    </div>
  );
}

const captionStyle = {
  color: 'var(--text-muted)',
  fontSize: '12px',
  fontWeight: 500,
};

const emptyStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-muted)',
  fontSize: '13px',
  padding: '14px 16px',
};

export default ScreenerWatchlistPanel;
