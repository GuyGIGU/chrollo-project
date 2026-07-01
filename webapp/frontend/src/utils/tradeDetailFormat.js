// Display formatters for the trade-detail drawer metrics (Live / P&L / To Stop /
// Next Target). These are all no-multiply: the derived values they receive are
// already in their final unit (P&L in dollars, distances in percent, R in Rs),
// so they REUSE the no-multiply `fmtMoney` from tradeTableUtils. Do NOT swap in
// the portfolioFormat.fmtMoney (currency-aware) or any percent formatter that
// multiplies by 100 — the audit flagged a multiply/no-multiply collision, and
// the drawer's inputs are the no-multiply family. Extracted verbatim from
// TradeDetailDrawer.jsx to preserve byte-identical output.

import { fmtMoney } from './tradeTableUtils';

export const moneyValue = (value) => (value == null ? '-' : `$${fmtMoney(value)}`);

export const signedMoney = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value) >= 0 ? '+' : '-'}$${fmtMoney(Math.abs(Number(value)))}`;
};

export const formatPct = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value).toFixed(1)}%`;
};

export const formatR = (value, signed = false) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${signed && Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}R`;
};

export const targetValue = (target) => (
  target ? `${target.label} $${fmtMoney(target.price)}` : '-'
);

export const targetDistance = (target) => {
  if (!target || target.distToTargetPct == null || !Number.isFinite(Number(target.distToTargetPct))) return '-';
  return `${formatPct(target.distToTargetPct)} / ${formatR(target.rToTarget)}`;
};

export const targetSub = (target, ladder) => {
  if (target) return `${targetDistance(target)} away`;
  return ladder?.length ? 'Complete' : 'No target';
};

export const sourceLabel = (source) => {
  if (source === 'ibkr') return 'IBKR';
  if (source === 'yf') return 'Live quote';
  if (source === 'fills') return 'Fills';
  return 'No quote';
};

export const signedTone = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  if (Number(value) > 0) return 'success';
  if (Number(value) < 0) return 'danger';
  return 'muted';
};

export const toneColor = (tone) => {
  if (tone === 'success') return 'var(--success)';
  if (tone === 'danger' || tone === 'breached') return 'var(--danger)';
  if (tone === 'warning') return 'var(--warning)';
  if (tone === 'target') return 'var(--accent-blue)';
  if (tone === 'muted') return 'var(--text-muted)';
  return 'var(--text-main)';
};
