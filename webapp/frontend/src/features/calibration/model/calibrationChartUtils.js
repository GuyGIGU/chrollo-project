// Pure decision logic for the calibration chart lookup (node --test'able —
// Council Review 2026-07-11, finding 13 tail). No fetch, no React: the hook
// owns IO and state; THIS module owns the judgments a regression would
// silently break.

export const normalizeTicker = (t) => (t || '').trim().toUpperCase();

export const cacheKey = (ticker, asOf) => `${normalizeTicker(ticker)}|${asOf}`;

// Every key a successful payload answers: the requested key, plus the
// resolved-session alias (a Sunday and its Friday are ONE payload).
export function cacheKeysFor(requestKey, body) {
  const keys = [requestKey];
  const resolved = body?.as_of_session && `${body.ticker}|${body.as_of_session}`;
  if (resolved && resolved !== requestKey) keys.push(resolved);
  return keys;
}

// One judgment for "what did the backend actually say": a real chart payload,
// a named failure, the stale-service SPA catch-all (a 200 that isn't a chart
// — the running service predates the endpoint), or an unclassified failure.
export function classifyChartResponse(ok, status, body) {
  if (ok) {
    if (Array.isArray(body?.candles)) return { kind: 'chart', body };
    return {
      kind: 'failure',
      failure: {
        class: 'service_stale',
        message: 'the running dashboard service does not know /calibration yet',
      },
    };
  }
  const detail = body?.detail;
  return {
    kind: 'failure',
    failure: detail?.class
      ? detail
      : { class: 'unknown', message: `lookup failed (${status})` },
  };
}
