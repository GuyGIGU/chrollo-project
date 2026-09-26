// A single-purpose handoff out to TradingView for one symbol. Deliberately
// SEPARATE from the chart-peek action so a click is never ambiguous about
// whether it opens a quick look or launches an external app.
export default function BridgeOut({ ticker, compact = false }) {
  const url = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(ticker)}`;
  return (
    <a
      className="home-bridge"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      title={`Open ${ticker} on TradingView`}
    >
      {compact ? '↗' : '↗ TradingView'}
    </a>
  );
}
