// Display formatters for the trade-detail drawer metrics (Live / P&L / To Stop /
// Next Target). These are all no-multiply: the derived values they receive are
// already in their final unit (P&L in dollars, distances in percent, R in Rs),
// so they compose the no-multiply primitives from shared/formatting/format. Do NOT swap in
// fmtMoneyUsd (currency-aware) or any percent formatter that multiplies by 100
// — the audit flagged a multiply/no-multiply collision, and the drawer's
// inputs are the no-multiply family.

import { EMPTY, finiteOrNull, fmtNum } from '../../../shared/formatting/format.js';
import { fmtMoney } from '../model/tradeTableUtils.js';

export const moneyValue = (value) => (value == null ? EMPTY : `$${fmtMoney(value)}`);

export const signedMoney = (value) => {
  const n = finiteOrNull(value);
  if (n == null) return EMPTY;
  return `${n >= 0 ? '+' : '-'}$${fmtNum(Math.abs(n))}`;
};

export const formatPct = (value) => {
  const n = finiteOrNull(value);
  return n == null ? EMPTY : `${n.toFixed(1)}%`;
};

export const formatR = (value, signed = false) => {
  const n = finiteOrNull(value);
  if (n == null) return EMPTY;
  return `${signed && n >= 0 ? '+' : ''}${n.toFixed(2)}R`;
};

export const targetValue = (target) => (
  target ? `${target.label} $${fmtMoney(target.price)}` : EMPTY
);

export const targetDistance = (target) => {
  if (!target || finiteOrNull(target.distToTargetPct) == null) return EMPTY;
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
