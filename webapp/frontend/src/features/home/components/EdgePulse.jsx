import useEdgePulse from '../hooks/useEdgePulse';
import HomeZone from './HomeZone';
import { PulseIcon } from '../../../shared/components/NavIcons';
import { pct, signedPct } from './homeFormat';
import { tierColor } from '../../../shared/presentation/theme';
import { TIER_LETTERS } from '../../../shared/presentation/wireVocabulary';

// Display floors: a median MFE over very few rows is noise; a win-rate over few
// LABELLED (resolved) rows is worse. Below the floor we show the n, never a
// precise-looking number that would read as a real edge.
const MFE_MIN_N = 10;
// An exceedance rate needs a bigger floor than a median: the base rate is ~6%, so
// under a hundred rows a single extra winner swings it by more than the whole
// spread between tiers. Measured 2026-09-08, tier C read 7.32% on 41 rows (three
// hits) and would otherwise have out-ranked tier B on 498 — the same trap the win
// rate fell into, in a new column.
const TAIL_MIN_N = 100;
const TIERS = TIER_LETTERS;

// Format only. The threshold arrives on the wire beside the rate it was measured
// against, so this labels what the backend measured and never declares it (EC-28).
const bandLabel = (band) => `≥${Math.round((band?.threshold ?? 0) * 100)}%`;

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

  // Format ONLY — never re-derive the median/win-rate/tail-rate here (byte-parity
  // with the backtest harness). Suppress below the floor by showing the sample size.
  const headlineMfe = data.headline_mfe_n >= MFE_MIN_N ? pct(data.headline_mfe_median) : `n=${data.headline_mfe_n}`;
  const headTail = data.tail ?? { n: 0, bands: [] };
  const headBands = headTail.bands ?? [];
  // Both bands share ONE headline figure — denser than a figure each, and the
  // pair is what carries the read (the rate falls off steeply with the threshold).
  const tailValue = headTail.n >= TAIL_MIN_N
    ? headBands.map((b) => pct(b.rate)).join(' / ')
    : `n=${headTail.n}`;
  const tailLabel = headBands.length
    ? `MFE ${headBands.map(bandLabel).join(' / ')} in 20d`
    : 'MFE tail in 20d';
  // The tier column shows the FIRST measured band; the headline shows every band.
  const tierBandIdx = 0;

  return (
    <HomeZone title="Engine Edge" icon={icon} status="ready">
      <div className="home-edge-tile">
        <div className="home-edge-heads">
          <Figure value={tailValue} label={tailLabel} />
          <Figure value={headlineMfe} label="median MFE" />
          <Figure value={signedPct(data.abnormal_median)} label="excess vs SPY" />
        </div>
        <div className="home-edge-tiers">
          {TIERS.map((t) => {
            const b = data.by_tier?.[t];
            if (!b) return null;
            const mfe = b.mfe_n >= MFE_MIN_N ? pct(b.mfe_median) : `n=${b.mfe_n}`;
            const tail = b.tail ?? { n: 0, bands: [] };
            const band = (tail.bands ?? [])[tierBandIdx];
            const tailCell = tail.n >= TAIL_MIN_N && band
              ? pct(band.rate)
              : (tail.n ? `n=${tail.n}` : '—');
            // The win rate lives in the tooltip WITH its resolution rate. It is
            // conditional on the setup having resolved, and the resolution rate
            // runs 62% for S down to 16% for C — quoted alone it ranked the
            // thinnest tier best. Never surface one without the other.
            const winPart = b.win_rate != null
              ? `, win ${pct(b.win_rate)} of the ${b.n_labelled} resolved (${pct(b.resolution_rate, 0)} of the tier)`
              : '';
            return (
              <div key={t} className="home-edge-tier" title={`${t}: ${b.n} setups${winPart}`}>
                <span className="home-edge-tier-id" style={{ color: tierColor(t) }}>{t}</span>
                <span className="home-edge-tier-v">{mfe}</span>
                <span className="home-edge-tier-w">{tailCell}</span>
              </div>
            );
          })}
        </div>
        <span className="home-edge-foot">
          median MFE, elapsed window · tier column {headBands[tierBandIdx] ? `= MFE ${bandLabel(headBands[tierBandIdx])} in 20d` : ''} · unbiased, excludes seed · n={n}
        </span>
      </div>
    </HomeZone>
  );
}
