import { useCallback, useMemo, useState } from 'react';
import HomeZone from './HomeZone';
import ScreenerModal from '../../../shared/setup/ScreenerModal';
import BridgeOut from './BridgeOut';
import InstrumentTable from '../../../shared/components/InstrumentTable';
import HoverGlass from '../../../shared/charts/glance/HoverGlass';
import { EyeIcon } from '../../../shared/components/NavIcons';
import useWatchlistRecords from '../../watchlist/hooks/useWatchlistRecords';
import useHoverGlance from '../../../shared/charts/glance/useHoverGlance';
import { artifactGlance, snapshotGlance } from '../../../shared/charts/glance/glanceResolvers';
import { adaptReplaySnapshot, replayProvenance } from '../../../shared/charts/glance/replayAdapter';
import { toast } from '../../../shared/components/feedback';
import { API_BASE } from '../../../api/base';
import { tierColor } from '../../../shared/presentation/theme';
import { signedPct } from '../presentation/homeFormat';
import { nearTriggerFrac, triggerFired } from '../../../shared/setup/triggerProximity.js';
import { finiteOrNull } from '../../../shared/formatting/format.js';

// "Near" = the shared triggerProximity band (the ONE client-side trigger judgment, EC-3).
const ICON = <EyeIcon className="home-zone-iconsvg" />;

function lastClose(data) {
  const candles = data?.candles;
  if (!candles || !candles.length) return null;
  const c = candles[candles.length - 1];
  const v = c?.close ?? c?.c ?? null;
  return Number.isFinite(Number(v)) ? Number(v) : null;
}

// Whole days since the save event's dated key (the ledger's save_date, a
// YYYY-MM-DD the server stamps from the UTC date). Both endpoints are taken in
// THAT calendar — read against local midnights, a save made after local
// midnight but before UTC midnight (the operator's post-scan review window)
// would read "1d" the instant it was clicked. null = optimistic row in flight.
function savedAgeDays(saveDate) {
  if (!saveDate) return null;
  const saved = Date.parse(`${saveDate}T00:00:00Z`);
  if (Number.isNaN(saved)) return null;
  const today = Date.parse(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`);
  return Math.max(0, Math.round((today - saved) / 86400000));
}

const fmtAge = (days) => (days == null ? '—' : days === 0 ? 'today' : `${days}d`);

// The promoted Watchlist (Finviz plan Task 13): the InstrumentTable idiom in a
// double-width cell — dense rows, tabular mono numerics, the new width spent on
// COLUMNS (ticker+tier, last, signed %, trigger proximity, saved-age, bridge),
// not padding. Rows come from the shared ledger store's dated records, so the
// saved-age column is the provenance stamp's tabular twin.
export default function WatchlistZone({ screenerData, prices = {}, priceErr = false }) {
  const records = useWatchlistRecords();
  const [peek, setPeek] = useState(null);
  const [replay, setReplay] = useState(null);
  const [sort, setSort] = useState({ by: 'ticker', dir: 'asc' });

  const chartData = useMemo(() => screenerData?.chart_data || {}, [screenerData]);

  // Live prices + the stale flag come from HomeView's single shared poller
  // (useLivePrices), so the Home surface issues one /live-prices/ request per
  // cycle rather than one per zone.

  const scanStamp = screenerData?.scan_identity?.scan_date || screenerData?.scanned_at || null;

  // Hover reads the scan already in memory; a name that fell out of it falls
  // back to the chart stored when it was saved, so the glance answers for every
  // row rather than only today's.
  const resolveGlance = useCallback((row) => (
    chartData[row.t]
      ? artifactGlance(chartData, row.t, scanStamp)
      : snapshotGlance(row.watchId, row.t)
  ), [chartData, scanStamp]);

  const { glassProps, anchorProps, closeGlance } = useHoverGlance(
    resolveGlance,
    { suspended: Boolean(peek) || Boolean(replay) },
  );

  // Click is commit: a name in the latest scan opens its live chart; a name
  // that fell out opens the chart stored with its most recent save, clearly
  // framed as as-saved. The dead disabled row is retired — but a save made
  // before charts were stored (every legacy row) still has nothing to show, so
  // it says so rather than opening an empty modal.
  const openRow = useCallback((row) => {
    closeGlance();
    if (row.data) { setPeek(row.t); return; }
    if (row.watchId == null) return;
    fetch(`${API_BASE}/watchlist/${row.watchId}/replay`)
      .then((response) => {
        if (!response.ok) throw new Error(`replay ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        const adapted = adaptReplaySnapshot(payload?.snapshot);
        if (!adapted) {
          toast(`${row.t} was saved before charts were stored — nothing to replay.`);
          return;
        }
        setReplay({ ticker: row.t, entry: adapted.entry, provenance: replayProvenance(payload) });
      })
      .catch((error) => {
        console.error('Watchlist replay failed', error);
        toast(`Could not load the saved chart for ${row.t}.`, { tone: 'danger' });
      });
  }, [closeGlance]);

  const rows = useMemo(() => records.map((record) => {
    const t = record.ticker;
    const data = chartData[t];
    const live = prices[t];
    const close = lastClose(data);
    const chg = (live != null && close) ? (live - close) / close : null;
    const triggered = triggerFired(data, live);
    const nearPct = triggered ? null : nearTriggerFrac(data, live);
    const stale = priceErr && live == null;
    return {
      t, data, live, chg, triggered,
      near: nearPct,
      stale,
      age: savedAgeDays(record.save_date),
      // The active save event's id — the row's own most recent save, which is
      // what a name absent from today's scan replays.
      watchId: record.id ?? null,
    };
  }), [records, chartData, prices, priceErr]);

  const sorted = useMemo(() => {
    const dir = sort.dir === 'asc' ? 1 : -1;
    const num = (v) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v));
    const value = {
      ticker: (row) => row.t,
      last: (row) => num(row.live),
      chg: (row) => num(row.chg),
      age: (row) => row.age,
    }[sort.by] || ((row) => row.t);
    // Nulls sink to the bottom in EITHER direction — the direction multiplier
    // only applies to real values, so flipping a column never floats the
    // no-data rows to the top.
    return [...rows].sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return dir * (typeof va === 'string' ? va.localeCompare(vb) : va - vb);
    });
  }, [rows, sort]);

  if (records.length === 0) {
    return <HomeZone title="Watchlist" icon={ICON} status="empty" empty="No names yet. Star a setup to track it here." />;
  }

  const onSort = (key) => setSort((prev) => (
    prev.by === key ? { by: key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { by: key, dir: 'asc' }
  ));

  const columns = [
    {
      key: 'ticker',
      label: 'Ticker',
      render: (row) => (
        <span
          className="home-wlt-ident"
          title={row.data ? undefined : `${row.t} — not in the latest scan; opens the chart saved with it`}
        >
          {/* No color of its own when the name isn't in the scan — the row's
              `muted` class dims it, which an inline color would defeat. */}
          <span style={{ color: row.data ? tierColor(row.data.tier) : undefined, fontWeight: 800 }}>{row.t}</span>
          {row.data?.tier ? (
            <span className="home-wlt-tier" style={{ borderColor: `${tierColor(row.data.tier)}55`, color: tierColor(row.data.tier) }}>
              {row.data.tier}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: 'last',
      label: 'Last',
      align: 'right',
      render: (row) => (
        <span style={{ color: row.stale ? 'var(--text-faint)' : 'var(--text-main)' }}>
          {finiteOrNull(row.live) != null ? finiteOrNull(row.live).toFixed(2) : '—'}
        </span>
      ),
    },
    {
      key: 'chg',
      label: 'Chg',
      align: 'right',
      render: (row) => (
        <span style={{ color: row.chg == null ? 'var(--text-faint)' : row.chg >= 0 ? 'var(--success)' : 'var(--danger)' }}>
          {row.chg == null ? '·' : signedPct(row.chg)}
        </span>
      ),
    },
    {
      key: 'trig',
      label: 'Trigger',
      align: 'right',
      sortable: false,
      render: (row) => row.triggered
        ? <span style={{ color: 'var(--success)', fontWeight: 700 }}>▲ fired</span>
        : row.near != null
          ? <span style={{ color: 'var(--warning)', fontWeight: 700 }}>{(row.near * 100).toFixed(1)}% away</span>
          : <span style={{ color: 'var(--text-faint)' }}>{row.stale ? 'stale' : '—'}</span>,
    },
    {
      key: 'age',
      label: 'Saved',
      align: 'right',
      render: (row) => (
        <span style={{ color: 'var(--text-muted)' }}>{fmtAge(row.age)}</span>
      ),
    },
    {
      key: 'bridge',
      label: '',
      align: 'right',
      sortable: false,
      render: (row) => <BridgeOut ticker={row.t} compact />,
    },
  ];

  return (
    <>
      <HomeZone title="Watchlist" icon={ICON} status="ready">
        <InstrumentTable
          ariaLabel="Watchlist"
          columns={columns}
          rows={sorted}
          rowKey={(row) => row.t}
          sortBy={sort.by}
          sortDir={sort.dir}
          onSort={onSort}
          onRowClick={openRow}
          // Every row opens SOMETHING now: a name in the latest scan opens its
          // live chart, and one that fell out opens the chart stored when it
          // was saved. Only a name saved before charts were stored has nothing
          // behind it, and that row alone declines the affordance.
          rowClickable={(row) => Boolean(row.data) || row.watchId != null}
          rowClassName={(row) => (row.data ? '' : 'muted')}
          // The whole row summons the chart — the ticker cell is 40px of a
          // 500px row, and hovering a row and getting nothing reads as broken.
          rowProps={(row) => anchorProps(row.t, row, row.t)}
          maxHeight={368}
        />
      </HomeZone>
      <HoverGlass {...glassProps} />
      {peek && chartData[peek] && (
        <ScreenerModal
          ticker={peek}
          data={chartData[peek]}
          scanIdentity={screenerData?.scan_identity ?? null}
          onClose={() => setPeek(null)}
          footer={<BridgeOut ticker={peek} />}
        />
      )}
      {replay?.entry && (
        <ScreenerModal
          ticker={replay.ticker}
          data={replay.entry}
          // As-saved, not live: the verdict control stays inert because this is
          // not the current scan (the same contract the weekly review uses).
          scanIdentity={null}
          onClose={() => setReplay(null)}
          footer={<ReplayFooter replay={replay} />}
        />
      )}
    </>
  );
}

// The as-saved frame. Deliberately the SAME sentence the weekly review already
// speaks over the identical envelope — same words, same faint mono stamp, no
// color: the chart's palette is spoken for, and two different phrasings for one
// fact would read as two different facts.
function ReplayFooter({ replay }) {
  const { provenance, ticker } = replay;
  return (
    <div style={{
      alignItems: 'center',
      borderTop: '1px solid var(--border-color)',
      display: 'flex',
      flexWrap: 'wrap',
      gap: 12,
      padding: '8px 14px',
    }}>
      <span style={{
        color: 'var(--text-faint)',
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.08em',
      }}>
        {`AS SCANNED ${provenance?.asScanned || '—'} · saved ${provenance?.savedOn || '—'}`}
        {provenance?.unstarred ? ' · unstarred' : ''}
      </span>
      {provenance?.archiveNote ? (
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{provenance.archiveNote}</span>
      ) : null}
      <span style={{ marginLeft: 'auto' }}><BridgeOut ticker={ticker} /></span>
    </div>
  );
}
