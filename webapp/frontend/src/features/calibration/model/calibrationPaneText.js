// The chart pane's words on the Calibration page: the lookup states (blank /
// loading / failure classes) and the provenance chip. Presentational copy only
// (EC-28) — pure, so node --test pins it.
import { fx } from '../../../shared/formatting/format.js';

const FAILURE_HINTS = {
  bad_ticker: 'Tickers are 1-10 chars: A-Z, 0-9, dot or dash.',
  bad_date: 'Dates are YYYY-MM-DD, 2000 or later.',
  future_date: 'Pick a past session.',
  rate_limited: 'The data vendor is briefly throttling — any loaded chart stays up; wait a few seconds and retry.',
  no_data: 'Unknown/delisted ticker — or the vendor is briefly throttling; wait a moment and retry.',
  no_bars_at_date: 'This ticker has no history at that date; try a later one.',
  network: 'Start the dashboard service, then retry.',
  service_stale: 'Run update_dashboard.bat to load the new backend, then retry.',
  freeze_failed: 'Check disk space / calibration_frames permissions, then retry.',
  unknown: 'Retry once; if it persists, check the service log.',
};

export function paneTitle(loading, failure) {
  if (loading) return 'Loading…';
  if (failure) return `Lookup failed — ${failure.class}`;
  return 'Pull up a chart';
}

export function paneBody(loading, failure) {
  if (loading) return 'Fetching candles through the provider (bounded).';
  if (failure) {
    const hint = FAILURE_HINTS[failure.class];
    return hint ? `${failure.message}. ${hint}` : failure.message;
  }
  return 'Pick a setup on the right, or enter a ticker and a date. The chart renders on Chrollo’s own '
    + 'data — marks drawn here are born on the exact frame the engine replays.';
}

// The one-line notice a failed lookup rides above the last good chart with. A
// transient rate-limit is not an error, so it does not say "failed".
export function failureNotice(failure) {
  return failure.class === 'rate_limited'
    ? `Vendor busy. ${paneBody(false, failure)}`
    : `Lookup failed — ${failure.class}. ${paneBody(false, failure)}`;
}

// The pane's provenance chip (top-left): which frame is on screen. It moved
// out of the command band (operator ask 2026-10-02: the band "got to much dead
// space"). Figures change on every load, so the chip renders them mono.
export function provenanceLine(chartData) {
  return `${chartData.ticker} @ ${chartData.as_of_session} · close ${fx(chartData.anchor_close, 2)}`
    + ` · ${chartData.bar_count} bars · ${chartData.data_regime}`;
}

// A chart served from the preserved copy (the vendor lost the ticker — SKYT,
// 2026-10-02) says so on the chip itself, not only in the dismissible notice.
export const PRESERVED_LABEL = 'preserved copy';
const PRESERVED_WHY = {
  no_data: 'the vendor no longer serves the ticker',
  rate_limited: 'the vendor was throttling — reload the date later for its latest bars',
  vendor_error: 'the vendor failed on this request — reload the date later for its latest bars',
};
export function preservedTitle(reason) {
  return 'Drawn from the bars frozen when this chart was first loaded — '
    + `${PRESERVED_WHY[reason] ?? PRESERVED_WHY.no_data}. Marking and engine tests work as usual.`;
}
