import useEdgePulse from '../../hooks/useEdgePulse';
import HomeZone from './HomeZone';
import { PulseIcon } from '../NavIcons';
import { pct, signedPct } from './homeFormat';
import { tierColor } from '../../theme';
import { TIER_LETTERS } from '../wireVocabulary';

// Display floors: a median MFE over very few rows is noise; a win-rate over few
// LABELLED (resolved) rows is worse. Below the floor we show the n, never a
// precise-looking number that would read as a real edge.
const MFE_MIN_N = 10;
const WIN_MIN_N = 15;
const TIERS = TIER_LETTERS;

function Figure({ value, label }) {
  return (
    <div className="home-edge-fig">
      <span className="home-edge-val">{value ?? '—'}</span>
      <span className="home-edge-lbl">{label}</span>
    </div>
  );
}

export default function EdgePulse() {
  const { data, status } = useEdgePulse();
  const icon = <PulseIcon className="home-zone-iconsvg" />;

  if (status === 'loading') {
    return <HomeZone title="Engine Edge" icon={icon} status="loading" skeletonRows={2} />;
  }
  if (status === 'error') {
    return <HomeZone title="Engine Edge" icon={icon} status="empty" empty="Edge unavailable — restart the backend to enable /engine-edge." />;
  }

  const n = data?.n_unbiased || 0;
  if (!data || n === 0 || data.headline_mfe_median == null) {
    return <HomeZone title="Engine Edge" icon={icon} status="empty" empty="Not enough measured outcomes yet." />;
  }

  // Format ONLY — never re-derive the median/win-rate here (byte-parity with the
  // backtest harness). Suppress below the floor by showing the sample size.
  const headlineMfe = data.headline_mfe_n >= MFE_MIN_N ? pct(data.headline_mfe_median) : `n=${data.headline_mfe_n}`;

  return (
    <HomeZone title="Engine Edge" icon={icon} status="ready">
      <div className="home-edge-tile">
        <div className="home-edge-heads">
          <Figure value={headlineMfe} label="median MFE" />
          <Figure value={signedPct(data.abnormal_median)} label="excess vs SPY" />
        </div>
        <div className="home-edge-tiers">
          {TIERS.map((t) => {
            const b = data.by_tier?.[t];
            if (!b) return null;
            const mfe = b.mfe_n >= MFE_MIN_N ? pct(b.mfe_median) : `n=${b.mfe_n}`;
            const win = b.n_labelled >= WIN_MIN_N ? pct(b.win_rate) : (b.n_labelled ? `win n=${b.n_labelled}` : '—');
            return (
              <div key={t} className="home-edge-tier" title={`${t}: ${b.n} setups, ${b.n_labelled} resolved`}>
                <span className="home-edge-tier-id" style={{ color: tierColor(t) }}>{t}</span>
                <span className="home-edge-tier-v">{mfe}</span>
                <span className="home-edge-tier-w">{win}</span>
              </div>
            );
          })}
        </div>
        <span className="home-edge-foot">median MFE, elapsed window · unbiased, excludes seed · n={n}</span>
      </div>
    </HomeZone>
  );
}
