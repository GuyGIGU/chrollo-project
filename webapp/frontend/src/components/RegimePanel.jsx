import { useState } from 'react';
import MarketRegimeDetailModal from './MarketRegimeDetailModal';
import {
  STATE_META,
  breadthTone,
  buildRegimeReasons,
  clamp01,
  countLabel,
  distributionTone,
  fxDays,
  fxPct,
  postureText,
} from './marketRegimeFormat';

// The regime internals, beside the index chart and aligned to the same grid
// column. Breadth/distribution + index posture; clicking an index opens the
// existing regime detail modal. Reads the SAME scan source as Fresh Setups
// (screenerData.market_context), so the two can never desync.
function RegimeStat({ label, value, detail, tone, barValue }) {
  return (
    <div className="mp-stat">
      <span className="mp-stat-label">{label}</span>
      <strong className="mp-stat-val" style={{ color: tone || 'var(--text-main)' }}>{value}</strong>
      {detail ? <span className="mp-stat-detail">{detail}</span> : null}
      {barValue != null && Number.isFinite(Number(barValue)) && (
        <div className="mp-stat-bar"><div style={{ width: `${clamp01(barValue) * 100}%`, background: tone || 'var(--accent-blue)' }} /></div>
      )}
    </div>
  );
}

function PostureRow({ symbol, trend, onOpen }) {
  return (
    <button type="button" className="rp-posture-row" onClick={onOpen} title={`Open ${symbol} regime details`}>
      <span className="rp-posture-sym">{symbol}</span>
      <span className="rp-posture-badges">
        <b>{postureText(trend?.above_sma_50)} 50D</b>
        <b>{postureText(trend?.above_sma_200)} 200D</b>
      </span>
    </button>
  );
}

export default function RegimePanel({ marketContext }) {
  const [detailSymbol, setDetailSymbol] = useState(null);

  if (!marketContext) {
    return (
      <section className="rp-card instrument-tile">
        <span className="rp-eyebrow">Market Regime</span>
        <div className="home-skeleton">{[0, 1, 2].map((i) => <div key={i} className="home-skeleton-row" />)}</div>
      </section>
    );
  }

  const regime = marketContext.regime || {};
  const state = regime.state || 'UNKNOWN';
  const meta = STATE_META[state] || STATE_META.UNKNOWN;
  const indexes = regime.indexes || {};
  const spy = indexes.SPY || {};
  const qqq = indexes.QQQ || {};
  const reasons = buildRegimeReasons(regime, spy, qqq);
  const selectedIndex = detailSymbol ? indexes[detailSymbol] || {} : null;

  return (
    <>
      <section className="rp-card instrument-tile">
        <div className="rp-head">
          <span className="rp-eyebrow">Market Regime</span>
          <div className="rp-state">
            <span className="mp-dot" style={{ background: meta.tone, boxShadow: `0 0 10px ${meta.tone}` }} />
            <strong style={{ color: meta.tone }}>{meta.label}</strong>
          </div>
          <span className="rp-sub">{meta.summary}</span>
        </div>

        <div className="rp-stats">
          <RegimeStat label="Breadth 50D" value={fxPct(regime.breadth_50_pct)}
            detail={countLabel(regime.breadth_50_count, regime.breadth_50_total)}
            barValue={regime.breadth_50_pct} tone={breadthTone(regime.breadth_50_pct)} />
          <RegimeStat label="Breadth 200D" value={fxPct(regime.breadth_200_pct)}
            detail={countLabel(regime.breadth_200_count, regime.breadth_200_total)}
            barValue={regime.breadth_200_pct} tone={breadthTone(regime.breadth_200_pct)} />
          <RegimeStat label="Distribution" value={fxDays(regime.distribution_days)}
            detail="selling pressure" tone={distributionTone(regime.distribution_days)} />
        </div>

        <div className="rp-posture">
          <PostureRow symbol="SPY" trend={spy} onOpen={() => setDetailSymbol('SPY')} />
          <PostureRow symbol="QQQ" trend={qqq} onOpen={() => setDetailSymbol('QQQ')} />
        </div>
      </section>

      {detailSymbol && (
        <MarketRegimeDetailModal
          symbol={detailSymbol}
          trend={selectedIndex}
          regime={regime}
          meta={meta}
          reasons={reasons}
          onClose={() => setDetailSymbol(null)}
        />
      )}
    </>
  );
}
