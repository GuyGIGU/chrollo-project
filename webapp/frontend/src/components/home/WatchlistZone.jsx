import { useMemo, useState } from 'react';
import HomeZone from './HomeZone';
import ScreenerModal from '../ScreenerModal';
import BridgeOut from './BridgeOut';
import InstrumentTable from '../ui/InstrumentTable';
import { EyeIcon } from '../NavIcons';
import useWatchlistRecords from '../../hooks/useWatchlistRecords';
import { tierColor } from '../../theme';
import { signedPct } from './homeFormat';

const NEAR_TRIGGER_PCT = 0.02; // within 2% below the trigger (high of the last LPS bar)
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
  const [sort, setSort] = useState({ by: 'ticker', dir: 'asc' });

  const chartData = useMemo(() => screenerData?.chart_data || {}, [screenerData]);

  // Live prices + the stale flag come from HomeView's single shared poller
  // (useLivePrices), so the Home surface issues one /live-prices/ request per
  // cycle rather than one per zone.

  const rows = useMemo(() => records.map((record) => {
    const t = record.ticker;
    const data = chartData[t];
    const live = prices[t];
    const close = lastClose(data);
    const chg = (live != null && close) ? (live - close) / close : null;
    const trig = data?.trigger;
    const triggered = (live != null && Number.isFinite(Number(trig))) ? live >= trig : false;
    const nearPct = (live != null && Number.isFinite(Number(trig)) && !triggered)
      ? (trig - live) / trig
      : null;
    const stale = priceErr && live == null;
    return {
      t, data, live, chg, triggered,
      near: nearPct != null && nearPct <= NEAR_TRIGGER_PCT ? nearPct : null,
      stale,
      age: savedAgeDays(record.save_date),
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
        <span className="home-wlt-ident" title={row.data ? undefined : `${row.t} — not in the latest scan`}>
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
          {row.live != null ? Number(row.live).toFixed(2) : '—'}
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
          onRowClick={(row) => setPeek(row.t)}
          // A name that fell out of the latest scan has nothing to peek at, so
          // it must not wear the click affordance (the old surface disabled its
          // button; the row would otherwise glow and then do nothing).
          rowClickable={(row) => Boolean(row.data)}
          rowClassName={(row) => (row.data ? '' : 'muted')}
          maxHeight={368}
        />
      </HomeZone>
      {peek && chartData[peek] && (
        <ScreenerModal
          ticker={peek}
          data={chartData[peek]}
          scanIdentity={screenerData?.scan_identity ?? null}
          onClose={() => setPeek(null)}
          footer={<BridgeOut ticker={peek} />}
        />
      )}
    </>
  );
}
