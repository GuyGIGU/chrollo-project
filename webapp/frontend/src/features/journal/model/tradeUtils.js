const HUMAN_OPTION_SYMBOL_RE = /^([A-Z.]+)\s+\d{1,2}[A-Z]{3}\d{2}\s+[\d.]+\s+[CP]$/;
const IBKR_LOCAL_OPTION_SYMBOL_RE = /^([A-Z.]+)\s+\d{6}[CP]\d{8}$/;
const OCC_OPTION_SYMBOL_RE = /^([A-Z.]{1,6})\d{6}[CP]\d{8}$/;

export const isOptionSymbol = (symbol) => {
  if (!symbol) return false;
  const value = String(symbol).trim().toUpperCase().replace(/\s+/g, ' ');
  const compact = value.replace(/\s+/g, '');
  return HUMAN_OPTION_SYMBOL_RE.test(value) ||
    IBKR_LOCAL_OPTION_SYMBOL_RE.test(value) ||
    OCC_OPTION_SYMBOL_RE.test(compact);
};

export const optionUnderlyingSymbol = (symbol) => {
  if (!symbol) return '';
  const value = String(symbol).trim().toUpperCase().replace(/\s+/g, ' ');
  const compact = value.replace(/\s+/g, '');
  return (
    value.match(HUMAN_OPTION_SYMBOL_RE)?.[1] ||
    value.match(IBKR_LOCAL_OPTION_SYMBOL_RE)?.[1] ||
    compact.match(OCC_OPTION_SYMBOL_RE)?.[1] ||
    ''
  );
};

export const inferDirection = (trade) => {
  const direction = String(trade?.direction || '').toUpperCase();
  if (direction === 'L' || direction === 'LONG') return 'LONG';
  if (direction === 'S' || direction === 'SHORT') return 'SHORT';

  const entry = Number(trade?.entry_price);
  const stop = Number(trade?.stop_loss);
  if (Number.isFinite(entry) && Number.isFinite(stop) && stop !== 0) {
    return stop < entry ? 'LONG' : 'SHORT';
  }
  return 'LONG';
};
