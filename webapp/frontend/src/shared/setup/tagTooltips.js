// Rich v2 chip tooltips — the staged-retirement "Migrate the rich explainTip
// tooltip copy" item (docs/ta_grade_flip_checklist_2026-08.md), pulled
// forward. Static copy is ported VERBATIM from setupTagsData.js's TAG_DEFS;
// that file stays byte-untouched because it IS the legacy epoch's rollback
// path. Dynamic tags rebuild their measured suffixes from the fired entry's
// `detail` — ONLY the snake_case facts each TagSpec in
// engine_alpha/scoring/taxonomy.py attaches ride the wire, and an absent or
// non-finite fact drops its sentence (never 'undefined', never NaN).
// Explicit .js extensions: this module runs under node --test as well as
// Vite (the tagResolver node-suite convention).
import { explainTip } from '../formatting/tooltipText.js';

// Tooltip wording only, mirrored from the legacy module's literal — it never
// changes which chips fire (the wire carries verdicts, never rules).
const CONTRACTION_VOL_TREND_CONFIRM = 0.70;

// Tooltip wording only, mirrors the ruled rail-area band (the engine's
// MINI_POSITION_TOL_ATR; decisions.md 2026-08-30) — a re-ruled tolerance
// updates the chip copy here, never a buried mid-sentence literal.
const POSITION_RAIL_AREA_ATR = 0.5;

const num = (detail, key) => {
  const v = detail?.[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
};

const rTouchVolSentence = (detail) => {
  const z = num(detail, 'r_touch_vol_z');
  return z != null ? ` Measured resistance-touch volume z-score: ${z.toFixed(2)} vs the base.` : '';
};

// One measured suffix for the whole position family: the raw signed rail
// distances (inner rail minus parent rail, in ATRs) that produced the band.
const positionSentence = (detail) => {
  let s = '';
  const r = num(detail, 'inner_position_r_atr');
  if (r != null) s += ` Top vs resistance: ${r >= 0 ? '+' : ''}${r.toFixed(2)} ATR.`;
  const sd = num(detail, 'inner_position_s_atr');
  if (sd != null) s += ` Bottom vs support: ${sd >= 0 ? '+' : ''}${sd.toFixed(2)} ATR.`;
  return s;
};

const BASE_TIPS = {
  phase_d: explainTip({
    what: 'A tighter, newer consolidation has formed inside or near the right side of the larger base.',
    why: 'This often marks the final narrowing phase after the base has already done most of its work.',
    use: 'Watch the inner-box edges for the trigger and prefer it when volume also dries up.',
  }),
  old_base: explainTip({
    what: 'The stock has spent many bars building the current consolidation.',
    why: 'A longer base can show meaningful cause, but time alone does not make the setup ready.',
    use: 'Treat age as context; still require a tight actionable edge, sound support, and confirmation near the trigger.',
  }),
  vcp_coil: explainTip({
    what: 'A Minervini-style Volatility Contraction Pattern: pullbacks inside the base are getting smaller, often ending in a tight final coil.',
    why: 'The contraction sequence suggests supply pressure is fading in stages before a possible breakout.',
    use: 'Prefer it when the final pullback is quiet and tight; still require demand to show up on the breakout.',
  }),
  tight_box: explainTip({
    what: 'Price is compressed into a narrow support-to-resistance range.',
    why: 'A tighter box can make the breakout level and invalidation area easier to define.',
    use: 'Look for a clean breakout on stronger demand; if price fails, the tight range should keep risk easier to control.',
  }),
  ascending_support: explainTip({
    what: 'The base swing lows are rising, so buyers are stepping in at higher prices.',
    why: 'Rising support under resistance can show demand becoming more aggressive.',
    use: 'Treat it as constructive pressure inside the base, but avoid chasing if price is already extended above the trigger.',
  }),
  worked_equilibrium: explainTip({
    what: 'The base has traveled between support and resistance repeatedly instead of living near one rail.',
    why: 'Repeated two-sided tests make the rails more meaningful and reduce the chance a rail was drawn where price never actually traded.',
    use: 'Give more trust to the detected support and resistance, then verify the latest action is tightening near the trigger.',
  }),
  phase_c_test: explainTip({
    what: 'A late Phase C support undercut and recovery was measured near the base floor.',
    why: 'A spring or test can show remaining supply being shaken out before price returns to the range.',
    use: 'Only treat it as constructive when price recovers and holds support; without recovery, it is a breakdown risk.',
  }),
  tight_lps: explainTip({
    what: 'The final last-point-of-support pullback is unusually narrow and calm.',
    why: 'A tight LPS can show sellers are not pushing price far from the trigger.',
    use: 'Use it to define risk around the recent support area; it weakens if support fails or price stretches away.',
  }),
  no_supply: explainTip({
    what: 'Resistance was tested on below-average volume.',
    why: 'Light volume at the ceiling can mean fewer sellers are defending resistance.',
    use: 'Treat it as constructive context, then require breakout demand to confirm buyers can actually clear the level.',
  }),
  vol_dryup: explainTip({
    what: 'Volume in the final pause is well below its recent baseline.',
    why: 'Drying volume can show supply pressure fading as price tightens.',
    use: 'Prefer it before the trigger, then look for volume expansion on the breakout to confirm demand.',
  }),
  demand_at_s: explainTip({
    what: 'Support was tested on above-average volume while price held or recovered the floor.',
    why: 'That can show active demand absorbing selling at the bottom of the range.',
    use: 'Use it as support-quality evidence, separate from the Spring/Test chip, and watch for a later tightening near resistance.',
  }),
  strong_rs: explainTip({
    what: 'The stock is outperforming SPY over the lookback window.',
    why: 'Relative-strength leaders often hold up better and attract attention when the market turns supportive.',
    use: 'Prefer leaders over laggards when the structure is also clean; do not use RS alone as an entry signal.',
  }),
  uptrend: explainTip({
    what: 'The detected base sits inside an established longer-term uptrend — a continuation (markup) context.',
    why: 'Continuation setups usually have better context than bottom-fishing attempts.',
    use: 'Favor the setup when the base forms as a pause in the trend, while still respecting support and trigger behavior.',
  }),
  weekly_reaccum: explainTip({
    what: 'The daily base sits inside a weekly uptrend consolidation or Wyckoff re-accumulation read.',
    why: 'This aligns the daily setup with a larger uptrend pause instead of an isolated short-term pattern.',
    use: 'Give it more priority when the daily box nests inside the weekly box and monthly context also agrees.',
  }),
  high_adr: explainTip({
    what: 'The stock has high ADR%, the Qullamaggie-style 20-session average daily range relative to price.',
    why: 'High ADR can create more room for momentum, but it also means larger normal swings.',
    use: 'Match position size and stop distance to the volatility; a tight base matters more when ADR is high.',
  }),
  last_supper: explainTip({
    what: 'The LPS foot formed above the box that produced the move.',
    why: 'That can be a Last Supper risk: a valid-looking support test may already be stretched away from its energy source.',
    use: 'Treat it as a caution tag only. It does not reject, score, or filter the setup by itself.',
  }),
  heavy_resistance: explainTip({
    what: 'Resistance is being tested on above-average volume.',
    why: 'Heavy volume at the ceiling can mean sellers are still active there.',
    use: 'Treat it as a caution flag: require stronger breakout demand and be quicker to reject the setup if price stalls.',
  }),
  weak_monthly: explainTip({
    what: 'The monthly (higher-timeframe) trend is pointing down.',
    why: 'A daily base forming inside a falling monthly trend has a weaker backdrop than one inside a rising or neutral monthly.',
    use: 'Treat it as caution context only — it does not reject, score, or filter the setup. Weigh the monthly backdrop by eye alongside the daily structure.',
  }),
  // The position family: descriptors of WHERE the inner mini-consolidation
  // sits against the base rails (each rail is an area, ±0.5 ATR around the
  // line). Never a ranking — the surrounding story gives a position meaning.
  position_at_ceiling: explainTip({
    what: `The latest tight mini-consolidation sits in the resistance area — its top within ${POSITION_RAIL_AREA_ATR} ATR of the rail, touching it or poking through.`,
    why: 'A rest held up against resistance shows sellers failing to push price away from the breakout level.',
    use: 'Read it with what follows: a pivot back is respect, clean continuation is the departure. The chip describes position, not quality.',
  }),
  position_mid_range: explainTip({
    what: 'The latest tight mini-consolidation floats in the middle of the base — clear of both the resistance and support areas.',
    why: 'A mid-base rest is cause still building; neither rail is being tested by it.',
    use: 'Watch which rail it engages next; the position alone carries no verdict.',
  }),
  position_on_support: explainTip({
    what: `The latest tight mini-consolidation holds in the support area — its bottom within ${POSITION_RAIL_AREA_ATR} ATR of the rail, including slight pokes below.`,
    why: 'Holding at support — even slightly under it — is the line being proven as support.',
    use: 'Treat pokes that hold as respect for the area; a collapse through it is a different event entirely.',
  }),
  position_touching_both: explainTip({
    what: 'The mini-consolidation touches both rail areas at once — the base is about one bar of height, or the rest spans it rail-to-rail.',
    why: 'When the whole base fits inside the two rail areas, position carries no separating information — an at-resistance read here would be an artifact.',
    use: 'Judge the base by its overall shape and story; this chip only says the position read does not apply here.',
  }),
};

const DETAIL_SUFFIXES = {
  vcp_coil: (detail) => {
    let s = '';
    const count = num(detail, 'contraction_count');
    if (count != null) s += ` Contractions measured: ${count}.`;
    const vt = num(detail, 'contraction_vol_trend');
    if (vt != null) {
      const pts = `${(vt * 100).toFixed(0)}/100`;
      s += vt >= CONTRACTION_VOL_TREND_CONFIRM
        ? ` Volume context: dry-up confirms across the contractions (${pts}), with the final coil among the quietest areas.`
        : ` Volume context: dry-up is not confirmed across the contractions yet (${pts}); ideally volume tapers into the final coil.`;
    }
    return s;
  },
  // bin_c_type also rides this entry but stays unrendered: its values are raw
  // engine enums (SPRING / TERMINAL_SHAKEOUT) with no signed display label.
  phase_c_test: (detail) => {
    let s = '';
    const undercut = num(detail, 'bin_c_undercut_atr');
    if (undercut != null) s += ` Measured undercut: ${undercut.toFixed(1)} ATR.`;
    const bars = num(detail, 'bin_c_recovery_bars');
    s += bars != null
      ? ` Recovery: closed back inside after ${bars} bar${bars === 1 ? '' : 's'}.`
      : ' Recovery timing not available.';
    return s;
  },
  last_supper: (detail) => {
    let s = '';
    const box = num(detail, 'lps_stretch_box');
    if (box != null) s += ` Stretch: ${box.toFixed(2)} box.`;
    const atr = num(detail, 'lps_stretch_atr');
    if (atr != null) s += ` Stretch: ${atr.toFixed(2)} ATR.`;
    const pullback = num(detail, 'last_supper_pullback_from_extension_pct');
    if (pullback != null) s += ` Pullback: ${(pullback * 100).toFixed(1)}%.`;
    const reclaim = num(detail, 'last_supper_reclaim_quality');
    if (reclaim != null) s += ` Reclaim quality: ${reclaim.toFixed(2)}.`;
    return s;
  },
  no_supply: rTouchVolSentence,
  heavy_resistance: rTouchVolSentence,
  demand_at_s: (detail) => {
    const z = num(detail, 's_touch_vol_z');
    return z != null ? ` Measured support-touch volume z-score: ${z.toFixed(2)} vs the base.` : '';
  },
  worked_equilibrium: (detail) => {
    const density = num(detail, 'traversal_density');
    return density != null ? ` Measured traversal density: ${density.toFixed(2)}.` : '';
  },
  position_at_ceiling: positionSentence,
  position_mid_range: positionSentence,
  position_on_support: positionSentence,
  position_touching_both: positionSentence,
};

export function tooltipForTag(id, detail) {
  const base = BASE_TIPS[id];
  if (!base) return null;
  const suffix = DETAIL_SUFFIXES[id];
  return suffix ? base + suffix(detail || {}) : base;
}
