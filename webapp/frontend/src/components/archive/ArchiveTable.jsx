import { memo, useCallback } from 'react';
import HoverGlass from '../ui/HoverGlass';
import useHoverGlance from '../../hooks/useHoverGlance';
import { archiveGlance } from '../glanceResolvers';
import {
  ITEMS_PER_PAGE,
  QUALITY_LABELS,
  REVIEW_REASONS,
  fixed,
  labelColor,
  pct,
  rMultipleColor,
  signColor,
  tierColor,
} from '../../utils/archiveTabUtils';

// One row per episode (first-seen setup). Charts are NOT rendered per row —
// they open in a modal on click, so the table stays light at any row count.
const COLUMNS = [
  { key: 'ticker', label: 'Ticker', align: 'left' },
  { key: 'scan_date', label: 'Entry', align: 'left' },     // == first_seen for an episode
  { key: 'tier', label: 'Tier', align: 'left' },
  { key: 'score', label: 'Score', align: 'right' },
  { key: 'setup_type', label: 'Type', align: 'left' },
  { key: 'scan_count', label: 'Scans', align: 'right' },
  { key: 'fwd_return_20d', label: '20d', align: 'right' },
  { key: 'r_multiple_20d', label: 'R', align: 'right' },
  { key: 'triggered', label: 'Trig', align: 'center' },
  { key: '__passed', label: 'Seen?', align: 'center', sortable: false },
  { key: '__reason', label: 'Reason', align: 'left', sortable: false },
  { key: '__label', label: 'Label', align: 'left', sortable: false },
];

function ArchiveTable({
  currentPage,
  filteredSetups,
  onLabelChange,
  onOpenChart,
  onReviewReasonChange,
  onSort,
  onTogglePassed,
  pageSetups,
  setCurrentPage,
  sortBy,
  sortDir,
  totalPages,
}) {
  // The archive is the ONE surface whose glance must leave the page — its rows
  // predate the in-memory scan. The resolver caches per setup and shares one
  // in-flight request, because a hover sweep down 24 rows otherwise becomes 24
  // vendor pulls against the bucket the nightly scans depend on.
  const resolveGlance = useCallback((setup) => archiveGlance(setup.id, setup.ticker), []);
  const { glassProps, anchorProps } = useHoverGlance(resolveGlance);

  if (filteredSetups.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>
        No setups in archive yet. Run a screener scan, seed historical setups, or use + Add Setup above.
      </div>
    );
  }

  return (
    <>
      <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
        {rangeLabel(currentPage, filteredSetups.length)}
      </div>
      <div className="instrument-well" style={{ border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: '12px', width: '100%' }}>
          <thead>
            <tr>
              {COLUMNS.map(col => (
                <HeaderCell
                  key={col.key}
                  active={sortBy === col.key}
                  col={col}
                  onSort={onSort}
                  sortDir={sortDir}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {pageSetups.map(setup => (
              <SetupRow
                key={setup.episode_key || setup.id}
                onLabelChange={onLabelChange}
                onOpenChart={onOpenChart}
                onReviewReasonChange={onReviewReasonChange}
                onTogglePassed={onTogglePassed}
                setup={setup}
                tickerHover={anchorProps(String(setup.id), setup, setup.ticker)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <HoverGlass {...glassProps} />
      <ArchivePager currentPage={currentPage} setCurrentPage={setCurrentPage} totalPages={totalPages} />
    </>
  );
}

function HeaderCell({ active, col, onSort, sortDir }) {
  const sortable = col.sortable !== false;
  const arrow = active ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';
  return (
    <th
      onClick={sortable ? () => onSort(col.key) : undefined}
      style={{
        background: 'var(--bg-main)',
        borderBottom: '1px solid var(--border-color)',
        color: active ? 'var(--text-main)' : 'var(--text-muted)',
        cursor: sortable ? 'pointer' : 'default',
        fontWeight: active ? 700 : 600,
        padding: '8px 12px',
        textAlign: col.align,
        userSelect: 'none',
        whiteSpace: 'nowrap',
      }}
    >
      {col.label}{arrow}
    </th>
  );
}

const SetupRow = memo(({ onLabelChange, onOpenChart, onReviewReasonChange, onTogglePassed, setup, tickerHover }) => {
  const persisted = setup.scan_count > 1;
  return (
    <tr
      onClick={() => onOpenChart(setup)}
      onMouseEnter={event => { event.currentTarget.style.background = 'var(--bg-main)'; }}
      onMouseLeave={event => { event.currentTarget.style.background = 'transparent'; }}
      style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer' }}
    >
      <Cell align="left">
        <span style={{ color: tierColor(setup.tier), fontWeight: 700 }} {...tickerHover}>{setup.ticker}</span>
      </Cell>
      <Cell align="left" muted>{setup.first_seen || setup.scan_date}</Cell>
      <Cell align="left">
        <span style={{ color: tierColor(setup.tier), fontWeight: 600 }}>{setup.tier}</span>
      </Cell>
      <Cell align="right">{fixed(setup.score, 0)}</Cell>
      <Cell align="left" muted>{setup.setup_type}</Cell>
      <Cell align="right">
        <span title={persisted ? `flagged on ${setup.scan_count} scans (${setup.first_seen} → ${setup.last_seen})` : undefined}
          style={{ color: persisted ? 'var(--text-main)' : 'var(--text-muted)' }}>
          {setup.scan_count}
        </span>
      </Cell>
      <Cell align="right" color={signColor(setup.fwd_return_20d)}>{pct(setup.fwd_return_20d)}</Cell>
      <Cell align="right" color={rMultipleColor(setup.r_multiple_20d)}>{fixed(setup.r_multiple_20d, 2)}</Cell>
      <Cell align="center">
        {setup.triggered === 1 && <span style={{ color: 'var(--success)' }}>Yes</span>}
        {setup.triggered === 0 && <span style={{ color: 'var(--text-muted)' }}>No</span>}
        {setup.triggered == null && <span style={{ color: 'var(--text-muted)' }}>-</span>}
      </Cell>
      <Cell align="center">
        <button
          onClick={event => { event.stopPropagation(); onTogglePassed(setup.ticker, setup.first_seen); }}
          title={setup.passed ? 'Reviewed & skipped — click to unmark' : 'Mark as reviewed & skipped'}
          style={{
            background: setup.passed ? 'var(--accent-active)' : 'transparent',
            border: '1px solid',
            borderColor: setup.passed ? 'var(--accent-active)' : 'var(--border-color)',
            borderRadius: '4px',
            color: setup.passed ? 'var(--myth-ink)' : 'var(--text-muted)',
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: '10px',
            padding: '2px 8px',
            whiteSpace: 'nowrap',
          }}
        >
          {setup.passed ? '✓ Passed' : 'Pass'}
        </button>
      </Cell>
      <Cell align="left">
        <select
          onChange={event => onReviewReasonChange(setup.ticker, setup.first_seen, event.target.value || null)}
          onClick={event => event.stopPropagation()}
          title="Why this setup was reviewed and skipped"
          style={{
            background: 'var(--bg-main)',
            border: '1px solid var(--border-color)',
            borderRadius: '4px',
            color: setup.passed ? 'var(--text-main)' : 'var(--text-muted)',
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: '11px',
            padding: '2px 4px',
          }}
          value={setup.review_note || ''}
        >
          <option value="">-</option>
          {REVIEW_REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </Cell>
      <Cell align="left">
        <select
          onChange={event => onLabelChange(setup.id, event.target.value || null)}
          onClick={event => event.stopPropagation()}
          style={{
            background: 'var(--bg-main)',
            border: '1px solid var(--border-color)',
            borderRadius: '4px',
            color: labelColor(setup.quality_label),
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontSize: '11px',
            padding: '2px 4px',
          }}
          value={setup.quality_label || ''}
        >
          <option value="">-</option>
          {QUALITY_LABELS.map(label => <option key={label} value={label}>{label}</option>)}
        </select>
      </Cell>
    </tr>
  );
});

function Cell({ align, children, color, muted }) {
  return (
    <td style={{
      color: color || (muted ? 'var(--text-muted)' : 'var(--text-main)'),
      padding: '7px 12px',
      textAlign: align,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </td>
  );
}

function ArchivePager({ currentPage, setCurrentPage, totalPages }) {
  if (totalPages <= 1) return null;
  return (
    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginBottom: '20px', marginTop: '8px' }}>
      <PagerButton disabled={currentPage === 1} onClick={() => setCurrentPage(page => page - 1)}>Prev</PagerButton>
      {Array.from({ length: totalPages }, (_, index) => index + 1).map(page => (
        <PagerButton key={page} active={currentPage === page} onClick={() => setCurrentPage(page)}>
          {page}
        </PagerButton>
      ))}
      <PagerButton disabled={currentPage === totalPages} onClick={() => setCurrentPage(page => page + 1)}>Next</PagerButton>
    </div>
  );
}

function PagerButton({ active, children, disabled, onClick }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        background: active ? 'var(--accent-active)' : 'var(--bg-main)',
        border: '1px solid',
        borderColor: active ? 'var(--accent-active)' : 'var(--border-color)',
        borderRadius: '6px',
        color: active ? 'var(--myth-ink)' : 'var(--text-main)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
        fontWeight: active ? '600' : '400',
        opacity: disabled ? 0.5 : 1,
        padding: '6px 14px',
      }}
    >
      {children}
    </button>
  );
}

const rangeLabel = (currentPage, total) => {
  const start = (currentPage - 1) * ITEMS_PER_PAGE + 1;
  const end = Math.min(currentPage * ITEMS_PER_PAGE, total);
  return `Showing ${start}-${end} of ${total} setups`;
};

export default ArchiveTable;
