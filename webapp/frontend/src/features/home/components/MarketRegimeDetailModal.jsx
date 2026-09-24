import { useEffect } from 'react';
import {
  STATE_META,
  distributionTone,
  fxDays,
  fxPrice,
  fxSignedPct,
  postureText,
  rangeToPct,
  trendPhrase,
  visualRange,
} from '../presentation/marketRegimeFormat';

// Plain-English hint per metric — the "explanations" that turn a number into a
// read. Kept short so each card stays scannable.
const METRIC_HINTS = {
  close: 'Most recent closing price for the index.',
  sma50: 'The 50-day average — the short-term trend. Price above it is near-term strength; below is weakness.',
  sma200: 'The 200-day average — the long-term trend. Above it is healthy market structure; below warns of a deeper downtrend.',
  slope: 'Which way the 50-day average is pointing. Rising means the trend is still improving; falling means it is rolling over.',
  distribution: 'Higher-volume down days over the last few weeks. Five or more hints at institutional selling under the surface.',
  lastbar: 'The date of the latest price bar feeding this read.',
};

function MarketRegimeDetailModal({ symbol, trend, meta, reasons, onClose }) {
  const above50 = trend?.above_sma_50;
  const above200 = trend?.above_sma_200;
  const slope = Number(trend?.sma_50_slope_pct);
  const hasSlope = trend?.sma_50_slope_pct != null && Number.isFinite(slope);
  const close = Number(trend?.close);
  const sma50 = Number(trend?.sma_50);
  const sma200 = Number(trend?.sma_200);
  const range = visualRange([close, sma50, sma200]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div style={overlayStyle} onClick={onClose}>
      <section aria-modal="true" role="dialog" style={modalStyle} onClick={event => event.stopPropagation()}>
        <header style={modalHeaderStyle}>
          <div style={{ minWidth: 0 }}>
            <span style={eyebrowStyle}>{symbol} Market Context</span>
            <div style={modalTitleStyle}>
              <span style={stateDotStyle(meta)} />
              <strong style={{ color: meta.tone }}>{meta.label}</strong>
            </div>
            <span style={summaryStyle}>{meta.summary}</span>
          </div>
          <button type="button" onClick={onClose} style={closeButtonStyle} title="Close" aria-label="Close">✕</button>
        </header>

        <div style={modalBodyStyle}>
          {/* What this means — the read, before the raw numbers */}
          <div style={cardStyle}>
            <span style={sectionTitleStyle}>What this means</span>
            <div style={guidanceListStyle}>
              <GuidanceRow label="What it is" text={meta.what} />
              <GuidanceRow label="Why it matters" text={meta.why} />
              <GuidanceRow label="How to use it" text={meta.use} accent={meta.tone} />
            </div>
          </div>

          {/* Price vs its own averages */}
          <div style={cardStyle}>
            <span style={sectionTitleStyle}>Price vs its averages</span>
            <p style={captionStyle}>
              Where {symbol}&apos;s close sits between its long- and short-term averages. Left (red) is weak,
              right (green) is strong — {symbol} is currently <strong style={{ color: meta.tone }}>{trendPhrase(above50, above200).toLowerCase()}</strong>.
            </p>
            <div style={priceScaleStyle}>
              <ScaleMarker label={`${symbol} Close`} value={close} range={range} tone="var(--text-main)" />
              <ScaleMarker label="50D Avg" value={sma50} range={range} tone="var(--accent-blue)" />
              <ScaleMarker label="200D Avg" value={sma200} range={range} tone="var(--accent-purple)" />
            </div>
          </div>

          {/* The numbers, each with a one-line read */}
          <div style={modalMetricGridStyle}>
            <DetailMetric label="Close" value={fxPrice(trend?.close)} hint={METRIC_HINTS.close} />
            <DetailMetric
              label="50D Average" value={fxPrice(trend?.sma_50)}
              tone={above50 === true ? 'var(--success)' : above50 === false ? 'var(--danger)' : null}
              detail={`price ${postureText(above50)}`} hint={METRIC_HINTS.sma50}
            />
            <DetailMetric
              label="200D Average" value={fxPrice(trend?.sma_200)}
              tone={above200 === true ? 'var(--success)' : above200 === false ? 'var(--danger)' : null}
              detail={`price ${postureText(above200)}`} hint={METRIC_HINTS.sma200}
            />
            <DetailMetric
              label="50D Slope" value={fxSignedPct(trend?.sma_50_slope_pct)}
              tone={hasSlope ? (slope > 0 ? 'var(--success)' : 'var(--warning)') : null}
              detail={hasSlope ? (trend?.sma_50_rising ? 'rising' : 'not rising') : null} hint={METRIC_HINTS.slope}
            />
            <DetailMetric
              label="Distribution" value={fxDays(trend?.distribution_days)}
              tone={distributionTone(trend?.distribution_days)} hint={METRIC_HINTS.distribution}
            />
            <DetailMetric label="Last Bar" value={trend?.last_bar_date || 'n/a'} hint={METRIC_HINTS.lastbar} />
          </div>

          {/* The signals that produced the state */}
          <div style={cardStyle}>
            <span style={sectionTitleStyle}>Signals behind this state</span>
            <p style={captionStyle}>The specific trend, breadth, and distribution reads the regime label is built from.</p>
            <div style={reasonListStyle}>
              {reasons.map(reason => (
                <span key={reason} style={reasonPillStyle}>{reason}</span>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function GuidanceRow({ label, text, accent }) {
  return (
    <div style={guidanceRowStyle}>
      <span style={{ ...guidanceLabelStyle, color: accent || 'var(--text-faint)' }}>{label}</span>
      <span style={guidanceTextStyle}>{text}</span>
    </div>
  );
}

function DetailMetric({ label, value, detail, tone, hint }) {
  return (
    <div style={detailMetricStyle}>
      <span style={metricLabelStyle}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ color: tone || 'var(--text-main)', fontSize: 16 }}>{value}</strong>
        {detail && <span style={metricDetailStyle}>{detail}</span>}
      </div>
      {hint && <span style={metricHintStyle}>{hint}</span>}
    </div>
  );
}

function ScaleMarker({ label, value, range, tone }) {
  if (!Number.isFinite(value)) return null;
  const left = `${rangeToPct(value, range)}%`;
  return (
    <div style={{ ...scaleMarkerStyle, left }}>
      <span style={{ ...scaleLabelStyle, color: tone }}>{label}</span>
      <strong style={scaleValueStyle}>{fxPrice(value)}</strong>
      <span style={{ ...scaleDotStyle, background: tone }} />
    </div>
  );
}

const overlayStyle = {
  alignItems: 'center', background: 'rgba(8, 10, 15, 0.76)', bottom: 0, display: 'flex',
  justifyContent: 'center', left: 0, padding: 24, position: 'fixed', right: 0, top: 0, zIndex: 5200,
};

const modalStyle = {
  background: 'var(--bg-main)', border: '1px solid var(--border-color)', borderRadius: 8,
  boxShadow: '0 22px 55px rgba(0,0,0,0.45)', display: 'flex', flexDirection: 'column',
  maxWidth: 760, maxHeight: '92vh', overflow: 'hidden', width: 'min(760px, 96vw)',
};

const modalHeaderStyle = {
  alignItems: 'flex-start', background: 'var(--bg-panel)', borderBottom: '1px solid var(--border-color)',
  display: 'flex', justifyContent: 'space-between', gap: 12, padding: '14px 16px', flexShrink: 0,
};

const modalTitleStyle = { alignItems: 'center', display: 'flex', fontSize: 20, gap: 8, marginTop: 5 };
const summaryStyle = { color: 'var(--text-muted)', display: 'block', fontSize: 12, marginTop: 4 };

const closeButtonStyle = {
  background: 'transparent', border: '1px solid var(--border-color)', borderRadius: 6, color: 'var(--text-muted)',
  cursor: 'pointer', fontFamily: 'inherit', fontSize: 14, height: 32, width: 34, flexShrink: 0,
};

const modalBodyStyle = { display: 'flex', flexDirection: 'column', gap: 12, padding: 16, overflowY: 'auto' };

const cardStyle = {
  background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: 6, padding: 13,
};

const sectionTitleStyle = {
  color: 'var(--text-faint)', display: 'block', fontSize: 10, fontWeight: 700,
  letterSpacing: '0.08em', textTransform: 'uppercase',
};

const guidanceListStyle = { display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 };
const guidanceRowStyle = { display: 'grid', gridTemplateColumns: '116px 1fr', gap: 12, alignItems: 'start' };
const guidanceLabelStyle = { fontSize: 11, fontWeight: 700, letterSpacing: '0.02em', paddingTop: 1 };
const guidanceTextStyle = { color: 'var(--text-main)', fontSize: 13, lineHeight: 1.5 };

const captionStyle = { color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.45, margin: '8px 0 0' };

const priceScaleStyle = {
  background: 'linear-gradient(90deg, rgba(var(--danger-rgb),0.20), rgba(var(--warning-rgb),0.16), rgba(var(--success-rgb),0.18))',
  border: '1px solid rgba(255,255,255,0.06)', borderRadius: 999, height: 8, marginTop: 46, marginBottom: 6, position: 'relative',
};

const scaleMarkerStyle = {
  alignItems: 'center', display: 'flex', flexDirection: 'column', gap: 2, position: 'absolute',
  top: -42, transform: 'translateX(-50%)', whiteSpace: 'nowrap',
};
const scaleDotStyle = { border: '2px solid var(--bg-main)', borderRadius: '50%', height: 12, marginTop: 4, width: 12 };
const scaleLabelStyle = { fontSize: 10, fontWeight: 800, textTransform: 'uppercase' };
const scaleValueStyle = { color: 'var(--text-main)', fontSize: 12 };

const modalMetricGridStyle = { display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' };

const detailMetricStyle = {
  background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.045)', borderRadius: 6,
  display: 'flex', flexDirection: 'column', gap: 4, padding: '10px 11px',
};

const reasonListStyle = { display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 };
const reasonPillStyle = {
  border: '1px solid var(--border-color)', borderRadius: 999, color: 'var(--text-main)',
  fontSize: 11, fontWeight: 700, padding: '4px 8px',
};

const metricLabelStyle = {
  color: 'var(--text-faint)', fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
};
const metricDetailStyle = { color: 'var(--text-muted)', fontSize: 11 };
const metricHintStyle = { color: 'var(--text-muted)', fontSize: 11, lineHeight: 1.4, marginTop: 2 };

const eyebrowStyle = {
  color: 'var(--text-muted)', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
};
const stateDotStyle = (meta) => ({
  background: meta.tone, borderRadius: '50%', boxShadow: `0 0 10px ${meta.tone}`, flex: '0 0 auto', height: 8, width: 8,
});

export default MarketRegimeDetailModal;
