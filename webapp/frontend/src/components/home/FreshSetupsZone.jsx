import { useState } from 'react';
import { Link } from 'react-router-dom';
import HomeZone from './HomeZone';
import HomeSetupTile from './HomeSetupTile';
import BridgeOut from './BridgeOut';
import ScreenerModal from '../ScreenerModal';
import { ScreenerIcon } from '../NavIcons';
import { tierColor } from '../../theme';
import { fmtScanTime } from '../../utils/appFormat';
import { TIER_LETTERS } from '../wireVocabulary';

const TOP_N = 4;
const TIERS = TIER_LETTERS;
const ICON = <ScreenerIcon className="home-zone-iconsvg" />;

function selectTodaysScan(screenerData) {
  const ordered = screenerData?.ordered_tickers || [];
  const chartData = screenerData?.chart_data || {};
  const counts = { S: 0, A: 0, B: 0, C: 0 };
  for (const t of ordered) {
    const tier = chartData[t]?.tier;
    if (tier && counts[tier] != null) counts[tier] += 1;
  }
  return { counts, top: ordered.slice(0, TOP_N), total: ordered.length };
}

// "stale" = the last successful scan ran on a PRIOR calendar day, so the counts
// below reflect yesterday, not today. A distinct fact from "no scan" / "0 matched".
function ranOnPriorDay(scanStatus) {
  const when = scanStatus?.finished_at;
  if (!when) return false;
  const dt = new Date(when);
  if (Number.isNaN(dt.getTime())) return false;
  return dt.toDateString() !== new Date().toDateString();
}

export default function FreshSetupsZone({ screenerData, scanStatus }) {
  const [peek, setPeek] = useState(null);
  const link = <Link className="home-zone-link" to="/screener">Open the grid →</Link>;
  const status = scanStatus?.status;

  if (status === 'never') {
    return <HomeZone title="Fresh Setups" icon={ICON} link={link} status="empty" empty="No scan has run yet." />;
  }
  if (!scanStatus && !screenerData) {
    return <HomeZone title="Fresh Setups" icon={ICON} link={link} status="loading" skeletonRows={2} />;
  }

  const { counts, top, total } = selectTodaysScan(screenerData);
  const running = status === 'running';
  const stale = ranOnPriorDay(scanStatus);
  const chartData = screenerData?.chart_data || {};

  const meta = (
    <span className="home-zone-sub" style={{ color: stale ? 'var(--warning)' : 'var(--text-faint)' }}>
      {running ? 'scanning…' : `scanned ${fmtScanTime(scanStatus?.finished_at)}${stale ? ' · stale' : ''}`}
    </span>
  );

  let body;
  if (total === 0) {
    body = (
      <div className="home-zone-msg" style={{ color: 'var(--text-muted)' }}>
        {running ? 'Scan in progress…' : 'Scan ran — 0 setups matched.'}
      </div>
    );
  } else {
    body = (
      <>
        <div className="home-fresh-counts">
          {TIERS.map((t) => (
            <span
              key={t}
              className="home-count-chip"
              style={{ borderColor: `${tierColor(t)}55`, color: tierColor(t) }}
            >
              {t} {counts[t]}
            </span>
          ))}
          <span className="home-count-total">{total} total</span>
        </div>
        <div className="home-fresh-tiles">
          {top.map((t) => <HomeSetupTile key={t} ticker={t} data={chartData[t]} onClick={setPeek} />)}
        </div>
      </>
    );
  }

  return (
    <>
      <HomeZone title="Fresh Setups" icon={ICON} meta={meta} link={link} status="ready">
        {body}
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
