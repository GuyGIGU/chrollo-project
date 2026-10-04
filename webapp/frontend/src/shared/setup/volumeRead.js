// Volume at key points (operator go-ahead 2026-10-04): his key points, the LPS
// pullback and the Phase C spring, each against the 50-day average volume. Shown,
// never graded (his answer 10: "Volume: no hard gates, no points"). The wire
// carries the ratios; this module only labels them (EC-28).
import { EMPTY, finiteOrNull, fx } from '../formatting/format.js';

export const volumeRatioLabel = (ratio) => {
  const n = finiteOrNull(ratio);
  return n == null ? EMPTY : `${fx(n, 2)}× avg`;
};

const NOT_GRADED = 'Shown, never graded.';

export const volumeCells = (data) => [
  {
    k: 'LPS pullback',
    v: volumeRatioLabel(data?.lps_volume_ratio),
    title: `The LPS pullback's average volume against the 50-day average (below 1 = quieter than usual). In the archive (2026-10-04), the quietest quarter of LPS pullbacks reached +25% about 2.5 times as often as the loudest. ${NOT_GRADED}`,
  },
  {
    k: 'Phase C spring',
    v: volumeRatioLabel(data?.spring_volume_ratio),
    title: `The spring day's volume against the 50-day average; a dash when the base has no spring. A quiet spring and a loud one that chokes off the sellers can both be constructive. ${NOT_GRADED}`,
  },
];

export const hasVolumeRead = (data) =>
  [data?.lps_volume_ratio, data?.spring_volume_ratio].some((value) => finiteOrNull(value) != null);
