import { useState } from 'react';
import MarketRegimeDetailModal from './MarketRegimeDetailModal';
import {
  STATE_META,
  breadthTone,
  buildRegimeReasons,
  clamp01,
  countLabel,
  distributionTone,
  fxDate,
  fxDays,
  fxPct,
  fxPrice,
  fxSignedPct,
  indexTone,
  postureText,
  trendPhrase,
} from './marketRegimeFormat';

function MarketRegimeBanner({ marketContext }) {
  const [detailSymbol, setDetailSymbol] = useState(null);
  const regime = marketContext?.regime || {};
  const state = regime.state || 'UNKNOWN';
  const meta = STATE_META[state] || STATE_META.UNKNOWN;
  const indexes = regime.indexes || {};
  const spy = indexes.SPY || {};
  const qqq = indexes.QQQ || {};
  const selectedIndex = detailSymbol ? indexes[detailSymbol] || {} : null;
  const hasRegime = state !== 'UNKNOWN';
  const reasons = buildRegimeReasons(regime, spy, qqq);

  return (
    <>
      <section style={bannerStyle(meta)} title={meta.detail}>
        <button
          type="button"
          onClick={() => setDetailSymbol('SPY')}
          style={primaryButtonStyle}
          title="Open SPY regime details"
        >
          <span style={eyebrowStyle}>Market Regime</span>
          <span style={stateRowStyle}>
            <span style={stateDotStyle(meta)} />
            <strong style={{ color: meta.tone, fontSize: 20 }}>{meta.label}</strong>
          </span>
          <span style={summaryStyle}>{meta.summary}</span>
          <span style={timestampStyle}>
            {hasRegime ? `Updated ${fxDate(marketContext?.computed_at)}` : 'Awaiting new scan'}
          </span>
        </button>

        <div style={metricGridStyle}>
          <Metric
            label="Breadth 50D"
            value={fxPct(regime.breadth_50_pct)}
            detail={countLabel(regime.breadth_50_count, regime.breadth_50_total)}
            barValue={regime.breadth_50_pct}
            tone={breadthTone(regime.breadth_50_pct)}
            title="Share of screened names closing above their 50-day average. Weak 50D breadth can put the regime under pressure."
          />
          <Metric
            label="Breadth 200D"
            value={fxPct(regime.breadth_200_pct)}
            detail={countLabel(regime.breadth_200_count, regime.breadth_200_total)}
            barValue={regime.breadth_200_pct}
            tone={breadthTone(regime.breadth_200_pct)}
            title="Share of screened names closing above their 200-day average. Weak 200D breadth confirms broader market stress."
          />
          <Metric
            label="Distribution"
            value={fxDays(regime.distribution_days)}
            detail="selling pressure"
            tone={distributionTone(regime.distribution_days)}
            title="Recent index down days on higher volume. More distribution days mean institutions may be selling into the tape."
          />
          <IndexMetric symbol="SPY" trend={spy} onOpen={() => setDetailSymbol('SPY')} />
          <IndexMetric symbol="QQQ" trend={qqq} onOpen={() => setDetailSymbol('QQQ')} />
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

function Metric({ label, value, detail, title, tone, barValue }) {
  return (
    <div style={metricStyle} title={title}>
      <span style={metricLabelStyle}>{label}</span>
      <strong style={{ ...metricValueStyle, color: tone || 'var(--text-main)' }}>{value}</strong>
      <span style={metricDetailStyle}>{detail || 'n/a'}</span>
      {barValue != null && Number.isFinite(Number(barValue)) && (
        <div style={barTrackStyle}>
          <div style={{ ...barFillStyle, background: tone || 'var(--accent-blue)', width: `${clamp01(barValue) * 100}%` }} />
        </div>
      )}
    </div>
  );
}

function IndexMetric({ symbol, trend, onOpen }) {
  const above50 = trend?.above_sma_50;
  const above200 = trend?.above_sma_200;
  const tone = indexTone(above50, above200);
  const title = `${symbol}: close ${fxPrice(trend?.close)}, 50D ${postureText(above50)}, 200D ${postureText(above200)}, 50D slope ${fxSignedPct(trend?.sma_50_slope_pct)}. Click for details.`;

  return (
    <button type="button" onClick={onOpen} style={indexMetricStyle} title={title}>
      <span style={metricLabelStyle}>{symbol}</span>
      <strong style={{ ...metricValueStyle, color: tone }}>{trendPhrase(above50, above200)}</strong>
      <span style={metricDetailStyle}>50D slope {fxSignedPct(trend?.sma_50_slope_pct)}</span>
      <span style={miniBadgesStyle}>
        <TrendBadge label="50D" value={above50} />
        <TrendBadge label="200D" value={above200} />
      </span>
    </button>
  );
}

function TrendBadge({ label, value }) {
  const tone = value === true ? 'var(--success)' : value === false ? 'var(--danger)' : 'var(--text-muted)';
  return (
    <span style={{ ...trendBadgeStyle, borderColor: tone, color: tone }}>
      {label} {postureText(value)}
    </span>
  );
}

const bannerStyle = (meta) => ({
  alignItems: 'stretch',
  background: 'var(--bg-panel)',
  border: `1px solid ${meta.border}`,
  borderLeft: `3px solid ${meta.tone}`,
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  flexWrap: 'wrap',
  gap: 16,
  padding: '14px 16px',
});

const primaryButtonStyle = {
  background: 'transparent',
  border: 0,
  color: 'inherit',
  cursor: 'pointer',
  display: 'flex',
  flex: '1 1 220px',
  flexDirection: 'column',
  fontFamily: 'inherit',
  gap: 6,
  justifyContent: 'center',
  minWidth: 0,
  padding: 0,
  textAlign: 'left',
};

const metricGridStyle = {
  display: 'grid',
  flex: '3 1 660px',
  gap: 10,
  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
  minWidth: 0,
};

const metricStyle = {
  background: 'rgba(255, 255, 255, 0.025)',
  border: '1px solid rgba(255, 255, 255, 0.045)',
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  flexDirection: 'column',
  gap: 5,
  minHeight: 78,
  minWidth: 0,
  padding: '9px 10px',
};

const indexMetricStyle = {
  ...metricStyle,
  color: 'inherit',
  cursor: 'pointer',
  fontFamily: 'inherit',
  textAlign: 'left',
};

const eyebrowStyle = {
  color: 'var(--text-muted)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
};

const stateRowStyle = {
  alignItems: 'center',
  display: 'flex',
  gap: 8,
  minWidth: 0,
};

const stateDotStyle = (meta) => ({
  background: meta.tone,
  borderRadius: '50%',
  boxShadow: `0 0 10px ${meta.tone}`,
  flex: '0 0 auto',
  height: 8,
  width: 8,
});

const summaryStyle = {
  color: 'var(--text-main)',
  fontSize: 12,
  fontWeight: 600,
};

const timestampStyle = {
  color: 'var(--text-faint)',
  fontSize: 11,
};

const metricLabelStyle = {
  color: 'var(--text-faint)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
};

const metricValueStyle = {
  color: 'var(--text-main)',
  fontSize: 13,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const metricDetailStyle = {
  color: 'var(--text-muted)',
  fontSize: 11,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const barTrackStyle = {
  background: 'rgba(255, 255, 255, 0.06)',
  borderRadius: 2,
  height: 4,
  marginTop: 'auto',
  overflow: 'hidden',
};

const barFillStyle = {
  borderRadius: 2,
  height: '100%',
};

const miniBadgesStyle = {
  display: 'flex',
  gap: 5,
  marginTop: 'auto',
  minWidth: 0,
};

const trendBadgeStyle = {
  border: '1px solid',
  borderRadius: 4,
  fontSize: 10,
  fontWeight: 700,
  padding: '2px 5px',
  whiteSpace: 'nowrap',
};

export default MarketRegimeBanner;
