import { useMemo, useState } from 'react';
import CandleChart from './CandleChart';
import useCalibrationChart from '../hooks/useCalibrationChart';
import { baseChartOptions } from './chartTheme';

// The Calibration page (Calibration at Scale, Task 10): pull up ANY ticker at
// ANY historical as-of date on Chrollo's own data. The chart is the
// protagonist — one compact command band above a fixed, never-shifting chart
// pane whose lookup states (blank / loading / failure classes / ideal) render
// INSIDE the pane so the operator's eyes never lose their place between the
// dozens of lookups a marking sitting takes. The interactive marking layer
// (click-to-place rails, worklist loop, verdicts) lands on this shell next
// (Tasks 11-12); this page deliberately owns all its state — nothing in
// AppShell, no app-level context.
const fx = (v, d) => ((v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d));

const FAILURE_HINTS = {
  bad_ticker: 'Tickers are 1-10 chars: A-Z, 0-9, dot or dash.',
  bad_date: 'Dates are YYYY-MM-DD, 2000 or later.',
  future_date: 'Pick a past session.',
  no_data: 'Unknown or delisted ticker — or the vendor hiccuped; retry once.',
  no_bars_at_date: 'This ticker has no history at that date; try a later one.',
  network: 'Start the dashboard service, then retry.',
  service_stale: 'Run update_dashboard.bat to load the new backend, then retry.',
  freeze_failed: 'Check disk space / calibration_frames permissions, then retry.',
  unknown: 'Retry once; if it persists, check the service log.',
};

function CalibrationTab() {
  const { chartData, loading, failure, load } = useCalibrationChart();
  const [ticker, setTicker] = useState('');
  const [asOf, setAsOf] = useState('');

  // On success the date input snaps to the RESOLVED session, so input,
  // provenance strip and chart always name the same session; on failure the
  // input keeps whatever the operator typed (nothing is poisoned).
  const lookup = async (t, date) => {
    const result = await load(t, date);
    if (result) setAsOf(result.as_of_session);
  };

  const submit = (event) => {
    event?.preventDefault();
    if (ticker.trim() && asOf) lookup(ticker, asOf);
  };

  // Day-scrub: step the SERVER-NAMED adjacent sessions (never guessed
  // calendar days — a Friday's "next day" is Monday, not a Saturday that
  // resolves straight back to Friday). Cached revisits are instant; each
  // NEW session costs one bounded fetch (it also freezes that session's
  // frame server-side, which a mark needs anyway).
  const scrub = (direction) => {
    const target = direction < 0 ? chartData?.prev_session : chartData?.next_session;
    if (target) lookup(chartData.ticker, target);
  };

  const spec = useMemo(() => ({
    chartOptions: (container) => ({
      ...baseChartOptions('modal', container.clientWidth, container.clientHeight),
      handleScroll: true,
      handleScale: true,
    }),
    candles: chartData?.candles,
    volumes: chartData?.volumes,
    showVolume: true,
    onResize: (chart, container) => chart.applyOptions({
      width: container.clientWidth, height: container.clientHeight,
    }),
    deps: [chartData],
  }), [chartData]);

  return (
    <div className="calibration-page" style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>
      <form className="screener-command-band" onSubmit={submit}
            style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ letterSpacing: '0.04em' }}>CALIBRATION</strong>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker"
          aria-label="Ticker"
          style={{ width: 110, fontFamily: 'inherit' }}
        />
        <input
          type="date"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
          aria-label="As-of date"
        />
        <button type="submit" disabled={loading || !ticker.trim() || !asOf}>
          {loading ? 'Loading…' : 'Load'}
        </button>
        {chartData && (
          <>
            <button type="button" onClick={() => scrub(-1)}
                    disabled={loading || !chartData.prev_session}
                    title={chartData.prev_session ? 'Previous session' : 'At the left edge of the fetched window'}>
              ◀ day
            </button>
            <button type="button" onClick={() => scrub(1)}
                    disabled={loading || !chartData.next_session}
                    title={chartData.next_session ? 'Next session' : 'No later session in the fetched window'}>
              day ▶
            </button>
            <span style={{ opacity: 0.8 }}>
              {chartData.ticker} @ {chartData.as_of_session} · close {fx(chartData.anchor_close, 2)}
              {' '}· {chartData.bar_count} bars · {chartData.data_regime}
            </span>
          </>
        )}
      </form>

      {chartData?.warnings?.length > 0 && (
        <div style={{ fontSize: 12, opacity: 0.85 }}>
          {chartData.warnings.map((w) => <div key={w}>⚠ {w}</div>)}
        </div>
      )}

      <div style={{ flex: 1, minHeight: 420, position: 'relative' }}>
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
              // frame stays up and the failure rides above it.
              <div style={{
                position: 'absolute', top: 8, left: 8, right: 8, zIndex: 5,
                padding: '6px 10px', borderRadius: 6, fontSize: 12,
                border: '1px solid #2f3447', background: 'rgba(23, 25, 34, 0.92)',
              }}>
                Lookup failed — {failure.class}. {paneBody(false, failure)}
              </div>
            )}
          </>
        ) : (
          <PaneMessage
            title={paneTitle(loading, failure)}
            body={paneBody(loading, failure)}
          />
        )}
      </div>
    </div>
  );
}

function paneTitle(loading, failure) {
  if (loading) return 'Loading…';
  if (failure) return `Lookup failed — ${failure.class}`;
  return 'Pull up a chart';
}

function paneBody(loading, failure) {
  if (loading) return 'Fetching candles through the provider (bounded).';
  if (failure) {
    const hint = FAILURE_HINTS[failure.class];
    return hint ? `${failure.message}. ${hint}` : failure.message;
  }
  return 'Enter a ticker and an as-of date. The chart renders on Chrollo’s own '
    + 'data — marks drawn here are born on the exact frame the engine replays.';
}

function PaneMessage({ title, body }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 6,
      border: '1px solid #2f3447', borderRadius: 8, background: '#171922',
    }}>
      <div style={{ fontWeight: 600 }}>{title}</div>
      <div style={{ fontSize: 12, opacity: 0.75, maxWidth: 520, textAlign: 'center' }}>{body}</div>
    </div>
  );
}

export default CalibrationTab;
