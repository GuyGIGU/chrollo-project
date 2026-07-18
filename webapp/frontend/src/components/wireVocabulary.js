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
  // LPS completion forms (one detector, three forms; wire enums frozen)
  terminal_valley: { label: 'LPS', short: 'LPS' },
  holding_shelf: { label: 'LPS — flat hold', short: 'flat hold' },
  buec_shelf: { label: 'LPS above R (throwback)', short: 'throwback' },
  OVERSHOOT_R: { label: 'LPS above R (throwback)', short: 'throwback' },
  // Structure verdict labels
  descent_tail: { label: 'Stale-Support Reject', short: 'stale support' },
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
    lastSupperPullbackPct: data.last_supper_pullback_from_extension_pct,
    lastSupperSourceBoxAge: data.last_supper_source_box_age,
    lastSupperReclaimQuality: data.last_supper_reclaim_quality,
  };
}
