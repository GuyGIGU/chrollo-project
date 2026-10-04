// His calibration setups on the Archive screen (operator ruling 2026-10-03:
// archived setups too). They list from their own route and never mix into the
// engine's episodes: they were chosen for quality, so every study keeps them a
// group of their own. Labels and routing only; every outcome arrives measured.

export const CALIBRATION_SOURCE = 'calibration';
export const isCalibration = (sourceFilter) => sourceFilter === CALIBRATION_SOURCE;

export const CALIBRATION_SORT_OPTIONS = [
  ['his_trigger_date', 'Buy day'],
  ['mfe_to_date', 'Best gain'],
  ['fwd_return_20d', '20d'],
  ['r_multiple_20d', 'R'],
  ['days_to_15pct', 'Days to +15%'],
  ['ticker', 'Ticker'],
];

// The sort each list opens on; a list switch resets to it, because the two lists
// share no sort key the other can read.
export const defaultSortFor = (sourceFilter) => (
  isCalibration(sourceFilter) ? 'his_trigger_date' : 'scan_date');

export const archiveListPath = (sourceFilter) => (
  isCalibration(sourceFilter) ? '/archive/calibration-setups' : '/archive/episodes');

// The barrier outcome in words: the wire carries the label, this only names it.
// No label yet means still inside its outcome window ("open"), or not measured.
export const calibrationResult = (row) => {
  if (row?.barrier_label === 'win') return row.win_barrier === '2.5R' ? 'win (2.5R)' : 'win (+15%)';
  if (row?.barrier_label === 'loss') return 'stopped';
  if (row?.barrier_label === 'timeout') return 'timed out';
  return row?.bars_to_date == null ? 'not measured' : 'open';
};
