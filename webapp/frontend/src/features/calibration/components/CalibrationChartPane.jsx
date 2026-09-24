import CandleChart from '../../../shared/charts/CandleChart';
import { CHART_FONT, surfaceOf } from '../../../shared/charts/chartTheme';
import {
  engineLine,
  engineTitle,
  failureNotice,
  paneBody,
  paneTitle,
} from '../model/calibrationPaneText';

// The calibration page's fixed, never-shifting chart pane: the retained chart
// with its in-pane overlays (lookup failure, engine chip, refused-placement
// notice, data warnings), or — before the first good lookup — the blank /
// loading / failure message in the chart's own skin. Every state renders INSIDE
// the pane so the operator's eyes never lose their place. Dumb — all state in
// the parent.
function CalibrationChartPane({
  chartData, spec, loading, failure,
  engineOn, engineRead, engineStatus,
  placeNotice, warningsOpen, onDismissWarnings,
}) {
  return (
    <div className="instrument-well"
         style={{ flex: 1, minHeight: 420, position: 'relative',
                  borderRadius: 8, overflow: 'hidden' }}>
      {chartData ? (
        <>
          <CandleChart
            spec={spec}
            className="calibration-chart"
            style={{ position: 'absolute', inset: 0 }}
            errorFallback={<PaneMessage title="Chart failed to draw" body="Reload the lookup." />}
            emptyFallback={<PaneMessage title="No drawable bars" body="Every bar in this window was non-finite." />}
          />
          {failure && (
            // A failed step never wipes the working chart — the last good
            // frame stays up and the failure rides above it. A transient
            // rate-limit is not an error: it wears the calm warning ink, not
            // danger red, so a self-healing hiccup never trains distrust.
            <div style={{
              position: 'absolute', top: 8, left: 8, right: 8, zIndex: 5,
              padding: '6px 10px', borderRadius: 6, fontSize: 12,
              border: `1px solid ${surfaceOf('modal').border}`,
              borderLeft: `2px solid ${failure.class === 'rate_limited' ? 'var(--warning)' : 'var(--danger)'}`,
              background: 'rgba(23, 25, 34, 0.92)',
            }}>
              {failureNotice(failure)}
            </div>
          )}
          {engineOn && (
            // What the engine thinks, in words — rails land on the chart in
            // engine ink; this chip carries the session/no-read verdict.
            <div title={engineTitle(engineRead)} style={{
              position: 'absolute', top: 8, right: 8, zIndex: 4,
              fontSize: 11, fontFamily: CHART_FONT, color: 'var(--text-muted)',
              fontVariantNumeric: 'tabular-nums',
              background: 'rgba(23, 25, 34, 0.85)', padding: '3px 8px',
              borderRadius: 6,
            }}>
              {engineLine(engineRead, engineStatus)}
            </div>
          )}
          {placeNotice && (
            // Why a click was refused (top-center, out of the rails' way): a
            // geometry mark placed past the as-of line, or a Trigger outside
            // its forward window. Neutral warning ink — a placement that does
            // not fit, not an error. Clears when the tool/frame changes or a
            // valid placement lands.
            <div style={{
              position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
              zIndex: 6, fontSize: 11, color: 'var(--warning)',
              border: '1px solid color-mix(in srgb, var(--warning) 55%, transparent)',
              background: 'rgba(23, 25, 34, 0.92)', padding: '3px 10px',
              borderRadius: 6, whiteSpace: 'nowrap',
            }}>
              {placeNotice}
            </div>
          )}
          {chartData.warnings?.length > 0 && warningsOpen && (
            // Warnings live INSIDE the pane (bottom edge) — the chart's geometry
            // never shifts when a lookup gains or loses one. Dismissible with the
            // × since the banner can sit over the date axis (operator 2026-07-21);
            // it re-shows on the next frame that carries a notice.
            <div style={{
              position: 'absolute', bottom: 8, left: 8, zIndex: 5,
              maxWidth: 'calc(100% - 16px)',
              display: 'flex', alignItems: 'flex-start', gap: 6,
              fontSize: 11, color: 'var(--accent-yellow)',
              background: 'rgba(23, 25, 34, 0.85)', padding: '3px 8px',
              borderRadius: 6,
            }}>
              <div>{chartData.warnings.map((w) => <div key={w}>{w}</div>)}</div>
              <button type="button" onClick={onDismissWarnings}
                      aria-label="Dismiss data notice"
                      title="Dismiss (re-shows on the next frame with a notice)"
                      style={{ background: 'none', border: 'none', color: 'inherit',
                               cursor: 'pointer', fontSize: 13, lineHeight: 1,
                               padding: '0 2px', opacity: 0.75 }}>
                ×
              </button>
            </div>
          )}
        </>
      ) : (
        <PaneMessage
          title={paneTitle(loading, failure)}
          body={paneBody(loading, failure)}
          danger={!loading && !!failure && failure.class !== 'rate_limited'}
        />
      )}
    </div>
  );
}

function PaneMessage({ title, body, danger = false }) {
  // The pane states wear the modal chart's OWN skin (imported, never
  // hand-copied hexes) so blank/loading/failure and the drawn chart read as
  // one surface; a failure gets one restrained semantic cue.
  const skin = surfaceOf('modal');
  return (
    <div style={{
      position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 6,
      border: `1px solid ${skin.border}`, borderRadius: 8,
      background: skin.background,
    }}>
      <div style={{ fontWeight: 600,
                    color: danger ? 'var(--danger)' : 'var(--text-main)' }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-faint)', maxWidth: 520,
                    textAlign: 'center' }}>
        {body}
      </div>
    </div>
  );
}

export default CalibrationChartPane;
