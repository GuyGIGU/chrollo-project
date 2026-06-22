import { ScoreBreakdownPills } from './ScoreBreakdown';
import { TagRow } from './SetupTags';
import { buildPhaseRegions } from './chartPhaseOverlay';
import { explainTip } from './tooltipText';

const scoreLabel = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `${Math.round(Number(value))}`
);

const money = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `$${Number(value).toFixed(2)}`
);

const pct = (value, digits = 1) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : `${Number(value).toFixed(digits)}%`
);

const tierColor = (tier) => {
  switch (tier) {
    case 'S': return '#ff9f43';
    case 'A': return '#bb86fc';
    case 'B': return '#58a6ff';
    case 'C': return '#3fb950';
    default: return '#8b949e';
  }
};

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

function SnapshotMetric({ label, title, tone, value }) {
  return (
    <div className="stock-lens-metric" title={title}>
      <span>{label}</span>
      <strong style={{ color: tone || 'var(--text-main)' }}>{value}</strong>
    </div>
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

function DecisionRead({ data }) {
  const distance = distanceToTriggerPct(data);
  const currentPrice = finiteNumber(data?.price ?? latestCandle(data)?.close);

  return (
    <section className="stock-lens-section stock-lens-read">
      <div className="stock-lens-identity">
        <div>
          <span className="stock-lens-kicker">Selected setup</span>
          <strong>{data.setup || '-'}</strong>
        </div>
        <span
          className="stock-lens-tier"
          style={{ borderColor: `${tierColor(data.tier)}66`, color: tierColor(data.tier) }}
          title={explainTip({
            what: 'The engine rank for this setup after scoring structure and confirmation context.',
            why: 'It helps us triage the scan quickly without treating every setup as equal.',
            use: 'Review higher tiers first, then still confirm the chart, trigger, and risk manually.',
          })}
        >
          {data.tier || '-'} Tier
        </span>
      </div>

      <div className="stock-lens-metrics-grid">
        <SnapshotMetric
          label="Price"
          title={explainTip({
            what: 'The latest closing price included in the scan result.',
            why: 'It anchors the setup read to the data the screener actually scored.',
            use: 'Compare it with the trigger and box levels before deciding whether the setup is close enough to watch.',
          })}
          value={money(currentPrice)}
        />
        <SnapshotMetric
          label="Trigger"
          title={explainTip({
            what: 'The breakout level calculated from the detected resistance area.',
            why: 'It gives us the price area where demand must prove it can clear the base.',
            use: 'Treat it as a review level, not an automatic order; look for clean price action and volume confirmation.',
          })}
          tone="#e3b341"
          value={money(data.trigger)}
        />
        <SnapshotMetric
          label="To Trigger"
          title={explainTip({
            what: 'The percent distance from the latest close to the trigger.',
            why: 'It tells us whether the setup is actionable, extended, or still needs time.',
            use: 'Lower is closer; a negative value means price is already above the trigger and needs extra caution.',
          })}
          tone={triggerTone(distance)}
          value={pct(distance)}
        />
        <SnapshotMetric
          label="Read"
          title={explainTip({
            what: 'A plain-language summary of the trigger distance.',
            why: 'It turns the distance number into a faster triage read.',
            use: 'Use it to sort attention, then make the actual decision from the chart and risk plan.',
          })}
          tone={triggerTone(distance)}
          value={triggerRead(distance)}
        />
      </div>
    </section>
  );
}

function ContextPanel({ data }) {
  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>Stock Context</span>
      </div>
      <div className="stock-lens-context-grid">
        <SnapshotMetric
          label="Sector"
          title={explainTip({
            what: 'The stock sector or sector ETF available from the cached map.',
            why: 'Sector context helps us see whether the idea is part of a stronger theme or standing alone.',
            use: 'Prefer setups that agree with strong sector behavior; treat missing sector detail as neutral.',
          })}
          value={sectorLabel(data)}
        />
        <SnapshotMetric
          label="Score"
          title={explainTip({
            what: 'The total setup score from the screener.',
            why: 'It combines the measured structure and confirmation signals into one triage number.',
            use: 'Use it to prioritize candidates, then inspect the chart because the score is not a trade signal by itself.',
          })}
          tone={tierColor(data.tier)}
          value={scoreLabel(data.score)}
        />
        <SnapshotMetric
          label="ADR"
          title={explainTip({
            what: 'Average Daily Range percent: the stock average daily movement relative to price.',
            why: 'Higher ADR means more movement potential, but also wider normal volatility.',
            use: 'Use it like the Qullamaggie-style volatility filter: size stops and position risk around the stock actual movement.',
          })}
          value={pct(data.adr_pct)}
        />
        <SnapshotMetric
          label="Base"
          title={explainTip({
            what: 'The number of bars inside the detected consolidation base.',
            why: 'Base length tells us how much time the stock has spent building the current structure.',
            use: 'Longer bases can be meaningful, but act only when the final structure is tight and near a clear trigger.',
          })}
          value={bars(data.base_len)}
        />
        <SnapshotMetric
          label="Box Width"
          title={explainTip({
            what: 'The distance from support to resistance, shown as a percent of support.',
            why: 'It measures how tight or wide the actionable box is.',
            use: 'Prefer tighter boxes when the rails are clean, because risk can usually be defined more precisely.',
          })}
          value={pct(boxWidthPct(data))}
        />
        <SnapshotMetric
          label="LPS"
          title={explainTip({
            what: 'The length of the latest last-point-of-support pullback.',
            why: 'A shorter, controlled LPS can show that sellers are not pushing price far from the trigger.',
            use: 'Use it to judge whether the final pause is tight; a failed support test weakens the setup.',
          })}
          value={bars(data.lps_len)}
        />
      </div>
    </section>
  );
}

function TagsPanel({ data }) {
  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>Why It Stands Out</span>
      </div>
      <TagRow
        subScores={data.sub_scores}
        flags={{
          phaseDInner: data.phase_d_inner,
          rTouchVolZ: data.r_touch_vol_z,
          sTouchVolZ: data.s_touch_vol_z,
          contractionVolTrend: data.contraction_vol_trend,
          cogEnd: data.bin_b_cog_end,
          cogCrossings: data.bin_b_cog_crossings,
          traversalDensity: data.traversal_density,
          cogRng: data.bin_b_cog_rng,
          cogCorr: data.bin_b_cog_corr,
          binCPresent: data.bin_c_present,
          binCType: data.bin_c_type,
          binCUndercutAtr: data.bin_c_undercut_atr,
          binCRecoveryBars: data.bin_c_recovery_bars,
          binCSpringVolZ: data.bin_c_spring_vol_z,
          htfWeeklyReaccum: data.htf_w_reaccum,
          htfWeeklyPhase: data.htf_w_phase,
          htfDailyNested: data.htf_w_daily_nested,
          htfMonthlyReaccum: data.htf_m_reaccum,
        }}
        maxTags={null}
        style={{ padding: 0 }}
      />
      <ScoreBreakdownPills subScores={data.sub_scores} style={{ marginTop: 10 }} />
    </section>
  );
}

export default function ScreenerStockLens({ activeRegion, data, interval = 'D', onRegionChange }) {
  const showDailyStructure = interval === 'D';
  return (
    <div className="stock-lens">
      <div className="stock-lens-top">
        <DecisionRead data={data} />
        <ContextPanel data={data} />
      </div>
      <div className="stock-lens-bottom">
        {showDailyStructure ? (
          <PhaseBinPanel activeRegion={activeRegion} data={data} onRegionChange={onRegionChange} />
        ) : null}
        <TagsPanel data={data} />
      </div>
    </div>
  );
}
