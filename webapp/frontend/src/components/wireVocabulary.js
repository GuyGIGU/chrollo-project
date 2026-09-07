// The ONE frontend vocabulary module (Purity task 12; the setupScoreMath
// pattern AGENTS.md mandates for caps, applied to labels): stable wire/archive
// keys -> the operator-signed display label + sanctioned short form
// (task4-sitting A, 2026-07-17). Wire keys are FROZEN forever — vocabulary
// changes live here, where humans read, never on the wire.
//
// Rules:
// - JS identifiers stay matched to their wire keys (traversalDensity mirrors
//   the frozen wire key traversal_density — never rename one without the other).
// - Unknown ids fall through VERBATIM (never blank): a new engine slug renders
//   as itself until it earns a signed label.
// - Reject-reason slugs arrive already renamed at the engine source (task 13);
//   this module adds no prettifying translation layer for them.

export const DISPLAY_LABELS = {
  // Concept labels (signed 2026-07-05 / 2026-07-17)
  traversal_density: { label: 'Equilibrium', short: 'Eq.' },
  score_traversal_quality: { label: 'Equilibrium', short: 'Eq.' },
  dwell_balance: { label: 'Dwell Balance', short: 'Dwell' },
  r_touch_vol_z: { label: 'Resistance Volume', short: 'R vol' },
  s_touch_vol_z: { label: 'Support Volume', short: 'S vol' },
  // LPS completion forms (ONE detector; the wire enum has SIX values and every
  // one of them now carries a signed label — before 2026-07-26 the last three
  // fell through and rendered to the operator as raw snake_case slugs).
  terminal_valley: { label: 'LPS', short: 'LPS' },
  holding_shelf: { label: 'LPS — flat hold', short: 'flat hold' },
  buec_shelf: { label: 'LPS above R', short: 'above R' },
  OVERSHOOT_R: { label: 'LPS above R', short: 'above R' },
  rising_support_shelf: { label: 'LPS — rising support', short: 'rising support' },
  clean_downswing: { label: 'LPS — clean pullback', short: 'clean pullback' },
  undercut_rebound: { label: 'LPS — spring rebound', short: 'spring rebound' },
  // Structure verdict labels
  descent_tail: { label: 'Stale-Support Reject', short: 'stale support' },
  // Electing-pool provenance (Surface the Read; closed set, frozen wire).
  // All four SIGNED by the operator 2026-08-04: "Above Resistance" =
  // consolidation -> breakout/SOS -> LPS above resistance; band = a special
  // second attempt with structure-break tolerance; story = judged BY the
  // event map (which every read carries — this route is the one it elects).
  strict: { label: 'Clean election', short: 'clean' },
  rescued: { label: 'Above Resistance', short: 'above R' },
  band: { label: 'Structure Break Tolerance', short: 'break tolerance' },
  story: { label: 'Event Map', short: 'event map' },
  // (The former worked-story chip entry was removed 2026-08-05 on the
  // operator's ruling: the Event Map is a base feature every stock carries —
  // the grading rework will grade setups BY their event maps — never a chip.)
};

// Mini-consolidation position (rails-are-areas rulings 2026-08-29/30): the
// wire/archive enum is FROZEN — at_ceiling / mid_range / on_support /
// touching_both. Display words operator-SIGNED 2026-08-30: "at resistance"
// chosen by him over "top of the base" ("the top of the base is the
// Resistance line"); "middle of the base" = clear of both rails; touching
// both = the base is about a bar's worth of height (or the mini spans it
// rail-to-rail), so the position carries no separating information.
export const POSITION_LABELS = {
  at_ceiling: { label: 'At resistance', short: 'at R' },
  mid_range: { label: 'Middle of the base', short: 'mid-base' },
  on_support: { label: 'On support', short: 'on S' },
  touching_both: { label: 'Touching both rails', short: 'both rails' },
};

export function positionLabel(value) {
  return POSITION_LABELS[value]?.label ?? value;
}

// Rail-episode outcomes (Surface the Read): the wire enum is frozen
// (completed/failed/unreadable/open per rail); the display names are the
// RULED forms from strategy_alpha's episode table. Keyed "RAIL:outcome"
// because a completed episode reads differently per rail.
export const EPISODE_LABELS = {
  'S:completed': 'completed support test',
  'R:completed': 'completed resistance rejection',
  'S:failed': 'failed episode — support broke',
  'R:failed': 'failed episode — closed above resistance',
  'S:unreadable': 'unreadable episode',
  'R:unreadable': 'unreadable episode',
  'S:open': 'open episode',
  'R:open': 'open episode',
};

export function episodeLabel(rail, outcome) {
  return EPISODE_LABELS[`${rail}:${outcome}`] ?? `${rail}:${outcome}`;
}

// Election-trace vocabulary (Surface the Read): cascade stages + per-root
// outcomes, plain chart words. Sentences inside the trace arrive PRE-RENDERED
// from the engine's own vocabulary (trace_export.leg_sentence) — these label
// only the codes the compact shape still carries.
export const TRACE_STAGE_LABELS = {
  width: 'box width',
  window: 'window length',
  respect: 'rail respect',
  occupancy: 'occupancy',
  traversal: 'rail-to-rail traversal',
  story: 'story admission',
  selection: 'election',
};

export const ROOT_OUTCOME_LABELS = {
  no_box: 'no worked range',
  no_lps: 'no last point of support',
  complete: 'complete story',
};

// The letter ladder — the closed set the engine can emit for `tier`
// (engine_alpha.scoring._apply_tier_ladder). Defined ONCE here at the
// 2026-08-09 flip: D was already first-class in the archive and watchlist
// vocabulary, but the screener command band and both home zones each carried
// their own S-A-B-C literal, so a D-tier row was simply invisible on those
// three surfaces. Consumers spread this rather than forking it a fourth time.
export const TIER_LETTERS = ['S', 'A', 'B', 'C', 'D'];

// Pre-box trend states (event_map_pre_box_trend) + the DAILY trend-state
// vocabulary (market_structure.TREND_STATES, Power-Play program Task 11) in
// the SAME registry — one home for trend words, keys disjoint by design.
export const TREND_STATE_LABELS = {
  up: 'uptrend',
  down: 'downtrend',
  range: 'range',
  trending: 'trending',
  correcting: 'correcting',
  consolidating: 'consolidating',
  choppy: 'choppy',
};

// Power-Play species candidacy (the server-derived closed set —
// evaluation.PP_WIRE_STATUS; program Task 14). The wire carries the VERDICT,
// never the rule (EC-28): no client code may reconstruct these from null
// patterns, and unknown slugs render verbatim until they earn a signed label.
// "watched, ungraded" is deliberately MARK-register language: a candidacy is
// a note in the margin, never a chip, never a tier color, until the operator's
// flip promotes it.
export const POWER_PLAY_STATUS_LABELS = {
  fired: 'Power Play — fired',
  watched_ungraded: 'Power Play — watched, ungraded',
  not_watched_clock: 'Power Play — missed by the clock',
  refused_occupancy: 'Power Play — refused (occupancy)',
  refused_story: 'Power Play — refused (story)',
};

export function powerPlayStatusLabel(id) {
  return POWER_PLAY_STATUS_LABELS[id] ?? id;
}

// Story chapters (TA-grade build task 12): the grade's breakdown vocabulary.
// Wire ids mirror taxonomy.CHAPTER_ORDER (ruled 2026-08-06; vocabulary
// re-ruled 2026-08-08 to the operator's phase-overlay words); the order mirrors
// the ruling — left→right like the chart, NEVER points-sorted.
//
// RE-PARTITIONED 2026-08-12 (operator): Cause and Phase B graded the same
// object from two sides and are fused as `consolidation` — "call it
// Consolidation Grade, since a two-sided zigzag price action can be folded into
// one of the quality traits we look for in a consolidation as a whole". Phase C
// is no longer a chapter at all: it is a MARK on the chart (see setupStoryRows).
// Unknown wire chapters still fall through verbatim, so a stale build renders a
// server-side re-chaptering rather than dropping it.
export const CHAPTER_ORDER = ['consolidation', 'phase_d', 'trend'];

export const CHAPTER_LABELS = {
  // short === label: the panel prints the chip alone when they match, so
  // Consolidation renders as one wide chip rather than "Cons.  Consolidation".
  consolidation: { label: 'Consolidation', short: 'Consolidation' },
  phase_d: { label: 'Phase D', short: 'D' },
  trend: { label: 'Trend', short: 'Trend' },
};

// Grade warning labels (unknown ids fall through verbatim — never blank).
// terminal_drift renamed 2026-08-10 (operator: the term was never approved;
// naming doctrine = describe the event plainly, the narrative panel's own
// words). The wire id is frozen — vocabulary changes here, never on the wire.
export const WARNING_LABELS = {
  terminal_drift: 'Ends drifting on support',
  weak_monthly: 'Weak monthly',
};

// Phase overlay names — the one source for A/B/C/D naming (chartPhaseOverlay
// keys its colors/details off these).
export const PHASE_NAMES = {
  a: 'Phase A',
  b: 'Phase B',
  c: 'Phase C',
  d: 'Phase D',
  lps: 'LPS',
};

// The BINARY scan verdict — the operator's own two states, named for the ACTION
// each implies. RESOLVED SERVER-SIDE (services/scan_diagnosis.py): the wire
// carries the verdict, never the rule (EC-28), so nothing in this app may work
// out which of the two it is — from the failure kind, the status, the number of
// failing checks, or anything else. These are its words and its tone, nothing
// more, and an unknown slug falls through to the old "Degraded" wording rather
// than blank (an older backend that has not been restarted yet).
export const RUN_VERDICT_LABELS = {
  rerunnable: 'Re-run the scan',
  needs_attention: 'Needs attention',
};

export const RUN_VERDICT_TONES = {
  rerunnable: 'var(--warning)',
  needs_attention: 'var(--danger)',
};

// Background-job kinds (the frozen scan_runs.kind enum) in plain trading words,
// for the scan-run diagnostics registry. Labels only — the registry never
// derives a verdict from the kind.
export const RUN_KIND_LABELS = {
  scan: 'Screener scan',
  maturation: 'Outcome backfill',
  download: 'Market-data download',
};

// The run statuses (the frozen scan_runs.status enum) in the operator's words.
// One map for BOTH surfaces that name a run — the topbar pill and the registry
// row — so a stale-data run cannot read "stale" on one and `stale_data` on the
// other. Labels only.
export const RUN_STATUS_LABELS = {
  ok: 'ok',
  running: 'running',
  failed: 'failed',
  aborted: 'stopped by you',
  stale_data: 'stale',
  never: 'never run',
};

// How a run was started. `os_task` (the Windows scheduled task that ticks the
// outcome backfill) reaches the operator for the first time in the registry.
export const RUN_TRIGGER_LABELS = {
  scheduled: 'nightly timer',
  manual: 'you',
  manual_evaluation: 'you (Evaluate)',
  manual_download: 'you (Download)',
  os_task: 'Windows task',
};

export function displayLabel(id) {
  return DISPLAY_LABELS[id]?.label ?? id;
}

export function shortLabel(id) {
  return DISPLAY_LABELS[id]?.short ?? id;
}

