// The vocabulary pinning law (council review 2026-08-05, finding 15): the
// operator-SIGNED display words are immutable expected values — a well-meaning
// edit to a signed label must go red here, and no retired Wyckoff jargon may
// ever reach an operator-facing string (the frontend twin of the engine's
// test_leg_sentences_never_carry_engineer_vocabulary).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  DISPLAY_LABELS,
  EPISODE_LABELS,
  POSITION_LABELS,
  ROOT_OUTCOME_LABELS,
  RUN_VERDICT_LABELS,
  RUN_VERDICT_TONES,
  TRACE_STAGE_LABELS,
  TREND_STATE_LABELS,
  episodeLabel,
  positionLabel,
} from './wireVocabulary.js';

test('the four pool labels are the operator-signed words, verbatim', () => {
  // SIGNED 2026-08-04 — changing any of these requires the operator's word,
  // not a refactor.
  assert.equal(DISPLAY_LABELS.strict.label, 'Clean election');
  assert.equal(DISPLAY_LABELS.rescued.label, 'Above Resistance');
  assert.equal(DISPLAY_LABELS.band.label, 'Structure Break Tolerance');
  assert.equal(DISPLAY_LABELS.story.label, 'Event Map');
});

test('the four position labels are the operator-signed words, verbatim', () => {
  // SIGNED 2026-08-30 — "at resistance" was his pick ("since the top of the
  // base is the Resistance line"); "middle of the base" and touching-both are
  // his phrases from the same sitting. Changing any of these requires the
  // operator's word, not a refactor.
  assert.equal(POSITION_LABELS.at_ceiling.label, 'At resistance');
  assert.equal(POSITION_LABELS.mid_range.label, 'Middle of the base');
  assert.equal(POSITION_LABELS.on_support.label, 'On support');
  assert.equal(POSITION_LABELS.touching_both.label, 'Touching both rails');
  // Unknown wire values fall through verbatim — visible, never blank.
  assert.equal(positionLabel('future_value'), 'future_value');
});

test('the Event Map is never a chip — no admission-chip entry exists', () => {
  // Operator ruling 2026-08-05: the Event Map is a base feature every stock
  // carries (the lens panel is its surface) and the grading rework grades
  // setups BY it — it must not reappear as a card badge.
  assert.equal(DISPLAY_LABELS.worked_story, undefined);
});

test('every episode outcome/stage/trend code resolves to a label', () => {
  for (const rail of ['S', 'R']) {
    for (const outcome of ['completed', 'failed', 'unreadable', 'open']) {
      const label = episodeLabel(rail, outcome);
      assert.ok(label && !label.includes(':'), `${rail}:${outcome} -> ${label}`);
    }
  }
  // Unknown codes fall through verbatim — visible, never blank.
  assert.equal(episodeLabel('S', 'future_outcome'), 'S:future_outcome');
  for (const labels of [TRACE_STAGE_LABELS, ROOT_OUTCOME_LABELS, TREND_STATE_LABELS]) {
    for (const value of Object.values(labels)) {
      assert.ok(typeof value === 'string' && value.length > 0);
    }
  }
});

test('no retired jargon and no engineer CONSTANT_CASE in any operator-facing string', () => {
  const strings = [];
  for (const entry of Object.values(DISPLAY_LABELS)) {
    strings.push(entry.label, entry.short ?? '');
  }
  for (const entry of Object.values(POSITION_LABELS)) {
    strings.push(entry.label, entry.short ?? '');
  }
  strings.push(...Object.values(EPISODE_LABELS));
  strings.push(...Object.values(TRACE_STAGE_LABELS));
  strings.push(...Object.values(ROOT_OUTCOME_LABELS));
  strings.push(...Object.values(TREND_STATE_LABELS));
  for (const s of strings) {
    for (const banned of ['creek', 'ice', 'buec', 'mini-bc']) {
      assert.ok(!new RegExp(`\\b${banned}\\b`, 'i').test(s), `retired jargon in "${s}"`);
    }
    // Settings-constant leakage (MAX_BOX_WIDTH style — an underscore-joined
    // CONSTANT). Bare acronyms like LPS/ADR are legitimate operator words.
    assert.ok(!/\b[A-Z]+_[A-Z_]+\b/.test(s), `settings-constant token in "${s}"`);
  }
});

test('the scan verdict set is closed, two-valued, and wears operator words', () => {
  // THE OTHER HALF of the server's coverage gate
  // (tests/test_scan_diagnosis.py::test_every_failure_kind_maps_to_exactly_one_verdict).
  // The operator asked for exactly TWO states — "either the Scan failed because
  // of a technical issue ... or there is a real issue that needs to be tended by
  // you" — so a third arriving on the wire, or a slug reaching him unlabelled,
  // must go red here rather than render as raw snake_case.
  assert.deepEqual(Object.keys(RUN_VERDICT_LABELS).sort(),
    ['needs_attention', 'rerunnable']);
  assert.deepEqual(Object.keys(RUN_VERDICT_TONES).sort(),
    Object.keys(RUN_VERDICT_LABELS).sort());
  // Each state is named for the ACTION it implies, and neither leaks its slug.
  assert.equal(RUN_VERDICT_LABELS.rerunnable, 'Re-run the scan');
  assert.equal(RUN_VERDICT_LABELS.needs_attention, 'Needs Claude');
  for (const [slug, label] of Object.entries(RUN_VERDICT_LABELS)) {
    assert.ok(!label.includes('_'), `wire slug leaked into "${label}"`);
    assert.ok(!label.toLowerCase().includes(slug));
  }
});
