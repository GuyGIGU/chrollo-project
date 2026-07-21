import { useMemo, useState } from 'react';
import InstrumentTable from './ui/InstrumentTable';
import FrameThumb from './FrameThumb';
import { buildSetupRows, sortSetupRows } from '../utils/calibrationTables';
import { fmtDateShort } from '../utils/format';

// The calibrated-list navigator (Task 7): a persistent RIGHT-SIDE rail of
// first-class SETUPS — one row per (ticker, as_of) — so the chart stays the
// protagonist and two setups on one symbol read as two distinct entries (never
// collapsed onto "the ticker"). Grouped by ticker like a TradingView watchlist.
// A click LOADS that setup for review/edit; it never advances the worklist queue
// (Friedman watchpoint — the rail and the forward queue are distinct intents).
// The active row is DERIVED from the loaded (ticker, as_of) — no store, no
// selectedSetupId. Rows are cheap static DOM (a mini FrameThumb, never a live
// chart). Element indicators answer the priority order Box/R/S → LPS → Trigger
// at a glance; the engine-test verdict lands here in Task 12.
function CalibrationRail({ setups, activeTicker, activeAsOf, onPick }) {
  const [sort, setSort] = useState({ by: 'ticker', dir: 'asc' });

  const rows = useMemo(
    // Defensive: accept either prebuilt setup rows or raw marks, so the rail is
    // correct even if a caller hands it the marks array directly.
    () => {
      const built = Array.isArray(setups) && setups.length && 'key' in setups[0]
        ? setups
        : buildSetupRows(setups);
      return sortSetupRows(built, sort.by, sort.dir);
    },
    [setups, sort],
  );

  const isActive = (row) => row.ticker === activeTicker && row.asOf === activeAsOf;

  const onSort = (key) =>
    setSort((current) =>
      current.by === key
        ? { by: key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        : { by: key, dir: key === 'ticker' ? 'asc' : 'desc' });

  const columns = [
    {
      key: 'ticker',
      label: 'Ticker',
      align: 'left',
      render: (row) => (
        <span style={{
          fontWeight: 700,
          color: isActive(row) ? 'var(--myth-bright)' : 'var(--text-main)',
        }}>
          {row.ticker}
        </span>
      ),
    },
    {
      // The as-of session IS the setup's identity — what tells two setups on one
      // symbol apart. A ·N badge flags the rare multi-mark session (extra label /
      // a negative alongside the box).
      key: 'asOf',
      label: 'Setup',
      align: 'left',
      render: (row) => (
        <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {fmtDateShort(row.asOf)}
          {row.count > 1 && (
            <span style={{ color: 'var(--text-faint)', marginLeft: 4 }}>·{row.count}</span>
          )}
        </span>
      ),
    },
    {
      // What's marked, in priority order Box/R/S → LPS → Trigger. Verdict pill in
      // the operator hue; a neutral LPS chip; the Trigger flag in its warm token.
      key: 'marked',
      label: 'Marked',
      align: 'left',
      sortable: false,
      render: (row) => (
        <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', whiteSpace: 'nowrap' }}>
          <span className={`inst-pill ${row.isBox ? 'box' : 'neg'}`}>{row.verdict}</span>
          {row.hasLps && (
            <span className="cal-rail-tag" title="An LPS is marked on this setup">LPS</span>
          )}
          {row.hasTrigger && (
            <span className="cal-rail-tag trig"
                  title={`Trigger (buy) marked${row.triggerDate ? ` @ ${row.triggerDate}` : ''}`}>
              T
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'frame',
      label: 'Frame',
      align: 'left',
      sortable: false,
      render: (row) => (
        <FrameThumb
          ticker={row.ticker}
          asOf={row.asOf}
          digest={row.frameDigest}
          isBox={row.isBox}
          r={row.resistance}
          s={row.support}
          boxStart={row.boxStart}
          boxEnd={row.boxEnd}
        />
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%' }}>
      <div style={{ color: 'var(--text-faint)', fontSize: 11, letterSpacing: '0.06em',
                    textTransform: 'uppercase', fontWeight: 600 }}>
        Setups{rows.length ? ` · ${rows.length}` : ''}
      </div>
      {rows.length ? (
        // Fill the rail's remaining height and scroll inside the well (the table
        // owns its own scroll when handed a maxHeight; '100%' resolves against
        // this flex:1 min-height:0 wrapper).
        <div style={{ flex: 1, minHeight: 0 }}>
          <InstrumentTable
            columns={columns}
            rows={rows}
            rowKey={(row) => row.key}
            sortBy={sort.by}
            sortDir={sort.dir}
            onSort={onSort}
            onRowClick={(row) => onPick(row.ticker, row.asOf)}
            rowClassName={(row) => (isActive(row) ? 'active-row' : '')}
            ariaLabel="Calibrated setups"
            maxHeight="100%"
          />
        </div>
      ) : (
        <div style={{ color: 'var(--text-faint)', fontSize: 12, padding: '8px 2px' }}>
          No setups yet — load a chart and mark one; it appears here.
        </div>
      )}
    </div>
  );
}

export default CalibrationRail;
