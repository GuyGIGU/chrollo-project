import { useEffect } from 'react';
import {
  STATE_META,
  distributionTone,
  fxDays,
  fxPrice,
  fxSignedPct,
  postureText,
  rangeToPct,
  visualRange,
} from './marketRegimeFormat';

function MarketRegimeDetailModal({ symbol, trend, regime, meta, reasons, onClose }) {
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
      <section
        aria-modal="true"
        role="dialog"
        style={modalStyle}
        onClick={event => event.stopPropagation()}
      >
        <header style={modalHeaderStyle}>
          <div style={{ minWidth: 0 }}>
            <span style={eyebrowStyle}>{symbol} Market Context</span>
            <div style={modalTitleStyle}>
              <span style={stateDotStyle(meta)} />
              <strong style={{ color: meta.tone }}>{meta.label}</strong>
            </div>
          </div>
          <button type="button" onClick={onClose} style={closeButtonStyle} title="Close">x</button>
        </header>

        <div style={modalBodyStyle}>
          <div style={visualPanelStyle}>
            <div style={priceScaleStyle}>
              <ScaleMarker label={`${symbol} Close`} value={close} range={range} tone="var(--text-main)" />
              <ScaleMarker label="50D Avg" value={sma50} range={range} tone="var(--accent-blue)" />
              <ScaleMarker label="200D Avg" value={sma200} range={range} tone="var(--accent-purple)" />
            </div>
          </div>

          <div style={modalMetricGridStyle}>
            <DetailMetric label="Close" value={fxPrice(trend?.close)} />
            <DetailMetric
              label="50D Average"
              value={fxPrice(trend?.sma_50)}
              tone={above50 === true ? 'var(--success)' : above50 === false ? 'var(--danger)' : null}
              detail={postureText(above50)}
            />
            <DetailMetric
              label="200D Average"
              value={fxPrice(trend?.sma_200)}
              tone={above200 === true ? 'var(--success)' : above200 === false ? 'var(--danger)' : null}
              detail={postureText(above200)}
            />
            <DetailMetric
              label="50D Slope"
              value={fxSignedPct(trend?.sma_50_slope_pct)}
              tone={hasSlope ? (slope > 0 ? 'var(--success)' : 'var(--warning)') : null}
              detail={hasSlope ? (trend?.sma_50_rising ? 'rising' : 'not rising') : null}
            />
            <DetailMetric
              label="Distribution"
              value={fxDays(trend?.distribution_days)}
              tone={distributionTone(trend?.distribution_days)}
            />
            <DetailMetric label="Last Bar" value={trend?.last_bar_date || 'n/a'} />
          </div>

          <div style={reasonPanelStyle}>
            <span style={metricLabelStyle}>Status Drivers</span>
            <div style={reasonListStyle}>
              {reasons.map(reason => (
                <span key={reason} style={reasonPillStyle}>{reason}</span>
              ))}
            </div>
            <p style={explainStyle}>{STATE_META[regime.state]?.detail || STATE_META.UNKNOWN.detail}</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function DetailMetric({ label, value, detail, tone }) {
  return (
    <div style={detailMetricStyle}>
      <span style={metricLabelStyle}>{label}</span>
      <strong style={{ color: tone || 'var(--text-main)', fontSize: 15 }}>{value}</strong>
      {detail && <span style={metricDetailStyle}>{detail}</span>}
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
  alignItems: 'center',
  background: 'rgba(8, 10, 15, 0.76)',
  bottom: 0,
  display: 'flex',
  justifyContent: 'center',
  left: 0,
  padding: 24,
  position: 'fixed',
  right: 0,
  top: 0,
  zIndex: 5200,
};

const modalStyle = {
  background: 'var(--bg-main)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  boxShadow: '0 22px 55px rgba(0,0,0,0.45)',
  display: 'flex',
  flexDirection: 'column',
  maxWidth: 820,
  overflow: 'hidden',
  width: 'min(820px, 96vw)',
};

const modalHeaderStyle = {
  alignItems: 'center',
  background: 'var(--bg-panel)',
  borderBottom: '1px solid var(--border-color)',
  display: 'flex',
  justifyContent: 'space-between',
  padding: '14px 16px',
};

const modalTitleStyle = {
  alignItems: 'center',
  display: 'flex',
  fontSize: 20,
  gap: 8,
  marginTop: 5,
};

const closeButtonStyle = {
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 18,
  height: 32,
  width: 34,
};

const modalBodyStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
  padding: 16,
};

const visualPanelStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  height: 120,
  padding: '20px 18px',
};

const priceScaleStyle = {
  background: 'linear-gradient(90deg, rgba(242,103,112,0.20), rgba(240,190,60,0.16), rgba(61,211,122,0.18))',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: 999,
  height: 8,
  marginTop: 42,
  position: 'relative',
};

const scaleMarkerStyle = {
  alignItems: 'center',
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  position: 'absolute',
  top: -42,
  transform: 'translateX(-50%)',
  whiteSpace: 'nowrap',
};

const scaleDotStyle = {
  border: '2px solid var(--bg-main)',
  borderRadius: '50%',
  height: 12,
  marginTop: 4,
  width: 12,
};

const scaleLabelStyle = {
  fontSize: 10,
  fontWeight: 800,
  textTransform: 'uppercase',
};

const scaleValueStyle = {
  color: 'var(--text-main)',
  fontSize: 12,
};

const modalMetricGridStyle = {
  display: 'grid',
  gap: 10,
  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
};

const detailMetricStyle = {
  background: 'rgba(255,255,255,0.025)',
  border: '1px solid rgba(255,255,255,0.045)',
  borderRadius: 6,
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
  padding: '10px 11px',
};

const reasonPanelStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  padding: 12,
};

const reasonListStyle = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 6,
  marginTop: 9,
};

const reasonPillStyle = {
  border: '1px solid var(--border-color)',
  borderRadius: 999,
  color: 'var(--text-main)',
  fontSize: 11,
  fontWeight: 700,
  padding: '4px 8px',
};

const explainStyle = {
  color: 'var(--text-muted)',
  fontSize: 12,
  lineHeight: 1.45,
  marginTop: 10,
};

const metricLabelStyle = {
  color: 'var(--text-faint)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
};

const metricDetailStyle = {
  color: 'var(--text-muted)',
  fontSize: 11,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const eyebrowStyle = {
  color: 'var(--text-muted)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
};

const stateDotStyle = (meta) => ({
  background: meta.tone,
  borderRadius: '50%',
  boxShadow: `0 0 10px ${meta.tone}`,
  flex: '0 0 auto',
  height: 8,
  width: 8,
});

export default MarketRegimeDetailModal;
