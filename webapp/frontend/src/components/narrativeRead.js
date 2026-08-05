// The ONE pure formatter for the narrative surface (Surface the Read) — the
// setupScoreMath pattern applied to the story: every component that renders
// the engine's read (card chip, lens tape, archive view) imports THIS module,
// so the load-bearing distinctions can never diverge between surfaces.
//
// Laws:
// - FORMATS, NEVER JUDGES. Counts, postures, admission, verdicts all arrive
//   pre-computed from the engine; this module only shapes them for layout.
//   It never re-derives a count from the tape (the sentence and its counts
//   share one as-of basis upstream — a client-side recount could contradict it).
// - NULL ≠ 0. "Not measured" (the family is null: pre-flip rows / flag off)
//   and "measured-and-empty" (explicit zeros — the junk separator IS zero)
//   are different states with different renders. Falsy checks are forbidden
//   on tape data; every presence test is an explicit null check.

import { episodeLabel } from './wireVocabulary.js';

// The scalar family that proves the story was measured. One representative
// is not enough (a partial write should read as measured), so: measured if
// ANY family scalar is non-null.
const FAMILY_SCALARS = [
  'event_map_completed_s', 'event_map_completed_r', 'event_map_alternations',
  'event_map_terminal_posture', 'event_map_terminal_drift',
  'event_map_story_admitted', 'event_map_episode_nan_bars',
];

export const NARRATIVE_STATUS = Object.freeze({
  NOT_MEASURED: 'not_measured',
  EMPTY: 'empty',
  READY: 'ready',
});

// The two absences, worded once for every surface (same semantic meaning
// always wears the same words): "not measured" says WHY in plain language;
// "empty" states the measured zero as a finding, not a blank.
export const ABSENCE_COPY = Object.freeze({
  not_measured: 'not measured — this row predates the event-map read',
  empty: 'no completed rail events',
});

export function narrativeStatus(data) {
  if (!data || FAMILY_SCALARS.every((k) => data[k] == null)) {
    return NARRATIVE_STATUS.NOT_MEASURED;
  }
  const episodes = Array.isArray(data.event_map_episodes)
    ? data.event_map_episodes : [];
  const s = data.event_map_completed_s;
  const r = data.event_map_completed_r;
  if (episodes.length === 0 && (s === 0 || s == null) && (r === 0 || r == null)) {
    return NARRATIVE_STATUS.EMPTY;
  }
  return NARRATIVE_STATUS.READY;
}

// The glyph strip: zip the engine-built profile tokens (authoritative — they
// carry the ~ unfixed mark, the ? unreadable mark, and the terminal ^ posture)
// with the tape entries (which carry the date anchors). On any mismatch the
// strip degrades to tokens-only (no hover spans) — layout degrades, meaning
// never does.
export function tapeGlyphs(data) {
  const profile = typeof data?.event_map_episode_profile === 'string'
    ? data.event_map_episode_profile.trim() : '';
  const tokens = profile ? profile.split(/\s+/) : [];
  const episodes = Array.isArray(data?.event_map_episodes)
    ? data.event_map_episodes : [];
  const aligned = tokens.length === episodes.length;
  return tokens.map((token, i) => {
    const ep = aligned ? episodes[i] : null;
    return {
      id: `episode-${i}`,
      token,
      unknowable: token.endsWith('~'),
      rail: ep ? ep.rail : (token.startsWith('S') ? 'S' : 'R'),
      outcome: ep ? ep.outcome : null,
      label: ep ? episodeLabel(ep.rail, ep.outcome) : token,
      span: ep && Array.isArray(ep.span) ? ep.span : null,
      knowable: ep ? (ep.knowable ?? null) : null,
      posture: ep ? Boolean(ep.posture) : token.endsWith('^'),
    };
  });
}

// Date-anchored chart spans for the modal's single activeRegion channel
// (one highlight channel; ids extend its vocabulary, never a second state).
export function episodeSpans(data) {
  return tapeGlyphs(data)
    .filter((g) => g.span && g.span.length === 2)
    .map((g) => ({ id: g.id, from: g.span[0], to: g.span[1], label: g.label }));
}

// Layout shaping for the election trace's compact export. Pure relabeling —
// the sentences inside arrive pre-rendered from the engine's own vocabulary.
export function shapeTrace(trace, labels = {}) {
  if (trace == null || typeof trace !== 'object') return null;
  const roots = Array.isArray(trace.roots) ? trace.roots : [];
  const stageLabel = (s) => labels.stages?.[s] ?? s;
  const outcomeLabel = (o) => labels.outcomes?.[o] ?? o;
  return {
    roots: roots.map((r, i) => ({
      id: `root-${i}`,
      climax: r.climax ?? null,
      ar: r.ar ?? null,
      outcome: outcomeLabel(r.outcome),
      candidates: r.candidates ?? 0,
      refused: Object.entries(r.refused || {}).map(([stage, n]) => ({
        stage: stageLabel(stage),
        count: n,
      })),
      furthest: r.furthest
        ? {
            passed: Boolean(r.furthest.passed),
            stage: r.furthest.stage == null ? null : stageLabel(r.furthest.stage),
            sentences: Array.isArray(r.furthest.sentences) ? r.furthest.sentences : [],
          }
        : null,
    })),
    elected: trace.elected
      ? {
          start: trace.elected.start ?? null,
          R: trace.elected.R ?? null,
          S: trace.elected.S ?? null,
          nCandidates: trace.elected.n_candidates ?? null,
          nValid: trace.elected.n_valid ?? null,
          rescued: Boolean(trace.elected.rescued),
        }
      : null,
  };
}
