import { ScoreBreakdownPills } from './ScoreBreakdown';
import { TagRow } from './SetupTags';
import { buildPhaseRegions } from './chartPhaseOverlay';

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
              title={`${region.name}: ${region.detail}`}
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
          title="Tier is the engine's rank for this setup."
        >
          {data.tier || '-'} Tier
        </span>
      </div>

      <div className="stock-lens-metrics-grid">
        <SnapshotMetric
          label="Price"
          title="Latest close from the scan payload."
          value={money(currentPrice)}
        />
        <SnapshotMetric
          label="Trigger"
          title="Breakout trigger price from the structure engine."
          tone="#e3b341"
          value={money(data.trigger)}
        />
        <SnapshotMetric
          label="To Trigger"
          title="How far the latest close is from the trigger. Lower is closer; negative means price is already above it."
          tone={triggerTone(distance)}
          value={pct(distance)}
        />
        <SnapshotMetric
          label="Read"
          title="Plain-English read of trigger distance."
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
          title="Sector context from the cached sector ETF map. Full industry names can be added in a later enrichment pass."
          value={sectorLabel(data)}
        />
        <SnapshotMetric
          label="Score"
          title="Total setup score from the screener."
          tone={tierColor(data.tier)}
          value={scoreLabel(data.score)}
        />
        <SnapshotMetric
          label="ADR"
          title="Average Daily Range. Higher means the stock tends to move more each day."
          value={pct(data.adr_pct)}
        />
        <SnapshotMetric
          label="Base"
          title="Number of bars in the detected base."
          value={bars(data.base_len)}
        />
        <SnapshotMetric
          label="Box Width"
          title="Resistance minus support, shown as percent of support. Lower means tighter structure."
          value={pct(boxWidthPct(data))}
        />
        <SnapshotMetric
          label="LPS"
          title="Length of the last point of support pullback."
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
          cogRng: data.bin_b_cog_rng,
          cogCorr: data.bin_b_cog_corr,
          binCPresent: data.bin_c_present,
          binCType: data.bin_c_type,
          binCUndercutAtr: data.bin_c_undercut_atr,
          binCRecoveryBars: data.bin_c_recovery_bars,
          binCSpringVolZ: data.bin_c_spring_vol_z,
        }}
        maxTags={null}
        style={{ padding: 0 }}
      />
      <ScoreBreakdownPills subScores={data.sub_scores} style={{ marginTop: 10 }} />
    </section>
  );
}

export default function ScreenerStockLens({ activeRegion, data, onRegionChange }) {
  return (
    <div className="stock-lens">
      <div className="stock-lens-top">
        <DecisionRead data={data} />
        <ContextPanel data={data} />
      </div>
      <div className="stock-lens-bottom">
        <PhaseBinPanel activeRegion={activeRegion} data={data} onRegionChange={onRegionChange} />
        <TagsPanel data={data} />
      </div>
    </div>
  );
}
