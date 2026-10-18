// "Fix the box" (his ask of Tue 13/10/2026, "if we can get the engine to draw like me", and
// Fri 17/10/2026, on MTLS: "build something to close the gap"): he corrects the reader's two
// lines on the fix page's daily chart, each click snapping to the bar's end point, and the fix is
// saved BESIDE the pair the reader showed. Pure: no DOM, no chart; node --test pins it. The hook
// (useBoxFix.js) does the clicks and the save, the page (BoxFixPage.jsx) draws the lines.

// The reader's parent box as the wire carries it (two_eyes.boxes), or null when it shows none.
export function readerPair(data) {
  const parent = (data?.two_eyes?.boxes || []).find((box) => box.role === 'parent');
  if (!parent) return null;
  return { r: parent.r, rDay: parent.r_day, s: parent.s, sDay: parent.s_day, opened: parent.opened };
}

// The empty draft: nothing drawn yet.
export const EMPTY_FIX = { r: null, rDay: null, s: null, sDay: null };

// The draft seated from the fix he saved on this chart before (the page opens on his latest word, so a
// save never replaces his lines with the reader's pair: Sat 18/10/2026, his DSGX lost 79.11 / 75.31 that way).
export function draftFromFix(fix) {
  if (!fix || fix.resistance == null || fix.support == null) return EMPTY_FIX;
  return { r: fix.resistance, rDay: fix.r_day, s: fix.support, sDay: fix.s_day };
}

// One click with the Resistance or the Support tool armed: the resistance lands on the bar's high,
// the support on its low, each remembering its day. The root swing is BC then AR after a rise and SC
// then AR after a fall (his word, Fri 17/10/2026: "what if we came from a down swing and the root
// swing is SC -> AR"), so either tool may come first; if the two lines end up crossed, the higher
// one is the resistance whatever he called them (the calibration page's own rule).
export function applyRailClick(draft, which, { date, bar }) {
  if (!date || !bar || !Number.isFinite(bar.high) || !Number.isFinite(bar.low)) return draft;
  const next = which === 'r' ? { ...draft, r: bar.high, rDay: date } : { ...draft, s: bar.low, sDay: date };
  if (next.r != null && next.s != null && next.s > next.r) {
    return { r: next.s, rDay: next.sDay, s: next.r, sDay: next.rDay };
  }
  return next;
}

// A draft is a box once both lines stand and the resistance sits over the support.
export function fixComplete(draft) {
  return draft?.r != null && draft?.s != null && draft.r > draft.s;
}

// Whether his box differs from the reader's to the cent (a fix that agrees is still worth saving:
// a chart he looked at and left as it was says "the box is right").
export function fixDiffers(draft, reader) {
  if (!fixComplete(draft)) return false;
  if (!reader) return true;
  return Math.abs(draft.r - reader.r) >= 0.005 || Math.abs(draft.s - reader.s) >= 0.005;
}

// The request body: his two lines, the reader's pair beside them, the chart's last day and the
// reader's stamp that night (the scan identity's engine_config_version, which hashes the ruleset).
export function fixPayload(ticker, data, draft, scanIdentity = null) {
  const candles = data?.candles || [];
  const reader = readerPair(data);
  return {
    ticker,
    scan_day: candles.length ? candles[candles.length - 1].time : null,
    resistance: draft.r,
    r_day: draft.rDay,
    support: draft.s,
    s_day: draft.sDay,
    reader_resistance: reader?.r ?? null,
    reader_r_day: reader?.rDay ?? null,
    reader_support: reader?.s ?? null,
    reader_s_day: reader?.sDay ?? null,
    reader_opened_day: reader?.opened ?? null,
    ruleset: scanIdentity?.engine_config_version || '',
    note: null,
  };
}
