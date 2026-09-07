import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import ScreenerModal from '../ScreenerModal';
import BridgeOut from './BridgeOut';
import useWatchlist from '../../hooks/useWatchlist';
import { tierColor } from '../../theme';
import { formatScore } from '../../utils/scoreFormat';
import { fmtScanTime, scanStatusColor } from '../../utils/appFormat';
import { nearTriggerFrac, triggerFired } from '../../utils/triggerProximity.js';
import {
  actionCenterReadiness,
  countLabel,
  emptyStateLine,
  partialReadNote,
} from '../../utils/actionCenterState.js';

// "What needs me right now" — the cockpit's attention digest, promoting the
// urgent items out of the three zones below into one strip, ordered by urgency:
// open risk → entry fired → entry approaching → fresh top-tier idea.
//
// Trigger = the engine's `data.trigger` (the breakout level = high of the last
// LPS bar), NOT the resistance rail. "Near" = within the shared
// triggerProximity band (the ONE client-side trigger judgment, EC-3).
const STOP_RANK = { breached: 0, danger: 1, warning: 2 };
const STOP_FLAG = {
  breached: { label: 'through stop', tone: 'var(--danger)' },
  danger: { label: 'near stop', tone: 'var(--danger)' },
  warning: { label: 'watch stop', tone: 'var(--warning)' },
};
const FRESH_MAX = 8;

// "stale" = the data these claims are made from was produced on a PRIOR
// calendar day. Keyed off the ARTIFACT's own timestamp, never the latest run's:
// a failed run stamps a fresh finished_at while the chips below still read
// yesterday's artifact, which would read as maximum freshness.
// (Re-homed from the deleted FreshSetupsZone — this header is the surface making
// claims from that scan, so it carries the freshness statement in ALL its states.)
function ranOnPriorDay(timestamp) {
  if (!timestamp) return false;
  const dt = new Date(timestamp);
  if (Number.isNaN(dt.getTime())) return false;
  return dt.toDateString() !== new Date().toDateString();
}

// A terminal run that did NOT produce a good artifact. The chips below are then
// computed from an OLDER scan, so the header says so in danger tone.
const RUN_FAILED = {
  failed: 'last scan failed',
  aborted: 'last scan aborted',
  stale_data: 'last scan hit stale data',
};

// The freshness states: never-ran / running / failed·aborted·stale-data /
// scanned-time / stale / 0-matched. null while scan status is still loading —
// claim nothing rather than guess.
function scanFreshness(scanStatus, screenerData, ordered) {
  const status = scanStatus?.status;
  if (status === 'never') return { text: 'no scan has run yet', color: 'var(--text-faint)' };
  if (status === 'running') return { text: 'scanning…', color: 'var(--accent-blue)' };
  if (!scanStatus) return null;
  if (RUN_FAILED[status]) {
    return {
      text: `${RUN_FAILED[status]} ${fmtScanTime(scanStatus.finished_at)}`,
      // The tone comes from the one status->colour map; RUN_FAILED stays the
      // copy map. The two sets became identical when 'aborted' joined
      // scanStatusColor, and two copies of one set drift (EC-3).
      color: scanStatusColor(status),
    };
  }
  const stale = ranOnPriorDay(screenerData?.scanned_at);
  const zero = screenerData && ordered.length === 0;
  return {
    text: `scanned ${fmtScanTime(scanStatus.finished_at)}${stale ? ' · stale' : ''}${zero ? ' · 0 matched' : ''}`,
    color: stale ? 'var(--warning)' : 'var(--text-faint)',
  };
}

export default function ActionCenter({
  screenerData, trades, riskFor, prices = {}, scanStatus,
  riskStatus, priceStatus, screenerStatus,
}) {
  const { watchlist } = useWatchlist();
  const [peek, setPeek] = useState(null);

  const chartData = useMemo(() => screenerData?.chart_data || {}, [screenerData]);
  const ordered = useMemo(() => screenerData?.ordered_tickers || [], [screenerData]);
  const wlTickers = useMemo(() => [...watchlist].sort(), [watchlist]);

  // Live prices come from HomeView's single shared poller (useLivePrices) so the
  // Home surface issues one /live-prices/ request per cycle, not one per zone.

  // Open positions through/near their stop — the only category that can't wait.
  const atRisk = useMemo(() => {
    const open = (trades || []).filter((t) => t.pnl == null && !t.closing_date && t.ticker);
    return open
      .map((t) => ({ ticker: String(t.ticker).toUpperCase(), d: riskFor(t) }))
      .filter((r) => r.d && (r.d.status === 'open' || r.d.status === 'partial') && STOP_RANK[r.d.stopRiskTone] != null)
      .sort((a, b) => STOP_RANK[a.d.stopRiskTone] - STOP_RANK[b.d.stopRiskTone]);
  }, [trades, riskFor]);

  // Watchlist names at / approaching their trigger.
  const { triggered, near } = useMemo(() => {
    const trig = [];
    const nr = [];
    for (const t of wlTickers) {
      const data = chartData[t];
      const live = prices[t];
      if (live == null) continue;
      if (triggerFired(data, live)) trig.push({ t, data, live });
      else {
        const pct = nearTriggerFrac(data, live);
        if (pct != null) nr.push({ t, data, live, pct });
      }
    }
    nr.sort((a, b) => a.pct - b.pct);
    return { triggered: trig, near: nr };
  }, [wlTickers, chartData, prices]);

  // Fresh top-tier ideas from the latest scan.
  const freshS = useMemo(
    () => ordered.filter((t) => chartData[t]?.tier === 'S').slice(0, FRESH_MAX),
    [ordered, chartData],
  );

  const total = atRisk.length + triggered.length + near.length + freshS.length;

  // The empty state is a CLAIM about the world, so it needs every source to have
  // answered first — an unanswered source contributes an empty list that is
  // indistinguishable from "nothing here" (finding 9). Statuses only; no
  // judgment is recomputed here.
  const readiness = actionCenterReadiness({
    risk: riskStatus, prices: priceStatus, screener: screenerStatus,
  });
  const emptyLine = emptyStateLine(readiness);
  const partialNote = partialReadNote(readiness);

  const openPeek = (t) => { if (chartData[t]) setPeek(t); };
  const freshness = scanFreshness(scanStatus, screenerData, ordered);

  return (
    <section className="home-action">
      <div className="ac-head">
        <span className="ac-title">Action Center</span>
        <span className="ac-count">{countLabel(total, readiness)}</span>
        {freshness && (
          <span className="ac-fresh" style={{ color: freshness.color }}>{freshness.text}</span>
        )}
        {total > 0 && partialNote && (
          <span className="ac-fresh" style={{ color: readiness.failed.length ? 'var(--danger)' : 'var(--text-faint)' }}>
            {partialNote}
          </span>
        )}
      </div>

      {total === 0 ? (
        <div className="ac-clear" style={emptyLine.color ? { color: emptyLine.color } : undefined}>
          {emptyLine.text}
        </div>
      ) : (
        <div className="ac-groups">
          {atRisk.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: 'var(--danger)' }}>⚠ At risk</span>
              {atRisk.map(({ ticker, d }) => {
                const flag = STOP_FLAG[d.stopRiskTone];
                return (
                  <Link key={ticker} to="/portfolio" className="ac-chip" style={{ borderColor: `${flag.tone}66`, color: flag.tone }}>
                    {ticker}<span className="ac-chip-sub">{flag.label}{d.distToStopPct == null ? '' : ` ${d.distToStopPct.toFixed(1)}%`}</span>
                  </Link>
                );
              })}
            </div>
          )}

          {triggered.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: 'var(--success)' }}>▲ Triggered</span>
              {triggered.map(({ t, live }) => (
                <button key={t} type="button" className="ac-chip" onClick={() => openPeek(t)} style={{ borderColor: 'rgba(61,211,122,0.4)', color: 'var(--success)' }}>
                  {t}<span className="ac-chip-sub">{live.toFixed(2)}</span>
                </button>
              ))}
            </div>
          )}

          {near.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: 'var(--warning)' }}>◷ Near trigger</span>
              {near.map(({ t, pct }) => (
                <button key={t} type="button" className="ac-chip" onClick={() => openPeek(t)} style={{ borderColor: 'rgba(var(--warning-rgb),0.4)', color: 'var(--warning)' }}>
                  {t}<span className="ac-chip-sub">{(pct * 100).toFixed(1)}% to trigger</span>
                </button>
              ))}
            </div>
          )}

          {freshS.length > 0 && (
            <div className="ac-group">
              <span className="ac-glabel" style={{ color: tierColor('S') }}>✦ Fresh S-tier</span>
              {freshS.map((t) => (
                <button key={t} type="button" className="ac-chip" onClick={() => openPeek(t)} style={{ borderColor: `${tierColor('S')}55`, color: tierColor('S') }}>
                  {t}<span className="ac-chip-sub">{formatScore(chartData[t]?.ta_grade)}</span>
                </button>
              ))}
              <Link to="/screener" className="ac-more">grid →</Link>
            </div>
          )}
        </div>
      )}

      {peek && chartData[peek] && (
        <ScreenerModal
          ticker={peek}
          data={chartData[peek]}
          scanIdentity={screenerData?.scan_identity ?? null}
          onClose={() => setPeek(null)}
          footer={<BridgeOut ticker={peek} />}
        />
      )}
    </section>
  );
}
