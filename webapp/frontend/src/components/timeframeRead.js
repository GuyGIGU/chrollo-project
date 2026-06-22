// Plain-language structural read for one higher timeframe (tf is 'w' or 'm') —
// the same Trend+Box state the daily engine reports ("all relative and
// derivative"), surfaced as the caption on the modal's weekly/monthly charts.
// Kept apart from the chart component so that file only exports a component
// (keeps React Fast Refresh happy).
export function readState(data, tf) {
  const trendState = data[`htf_${tf}_trend_state`];
  const inConsol = data[`htf_${tf}_in_consol`];
  const phase = data[`htf_${tf}_phase`];
  const reaccum = data[`htf_${tf}_reaccum`];
  const stage2 = data[`htf_${tf}_stage2`];
  const trend = trendState === 'up' ? { sym: '▲', col: '#3fb950' }
    : trendState === 'down' ? { sym: '▼', col: '#f85149' }
      : trendState === 'neutral' ? { sym: '▬', col: '#8b949e' }
        : { sym: '·', col: 'var(--text-faint)' };
  let text = 'No base in view';
  let col = 'var(--text-faint)';
  if (reaccum) { text = `Re-accumulation${phase ? ` · Phase ${phase}` : ''}`; col = '#ff9f43'; }
  else if (inConsol) { text = `Consolidating${phase ? ` · Phase ${phase}` : ''}`; col = '#58a6ff'; }
  else if (stage2) { text = 'Stage-2 uptrend'; col = '#3fb950'; }
  else if (trendState == null || trendState === 'unknown') { text = 'Not enough history'; }
  else if (trendState === 'down') { text = 'Downtrend'; col = '#f85149'; }
  else { text = 'Neutral'; }
  return { trend, text, col, nested: data[`htf_${tf}_daily_nested`] };
}
