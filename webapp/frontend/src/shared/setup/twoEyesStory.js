// The two-eyes reader's read as the grade panel tells it (Tue 13/10/2026, his "the Grade section at the advanced chart
// block is completely broken").
//
// The old panel's columns are the old grade's chapters (Consolidation, Phase D, Trend), and a row the new reader wrote
// carries none of them: the panel showed a grade and one "not graded" LPS. The new reader's own read is its box, the
// words of its story, its mini and its LPS, so that is what this panel tells, left to right in the order the chart
// played them: the box from the day it opened, each word on its day, the mini from the day it opened, the LPS.
//
// Pure and node-tested. Every fact arrives resolved on the wire (EC-28): the box's height in its own daily ranges,
// each word's day, price, swing and size; this module only orders them and puts them into words. A row the archive
// stored carries no story (the archive keeps no event), and says so instead of showing an empty one.
import { storyRegionId } from '../charts/chartPhaseOverlay.js';
import { fmtDay, fx } from '../formatting/format.js';

// The words of the story: the name he uses, the phase each lives in (its hue, the same as its band on the chart).
export const STORY_WORDS = {
  spring: { name: 'Spring', phase: 'c', token: 'C' },
  'spring test': { name: 'Spring test', phase: 'c', token: 'C' },
  upthrust: { name: 'Upthrust', phase: 'b', token: 'B' },
  SOS: { name: 'SOS', phase: 'd', token: 'D' },
  'last supper': { name: 'Last supper', phase: 'd', token: 'D' },
  'Phase D': { name: 'Phase D', phase: 'd', token: 'D' },
};

// Where the LPS sat against the box it was read in: his three positions against the mini (Sun 13/09/2026).
const LPS_HOW = { in: 'in the mini', on: 'resting on the mini', near: 'near the mini' };

// "18/08" for the narrow rails; the tooltip carries the weekday and the year.
const dayMonth = (day) => {
  const match = String(day ?? '').match(/^\d{4}-(\d{2})-(\d{2})/);
  return match ? `${match[2]}/${match[1]}` : '';
};

const ranges = (value) => (value == null ? null : `${fx(value, 1, null)} daily range${fx(value, 1, null) === '1.0' ? '' : 's'}`);

// One word's sentence, short (the rail) and whole (the tooltip).
function wordSentence(event) {
  const size = ranges(event.size);
  const what = {
    spring: size ? `${size} under support` : 'under support',
    'spring test': `tests the spring at ${fx(event.price, 2)}`,
    upthrust: size ? `${size} over resistance` : 'over resistance',
    SOS: size ? `ran ${size}` : `topped at ${fx(event.price, 2)}`,
    'last supper': size ? `dropped ${size}` : 'a deep drop',
    'Phase D': event.note ? `opened by the ${event.note}` : 'the right side opens',
  }[event.kind] ?? '';
  const forming = event.committed === false ? ' · still forming' : '';
  const note = event.kind !== 'Phase D' && event.note ? ` · ${event.note}` : '';
  return {
    short: `${dayMonth(event.day)} · ${what}${forming}`,
    whole: `${STORY_WORDS[event.kind]?.name ?? event.kind}, ${fmtDay(event.day)}: ${what}${note}${forming}.`,
  };
}

const regionIds = (regions) => new Set((regions || []).map((region) => region.id));

function boxColumn(box, role, regions, grade) {
  const isParent = role === 'parent';
  const id = isParent ? 'b' : 'mini';
  const days = grade?.base_days;
  const filled = days ? (days - (grade.empty_days ?? 0)) / days : null;
  const lines = `R ${fx(box.r, 2)} / S ${fx(box.s, 2)}`;
  return {
    key: id,
    kind: 'chapter',
    // The mini wears the box's hue: one setup, read closer in (his ruling of Sun 20/09/2026).
    phase: 'b',
    token: isParent ? 'B' : 'M',
    name: isParent ? 'Box' : 'Mini',
    figure: box.ranges_tall == null ? null : fx(box.ranges_tall, 1, null),
    unit: box.ranges_tall == null ? null : 'ranges tall',
    detail: `${lines} · opened ${dayMonth(box.opened)}`,
    title: [
      `${isParent ? 'The box' : 'The mini, a smaller box inside the setup'}: ${lines}, opened ${fmtDay(box.opened)}.`,
      box.ranges_tall == null ? null : `It is ${fx(box.ranges_tall, 1)} of its own daily ranges tall.`,
      isParent && filled != null
        ? `The bar under the name fills with the base days that had a bar in the box: ${days - grade.empty_days} of ${days}.`
        : null,
    ].filter(Boolean).join(' '),
    fraction: isParent ? filled : null,
    region: regionIds(regions).has(id) ? id : null,
    day: box.opened,
  };
}

function lpsColumn(data, regions) {
  const lps = data.two_eyes.lps || {};
  const region = (regions || []).find((r) => r.id === 'lps:active') ?? null;
  const days = region ? region.endIndex - region.startIndex + 1 : null;
  const where = lps.against === 'mini' ? (LPS_HOW[lps.how] ?? 'against the mini') : 'in the box';
  const trigger = lps.trigger ?? data.trigger ?? null;
  const span = lps.start ? `${dayMonth(lps.start)}${lps.end && lps.end !== lps.start ? `–${dayMonth(lps.end)}` : ''}` : null;
  return {
    key: 'lps',
    kind: 'chapter',
    phase: 'lps',
    token: 'LPS',
    name: 'LPS',
    figure: trigger == null ? null : fx(trigger, 2, null),
    unit: trigger == null ? null : 'trigger',
    detail: [span, days ? `${days} receding day${days === 1 ? '' : 's'}` : null, where].filter(Boolean).join(' · '),
    title: [
      'The LPS: the last run of receding days.',
      lps.start ? `${fmtDay(lps.start)} to ${fmtDay(lps.end)}, read ${where}.` : `Read ${where}.`,
      trigger == null ? null : `The buy is a day that trades over ${fx(trigger, 2)}, the last receding day's high.`,
    ].filter(Boolean).join(' '),
    fraction: null,
    region: region ? region.id : null,
    day: lps.start ?? null,
  };
}

function wordColumn(event, regions) {
  const word = STORY_WORDS[event.kind] ?? { name: event.kind, phase: null, token: '•' };
  const sentence = wordSentence(event);
  const id = storyRegionId(event);
  return {
    key: id,
    kind: 'mark',
    phase: word.phase,
    token: word.token,
    name: word.name,
    figure: null,
    unit: null,
    detail: sentence.short,
    title: sentence.whole,
    fraction: null,
    region: regionIds(regions).has(id) ? id : null,
    day: event.day,
  };
}

// The columns in chart order: the box, the words and the mini by their day (a tie keeps that telling order), and the
// LPS last, where the story ends (an archived row stores no LPS day at all).
export function twoEyesStory(data, regions = []) {
  const block = data?.two_eyes;
  if (!block) return { columns: [], footnote: null };
  const boxes = block.boxes || [];
  const parent = boxes.find((box) => box.role === 'parent');
  const mini = boxes.find((box) => box.role === 'mini');
  const told = Array.isArray(block.events);
  const dated = [
    ...(parent ? [boxColumn(parent, 'parent', regions, block.grade)] : []),
    ...(told ? block.events.map((event) => wordColumn(event, regions)) : []),
    ...(mini ? [boxColumn(mini, 'mini', regions, null)] : []),
  ];
  const byDay = (a, b) => (a.day === b.day ? 0 : String(a.day ?? '') < String(b.day ?? '') ? -1 : 1);
  const ordered = [...dated.sort(byDay), lpsColumn(data, regions)];
  let footnote = null;
  if (!told) footnote = 'No story came with this row: the archive keeps the boxes and the grade, and the story (spring, SOS, last supper) rides the night\'s scan.';
  else if (block.events.length === 0) footnote = 'The reader named no spring, upthrust, SOS or last supper on this box.';
  return { columns: ordered, footnote };
}

// The technical read's cells for a two-eyes row: the facts of its own read instead of the old engine's counts, which
// such a row does not carry (they printed as dashes). The base runs from the day the box opened to the last candle.
export function twoEyesTechnicalCells(data, regions = []) {
  const block = data?.two_eyes || {};
  const parent = (block.boxes || []).find((box) => box.role === 'parent');
  const mini = (block.boxes || []).find((box) => box.role === 'mini');
  const box = (regions || []).find((region) => region.id === 'b');
  const lps = (regions || []).find((region) => region.id === 'lps:active');
  const width = parent && parent.s > 0 ? ((parent.r - parent.s) / parent.s) * 100 : null;
  const count = (region) => (region ? region.endIndex - region.startIndex + 1 : null);
  const daysText = (n) => (n == null ? '-' : `${n} day${n === 1 ? '' : 's'}`);
  return [
    { k: 'Box width', v: width == null ? '-' : `${fx(width, 1)}%` },
    { k: 'Box height', v: parent?.ranges_tall == null ? '-' : `${fx(parent.ranges_tall, 1)} ranges`, title: 'How many of its own daily ranges tall the box is' },
    { k: 'Base', v: daysText(count(box)), title: 'Trading days from the day the box opened to the last day on the chart' },
    { k: 'LPS', v: daysText(count(lps)), title: 'The receding days of the LPS' },
    { k: 'Mini', v: mini ? `${fx(mini.ranges_tall, 1, '-')} ranges` : 'none', title: mini ? 'A smaller box inside the setup, its height in its own daily ranges' : 'No smaller box inside the setup' },
  ];
}
