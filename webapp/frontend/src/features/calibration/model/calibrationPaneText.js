// The chart pane's words on the Calibration page: the lookup states (blank /
// loading / failure classes) and the engine chip. Presentational copy only
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
  return 'Enter a ticker and an as-of date. The chart renders on Chrollo’s own '
    + 'data — marks drawn here are born on the exact frame the engine replays.';
}

// The one-line notice a failed lookup rides above the last good chart with. A
// transient rate-limit is not an error, so it does not say "failed".
export function failureNotice(failure) {
  return failure.class === 'rate_limited'
    ? `Vendor busy. ${paneBody(false, failure)}`
    : `Lookup failed — ${failure.class}. ${paneBody(false, failure)}`;
}

export function engineLine(engineRead, engineStatus) {
  if (engineStatus === 'loading') return 'engine: reading…';
  if (engineStatus) return `engine: ${engineStatus}`;
  if (!engineRead) return 'engine: —';
  if (!engineRead.elected) {
    // Operator's terms (2026-07-21): a plain verdict, not the raw detector
    // reason ("no structure elects within the snap window") — that moves to the
    // chip's hover title for when the diagnostic is actually wanted.
    return 'engine: does NOT confirm your box here';
  }
  const snap = engineRead.snapped
    ? ` (snapped −${engineRead.snapped})` : '';
  return `engine finds a box — R ${fx(engineRead.R, 2)} / S ${fx(engineRead.S, 2)}`
    + ` · from ${engineRead.box_start_date} @ ${engineRead.eval_session}${snap}`;
}

// The raw detector reason, kept off the headline but one hover away — so "why
// didn't it confirm?" is answerable without cluttering the plain verdict.
export function engineTitle(engineRead) {
  if (engineRead && !engineRead.elected && engineRead.reason) {
    return `engine detail: ${engineRead.reason}`;
  }
  return undefined;
}
