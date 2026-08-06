import { useMemo, useState } from 'react';
import HomeZone from './HomeZone';
import ScreenerModal from '../ScreenerModal';
import BridgeOut from './BridgeOut';
import { EyeIcon } from '../NavIcons';
import useWatchlist from '../../hooks/useWatchlist';
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

export default function WatchlistZone({ screenerData, prices = {}, priceErr = false }) {
  const { watchlist } = useWatchlist();
  const [peek, setPeek] = useState(null);

  const tickers = useMemo(() => [...watchlist].sort(), [watchlist]);
  const chartData = screenerData?.chart_data || {};

  // Live prices + the stale flag come from HomeView's single shared poller
  // (useLivePrices), so the Home surface issues one /live-prices/ request per
  // cycle rather than one per zone.

  if (tickers.length === 0) {
    return <HomeZone title="Watchlist" icon={ICON} status="empty" empty="No names yet. Star a setup to track it here." />;
  }

  const rows = tickers.map((t) => {
    const data = chartData[t];
    const live = prices[t];
    const close = lastClose(data);
    const chg = (live != null && close) ? (live - close) / close : null;
    const trig = data?.trigger;
    const triggered = (live != null && Number.isFinite(Number(trig))) ? live >= trig : false;
    const nearTrigger = (live != null && Number.isFinite(Number(trig)) && !triggered)
      ? (trig - live) / trig <= NEAR_TRIGGER_PCT
      : false;
    const stale = priceErr && live == null;
    return { t, data, live, chg, triggered, nearTrigger, stale };
  });

  return (
    <>
      <HomeZone title="Watchlist" icon={ICON} status="ready">
        <div className="home-wl">
          {rows.map(({ t, data, live, chg, triggered, nearTrigger, stale }) => (
            <div key={t} className="home-wl-row">
              <button
                type="button"
                className="home-wl-name"
                onClick={() => data && setPeek(t)}
                disabled={!data}
                title={data ? `Peek ${t}` : `${t} — not in the latest scan`}
                style={{ color: data ? tierColor(data.tier) : 'var(--text-main)', cursor: data ? 'pointer' : 'default' }}
              >
                {t}
                {data?.tier ? <span className="home-wl-tier" style={{ color: tierColor(data.tier) }}>{data.tier}</span> : null}
              </button>
              <span className="home-wl-px" style={{ color: stale ? 'var(--text-faint)' : 'var(--text-main)' }}>
                {live != null ? Number(live).toFixed(2) : '—'}
              </span>
              <span
                className="home-wl-chg"
                title="change vs last close"
                style={{ color: chg == null ? 'var(--text-faint)' : chg >= 0 ? 'var(--success)' : 'var(--danger)' }}
              >
                {chg == null ? '·' : signedPct(chg)}
              </span>
              {triggered
                ? <span className="home-wl-flag triggered">▲ trigger</span>
                : nearTrigger
                  ? <span className="home-wl-flag near">near trig</span>
                  : <span className="home-wl-flag">{stale ? <span className="home-wl-stale">stale</span> : null}</span>}
              <BridgeOut ticker={t} compact />
            </div>
          ))}
        </div>
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
