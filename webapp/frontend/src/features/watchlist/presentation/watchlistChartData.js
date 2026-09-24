// Pure data-source resolution for the Watchlist page — the page's real
// branching logic, kept out of JSX so node --test can pin it.
//
// The atomic pane-data contract (the load-bearing rule): a pane renders ONE
// artifact wholesale — the scan row (candles + rails + spans together) when
// the overlay is drawn, or the endpoint envelope's bare candles when it is
// not. There is NO field-level mixing path: the overlay's structure coloring
// and window framing are index-arithmetic against the exact candle array
// that shipped with the scan row, so scan overlay fields can never land on
// endpoint candles.

// Plain words for every no-candles reason (the endpoint's closed verdict
// vocabulary + the store's two transport states) — the operator reads an
// actual reason in the affected pane, never a generic "something went wrong".
export const CANDLE_REASON_COPY = {
  loading: 'loading candles…',
  error: 'candle fetch failed — reselect to retry',
  unknown_ticker: 'no cached candles for this name',
  no_cache: 'market-data cache unavailable',
  no_drawable_bars: 'no drawable history for this name',
};

// The rendered selection is DERIVED, never repaired by an effect: the chosen
// ticker while it is still on the list, else the first record, else null.
export function resolveRenderedSelection(chosen, records) {
  if (!records || !records.length) return null;
  if (chosen && records.some((r) => r.ticker === chosen)) return chosen;
  return records[0].ticker;
}

const EMPTY_FRAME = { candles: [], volumes: [], box: null };

function endpointFrame(envelope, key) {
  const frame = (envelope.frames || {})[key] || {};
  return {
    candles: frame.candles || [],
    volumes: frame.volumes || [],
    box: null, // EC-28: no engine read rides the candle wire — clean chart
  };
}

// One selected ticker's pane bundle from the two possible sources.
// `endpointEntry` is the candle store's cell: { status, envelope } or
// undefined while nothing has been asked yet.
export function resolvePaneData({ scanEntry, scanDate, endpointEntry, overlayOn }) {
  const overlayAvailable = Boolean(scanEntry);
  const overlayDrawn = Boolean(overlayOn && scanEntry);

  if (overlayDrawn) {
    return {
      source: 'scan',
      overlayAvailable,
      overlayDrawn,
      reason: null,
      // The daily pane consumes the scan row WHOLESALE — candles, rails,
      // spans, htf fields together, exactly as the Screener modal does.
      daily: scanEntry,
      weekly: {
        candles: scanEntry.weekly_candles || [],
        volumes: scanEntry.weekly_volumes || [],
        box: scanEntry.weekly_box || null,
      },
      monthly: {
        candles: scanEntry.monthly_candles || [],
        volumes: scanEntry.monthly_volumes || [],
        box: scanEntry.monthly_box || null,
      },
      provenance: {
        scanDate: scanDate || null,
        lastBarDate: null,
        priceSeries: null,
        forming: { weekly: null, monthly: null },
      },
    };
  }

  const envelope = endpointEntry?.status === 'ready' ? endpointEntry.envelope : null;
  if (envelope && envelope.status === 'ok') {
    // ONE access discipline for the whole envelope: every frame read goes
    // through the defensive accessor's fallbacks — never a bare deep reach
    // beside a guarded one.
    const frames = envelope.frames || {};
    const daily = frames.daily || {};
    return {
      source: 'endpoint',
      overlayAvailable,
      overlayDrawn: false,
      reason: null,
      // Clean chart: the SAME components fed less data — bare candles and
      // volumes, no overlay fields at all.
      daily: { candles: daily.candles || [], volumes: daily.volumes || [] },
      weekly: endpointFrame(envelope, 'weekly'),
      monthly: endpointFrame(envelope, 'monthly'),
      provenance: {
        scanDate: null,
        lastBarDate: envelope.last_bar_date || null,
        priceSeries: envelope.price_series || null,
        forming: {
          weekly: (frames.weekly || {}).forming_last_bar ?? null,
          monthly: (frames.monthly || {}).forming_last_bar ?? null,
        },
      },
    };
  }

  // Nothing drawable: name the reason — the endpoint's own verdict when it
  // answered ("unknown_ticker" / "no_cache" / "no_drawable_bars"), else the
  // store status ('loading' / 'error').
  let reason = 'loading';
  if (envelope) reason = envelope.status;
  else if (endpointEntry?.status === 'error') reason = 'error';
  return {
    source: null,
    overlayAvailable,
    overlayDrawn: false,
    reason,
    daily: null,
    weekly: { ...EMPTY_FRAME },
    monthly: { ...EMPTY_FRAME },
    provenance: {
      scanDate: null, lastBarDate: null, priceSeries: null,
      forming: { weekly: null, monthly: null },
    },
  };
}

// The card grid's per-ticker sourcing. A card renders ONE source wholesale:
// a scan-backed name carries the scan row itself ('scan' — the full screener
// card, rails and all), an off-scan name carries the endpoint batch's bare
// daily candles ('clean'), and anything undrawable is a 'void' with its named
// reason. Only names in neither source join the ONE batched endpoint fetch.
export function cardPlan(tickers, scanChartData, batchCells) {
  const cards = {};
  const toFetch = [];
  for (const ticker of tickers || []) {
    const entry = (scanChartData || {})[ticker];
    if (entry && (entry.candles || []).length) {
      cards[ticker] = { kind: 'scan', data: entry };
      continue;
    }
    const fetched = (batchCells || {})[ticker];
    if (fetched) {
      // The clean card's data IS the store cell (stable identity): the mini
      // chart's rebuild check keys on the data reference, so re-wrapping
      // here would tear down every clean card's chart on each plan run.
      cards[ticker] = fetched.status === 'ok'
        ? { kind: 'clean', data: fetched }
        : { kind: 'void', reason: fetched.status };
      continue;
    }
    cards[ticker] = { kind: 'void', reason: 'loading' };
    toFetch.push(ticker);
  }
  return { cards, toFetch };
}
