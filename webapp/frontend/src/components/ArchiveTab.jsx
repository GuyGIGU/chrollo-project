import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { API_BASE } from '../api';
import ScreenerModal from './ScreenerModal';
import ArchiveCard from './ArchiveCard';

const SORT_OPTIONS = [
  ['scan_date', 'Date'],
  ['score', 'Score'],
  ['fwd_return_20d', '20d Return'],
  ['mfe_20d', 'MFE 20d'],
  ['ticker', 'Ticker'],
];

const ITEMS_PER_PAGE = 24;

// ── Helpers ──────────────────────────────────────────────────────

const pct = (v) => v != null ? `${(v * 100).toFixed(2)}%` : '—';
const tierColor = (t) => ({ S: '#ff8c00', A: '#bb86fc', B: '#58a6ff', C: '#3fb950', D: '#8b949e' }[t] || '#8b949e');
const labelColor = (l) => ({ perfect: '#3fb950', good: '#58a6ff', noise: '#8b949e', miss: '#c76b73' }[l] || 'var(--text-muted)');

const QUALITY_LABELS = ['perfect', 'good', 'noise', 'miss'];
const TIERS = ['ALL', 'S', 'A', 'B', 'C', 'D'];
const SETUP_TYPES = ['ALL', 'LPS', 'REBOUND', 'BREAKOUT'];

// Archive sources. "Curated" = seed + manual (the cherry-picked regression
// suite). Default to curated so daily noise stays hidden.
const SOURCE_FILTERS = [
  ['curated', 'Curated', 'seed,manual'],
  ['all',     'All',     null],
  ['seed',    'Seed',    'seed'],
  ['manual',  'Manual',  'manual'],
  ['screener','Screener','screener'],
];

// ── Sub components ───────────────────────────────────────────────

// Summary panel rendered beneath the chart inside the modal — surfaces all
// the archive metadata that the grid-card view intentionally omits to stay
// readable. Five panels: Structure, Forward Returns, Risk, Context, Sub-Scores.
const SummaryPanel = ({ title, children }) => (
  <div style={{
    background: 'var(--bg-main)', border: '1px solid var(--border-color)',
    borderRadius: '6px', padding: '10px 12px',
    display: 'flex', flexDirection: 'column', gap: '6px',
  }}>
    <div style={{
      fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase',
      letterSpacing: '0.5px', fontWeight: 600,
    }}>{title}</div>
    {children}
  </div>
);

const SummaryRow = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: '11px' }}>
    <span style={{ color: 'var(--text-muted)' }}>{label}</span>
    <span style={{
      color: color || 'var(--text-main)', fontWeight: 600,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {value ?? '—'}
    </span>
  </div>
);

const ArchiveSummary = ({ setup: s, linkedTrades = [] }) => {
  if (!s) return null;
  const fmtPct = (v) => v != null ? `${(v * 100).toFixed(2)}%` : '—';
  const fmtNum = (v, d = 3) => v != null ? Number(v).toFixed(d) : '—';
  const trendColor = (t) => t === 'BULLISH' ? 'var(--success)' : t === 'BEARISH' ? 'var(--danger)' : undefined;
  const retColor = (v) => v == null ? undefined : v > 0 ? 'var(--success)' : v < 0 ? 'var(--danger)' : undefined;

  return (
    <div style={{
      padding: '14px 24px', borderTop: '1px solid var(--border-color)',
      background: 'var(--bg-panel)',
      display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
      gap: '12px', maxHeight: '38vh', overflowY: 'auto',
    }}>
      <SummaryPanel title="Structure">
        <SummaryRow label="Base" value={s.base_length != null ? `${s.base_length}d` : null} />
        <SummaryRow label="Box W" value={s.box_width != null ? `${(s.box_width * 100).toFixed(1)}%` : null} />
        <SummaryRow label="Touches" value={s.touches != null ? `${s.touches} (${s.r_touches ?? '–'}/${s.s_touches ?? '–'})` : null} />
        <SummaryRow label="ATR Ratio" value={fmtNum(s.atr_ratio)} />
        <SummaryRow label="LPS Len" value={s.lps_length != null ? `${s.lps_length}d` : null} />
        <SummaryRow label="Tightness" value={fmtNum(s.tightness_ratio)} />
        <SummaryRow label="Vol Contr." value={fmtPct(s.vol_contraction)} />
        <SummaryRow label="Trigger" value={s.trigger_price != null ? `$${s.trigger_price.toFixed(2)}` : null} />
      </SummaryPanel>

      <SummaryPanel title="Forward Returns">
        <SummaryRow label="1d"  value={fmtPct(s.fwd_return_1d)}  color={retColor(s.fwd_return_1d)} />
        <SummaryRow label="5d"  value={fmtPct(s.fwd_return_5d)}  color={retColor(s.fwd_return_5d)} />
        <SummaryRow label="10d" value={fmtPct(s.fwd_return_10d)} color={retColor(s.fwd_return_10d)} />
        <SummaryRow label="20d" value={fmtPct(s.fwd_return_20d)} color={retColor(s.fwd_return_20d)} />
        <SummaryRow label="60d" value={fmtPct(s.fwd_return_60d)} color={retColor(s.fwd_return_60d)} />
      </SummaryPanel>

      <SummaryPanel title="Trade Math">
        <SummaryRow
          label="R-Mult 20d"
          value={s.r_multiple_20d != null ? `${s.r_multiple_20d.toFixed(2)}R` : null}
          color={s.r_multiple_20d > 1 ? 'var(--success)' : s.r_multiple_20d < 0 ? 'var(--danger)' : undefined}
        />
        <SummaryRow
          label="R-Mult 60d"
          value={s.r_multiple_60d != null ? `${s.r_multiple_60d.toFixed(2)}R` : null}
          color={s.r_multiple_60d > 1 ? 'var(--success)' : s.r_multiple_60d < 0 ? 'var(--danger)' : undefined}
        />
        <SummaryRow
          label="Trig Vol ×"
          value={s.trigger_volume_ratio != null ? `${s.trigger_volume_ratio.toFixed(2)}×` : null}
          color={s.trigger_volume_ratio > 1.5 ? 'var(--success)' : s.trigger_volume_ratio < 1 ? 'var(--danger)' : undefined}
        />
        <SummaryRow
          label="Dist 52w High"
          value={fmtPct(s.dist_52w_high_pct)}
          color={s.dist_52w_high_pct > -0.10 ? 'var(--success)' : s.dist_52w_high_pct < -0.25 ? 'var(--danger)' : undefined}
        />
        <SummaryRow
          label="RS vs Sector"
          value={fmtPct(s.rs_vs_sector_pct)}
          color={s.rs_vs_sector_pct > 0 ? 'var(--success)' : s.rs_vs_sector_pct < 0 ? 'var(--danger)' : undefined}
        />
      </SummaryPanel>

      <SummaryPanel title="Risk Profile">
        <SummaryRow label="MFE 20d" value={fmtPct(s.mfe_20d)} color="var(--success)" />
        <SummaryRow label="MAE 20d" value={fmtPct(s.mae_20d)} color="var(--danger)" />
        <SummaryRow label="MFE 60d" value={fmtPct(s.mfe_60d)} color="var(--success)" />
        <SummaryRow label="MAE 60d" value={fmtPct(s.mae_60d)} color="var(--danger)" />
        <SummaryRow
          label="Triggered"
          value={s.triggered === 1 ? `✓ ${s.trigger_date || ''}` : s.triggered === 0 ? '✗' : '—'}
          color={s.triggered === 1 ? 'var(--success)' : s.triggered === 0 ? 'var(--text-muted)' : undefined}
        />
      </SummaryPanel>

      <SummaryPanel title="Context">
        <SummaryRow label="SPY"          value={s.spy_trend}    color={trendColor(s.spy_trend)} />
        <SummaryRow label="VIX"          value={s.vix_level != null ? s.vix_level.toFixed(2) : null} />
        <SummaryRow label="Sector ETF"   value={s.sector_etf} />
        <SummaryRow label="Sector Trend" value={s.sector_trend} color={trendColor(s.sector_trend)} />
        <SummaryRow label="Source"       value={s.source} />
        <SummaryRow label="Label"        value={s.quality_label} color={labelColor(s.quality_label)} />
      </SummaryPanel>

      <SummaryPanel title="Sub-Scores">
        <SummaryRow label="Box Tight"    value={fmtNum(s.score_box_tightness, 2)} />
        <SummaryRow label="Touch Dens."  value={fmtNum(s.score_touch_density, 2)} />
        <SummaryRow label="Oscillation"  value={fmtNum(s.score_oscillation, 2)} />
        <SummaryRow label="ATR Squeeze"  value={fmtNum(s.score_atr_squeeze, 2)} />
        <SummaryRow label="LPS Tight"    value={fmtNum(s.score_lps_tightness, 2)} />
        <SummaryRow label="Vol Contr."   value={fmtNum(s.score_vol_contraction, 2)} />
        <SummaryRow label="Base Age"     value={fmtNum(s.score_base_age, 2)} />
        <SummaryRow
          label="Uptrend Bonus"
          value={fmtNum(s.score_uptrend_bonus, 2)}
          color={s.score_uptrend_bonus > 0 ? 'var(--success)' : undefined}
        />
      </SummaryPanel>

      {linkedTrades.length > 0 && (
        <SummaryPanel title={`Linked Trades (${linkedTrades.length})`}>
          {linkedTrades.map(t => (
            <div key={t.id} style={{
              borderTop: '1px solid var(--border-color)', paddingTop: '4px', marginTop: '2px',
              fontSize: '10px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>{t.opening_date}</span>
                <span style={{
                  color: t.direction === 'L' ? 'var(--success)' : 'var(--danger)',
                  fontWeight: 600,
                }}>{t.direction}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>${t.entry_price?.toFixed(2)} → ${t.exit_price?.toFixed(2) ?? '—'}</span>
                <span style={{
                  color: (t.pnl ?? 0) > 0 ? 'var(--success)' : (t.pnl ?? 0) < 0 ? 'var(--danger)' : 'var(--text-muted)',
                  fontWeight: 600,
                }}>{t.pnl != null ? `$${t.pnl.toFixed(2)}` : '—'}</span>
              </div>
            </div>
          ))}
        </SummaryPanel>
      )}

      {s.notes && (
        <SummaryPanel title="Notes">
          <div style={{ fontSize: '11px', color: 'var(--text-main)', whiteSpace: 'pre-wrap' }}>
            {s.notes}
          </div>
        </SummaryPanel>
      )}
    </div>
  );
};


const TierCard = ({ tier, data }) => {
  if (!data) return null;
  return (
    <div style={{
      background: 'var(--bg-panel)', border: '1px solid var(--border-color)',
      borderRadius: '10px', padding: '16px 20px', flex: '1 1 0',
      borderTop: `3px solid ${tierColor(tier)}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '18px', fontWeight: '700', color: tierColor(tier) }}>{tier} Tier</span>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{data.count} setups</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', fontSize: '12px' }}>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Expectancy</div>
          <div style={{ fontWeight: '700', color: data.expectancy_r > 0 ? 'var(--success)' : data.expectancy_r < 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
            {data.expectancy_r != null ? `${data.expectancy_r.toFixed(2)}R` : '—'}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '9px', marginTop: '2px' }}>n={data.r_sample_size || 0}</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Avg R 20d</div>
          <div style={{ fontWeight: '600', color: data.avg_r_multiple_20d > 0 ? 'var(--success)' : 'var(--danger)' }}>
            {data.avg_r_multiple_20d != null ? `${data.avg_r_multiple_20d.toFixed(2)}R` : '—'}
          </div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Win Rate</div>
          <div style={{ fontWeight: '600' }}>{pct(data.win_rate)}</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>20d Return</div>
          <div style={{ fontWeight: '600', color: data.avg_fwd_20d > 0 ? 'var(--success)' : 'var(--danger)' }}>{pct(data.avg_fwd_20d)}</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Trigger Rate</div>
          <div style={{ fontWeight: '600' }}>{pct(data.trigger_rate)}</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Avg MFE 20d</div>
          <div style={{ fontWeight: '600', color: 'var(--success)' }}>{pct(data.avg_mfe_20d)}</div>
        </div>
      </div>
    </div>
  );
};


// Two-horizon correlation row: one label + a 20d bar and a 60d bar so the
// reader can spot horizon-specific edges (e.g. base_age weak at 20d but
// strong at 60d → long-hold signal, not swing signal).
const DualCorrelationBar = ({ label, value20, value60 }) => {
  const renderBar = (v) => {
    const abs = Math.abs(v || 0);
    const barWidth = Math.min(abs * 250, 100);
    const isPositive = (v || 0) >= 0;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1 }}>
        <div style={{ flex: 1, height: '12px', background: 'rgba(255,255,255,0.04)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${barWidth}%`, borderRadius: '3px',
            background: isPositive
              ? 'linear-gradient(90deg, var(--accent-blue), var(--success))'
              : 'linear-gradient(90deg, var(--danger), var(--accent-pink))',
            transition: 'width 0.5s ease',
          }} />
        </div>
        <div style={{
          width: '42px', textAlign: 'right', fontWeight: 600,
          fontFamily: "'JetBrains Mono', monospace", fontSize: '10px',
          color: isPositive ? 'var(--success)' : 'var(--danger)',
        }}>
          {v != null ? v.toFixed(3) : '—'}
        </div>
      </div>
    );
  };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', marginBottom: '5px' }}>
      <div style={{ width: '110px', color: 'var(--text-muted)', textTransform: 'capitalize', flexShrink: 0 }}>
        {label.replace(/_/g, ' ')}
      </div>
      {renderBar(value20)}
      {renderBar(value60)}
    </div>
  );
};


// Side-by-side current vs suggested weight per sub-score. Positive delta
// (orange) means the empirical fit wants more weight on this component;
// negative (blue) means less. Read-only — user must edit settings.py
// manually if they decide to apply.
const ReweightingStrip = ({ data, basis }) => {
  if (!data || data.length === 0) return null;
  // Null-safe number formatter: a sub-score with zero variance yields a null
  // correlation server-side, which can cascade into null suggested/delta. Never
  // call .toFixed on those directly or the whole Archive tab white-screens.
  const fx = (v, d) => (v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d);
  const totalCurrent = data.reduce((sum, r) => sum + (Number(r.current) || 0), 0);
  const totalSuggested = data.reduce((sum, r) => sum + (Number(r.suggested) || 0), 0);
  const basisLabel = basis === '20d+60d_avg'
    ? 'avg |corr| across 20d + 60d horizons'
    : basis === '20d_only'
      ? '20d |corr| only (60d sample too small — fewer than 15 setups have aged 60+ days)'
      : 'insufficient data';
  return (
    <div className="glass-panel">
      <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>⚖ Suggested Re-weighting</div>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '12px' }}>
        Basis: {basisLabel}, renormalized to preserve total cap ({fx(totalCurrent, 0)} pts).
        Read-only — edit <code style={{ background: 'rgba(255,255,255,0.06)', padding: '0 4px', borderRadius: '3px' }}>config/settings.py</code> manually if applying.
      </div>
      <table style={{ width: '100%', fontSize: '11px', fontFamily: "'JetBrains Mono', monospace" }}>
        <thead>
          <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border-color)' }}>
            <th style={{ textAlign: 'left',  padding: '4px 6px' }}>Sub-score</th>
            <th style={{ textAlign: 'right', padding: '4px 6px' }}>Current</th>
            <th style={{ textAlign: 'right', padding: '4px 6px' }}>Suggested</th>
            <th style={{ textAlign: 'right', padding: '4px 6px' }}>Δ</th>
            <th style={{ textAlign: 'right', padding: '4px 6px' }}>|corr|</th>
          </tr>
        </thead>
        <tbody>
          {data.map(r => (
            <tr key={r.name} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
              <td style={{ padding: '4px 6px', textTransform: 'capitalize' }}>{r.name.replace(/_/g, ' ')}</td>
              <td style={{ padding: '4px 6px', textAlign: 'right' }}>{fx(r.current, 0)}</td>
              <td style={{ padding: '4px 6px', textAlign: 'right' }}>{fx(r.suggested, 1)}</td>
              <td style={{
                padding: '4px 6px', textAlign: 'right', fontWeight: 600,
                color: r.delta > 0.5 ? '#ff8c00' : r.delta < -0.5 ? 'var(--accent-blue)' : 'var(--text-muted)',
              }}>
                {r.delta > 0 ? '+' : ''}{fx(r.delta, 1)}
              </td>
              <td style={{ padding: '4px 6px', textAlign: 'right', color: 'var(--text-muted)' }}>{fx(r.avg_abs_corr, 3)}</td>
            </tr>
          ))}
          <tr style={{ borderTop: '1px solid var(--border-color)' }}>
            <td style={{ padding: '4px 6px', color: 'var(--text-muted)' }}>Total</td>
            <td style={{ padding: '4px 6px', textAlign: 'right', color: 'var(--text-muted)' }}>{fx(totalCurrent, 0)}</td>
            <td style={{ padding: '4px 6px', textAlign: 'right', color: 'var(--text-muted)' }}>{fx(totalSuggested, 1)}</td>
            <td colSpan={2} />
          </tr>
        </tbody>
      </table>
    </div>
  );
};


// ── Equity Curve ─────────────────────────────────────────────────
// Cumulative R-multiple over time across all triggered setups. The single
// most motivating chart — answers "would this strategy actually have made
// money".
const EquityCurve = ({ data }) => {
  if (!data || !data.points || data.points.length === 0) {
    return (
      <div className="glass-panel">
        <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>💰 Equity Curve (R)</div>
        <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
          No triggered setups with R-multiples yet. Run forward-return updater.
        </div>
      </div>
    );
  }

  const W = 600;     // viewBox width — scales responsively via preserveAspectRatio
  const H = 140;
  const pts = data.points;
  const cums = pts.map(p => p.cum_r);
  const minR = Math.min(0, ...cums);
  const maxR = Math.max(0, ...cums);
  const span = maxR - minR || 1;

  const xStep = pts.length > 1 ? W / (pts.length - 1) : W / 2;
  const path = pts.map((p, i) => {
    const x = i * xStep;
    const y = H - ((p.cum_r - minR) / span) * (H - 4) - 2;
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  // Zero baseline
  const zeroY = H - ((0 - minR) / span) * (H - 4) - 2;
  const finalCum = cums[cums.length - 1];
  const lineColor = finalCum >= 0 ? '#3fb950' : '#c76b73';
  const sm = data.summary || {};

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4px' }}>
        <div style={{ fontSize: '13px', fontWeight: 600 }}>💰 Equity Curve (R)</div>
        <div style={{ fontSize: '12px', fontWeight: 700, color: lineColor, fontFamily: "'JetBrains Mono', monospace" }}>
          {finalCum >= 0 ? '+' : ''}{finalCum.toFixed(2)}R
        </div>
      </div>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '8px' }}>
        Cumulative R from {sm.total_setups} triggered setups · WR {(sm.win_rate * 100).toFixed(0)}% · Max DD {sm.max_drawdown_r}R
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height: '140px' }}>
        <line x1="0" y1={zeroY} x2={W} y2={zeroY} stroke="rgba(255,255,255,0.15)" strokeDasharray="3,3" />
        <path d={path} fill="none" stroke={lineColor} strokeWidth="2" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)', marginTop: '6px' }}>
        <span>Best: <span style={{ color: 'var(--success)' }}>+{sm.best_r}R</span></span>
        <span>Worst: <span style={{ color: 'var(--danger)' }}>{sm.worst_r}R</span></span>
        <span>Avg: <span style={{ color: 'var(--text-main)' }}>{sm.avg_r}R</span></span>
      </div>
    </div>
  );
};


// ── Main Component ───────────────────────────────────────────────

const ArchiveTab = () => {
  const [setups, setSetups] = useState([]);
  const [stats, setStats] = useState(null);
  const [calibration, setCalibration] = useState(null);
  const [equityCurve, setEquityCurve] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  // Result banner for the "Update Forward Returns" button. Without this the
  // button silently flashed a loading state and gave the user no signal of
  // what (if anything) happened — even when the subprocess succeeded.
  const [updateMsg, setUpdateMsg] = useState(null);  // { ok: bool, text: str }

  // Add Setup Modal State
  const [addOpen, setAddOpen] = useState(false);
  const [addTicker, setAddTicker] = useState('');
  const [addDate, setAddDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [addLabel, setAddLabel] = useState('');
  const [addNotes, setAddNotes] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState(null);

  // Chart Viewer State
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartTicker, setChartTicker] = useState(null);
  const [chartSetup, setChartSetup] = useState(null);   // full archive row for the summary panel
  const [linkedTrades, setLinkedTrades] = useState([]);

  // Filters
  const [tierFilter, setTierFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('curated');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('scan_date');
  const [sortDir, setSortDir] = useState('desc');

  // Grid pagination + bulk chart cache (id -> chartData) for the visible page
  const [currentPage, setCurrentPage] = useState(1);
  const [bulkCharts, setBulkCharts] = useState({});
  const [bulkLoading, setBulkLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const sourceParam = SOURCE_FILTERS.find(([k]) => k === sourceFilter)?.[2];
      const params = new URLSearchParams({ limit: '500', sort_by: sortBy, sort_dir: sortDir });
      if (tierFilter !== 'ALL') params.set('tier', tierFilter);
      if (typeFilter !== 'ALL') params.set('setup_type', typeFilter);
      if (sourceParam) params.set('source', sourceParam);
      const [setupsRes, statsRes, calRes, eqRes] = await Promise.all([
        fetch(`${API_BASE}/archive/setups?${params.toString()}`),
        fetch(`${API_BASE}/archive/stats`),
        fetch(`${API_BASE}/archive/calibration`),
        fetch(`${API_BASE}/archive/calibration/equity-curve`),
      ]);
      if (setupsRes.ok) setSetups(await setupsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (calRes.ok) setCalibration(await calRes.json());
      if (eqRes.ok) setEquityCurve(await eqRes.json());
    } catch (err) {
      console.error('Failed to fetch archive data:', err);
    }
    setLoading(false);
  }, [sortBy, sortDir, tierFilter, typeFilter, sourceFilter]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleUpdateReturns = async () => {
    setUpdating(true);
    setUpdateMsg(null);
    try {
      const res = await fetch(`${API_BASE}/archive/update-returns`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.returncode === 0) {
        // Python logging writes to stderr by default, so even on success the
        // meaningful "Updated N for X setups" / "No setups need updates"
        // line lands in stderr — not stdout. Look at both streams and pick
        // the last line that mentions update/setup outcomes.
        const combined = `${data.stdout || ''}\n${data.stderr || ''}`.trim();
        const lines = combined.split('\n').filter(Boolean);
        const summary = lines.reverse().find(l =>
          /updated|no setups|setups need/i.test(l)
        ) || lines[0] || 'Done.';
        // Strip the timestamp/log-level prefix if present (e.g. "2026-... INFO ").
        const clean = summary.replace(/^\S+\s+\S+\s+\S+\s+/, '').trim();
        setUpdateMsg({ ok: true, text: clean });
        await fetchAll();
      } else {
        // Surface stderr if the script failed; otherwise show the HTTP status.
        const errText = (data.stderr || data.detail || `HTTP ${res.status}`).trim();
        setUpdateMsg({ ok: false, text: errText.slice(-300) || 'Update failed.' });
        console.error('Forward returns update failed:', data);
      }
    } catch (err) {
      setUpdateMsg({ ok: false, text: `Network error: ${err.message || err}` });
      console.error('Failed to update returns:', err);
    }
    setUpdating(false);
    // Auto-dismiss the banner after 8s so it doesn't linger.
    setTimeout(() => setUpdateMsg(null), 8000);
  };

  const handleAddSetup = async () => {
    setAdding(true);
    setAddError(null);
    try {
      const res = await fetch(`${API_BASE}/archive/add-setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: addTicker.trim().toUpperCase(),
          scan_date: addDate,
          quality_label: addLabel || null,
          notes: addNotes || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setAddError(err.detail || `HTTP ${res.status}`);
      } else {
        setAddOpen(false);
        setAddTicker('');
        setAddNotes('');
        setAddLabel('');
        await fetchAll();
      }
    } catch (err) {
      setAddError(String(err));
    }
    setAdding(false);
  };

  const handleLabelChange = useCallback(async (id, label) => {
    try {
      await fetch(`${API_BASE}/archive/setups/${id}/label`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality_label: label }),
      });
      setSetups(prev => prev.map(s => s.id === id ? { ...s, quality_label: label } : s));
    } catch (err) {
      console.error('Failed to update label:', err);
    }
  }, []);

  const handleRowClick = async (setup) => {
    // If the bulk-fetched chart for this setup is already cached, open instantly
    // — no extra round trip. Falls back to the per-setup endpoint otherwise.
    setChartTicker(setup.ticker);
    setChartSetup(setup);
    setLinkedTrades([]);
    // Fire off linked-trades fetch in the background (independent of chart load).
    fetch(`${API_BASE}/archive/setups/${setup.id}/linked-trades?window_days=7`)
      .then(r => r.ok ? r.json() : [])
      .then(setLinkedTrades)
      .catch(() => setLinkedTrades([]));
    if (bulkCharts[setup.id]) {
      setChartData(bulkCharts[setup.id]);
      return;
    }
    setChartLoading(true);
    try {
      const res = await fetch(`${API_BASE}/archive/setups/${setup.id}/chart`);
      if (res.ok) {
        const data = await res.json();
        setChartData(data);
      } else {
        console.error('Failed to fetch chart data');
        setChartTicker(null);
        setChartSetup(null);
      }
    } catch (err) {
      console.error('Error fetching chart data:', err);
      setChartTicker(null);
      setChartSetup(null);
    }
    setChartLoading(false);
  };

  const filteredSetups = useMemo(() => {
    if (!searchTerm) return setups;
    return setups.filter(s => s.ticker.toLowerCase().includes(searchTerm.toLowerCase()));
  }, [setups, searchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredSetups.length / ITEMS_PER_PAGE));
  const pageSetups = useMemo(
    () => filteredSetups.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE),
    [filteredSetups, currentPage],
  );

  // Reset to page 1 whenever the filtered set changes shape.
  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(1);
  }, [totalPages, currentPage]);

  // Bulk-fetch chart data for the visible page. Skips IDs we already have.
  useEffect(() => {
    const missing = pageSetups.map(s => s.id).filter(id => !bulkCharts[id]);
    if (missing.length === 0) return;
    let cancelled = false;
    setBulkLoading(true);
    fetch(`${API_BASE}/archive/charts/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: missing }),
    })
      .then(r => r.ok ? r.json() : {})
      .then(data => {
        if (cancelled) return;
        setBulkCharts(prev => {
          const next = { ...prev };
          for (const [k, v] of Object.entries(data)) next[k] = v;
          return next;
        });
      })
      .catch(err => console.error('bulk chart fetch failed:', err))
      .finally(() => { if (!cancelled) setBulkLoading(false); });
    return () => { cancelled = true; };
  }, [pageSetups, bulkCharts]);

  const btnStyle = (active) => ({
    padding: '5px 14px', borderRadius: '16px', border: '1px solid',
    borderColor: active ? 'var(--accent-blue)' : 'var(--border-color)',
    background: active ? 'var(--accent-blue)' : 'transparent',
    color: active ? '#fff' : 'var(--text-main)',
    cursor: 'pointer', transition: 'all 0.2s ease',
    fontWeight: active ? '600' : '500', fontSize: '12px', fontFamily: 'inherit',
  });

  if (loading && setups.length === 0) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading archive…</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Chart Viewer */}
      {chartLoading && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(10,10,15,0.8)', zIndex: 5000, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
          Loading historical data for {chartTicker}...
        </div>
      )}
      {chartData && chartTicker && !chartLoading && (
        <ScreenerModal
          ticker={chartTicker}
          data={chartData}
          onClose={() => { setChartData(null); setChartTicker(null); setChartSetup(null); }}
          onNext={() => {}}
          onPrev={() => {}}
          footer={<ArchiveSummary setup={chartSetup} linkedTrades={linkedTrades} />}
        />
      )}

      {/* ── Header + Actions ─────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ color: 'var(--text-muted)' }}>
          {stats ? `${stats.total_setups} setups archived · ${stats.with_forward_returns} with forward returns` : 'Loading...'}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => { setAddError(null); setAddOpen(true); }}
            style={{
              background: 'transparent', color: 'var(--text-main)',
              border: '1px solid var(--border-color)', padding: '8px 16px',
              borderRadius: '6px', cursor: 'pointer', fontWeight: '600',
              fontSize: '12px', fontFamily: 'inherit', transition: 'all 0.2s',
            }}
          >
            ＋ Add Setup
          </button>
          <button
            onClick={handleUpdateReturns}
            disabled={updating}
            style={{
              background: updating ? 'var(--bg-hover)' : 'var(--accent-blue)',
              color: updating ? 'var(--text-muted)' : '#fff',
              border: 'none', padding: '8px 16px', borderRadius: '6px',
              cursor: updating ? 'not-allowed' : 'pointer',
              fontWeight: '600', fontSize: '12px', fontFamily: 'inherit',
              transition: 'all 0.2s',
            }}
          >
            {updating ? '⏳ Updating Returns…' : '🔄 Update Forward Returns'}
          </button>
        </div>
      </div>

      {updateMsg && (
        <div
          style={{
            margin: '8px 0 12px',
            padding: '8px 12px',
            borderRadius: '6px',
            background: updateMsg.ok ? 'rgba(63,185,80,0.10)' : 'rgba(248,81,73,0.10)',
            border: `1px solid ${updateMsg.ok ? 'rgba(63,185,80,0.35)' : 'rgba(248,81,73,0.35)'}`,
            color: updateMsg.ok ? '#3fb950' : '#f85149',
            fontSize: '12px',
            fontFamily: 'inherit',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {updateMsg.ok ? '✓ ' : '⚠ '}{updateMsg.text}
        </div>
      )}

      {addOpen && (
        <div
          onClick={() => !adding && setAddOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(10,10,15,0.85)',
            backdropFilter: 'blur(4px)', zIndex: 6000,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--bg-main)', border: '1px solid var(--border-color)',
              borderRadius: '12px', padding: '24px', width: '100%', maxWidth: '420px',
              boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ fontSize: '16px', fontWeight: '700', marginBottom: '4px' }}>Add Setup to Archive</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '16px' }}>
              Runs the screener at this date. Rejected if no LPS fires there.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Ticker
                <input
                  type="text" value={addTicker} autoFocus
                  onChange={(e) => setAddTicker(e.target.value)}
                  placeholder="e.g. AAPL"
                  style={{
                    display: 'block', width: '100%', marginTop: '4px',
                    padding: '8px 10px', borderRadius: '6px',
                    border: '1px solid var(--border-color)', background: 'var(--bg-panel)',
                    color: 'var(--text-main)', fontFamily: 'inherit', fontSize: '13px',
                    textTransform: 'uppercase', boxSizing: 'border-box',
                  }}
                />
              </label>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Scan date
                <input
                  type="date" value={addDate}
                  onChange={(e) => setAddDate(e.target.value)}
                  style={{
                    display: 'block', width: '100%', marginTop: '4px',
                    padding: '8px 10px', borderRadius: '6px',
                    border: '1px solid var(--border-color)', background: 'var(--bg-panel)',
                    color: 'var(--text-main)', fontFamily: 'inherit', fontSize: '13px',
                    boxSizing: 'border-box',
                  }}
                />
              </label>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Quality label (optional)
                <select
                  value={addLabel}
                  onChange={(e) => setAddLabel(e.target.value)}
                  style={{
                    display: 'block', width: '100%', marginTop: '4px',
                    padding: '8px 10px', borderRadius: '6px',
                    border: '1px solid var(--border-color)', background: 'var(--bg-panel)',
                    color: 'var(--text-main)', fontFamily: 'inherit', fontSize: '13px',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="">—</option>
                  {QUALITY_LABELS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </label>
              <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Notes (optional)
                <textarea
                  value={addNotes}
                  onChange={(e) => setAddNotes(e.target.value)}
                  rows={3}
                  style={{
                    display: 'block', width: '100%', marginTop: '4px',
                    padding: '8px 10px', borderRadius: '6px',
                    border: '1px solid var(--border-color)', background: 'var(--bg-panel)',
                    color: 'var(--text-main)', fontFamily: 'inherit', fontSize: '12px',
                    resize: 'vertical', boxSizing: 'border-box',
                  }}
                />
              </label>
            </div>
            {addError && (
              <div style={{
                marginTop: '12px', padding: '8px 12px', borderRadius: '6px',
                background: 'rgba(199,107,115,0.12)', border: '1px solid rgba(199,107,115,0.4)',
                color: '#c76b73', fontSize: '11px',
              }}>
                {addError}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              <button
                onClick={() => setAddOpen(false)} disabled={adding}
                style={{
                  padding: '8px 14px', borderRadius: '6px', fontFamily: 'inherit',
                  background: 'transparent', border: '1px solid var(--border-color)',
                  color: 'var(--text-main)', cursor: adding ? 'not-allowed' : 'pointer', fontSize: '12px',
                }}
              >Cancel</button>
              <button
                onClick={handleAddSetup} disabled={adding || !addTicker.trim()}
                style={{
                  padding: '8px 14px', borderRadius: '6px', fontFamily: 'inherit',
                  background: (adding || !addTicker.trim()) ? 'var(--bg-hover)' : 'var(--accent-blue)',
                  color: (adding || !addTicker.trim()) ? 'var(--text-muted)' : '#fff',
                  border: 'none', cursor: (adding || !addTicker.trim()) ? 'not-allowed' : 'pointer',
                  fontWeight: '600', fontSize: '12px',
                }}
              >
                {adding ? '⏳ Adding…' : 'Add Setup'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tier Performance Cards ────────────────────────── */}
      {calibration?.tier_performance && Object.keys(calibration.tier_performance).length > 0 && (
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {['S', 'A', 'B', 'C', 'D'].map(t =>
            calibration.tier_performance[t] ? <TierCard key={t} tier={t} data={calibration.tier_performance[t]} /> : null
          )}
        </div>
      )}

      {/* ── Calibration Panels ───────────────────────────── */}
      {calibration && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {/* Sub-Score Correlations — 20d / 60d side-by-side */}
          <div className="glass-panel">
            <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '4px', color: 'var(--text-main)' }}>
              📊 Sub-Score vs Forward Returns (Correlation)
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '10px' }}>
              n = {calibration.total_with_returns} (20d) · {calibration.total_with_60d_returns} (60d) ·
              higher = this component better predicts the horizon
            </div>
            <div style={{ display: 'flex', gap: '10px', fontSize: '10px', color: 'var(--text-muted)', marginBottom: '6px', paddingLeft: '110px' }}>
              <div style={{ flex: 1, paddingLeft: '10px' }}>20d</div>
              <div style={{ flex: 1, paddingLeft: '10px' }}>60d</div>
            </div>
            {calibration.sub_score_correlations_20d &&
              Object.keys(calibration.sub_score_correlations_20d)
                .sort((a, b) => {
                  const c20a = Math.abs(calibration.sub_score_correlations_20d[a] || 0);
                  const c60a = Math.abs(calibration.sub_score_correlations_60d?.[a] || 0);
                  const c20b = Math.abs(calibration.sub_score_correlations_20d[b] || 0);
                  const c60b = Math.abs(calibration.sub_score_correlations_60d?.[b] || 0);
                  return ((c20b + c60b) / 2) - ((c20a + c60a) / 2);
                })
                .map(key => (
                  <DualCorrelationBar
                    key={key}
                    label={key}
                    value20={calibration.sub_score_correlations_20d[key]}
                    value60={calibration.sub_score_correlations_60d?.[key]}
                  />
                ))
            }
          </div>

          {/* Setup Type Breakdown */}
          <div className="glass-panel">
            <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '12px', color: 'var(--text-main)' }}>
              🎯 Setup Type Performance
            </div>
            {calibration.setup_type_breakdown && Object.entries(calibration.setup_type_breakdown).map(([type, data]) => (
              <div key={type} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 12px', background: 'var(--bg-main)', borderRadius: '6px',
                marginBottom: '8px', border: '1px solid var(--border-color)',
              }}>
                <span style={{ fontWeight: '600', fontSize: '13px' }}>{type}</span>
                <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{data.count} trades</span>
                  <span style={{ color: data.avg_fwd_20d > 0 ? 'var(--success)' : 'var(--danger)', fontWeight: '600' }}>
                    {pct(data.avg_fwd_20d)}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>WR: {pct(data.win_rate)}</span>
                </div>
              </div>
            ))}

            {/* Market Context */}
            <div style={{ fontSize: '13px', fontWeight: '600', margin: '16px 0 12px', color: 'var(--text-main)' }}>
              🌎 Market Regime Impact
            </div>
            {calibration.market_context && Object.entries(calibration.market_context).map(([regime, data]) => (
              <div key={regime} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 12px', background: 'var(--bg-main)', borderRadius: '6px',
                marginBottom: '8px', border: '1px solid var(--border-color)',
              }}>
                <span style={{
                  fontWeight: '600', fontSize: '12px',
                  color: regime === 'BULLISH' ? 'var(--success)' : regime === 'BEARISH' ? 'var(--danger)' : 'var(--text-muted)',
                }}>
                  SPY {regime}
                </span>
                <div style={{ display: 'flex', gap: '16px', fontSize: '12px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{data.count} setups</span>
                  <span style={{ color: data.avg_fwd_20d > 0 ? 'var(--success)' : 'var(--danger)', fontWeight: '600' }}>
                    {pct(data.avg_fwd_20d)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Suggested Re-weighting ──────────────────────── */}
      {calibration?.suggested_weights && calibration.suggested_weights.length > 0 && (
        <ReweightingStrip data={calibration.suggested_weights} basis={calibration.weights_basis} />
      )}

      {/* ── Equity Curve ─────────────────────────────────── */}
      {equityCurve && <EquityCurve data={equityCurve} />}

      {/* ── Filters ──────────────────────────────────────── */}
      <div style={{
        padding: '10px 16px', background: 'var(--bg-panel)', border: '1px solid var(--border-color)',
        borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '4px' }}>Source:</span>
        {SOURCE_FILTERS.map(([key, label]) => (
          <button key={key} onClick={() => { setSourceFilter(key); setCurrentPage(1); }} style={btnStyle(sourceFilter === key)}>
            {label}
          </button>
        ))}
        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginLeft: '8px', marginRight: '4px' }}>Tier:</span>
        {TIERS.map(t => (
          <button key={t} onClick={() => { setTierFilter(t); setCurrentPage(1); }} style={btnStyle(tierFilter === t)}>
            {t === 'ALL' ? 'All' : t}
          </button>
        ))}
        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginLeft: '8px', marginRight: '4px' }}>Type:</span>
        {SETUP_TYPES.map(t => (
          <button key={t} onClick={() => { setTypeFilter(t); setCurrentPage(1); }} style={btnStyle(typeFilter === t)}>
            {t === 'ALL' ? 'All' : t}
          </button>
        ))}

        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginLeft: '8px', marginRight: '4px' }}>Sort:</span>
        <select
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value); setCurrentPage(1); }}
          style={{
            padding: '5px 10px', borderRadius: '8px', border: '1px solid var(--border-color)',
            background: 'var(--bg-main)', color: 'var(--text-main)', fontSize: '12px',
            fontFamily: 'inherit', cursor: 'pointer',
          }}
        >
          {SORT_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <button
          onClick={() => { setSortDir(d => d === 'asc' ? 'desc' : 'asc'); setCurrentPage(1); }}
          style={{
            ...btnStyle(false), padding: '5px 10px', minWidth: '36px',
          }}
          title={sortDir === 'desc' ? 'Descending' : 'Ascending'}
        >
          {sortDir === 'desc' ? '↓' : '↑'}
        </button>

        <input
          type="text" placeholder="Search ticker…" value={searchTerm}
          onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
          style={{
            marginLeft: 'auto', padding: '5px 14px', borderRadius: '8px',
            border: '1px solid var(--border-color)', background: 'var(--bg-main)',
            color: 'var(--text-main)', fontSize: '12px', width: '160px', outline: 'none',
            fontFamily: 'inherit',
          }}
        />
      </div>

      {/* ── Setup Grid ───────────────────────────────────── */}
      {filteredSetups.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No setups in archive yet. Run a screener scan, seed historical setups, or use ＋ Add Setup above.
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span>Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1}–{Math.min(currentPage * ITEMS_PER_PAGE, filteredSetups.length)} of {filteredSetups.length}</span>
            {bulkLoading && <span>⏳ loading charts…</span>}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: '20px',
          }}>
            {pageSetups.map(s => (
              <ArchiveCard
                key={s.id}
                setup={s}
                chartData={bulkCharts[s.id]}
                onClick={handleRowClick}
                onLabelChange={handleLabelChange}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '8px', marginBottom: '20px' }}>
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(p => p - 1)}
                style={{
                  padding: '6px 14px', background: 'var(--bg-main)', border: '1px solid var(--border-color)',
                  color: 'var(--text-main)', borderRadius: '6px',
                  cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                  opacity: currentPage === 1 ? 0.5 : 1, fontFamily: 'inherit',
                }}
              >◀ Prev</button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  style={{
                    padding: '6px 14px', borderRadius: '6px', border: '1px solid',
                    borderColor: currentPage === page ? 'var(--accent-blue)' : 'var(--border-color)',
                    background: currentPage === page ? 'var(--accent-blue)' : 'var(--bg-main)',
                    color: currentPage === page ? '#fff' : 'var(--text-main)',
                    cursor: 'pointer', fontWeight: currentPage === page ? '600' : '400',
                    fontFamily: 'inherit',
                  }}
                >{page}</button>
              ))}
              <button
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(p => p + 1)}
                style={{
                  padding: '6px 14px', background: 'var(--bg-main)', border: '1px solid var(--border-color)',
                  color: 'var(--text-main)', borderRadius: '6px',
                  cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                  opacity: currentPage === totalPages ? 0.5 : 1, fontFamily: 'inherit',
                }}
              >Next ▶</button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ArchiveTab;
