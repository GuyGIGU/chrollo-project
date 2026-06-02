export const emptyValue = '-';

export const fmtMoney = (value, currency = 'USD') => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return emptyValue;
  const numberValue = Number(value);
  const sign = numberValue < 0 ? '-' : '';
  const abs = Math.abs(numberValue).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}$${abs}${currency && currency !== 'USD' ? ` ${currency}` : ''}`;
};

export const fmtNum = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return emptyValue;
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

export const fmtPct = (value, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return emptyValue;
  return `${Number(value).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
};

export const fmtTime = (value) => {
  if (!value) return emptyValue;
  try {
    const raw = Number(value);
    const date = Number.isFinite(raw)
      ? new Date(raw < 1e12 ? raw * 1000 : raw)
      : new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
  } catch {
    return String(value);
  }
};

export const pnlColor = (value) => {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue) || numberValue === 0) return 'var(--text-muted)';
  return numberValue > 0 ? 'var(--success)' : 'var(--danger)';
};

export const summaryValue = (summary, key) => {
  const direct = summary?.values?.[key];
  if (direct !== null && direct !== undefined) return direct;

  const rawBuckets = Object.values(summary?.raw || {});
  let numericTotal = 0;
  let hasNumeric = false;
  let fallback = undefined;

  rawBuckets.forEach((bucket) => {
    const entry = bucket?.[key];
    if (!entry) return;
    const rawValue = entry.value;
    const numberValue = Number(rawValue);
    if (rawValue !== '' && Number.isFinite(numberValue)) {
      numericTotal += numberValue;
      hasNumeric = true;
    } else if (fallback === undefined) {
      fallback = rawValue;
    }
  });

  if (hasNumeric) return numericTotal;
  return fallback;
};

export const summaryCurrency = (summary, key) => {
  const direct = summary?.currency?.[key];
  if (direct) return direct;

  for (const bucket of Object.values(summary?.raw || {})) {
    const currency = bucket?.[key]?.currency;
    if (currency) return currency;
  }
  return undefined;
};
