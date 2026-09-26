import { useCallback, useMemo, useState } from 'react';
import InstrumentTable from '../../../shared/components/InstrumentTable';
import WeeklyReview from './WeeklyReview';
import HoverGlass from '../../../shared/charts/glance/HoverGlass';
import useHoverGlance from '../../../shared/charts/glance/useHoverGlance';
import { artifactGlance } from '../../../shared/charts/glance/glanceResolvers';
import { buildWatchlistRows, sortWatchlistRows } from '../presentation/watchlistTable';
import { fx as fixed } from '../../../shared/formatting/format';
import { tierColor } from '../../../shared/presentation/theme';
import { confirmDialog } from '../../../shared/components/feedback';

// The watchlist manager: every starred name as a dense, sortable ledger row —
// the ones live in today's scan carry their tier/score/setup, the rest read as a
// coherent muted "no live setup" row (roughly half a real watchlist). Replaces
// the old chip list; the in-scan setups still show as full chart cards in the
// grid above, so this is the manage-and-triage view, not a second chart wall.
function ScreenerWatchlistPanel({ watchlist, screenerData, isScanning, onToggleWatchlist }) {
  // Sort lives in the caller (controlled), not inside the table primitive.
  const [sort, setSort] = useState({ by: 'tier', dir: 'asc' });
  const [reviewOpen, setReviewOpen] = useState(false);

  // Derive the rows every render — never store them, or a star toggle / rescan
  // leaves a stale grid.
  const rows = useMemo(
    () => sortWatchlistRows(buildWatchlistRows(watchlist, screenerData), sort.by, sort.dir),
    [watchlist, screenerData, sort],
  );

  // Glance only — this panel's rows have no click verb (the cards above are
  // where a setup is opened), and hover must not invent one.
  const chartData = useMemo(() => screenerData?.chart_data || {}, [screenerData]);
  const scanStamp = screenerData?.scan_identity?.scan_date || screenerData?.scanned_at || null;
  const resolveGlance = useCallback(
    (ticker) => artifactGlance(chartData, ticker, scanStamp),
    [chartData, scanStamp],
  );
  const { glassProps, anchorProps } = useHoverGlance(resolveGlance, { suspended: reviewOpen });

  if (isScanning) return null;

  // The review entry point rides both states — un-starred HISTORY exists even
  // when the active watchlist is empty.
  const review = (
    <>
      <button type="button" className="focus-ring" style={reviewButtonStyle}
              onClick={() => setReviewOpen(true)}>
        Review
      </button>
      <WeeklyReview open={reviewOpen} onClose={() => setReviewOpen(false)}
                    screenerData={screenerData} />
    </>
  );

  if (!watchlist || watchlist.size === 0) {
    return (
      <div style={{ ...emptyStyle, alignItems: 'center', display: 'flex', gap: 12, justifyContent: 'space-between' }}>
        <span>
          No names on your watchlist yet. Star a setup (the ☆ on a screener card) to add it here.
        </span>
        {review}
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
  // an off-scan name has no card, so a confirm guards against an accidental
  // de-listing — though with the ledger it is no longer irreversible: its
  // history stays in Review, where any name can be re-starred.
  const removeName = async (ticker, inScan) => {
    if (!inScan) {
      const ok = await confirmDialog({
        title: 'Remove from watchlist?',
        message: `${ticker} has no setup in today's scan. Its saved history stays in Review, where you can re-star it any time. Remove it from the watchlist?`,
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
        <span
          style={{ color: row.in_scan ? tierColor(row.tier) : 'var(--text-muted)', fontWeight: 700 }}
        >
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
      key: 'grade',
      label: 'Grade',
      align: 'right',
      render: (row) => fixed(row.grade, 0),
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
      <div style={{ alignItems: 'center', display: 'flex', gap: 12 }}>
        <div style={captionStyle}>
          Watchlist — {watchlist.size} {watchlist.size === 1 ? 'name' : 'names'} · {inScanCount} with a live setup
        </div>
        {review}
      </div>
      <InstrumentTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.ticker}
        sortBy={sort.by}
        sortDir={sort.dir}
        onSort={onSort}
        rowClassName={(row) => (row.in_scan ? '' : 'muted')}
        // The whole row is the hover target; the glass lands beside the cursor.
        rowProps={(row) => anchorProps(row.ticker, row.ticker, row.ticker)}
        ariaLabel="Watchlist"
      />
      <HoverGlass {...glassProps} />
    </div>
  );
}

const captionStyle = {
  color: 'var(--text-muted)',
  fontSize: '12px',
  fontWeight: 500,
};

const reviewButtonStyle = {
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-lg)',
  color: 'var(--text-main)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 12,
  marginLeft: 'auto',
  padding: '3px 12px',
  whiteSpace: 'nowrap',
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
