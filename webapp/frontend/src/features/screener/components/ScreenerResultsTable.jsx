import { fx } from '../../../shared/formatting/format.js';
import { tierColor } from '../../../shared/presentation/theme';

// A second presentation of the exact same page, never a second ranking path.
export default function ScreenerResultsTable({ tickers, chartData, watchlist, liked, onOpen, onToggleWatchlist, onToggleLike }) {
  return (
    <div className="screener-results-table-wrap" role="region" aria-label="Setup comparison" tabIndex={0}>
      <table className="screener-results-table">
        <caption>Setups in the selected sort order. Open a ticker to inspect its chart.</caption>
        <thead>
          <tr>
            {['Ticker', 'Tier', 'TA / 100', 'Setup', 'Scan price', 'Trigger', 'RS', 'Base days', 'Watchlist', 'Liked'].map((label) => (
              <th key={label} scope="col">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => {
            const data = chartData[ticker];
            return (
              <tr key={ticker}>
                <th scope="row">
                  <button type="button" className="screener-result-open focus-ring" data-ticker={ticker}
                    aria-label={`Open ${ticker} chart`} onClick={() => onOpen(ticker)}>{ticker}</button>
                </th>
                <td style={{ color: tierColor(data.tier) }}>{data.tier || '—'}</td>
                <td>{fx(data.ta_grade, 0)}</td>
                <td className="screener-result-setup">{data.setup || '—'}</td>
                <td>{fx(data.price)}</td>
                <td>{fx(data.trigger)}</td>
                <td>{fx(data.rs_rating, 0)}</td>
                <td>{fx(data.base_len, 0)}</td>
                <td><button type="button" className="btn btn-sm" aria-label={`Watchlist ${ticker}`}
                  aria-pressed={watchlist.has(ticker)} onClick={() => onToggleWatchlist(ticker)}>
                  <span aria-hidden="true">{watchlist.has(ticker) ? '★' : '☆'}</span>
                </button></td>
                <td><button type="button" className="btn btn-sm" aria-label={`Like ${ticker}`}
                  aria-pressed={liked.has(ticker)} onClick={() => onToggleLike(ticker)}>
                  <span aria-hidden="true">{liked.has(ticker) ? '♥' : '♡'}</span>
                </button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
