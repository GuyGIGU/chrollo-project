// The phase board's facts (Thu 16/10/2026, his design): the phases at the top, the events that happened inside
// each one under them. Pure and node-testable; TwoEyesStoryBank.jsx draws it. Every fact arrives resolved on
// the wire (EC-28): this module only arranges and words them.
import { storyRegionId } from '../charts/chartPhaseOverlay.js';
import { fmtDay, fx } from '../formatting/format.js';

export const dayMonth = (day) => {
  const match = String(day ?? '').match(/^\d{4}-(\d{2})-(\d{2})/);
  return match ? `${match[2]}/${match[1]}` : '';
};
const ranges = (value) => (value == null ? null : `${fx(value, 1, null)} daily range${fx(value, 1, null) === '1.0' ? '' : 's'}`);
const regionIds = (regions) => new Set((regions || []).map((region) => region.id));

// Where the LPS sat against the box it was read in: his three positions against the mini (Sun 13/09/2026).
const LPS_HOW = { in: 'in the mini', on: 'resting on the mini', near: 'near the mini' };
const OPENERS = { SOS: 'the SOS', LPS: 'the LPS', 'round trip': 'the recovery test', staircase: 'a staircase of higher lows' };

// One event line: a hue dot, the name, the day in mono and one sentence.
function eventLine(key, name, day, sentence, { region = null, title = null, phase = null, hero = null } = {}) {
  return { key, name, day: day ?? null, sentence, region, title: title ?? `${name}${day ? `, ${fmtDay(day)}` : ''}: ${sentence}.`, phase, hero };
}

export function phaseBoard(data, regions = []) {
  const block = data?.two_eyes;
  if (!block) return null;
  const ids = regionIds(regions);
  const boxes = block.boxes || [];
  const parent = boxes.find((box) => box.role === 'parent');
  const mini = boxes.find((box) => box.role === 'mini');
  const events = Array.isArray(block.events) ? block.events : [];
  const byKind = (kind) => events.filter((event) => event.kind === kind);
  const lps = block.lps || null;

  // Phase A: the root swing the box stands on.
  const a = [];
  if (parent) {
    a.push(eventLine('a:r', 'Resistance', parent.r_day, 'the climax: the high the rise stopped at', { region: ids.has('b') ? 'b' : null, hero: fx(parent.r, 2) }));
    a.push(eventLine('a:s', 'Support', parent.s_day, 'the reaction low: where the first fall after it ended', { region: ids.has('b') ? 'b' : null, hero: fx(parent.s, 2) }));
    const days = block.grade?.base_days;
    const empty = block.grade?.empty_days;
    a.push(eventLine('a:box', 'Box', parent.opened,
      [parent.ranges_tall == null ? null : `${fx(parent.ranges_tall, 1)} of its daily ranges tall`,
        days != null ? `${days} base days${empty != null ? `, ${days - empty} with a bar in it` : ''}` : null].filter(Boolean).join(' · '),
      { region: ids.has('b') ? 'b' : null }));
  }

  // The upthrust on its own.
  const upthrusts = byKind('upthrust').map((event) => eventLine(storyRegionId(event), 'Upthrust', event.day,
    `${ranges(event.size) ?? 'a run'} over resistance, back inside by ${dayMonth(event.last ?? event.day)}${event.committed === false ? ' · still forming' : ''}`,
    { region: ids.has(storyRegionId(event)) ? storyRegionId(event) : null, hero: fx(event.price, 2) }));

  // Phase C: the spring, then its test.
  const c = [];
  for (const event of byKind('spring')) {
    c.push(eventLine(storyRegionId(event), 'Spring', event.day,
      `${ranges(event.size) ?? 'a dip'} under support to ${fx(event.price, 2)}${event.first && event.first !== event.day ? `, from ${dayMonth(event.first)}` : ''}${event.committed === false ? ' · still forming' : ''}`,
      { region: ids.has(storyRegionId(event)) ? storyRegionId(event) : null, hero: fx(event.price, 2) }));
  }
  for (const event of byKind('spring test')) {
    c.push(eventLine(storyRegionId(event), 'Spring test', event.day, `holds ${fx(event.price, 2)}, over the spring's low`,
      { region: ids.has(storyRegionId(event)) ? storyRegionId(event) : null, hero: fx(event.price, 2) }));
  }
  if (c.length === 1) c.push(eventLine('c:none', 'Spring test', null, 'none yet', { title: 'No valley back inside the support area has tested the spring yet.' }));

  // Phase D: what opened it, then its events in the order they played.
  const d = [];
  const opening = byKind('Phase D')[0] ?? null;
  const dated = [];
  for (const event of byKind('SOS')) {
    dated.push(eventLine(storyRegionId(event), 'SOS', event.day,
      `${event.size != null ? `ran ${ranges(event.size)}` : 'a push'} to ${fx(event.price, 2)}${event.first ? `, from ${dayMonth(event.first)}` : ''}${event.note ? ` · ${event.note}` : ''}${event.committed === false ? ' · still forming' : ''}`,
      { region: ids.has(storyRegionId(event)) ? storyRegionId(event) : null, hero: fx(event.price, 2) }));
  }
  for (const event of byKind('last supper')) {
    dated.push(eventLine(storyRegionId(event), 'Last supper', event.day,
      `${event.size != null ? `dropped ${ranges(event.size)}` : 'a deep drop'} off ${fx(event.price, 2)}${event.last ? `, to ${dayMonth(event.last)}` : ''}`,
      { region: ids.has(storyRegionId(event)) ? storyRegionId(event) : null, hero: fx(event.price, 2) }));
  }
  if (mini) {
    dated.push(eventLine('mini', 'Mini', mini.opened,
      `${mini.ranges_tall == null ? '' : `${fx(mini.ranges_tall, 1)} ranges tall · `}a smaller box inside the setup, read closer in`,
      { region: ids.has('mini') ? 'mini' : null, hero: `${fx(mini.r, 2)}/${fx(mini.s, 2)}` }));
  }
  if (lps && lps.start) {
    const region = (regions || []).find((r) => r.id === 'lps:active') ?? null;
    const days = region ? region.endIndex - region.startIndex + 1 : null;
    const where = lps.against === 'mini' ? (LPS_HOW[lps.how] ?? 'against the mini') : 'in the box';
    const trigger = lps.trigger ?? data.trigger ?? null;
    dated.push(eventLine('lps', 'LPS', lps.start,
      `${days ? `${days} receding day${days === 1 ? '' : 's'}` : 'the last receding days'}${lps.end && lps.end !== lps.start ? ` to ${dayMonth(lps.end)}` : ''}, ${where}${trigger != null ? ` · buy over ${fx(trigger, 2)}` : ''}`,
      { region: region ? region.id : null, hero: trigger == null ? null : fx(trigger, 2) }));
  }
  dated.sort((x, y) => String(x.day ?? '').localeCompare(String(y.day ?? '')));
  d.push(...dated);

  const score = block.grade?.score;
  const facts = block.grade?.empty_days != null && block.grade?.base_days != null;
  return {
    score: score == null || !Number.isFinite(Number(score)) ? null : Number(score),
    note: facts ? `${block.grade.empty_days} of ${block.grade.base_days} base days empty · the base ${block.grade.holds ? 'held' : 'did not hold'}` : null,
    phases: [
      { key: 'a', token: 'A', name: 'Phase A', meaning: 'the root swing the box stands on', lines: a },
      ...(upthrusts.length ? [{ key: 'ut', token: 'UT', name: 'Upthrust', meaning: 'the run over resistance that came back', lines: upthrusts, aside: true }] : []),
      { key: 'c', token: 'C', name: 'Phase C', meaning: 'the shakeout under support', lines: c.length ? c : [eventLine('c:none', 'Spring', null, 'no dip under support recovered', { title: 'The reader named no spring on this box.' })] },
      { key: 'd', token: 'D', name: 'Phase D', meaning: opening
        ? `opened ${dayMonth(opening.day)} by ${OPENERS[opening.note] ?? opening.note ?? 'the right side'}`
        : 'the right side has not opened',
        lines: d.length ? d : [eventLine('d:none', 'Right side', null, 'nothing on the right side yet')],
        opener: opening ? { region: ids.has(storyRegionId(opening)) ? storyRegionId(opening) : null, key: storyRegionId(opening) } : null },
    ],
    told: Array.isArray(block.events),
  };
}

