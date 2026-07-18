import { ScoreBreakdownPills } from './ScoreBreakdown';
import { TagRow } from './SetupTags';
import { buildPhaseRegions } from './chartPhaseOverlay';
import { explainTip } from './tooltipText';
import { displayLabel, tagFlagsFromWire } from './wireVocabulary';
import { tierColor, signColor } from '../theme';
import { fx, fmtSignedPctFrac, fmtDateShort } from '../utils/format';
import { dailyChangeFrac, htfStateLabel } from '../utils/screenerCardData';

const scoreLabel = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `${Math.round(Number(value))}`
);

const money = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `$${Number(value).toFixed(2)}`
);

const pct = (value, digits = 1) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `${Number(value).toFixed(digits)}%`
);

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const bars = (value) => {
  const number = finiteNumber(value);
  if (number == null) return '-';
  const rounded = Math.round(number);
  return `${rounded} bar${rounded === 1 ? '' : 's'}`;
};

const latestCandle = (data) => data?.candles?.[data.candles.length - 1] || null;

const latestLpsRegion = (regions) => (
  regions
    .filter((region) => region.key === 'lps')
    .sort((a, b) => b.endIndex - a.endIndex || b.startIndex - a.startIndex)[0] || null
);

const structurePanelRegions = (regions) => {
  const latestLps = latestLpsRegion(regions);
  const nonLps = regions.filter((region) => region.key !== 'lps');
  return latestLps ? [...nonLps, { ...latestLps, activeTarget: 'lps' }] : nonLps;
};

const distanceToTriggerPct = (data) => {
  const currentPrice = finiteNumber(data?.price ?? latestCandle(data)?.close);
  const trigger = finiteNumber(data?.trigger);
  if (currentPrice == null || trigger == null || currentPrice <= 0) return null;
  return ((trigger - currentPrice) / currentPrice) * 100;
};

const boxWidthPct = (data) => {
  const support = finiteNumber(data?.S);
  const resistance = finiteNumber(data?.R);
  if (support == null || resistance == null || support <= 0) return null;
  return ((resistance - support) / support) * 100;
};

const triggerTone = (value) => {
  if (value == null) return 'var(--text-main)';
  if (value < -0.25) return 'var(--warning)';
  if (value <= 2) return 'var(--success)';
  return 'var(--accent-blue)';
};

const triggerRead = (value) => {
  if (value == null) return 'No trigger read yet';
  if (value < -0.25) return 'Already above trigger';
  if (value <= 0.75) return 'Right under trigger';
  if (value <= 2) return 'Close to trigger';
  return 'Needs more room';
};

const sectorLabel = (data) => {
  if (data?.sector_name && data?.sector_etf) return `${data.sector_name} (${data.sector_etf})`;
  if (data?.sector_name) return data.sector_name;
  if (data?.sector_etf) return data.sector_etf;
  return '-';
};

const phaseRegionTip = (region) => {
  if (region.key === 'd' && region.evidenceSummary) {
    return explainTip({
      what: `${region.name} starts at the selected right-side evidence: ${region.detail.toLowerCase()}.`,
      why: `The evidence vocabulary is ${region.evidenceSummary}; the earliest credible signal after the Phase-C floor anchors the Phase-D band, with LPS as the fallback.`,
      use: 'Hover or focus it to highlight Phase D, then confirm that the selected evidence matches the tightening support behavior by eye.',
    });
  }
  return explainTip({
    what: `${region.name} marks ${region.detail.toLowerCase()} in the detected base.`,
    why: 'It shows which part of the Wyckoff-style structure the engine is reading on the chart.',
    use: 'Hover or focus it to highlight the matching region, then verify the support, resistance, and recovery behavior by eye.',
  });
};

// Next-earnings cell for the detail grid. Shows the actual DATE (never the
// cryptic "ER"), tinted by proximity — caution amber inside ~10 days, danger
// inside 3 — with a plain-language tooltip. '-' when no upcoming date is known.
const earningsDisplay = (earnings) => {
  const date = earnings?.date;
  if (!date) return { value: '-', tone: undefined, title: 'No upcoming earnings date available' };
  const days = earnings?.days_until;
  let tone;
  if (days != null && days >= 0) {
    if (days <= 3) tone = 'var(--danger)';
    else if (days <= 10) tone = 'var(--warning)';
  }
  const title = days == null
    ? `Next earnings: ${date}`
    : days >= 0
      ? `Next earnings in ${days} day${days === 1 ? '' : 's'} (${date})`
      : `Last earnings ${-days} day${days === -1 ? '' : 's'} ago (${date})`;
  return { value: fmtDateShort(date), tone, title };
};

// The Finviz-style dense read: one tight grid of the engine's technical facts.
// Finviz fills this with fundamentals (P/E, EPS); Chrollo has none, so every cell
// is a measured structural / trend fact from the scan payload — no invented data.
function TechnicalReadGrid({ data, earnings }) {
  const price = finiteNumber(data?.price ?? latestCandle(data)?.close);
  const distance = distanceToTriggerPct(data);
  const changePct = dailyChangeFrac(data?.candles);
  const weekly = htfStateLabel({
    stage2: data.htf_w_stage2, trendState: data.htf_w_trend_state,
    inConsol: data.htf_w_in_consol, phase: data.htf_w_phase, reaccum: data.htf_w_reaccum,
  });
  const monthly = htfStateLabel({
    stage2: data.htf_m_stage2, trendState: data.htf_m_trend_state,
    inConsol: data.htf_m_in_consol, phase: data.htf_m_phase, reaccum: data.htf_m_reaccum,
  });
  const contractions = finiteNumber(data.contraction_count);
  const earn = earningsDisplay(earnings);

  const cells = [
    { k: 'Price', v: money(price) },
    { k: 'Change', v: changePct == null ? '-' : fmtSignedPctFrac(changePct, 1), tone: signColor(changePct) },
    { k: 'Trigger', v: money(data.trigger), tone: '#e3b341' },
    { k: 'To trigger', v: pct(distance), tone: triggerTone(distance) },
    { k: 'Resistance', v: money(data.R) },
    { k: 'Support', v: money(data.S) },
    { k: 'Box width', v: pct(boxWidthPct(data)) },
    { k: 'ADR', v: pct(data.adr_pct) },
    { k: 'Base length', v: bars(data.base_len) },
    { k: 'LPS pullback', v: bars(data.lps_len) },
    { k: 'Contractions', v: contractions == null ? '-' : String(contractions) },
    { k: displayLabel('traversal_density'), v: fx(data.traversal_density, 2, '-') },
    { k: 'Sector', v: sectorLabel(data), tone: 'var(--accent-blue)' },
    { k: 'Earnings', v: earn.value, tone: earn.tone, title: earn.title },
    { k: 'Weekly', v: weekly.label, tone: weekly.tone },
    { k: 'Monthly', v: monthly.label, tone: monthly.tone },
    { k: 'Score', v: scoreLabel(data.score), tone: tierColor(data.tier) },
  ];

  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>Technical read</span>
        <small>{data.setup || ''}</small>
      </div>
      <div className="lens-grid">
        {cells.map((cell) => (
          <div className="lens-cell" key={cell.k} title={cell.title}>
            <span className="lens-k">{cell.k}</span>
            <span className="lens-v" style={{ color: cell.tone || 'var(--text-main)' }}>{cell.v}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function PhaseBinPanel({ activeRegion, data, onRegionChange }) {
  const regions = structurePanelRegions(buildPhaseRegions(data));
  if (regions.length === 0) return null;

  return (
    <section className="stock-lens-section stock-lens-structure">
      <div className="stock-lens-section-header">
        <span>Technical Structure Analysis</span>
      </div>
      <div className="stock-lens-phase-list">
        {regions.map(region => {
          const activeTarget = region.activeTarget || region.id;
          const isActive = activeRegion === activeTarget || activeRegion === region.id;
          const tokenStyle = region.color ? {
            borderColor: `${region.color}aa`,
            color: region.color,
          } : undefined;
          return (
            <button
              key={region.id}
              type="button"
              className={`phase-bin-control phase-bin-${region.key}${isActive ? ' is-active' : ''}`}
              onBlur={() => onRegionChange(null)}
              onFocus={() => onRegionChange(activeTarget)}
              onMouseEnter={() => onRegionChange(activeTarget)}
              onMouseLeave={() => onRegionChange(null)}
              aria-label={`${region.name} - ${region.detail}`}
              title={phaseRegionTip(region)}
            >
              <span className="phase-bin-token" style={tokenStyle}>{region.label}</span>
              <span className="phase-bin-copy">
                <span className="phase-bin-name">{region.name}</span>
                <span className="phase-bin-detail">{region.detail}</span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function TagsPanel({ data }) {
  const read = triggerRead(distanceToTriggerPct(data));
  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>Why It Stands Out</span>
        <small>{read}</small>
      </div>
      <TagRow
        subScores={data.sub_scores}
        flags={tagFlagsFromWire(data)}
        maxTags={null}
        style={{ padding: 0 }}
      />
      <ScoreBreakdownPills subScores={data.sub_scores} style={{ marginTop: 10 }} />
    </section>
  );
}

export default function ScreenerStockLens({ activeRegion, data, earnings, interval = 'D', onRegionChange }) {
  const showDailyStructure = interval === 'D';
  return (
    <div className="stock-lens">
      <TechnicalReadGrid data={data} earnings={earnings} />
      <div className="stock-lens-bottom">
        {showDailyStructure ? (
          <PhaseBinPanel activeRegion={activeRegion} data={data} onRegionChange={onRegionChange} />
        ) : null}
        <TagsPanel data={data} />
      </div>
    </div>
  );
}
