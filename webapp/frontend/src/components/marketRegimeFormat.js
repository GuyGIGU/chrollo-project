import { explainTip } from './tooltipText';
import { finiteOrNull, fmtPctFrac, fmtRound, fmtSignedPctFrac, fx } from '../utils/format';

// Each state carries structured guidance (what/why/use) so the detail modal can
// render it as readable labeled rows, while `detail` stays a single string for
// the hover tooltips elsewhere (banner title attribute).
const withGuidance = (base, what, why, use) => ({
  ...base, what, why, use, detail: explainTip({ what, why, use }),
});

export const STATE_META = {
  UPTREND: withGuidance(
    { label: 'Uptrend', tone: 'var(--success)', border: 'rgba(61, 211, 122, 0.30)', summary: 'Indexes and breadth are aligned.' },
    'The market backdrop is constructive: SPY is holding key moving averages, the 50-day average is rising, and breadth is healthy.',
    'Breakout setups usually work better when the broad market is supporting risk-taking.',
    'You can be more willing to review long setups, while still requiring each chart to meet its own trigger and risk rules.',
  ),
  NEUTRAL: withGuidance(
    { label: 'Neutral', tone: 'var(--accent-blue)', border: 'rgba(91, 138, 255, 0.32)', summary: 'Mixed backdrop.' },
    'The market backdrop is mixed from the available trend, breadth, and distribution measures.',
    'Mixed conditions can produce selective opportunities but less broad follow-through.',
    'Be choosy: prioritize the cleanest leaders and avoid forcing marginal setups.',
  ),
  UNDER_PRESSURE: withGuidance(
    { label: 'Under Pressure', tone: 'var(--warning)', border: 'rgba(var(--warning-rgb), 0.34)', summary: 'Constructive, but selective.' },
    'The index trend may still be intact, but breadth or distribution is flashing caution.',
    'A market can look fine at the index level while fewer stocks participate underneath.',
    'Reduce tolerance for sloppy setups and demand stronger confirmation before acting.',
  ),
  CORRECTION: withGuidance(
    { label: 'Correction', tone: 'var(--danger)', border: 'rgba(var(--danger-rgb), 0.34)', summary: 'Defensive backdrop.' },
    'SPY is below major trend support, or long-term breadth is weak enough to confirm market stress.',
    'Correction conditions raise the chance that breakouts fail or reverse quickly.',
    'Stay defensive and treat new long ideas as watchlist candidates until the backdrop improves.',
  ),
  UNKNOWN: withGuidance(
    { label: 'Pending', tone: 'var(--text-muted)', border: 'var(--border-color)', summary: 'Awaiting new scan.' },
    'The market regime has not been calculated for the current scan data.',
    'Without fresh context, the screener cannot judge whether the broad market is helping or hurting setups.',
    'Run a fresh scan before relying on regime, breadth, or distribution reads.',
  ),
};

// Regime dialect: 'n/a' is deliberate copy (these render inside prose rows).
export const fxPct = (value, digits = 0) => fmtPctFrac(value, digits, 'n/a');

export const fxSignedPct = (value, digits = 1) => fmtSignedPctFrac(value, digits, 'n/a');

export const fxPrice = (value) => fx(value, 2, 'n/a');

export const fxNum = (value) => fmtRound(value, 'n/a');

export const fxDays = (value) => {
  const n = finiteOrNull(value);
  if (n == null) return 'n/a';
  const rounded = Math.round(n);
  return `${rounded} day${rounded === 1 ? '' : 's'}`;
};

export function buildRegimeReasons(regime = {}, spy = {}, qqq = {}) {
  const reasons = [];
  if (spy?.above_sma_50 === true) reasons.push('SPY above 50D');
  if (spy?.above_sma_50 === false) reasons.push('SPY below 50D');
  if (spy?.above_sma_200 === true) reasons.push('SPY above 200D');
  if (spy?.above_sma_200 === false) reasons.push('SPY below 200D');
  if (qqq?.above_sma_50 === false) reasons.push('QQQ below 50D');
  if (regime.breadth_50_pct != null) reasons.push(`50D breadth ${fxPct(regime.breadth_50_pct)}`);
  if (regime.breadth_200_pct != null) reasons.push(`200D breadth ${fxPct(regime.breadth_200_pct)}`);
  if (regime.distribution_days != null) reasons.push(`${fxNum(regime.distribution_days)} distribution days`);
  return reasons.length ? reasons : ['No regime details yet'];
}

export function countLabel(count, total) {
  if (count == null || total == null || Number(total) <= 0) return 'n/a';
  return `${count}/${total} names`;
}

export function postureText(value) {
  if (value === true) return 'above';
  if (value === false) return 'below';
  return 'n/a';
}

export function trendPhrase(above50, above200) {
  if (above50 === true && above200 === true) return 'Above 50D and 200D';
  if (above50 === false && above200 === false) return 'Below 50D and 200D';
  if (above50 === true && above200 === false) return 'Above 50D, below 200D';
  if (above50 === false && above200 === true) return 'Below 50D, above 200D';
  return 'Trend data pending';
}

export function breadthTone(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 'var(--text-muted)';
  if (n >= 0.6) return 'var(--success)';
  if (n < 0.5) return 'var(--warning)';
  return 'var(--accent-blue)';
}

export function distributionTone(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 'var(--text-muted)';
  if (n >= 7) return 'var(--danger)';
  if (n >= 5) return 'var(--warning)';
  return 'var(--text-main)';
}

export function clamp01(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}

export function visualRange(values) {
  const finite = values.filter(value => Number.isFinite(value));
  if (!finite.length) return { min: 0, max: 1 };
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = max - min || Math.max(1, Math.abs(max) * 0.04);
  return { min: min - span * 0.18, max: max + span * 0.18 };
}

export function rangeToPct(value, range) {
  if (!Number.isFinite(value) || range.max === range.min) return 50;
  return Math.max(2, Math.min(98, ((value - range.min) / (range.max - range.min)) * 100));
}
