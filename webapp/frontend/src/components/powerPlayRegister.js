// The Power-Play register's pure projection (program Task 14; the
// setupStoryRows precedent): payload market_context.power_play -> display
// rows. Node-tested; no thresholds, no color ramps, no client judgments —
// the status token arrives server-derived (EC-28) and is passed through with
// its signed label. Numbers render through the house fx null-guard
// (utils/format.js — the app's ONE guard, never re-declared here): null is
// an em-dash ("not measured"), never 0, never red.

import { fx } from '../utils/format.js';
import { powerPlayStatusLabel } from './wireVocabulary.js';

// Register rows open with the ticker, so the shared species prefix would
// repeat as dead words on every line ("MAN — Power Play — …") and push the
// differentiator to the wrap point (2026-08-17 review, Saarinen). The rows
// render the label's TAIL; label-alone surfaces keep the full signed label.
const LABEL_PREFIX = 'Power Play — ';
export const statusTail = (label) =>
  label.startsWith(LABEL_PREFIX) ? label.slice(LABEL_PREFIX.length) : label;

export function powerPlayRows(marketContext) {
  const block = marketContext?.power_play;
  const candidates = Array.isArray(block?.candidates) ? block.candidates : [];
  // A malformed ELEMENT drops quietly rather than throwing mid-render — the
  // stated absent/malformed-context contract covers the rows too
  // (2026-08-17 review, Dodds).
  return candidates
    .filter((c) => c && typeof c === 'object' && !Array.isArray(c))
    .map((c) => {
      const statusLabel = powerPlayStatusLabel(c.status);
      return {
        ticker: c.ticker,
        status: c.status,                    // the wire token, untouched
        statusLabel,
        statusTail: statusTail(statusLabel),
        // Plain facts in one monospace-friendly meta line — dates and raw
        // measures only, in the operator's chart words.
        meta: [
          c.climax ? `climax ${c.climax}` : null,
          c.ar ? `AR ${c.ar}` : null,
          c.breakout ? `breakout ${c.breakout}` : null,
          c.pole_gain != null ? `pole ${fx(c.pole_gain * 100, 0)}%` : null,
          c.depth != null ? `depth ${fx(c.depth * 100, 1)}%` : null,
          c.clock != null ? `clock ${c.clock}` : null,
        ].filter(Boolean).join(' · '),
      };
    });
}

export function powerPlayCounts(marketContext) {
  const counts = marketContext?.power_play?.counts;
  return counts && typeof counts === 'object' ? counts : null;
}
