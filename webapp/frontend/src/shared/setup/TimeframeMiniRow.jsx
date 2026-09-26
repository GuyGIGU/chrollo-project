import TimeframeMainChart from '../charts/TimeframeMainChart';
import { htfStateLabel } from './screenerCardData';

// The W/M preview column beside the daily chart: two medium non-interactive
// cubes of the SAME higher-timeframe read the D/W/M tabs open full-pane (same
// rails, coloring — TimeframeMainChart in interactive=false mode, which takes
// the shallow htfPreview window so bars stay readable at cube width). Each
// pane's caption is the timeframe's structural state (htfStateLabel), and
// clicking a pane switches the modal to that interval. A pane with no resampled
// candles renders nothing; with neither, the column disappears.

function MiniPane({ tf, name, candles, volumes, box, state, onSelect }) {
  return (
    <div
      className="timeframe-mini-pane"
      role="button"
      tabIndex={0}
      aria-label={`Open the full ${name.toLowerCase()} chart — ${state.label}`}
      title={`Open the full ${name.toLowerCase()} chart`}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="timeframe-mini-caption">
        <span className="timeframe-mini-name">{name}</span>
        <span className="timeframe-mini-state" style={{ color: state.tone }}>{state.label}</span>
      </div>
      <div className="timeframe-mini-chart">
        <TimeframeMainChart
          box={box}
          candles={candles}
          interactive={false}
          label={tf === 'W' ? 'WEEKLY' : 'MONTHLY'}
          volumes={volumes}
        />
      </div>
    </div>
  );
}

export default function TimeframeMiniRow({ data, onSelectInterval }) {
  const panes = [];
  if (data?.weekly_candles?.length) {
    panes.push({
      tf: 'W',
      name: 'Weekly',
      candles: data.weekly_candles,
      volumes: data.weekly_volumes,
      box: data.weekly_box,
      state: htfStateLabel({
        stage2: data.htf_w_stage2, trendState: data.htf_w_trend_state,
        inConsol: data.htf_w_in_consol, phase: data.htf_w_phase, reaccum: data.htf_w_reaccum,
      }),
    });
  }
  if (data?.monthly_candles?.length) {
    panes.push({
      tf: 'M',
      name: 'Monthly',
      candles: data.monthly_candles,
      volumes: data.monthly_volumes,
      box: data.monthly_box,
      state: htfStateLabel({
        stage2: data.htf_m_stage2, trendState: data.htf_m_trend_state,
        inConsol: data.htf_m_in_consol, phase: data.htf_m_phase, reaccum: data.htf_m_reaccum,
      }),
    });
  }
  if (!panes.length) return null;

  return (
    <div className="timeframe-mini-col">
      {panes.map((pane) => (
        <MiniPane key={pane.tf} {...pane} onSelect={() => onSelectInterval(pane.tf)} />
      ))}
    </div>
  );
}
