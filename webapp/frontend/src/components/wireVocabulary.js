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

// Pre-box trend states (event_map_pre_box_trend).
export const TREND_STATE_LABELS = {
  up: 'uptrend',
  down: 'downtrend',
  range: 'range',
};

// Story chapters (TA-grade build task 12): the grade's breakdown vocabulary.
// Wire ids mirror taxonomy.CHAPTER_ORDER (ruled 2026-08-06; vocabulary
// re-ruled 2026-08-08 to the operator's phase-overlay words — the same
// vocabulary as PHASE_NAMES below); the order mirrors the ruling —
// left→right like the chart, NEVER points-sorted.
export const CHAPTER_ORDER = ['cause', 'phase_b', 'phase_c', 'phase_d', 'trend'];

export const CHAPTER_LABELS = {
  cause: { label: 'Cause', short: 'Cause' },
  phase_b: { label: 'Phase B', short: 'B' },
  phase_c: { label: 'Phase C', short: 'C' },
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

export function displayLabel(id) {
  return DISPLAY_LABELS[id]?.label ?? id;
}

export function shortLabel(id) {
  return DISPLAY_LABELS[id]?.short ?? id;
}

// THE one snake_case wire -> camelCase tag-flags adapter (the frontend's EC-3
// twin). Formerly hand-copied in useScreenerFilters / ScreenerCard /
// ScreenerStockLens — and the filter copy had silently drifted (it lacked the
// equilibrium + HTF flags, so tag FILTERS could not match chips the cards
// showed). One adapter ends that class of drift.
export function tagFlagsFromWire(data) {
  return {
    phaseDInner: data.phase_d_inner,
    rTouchVolZ: data.r_touch_vol_z,
    sTouchVolZ: data.s_touch_vol_z,
    contractionVolTrend: data.contraction_vol_trend,
    cogEnd: data.bin_b_cog_end,
    cogCrossings: data.bin_b_cog_crossings,
    traversalDensity: data.traversal_density,
    cogRng: data.bin_b_cog_rng,
    cogCorr: data.bin_b_cog_corr,
    binCPresent: data.bin_c_present,
    binCType: data.bin_c_type,
    binCUndercutAtr: data.bin_c_undercut_atr,
    binCRecoveryBars: data.bin_c_recovery_bars,
    binCSpringVolZ: data.bin_c_spring_vol_z,
    htfWeeklyReaccum: data.htf_w_reaccum,
    htfWeeklyPhase: data.htf_w_phase,
    htfDailyNested: data.htf_w_daily_nested,
    htfMonthlyReaccum: data.htf_m_reaccum,
    htfMonthlyTrendState: data.htf_m_trend_state,
    lpsStretchAtr: data.lps_stretch_atr,
    lpsStretchBox: data.lps_stretch_box,
    // Narrative read (Surface the Read): the engine's RULED story-admission
    // bit + the tape sentence — the chip consumes the ruled judgment, it
    // never re-derives one (EC-18).
    storyAdmitted: data.event_map_story_admitted,
    episodeProfile: data.event_map_episode_profile,
    lastSupperPullbackPct: data.last_supper_pullback_from_extension_pct,
    lastSupperSourceBoxAge: data.last_supper_source_box_age,
    lastSupperReclaimQuality: data.last_supper_reclaim_quality,
  };
}
