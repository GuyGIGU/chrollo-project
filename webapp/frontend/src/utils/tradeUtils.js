const OPTION_SYMBOL_RE = /^[A-Z.]+\s+\d{1,2}[A-Z]{3}\d{2}\s+[\d.]+\s+[CP]$/;

export const isOptionSymbol = (symbol) => (
  !!symbol && OPTION_SYMBOL_RE.test(String(symbol).trim())
);

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
