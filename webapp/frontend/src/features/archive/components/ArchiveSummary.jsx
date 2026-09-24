import { fixed, labelColor, pct, rMultipleColor, signColor } from '../presentation/archiveTabUtils';
import { EMPTY, fmtPctFrac } from '../../../shared/formatting/format';
import { shortLabel } from '../../../shared/presentation/wireVocabulary';

export default function ArchiveSummary({ linkedTrades = [], setup }) {
  if (!setup) return null;
  return (
    <div style={{
      background: 'var(--bg-panel)',
      borderTop: '1px solid var(--border-color)',
      display: 'grid',
      gap: '12px',
      gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
      maxHeight: '38vh',
      overflowY: 'auto',
      padding: '14px 24px',
    }}>
      <StructurePanel setup={setup} />
      <ReturnsPanel setup={setup} />
      <TradeMathPanel setup={setup} />
      <RiskPanel setup={setup} />
      <ContextPanel setup={setup} />
      <ScoresPanel setup={setup} />
      {linkedTrades.length > 0 && <LinkedTradesPanel trades={linkedTrades} />}
      {setup.notes && (
        <SummaryPanel title="Notes">
          <div style={{ color: 'var(--text-main)', fontSize: '11px', whiteSpace: 'pre-wrap' }}>
            {setup.notes}
          </div>
        </SummaryPanel>
      )}
    </div>
  );
}

function SummaryPanel({ children, title }) {
  return (
    <div style={{
      background: 'var(--bg-main)',
      border: '1px solid var(--border-color)',
      borderRadius: '6px',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
      padding: '10px 12px',
    }}>
      <div style={{
        color: 'var(--text-muted)',
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
      }}>{title}</div>
      {children}
    </div>
  );
}

function SummaryRow({ color, label, value }) {
  return (
    <div style={{ alignItems: 'baseline', display: 'flex', fontSize: '11px', justifyContent: 'space-between' }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: color || 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
        {value ?? '-'}
      </span>
    </div>
  );
}

function StructurePanel({ setup }) {
  return (
    <SummaryPanel title="Structure">
      <SummaryRow label="Base" value={setup.base_length != null ? `${setup.base_length}d` : null} />
      <SummaryRow label="Box W" value={percent1(setup.box_width)} />
      <SummaryRow label="Touches" value={setup.touches != null ? `${setup.touches} (${setup.r_touches ?? '-'}/${setup.s_touches ?? '-'})` : null} />
      <SummaryRow label="ATR Ratio" value={fixed(setup.atr_ratio, 3)} />
      <SummaryRow label="LPS Len" value={setup.lps_length != null ? `${setup.lps_length}d` : null} />
      <SummaryRow label="LPS Swing" value={swingTypeLabel(setup.lps_swing_type)} />
      <SummaryRow label="Swing Depth" value={percent1(setup.lps_swing_depth_pct)} />
      <SummaryRow label="Tightness" value={fixed(setup.tightness_ratio, 3)} />
      <SummaryRow label="Vol Contr." value={pct(setup.vol_contraction)} />
      <SummaryRow label="Trigger" value={money(setup.trigger_price)} />
    </SummaryPanel>
  );
}

function ReturnsPanel({ setup }) {
  return (
    <SummaryPanel title="Forward Returns">
      {[1, 5, 10, 20, 60].map(days => (
        <SummaryRow
          key={days}
          label={`${days}d`}
          value={pct(setup[`fwd_return_${days}d`])}
          color={signColor(setup[`fwd_return_${days}d`])}
        />
      ))}
    </SummaryPanel>
  );
}

function TradeMathPanel({ setup }) {
  return (
    <SummaryPanel title="Trade Math">
      <SummaryRow label="R-Mult 20d" value={rValue(setup.r_multiple_20d)} color={rMultipleColor(setup.r_multiple_20d)} />
      <SummaryRow label="R-Mult 60d" value={rValue(setup.r_multiple_60d)} color={rMultipleColor(setup.r_multiple_60d)} />
      <SummaryRow label="Trig Vol x" value={xValue(setup.trigger_volume_ratio)} color={ratioColor(setup.trigger_volume_ratio)} />
      <SummaryRow label="Dist 52w High" value={pct(setup.dist_52w_high_pct)} color={distanceColor(setup.dist_52w_high_pct)} />
      <SummaryRow label="RS vs Sector" value={pct(setup.rs_vs_sector_pct)} color={signColor(setup.rs_vs_sector_pct)} />
    </SummaryPanel>
  );
}

function RiskPanel({ setup }) {
  return (
    <SummaryPanel title="Risk Profile">
      <SummaryRow label="MFE 20d" value={pct(setup.mfe_20d)} color={valueColor(setup.mfe_20d, 'var(--success)')} />
      <SummaryRow label="MAE 20d" value={pct(setup.mae_20d)} color={valueColor(setup.mae_20d, 'var(--danger)')} />
      <SummaryRow label="MFE 60d" value={pct(setup.mfe_60d)} color={valueColor(setup.mfe_60d, 'var(--success)')} />
      <SummaryRow label="MAE 60d" value={pct(setup.mae_60d)} color={valueColor(setup.mae_60d, 'var(--danger)')} />
      <SummaryRow label="Triggered" value={triggeredLabel(setup)} color={setup.triggered === 1 ? 'var(--success)' : undefined} />
      <SummaryRow label="Last Supper" value={lastSupperLabel(setup)} color={lastSupperColor(setup)} />
      <SummaryRow label="LS Stretch" value={stretchValue(setup)} color={lastSupperColor(setup)} />
      <SummaryRow label="LS Pullback" value={percent1(setup.last_supper_pullback_from_extension_pct)} />
      <SummaryRow label="LS Age" value={barsValue(setup.last_supper_source_box_age)} />
      <SummaryRow label="LS Reclaim" value={fixed(setup.last_supper_reclaim_quality, 2)} />
    </SummaryPanel>
  );
}

function ContextPanel({ setup }) {
  return (
    <SummaryPanel title="Context">
      <SummaryRow label="SPY" value={setup.spy_trend} color={trendColor(setup.spy_trend)} />
      <SummaryRow label="VIX" value={fixed(setup.vix_level, 2)} />
      <SummaryRow label="Sector ETF" value={setup.sector_etf} />
      <SummaryRow label="Sector Trend" value={setup.sector_trend} color={trendColor(setup.sector_trend)} />
      <SummaryRow label="Source" value={setup.source} />
      <SummaryRow label="Label" value={setup.quality_label} color={labelColor(setup.quality_label)} />
    </SummaryPanel>
  );
}

function ScoresPanel({ setup }) {
  const rows = [
    ['Box Tight', 'score_box_tightness'],
    ['Touch Dens.', 'score_touch_density'],
    [shortLabel('score_traversal_quality'), 'score_traversal_quality'],
    ['ATR Squeeze', 'score_atr_squeeze'],
    ['LPS Tight', 'score_lps_tightness'],
    ['Vol Contr.', 'score_vol_contraction'],
    ['Base Age', 'score_base_age'],
    ['Uptrend Bonus', 'score_uptrend_bonus'],
  ];
  return (
    <SummaryPanel title="Sub-Scores">
      {rows.map(([label, key]) => (
        <SummaryRow key={key} label={label} value={fixed(setup[key], 0)} color={key === 'score_uptrend_bonus' && setup[key] > 0 ? 'var(--success)' : undefined} />
      ))}
    </SummaryPanel>
  );
}

function LinkedTradesPanel({ trades }) {
  return (
    <SummaryPanel title={`Linked Trades (${trades.length})`}>
      {trades.map(trade => (
        <div key={trade.id} style={{ borderTop: '1px solid var(--border-color)', fontSize: '10px', marginTop: '2px', paddingTop: '4px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)' }}>{trade.opening_date}</span>
            <span style={{ color: trade.direction === 'L' ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>{trade.direction}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>{trade.entry_price != null ? `$${fixed(trade.entry_price)}` : '-'} to {trade.exit_price != null ? `$${fixed(trade.exit_price)}` : '-'}</span>
            <span style={{ color: signColor(trade.pnl ?? 0), fontWeight: 600 }}>{trade.pnl != null ? `$${fixed(trade.pnl)}` : '-'}</span>
          </div>
        </div>
      ))}
    </SummaryPanel>
  );
}

// signColor and rMultipleColor imported from archiveTabUtils.
const trendColor = (trend) => (trend === 'BULLISH' ? 'var(--success)' : trend === 'BEARISH' ? 'var(--danger)' : undefined);
const hasNumber = (value) => value != null && Number.isFinite(Number(value));
const valueColor = (value, color) => (hasNumber(value) ? color : undefined);
const distanceColor = (value) => {
  if (!hasNumber(value)) return undefined;
  return Number(value) > -0.10 ? 'var(--success)' : Number(value) < -0.25 ? 'var(--danger)' : undefined;
};
const ratioColor = (value) => {
  if (!hasNumber(value)) return undefined;
  return Number(value) > 1.5 ? 'var(--success)' : Number(value) < 1 ? 'var(--danger)' : undefined;
};
const triggeredLabel = (setup) => (setup.triggered === 1 ? `Yes ${setup.trigger_date || ''}` : setup.triggered === 0 ? 'No' : EMPTY);
// Guard on the VALUE, never on the formatter's empty glyph.
const money = (value) => (hasNumber(value) ? `$${fixed(value, 2)}` : EMPTY);
const percent1 = (value) => fmtPctFrac(value, 1);
const rValue = (value) => (hasNumber(value) ? `${fixed(value, 2)}R` : EMPTY);
const xValue = (value) => (hasNumber(value) ? `${fixed(value, 2)}x` : EMPTY);
const swingTypeLabel = (value) => (
  value ? String(value).replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase()) : null
);
const barsValue = (value) => (hasNumber(value) ? `${Number(value)} bars` : null);
const isLastSupper = (setup) => (
  (hasNumber(setup.lps_stretch_box) && Number(setup.lps_stretch_box) > 0)
  || (hasNumber(setup.lps_stretch_atr) && Number(setup.lps_stretch_atr) > 0)
);
const lastSupperLabel = (setup) => {
  if (!hasNumber(setup.lps_stretch_box) && !hasNumber(setup.lps_stretch_atr)) return null;
  return isLastSupper(setup) ? 'Caution' : 'Neutral';
};
const lastSupperColor = (setup) => (isLastSupper(setup) ? 'var(--danger)' : undefined);
const stretchValue = (setup) => {
  if (!hasNumber(setup.lps_stretch_box) && !hasNumber(setup.lps_stretch_atr)) return null;
  return `${fixed(setup.lps_stretch_box, 2)} box / ${fixed(setup.lps_stretch_atr, 2)} ATR`;
};
