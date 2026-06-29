import ScreenerMiniChart from '../ScreenerMiniChart';
import { tierColor } from '../../theme';

const scoreLabel = (v) => (v == null || !Number.isFinite(Number(v)) ? '-' : `${Math.round(Number(v))}`);

// A compact, chart-bearing setup tile for the Fresh Setups zone. Reuses the
// screener's mini-chart but drops the toggles/tags/score-pills so the Home tile
// reads as a quick "rank + shape" glance. Only the top few render, so the number
// of lightweight-charts instances on Home stays bounded.
export default function HomeSetupTile({ ticker, data, onClick }) {
  if (!data) return null;
  return (
    <div
      className="home-tile"
      role="button"
      tabIndex={0}
      aria-label={`Open ${ticker} — ${data.setup}, tier ${data.tier}, score ${scoreLabel(data.score)}`}
      onClick={() => onClick(ticker)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(ticker);
        }
      }}
    >
      <div className="home-tile-head">
        <span className="home-tile-ident">
          <span className="home-tile-ticker" style={{ color: tierColor(data.tier) }}>{ticker}</span>
          <span className="home-tile-tier" style={{ borderColor: `${tierColor(data.tier)}55`, color: tierColor(data.tier) }}>
            {data.tier}
          </span>
        </span>
        <span className="home-tile-score">{scoreLabel(data.score)}</span>
      </div>
      <div className="home-tile-chart">
        {/* Smaller bar budget than the wide screener cards: the Home tile is
            only ~165px wide, so 130 bars would be a 1px sliver. ~44-72 keeps
            it a readable, faithfully-proportioned glance. */}
        <ScreenerMiniChart ticker={ticker} data={data} maxBars={72} minBars={44} />
      </div>
    </div>
  );
}
