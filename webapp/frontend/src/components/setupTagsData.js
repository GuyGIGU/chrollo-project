import { SUB_SCORE_CAPS } from './setupScoreMath';
import { explainTip } from './tooltipText';

// Tag backgrounds sit quiet (0.12 alpha) so a row of chips reads calm on a dense
// grid; the meaningful foreground hue is kept, and the warning tag keeps a little
// more presence (0.16) since it's the one chip meant to catch the eye.
export const GROUP_TONES = {
  consolidation: { bg: 'rgba(88,166,255,0.12)', fg: '#58a6ff' },
  lps: { bg: 'rgba(231,179,65,0.12)', fg: '#e3b341' },
  volume: { bg: 'rgba(166,226,46,0.12)', fg: '#a6e22e' },
  trend: { bg: 'rgba(63,185,80,0.12)', fg: '#3fb950' },
  warning: { bg: 'rgba(248,81,73,0.16)', fg: '#f85149' },
};

export const GROUP_ORDER = {
  consolidation: 0,
  lps: 1,
  volume: 2,
  trend: 3,
  warning: 4,
};

export const GROUP_LABELS = {
  consolidation: 'Structure',
  lps: 'LPS / support test',
  volume: 'Volume',
  trend: 'Trend',
  warning: 'Warning',
};

const TOUCH_VOL_Z_NO_SUPPLY = -0.30;
const TOUCH_VOL_Z_SPRING = 0.30;
const TOUCH_VOL_Z_HEAVY_R = 0.50;
const MAX_TAGS = 4;
// Volume drying up ACROSS the contractions (lightest at the final coil) at or
// above this [0,1] read flips the VCP-Coil tooltip from "not confirming yet" to
// "volume confirms". Tooltip wording only — it never changes which chips fire.
const CONTRACTION_VOL_TREND_CONFIRM = 0.70;

const firesAt = (scores, key, fraction) => (
  (scores?.[key] ?? 0) >= fraction * SUB_SCORE_CAPS[key]
);

const fmt = (value, digits = 1) => (
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—'
);
const fmtPct = (value) => (
  typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'
);

const tag = (id, label, group, title, weight, fires) => ({
  id,
  label,
  group,
  title,
  weight,
  fires,
});

const TAG_DEFS = [
  tag(
    'phase_d',
    '📐 Phase D',
    'consolidation',
    explainTip({
      what: 'A tighter, newer consolidation has formed inside or near the right side of the larger base.',
      why: 'This often marks the final narrowing phase after the base has already done most of its work.',
      use: 'Watch the inner-box edges for the trigger and prefer it when volume also dries up.',
    }),
    100,
    (_scores, flags) => !!flags.phaseDInner,
  ),
  tag('old_base', '🏛 Old Base', 'consolidation', explainTip({
    what: 'The stock has spent many bars building the current consolidation.',
    why: 'A longer base can show meaningful cause, but time alone does not make the setup ready.',
    use: 'Treat age as context; still require a tight actionable edge, sound support, and confirmation near the trigger.',
  }), 90, scores => firesAt(scores, 'base_age', 0.80)),
  tag(
    'vcp_coil',
    '🌀 VCP Coil',
    'consolidation',
    (_scores, flags) => {
      const base = explainTip({
        what: 'A Minervini-style Volatility Contraction Pattern: pullbacks inside the base are getting smaller, often ending in a tight final coil.',
        why: 'The contraction sequence suggests supply pressure is fading in stages before a possible breakout.',
        use: 'Prefer it when the final pullback is quiet and tight; still require demand to show up on the breakout.',
      });
      const vt = flags?.contractionVolTrend;
      if (typeof vt !== 'number' || !Number.isFinite(vt)) return base;
      const pts = `${(vt * 100).toFixed(0)}/100`;
      return base + (vt >= CONTRACTION_VOL_TREND_CONFIRM
        ? ` Volume context: dry-up confirms across the contractions (${pts}), with the final coil among the quietest areas.`
        : ` Volume context: dry-up is not confirmed across the contractions yet (${pts}); ideally volume tapers into the final coil.`);
    },
    88,
    scores => firesAt(scores, 'contraction', 0.80),
  ),
  tag('tight_box', '🔒 Tight Box', 'consolidation', explainTip({
    what: 'Price is compressed into a narrow support-to-resistance range.',
    why: 'A tighter box can make the breakout level and invalidation area easier to define.',
    use: 'Look for a clean breakout on stronger demand; if price fails, the tight range should keep risk easier to control.',
  }), 85, scores => firesAt(scores, 'box_tightness', 0.80)),
  tag('ascending_support', '📈 Ascending Support', 'consolidation', explainTip({
    what: 'The base swing lows are rising, so buyers are stepping in at higher prices.',
    why: 'Rising support under resistance can show demand becoming more aggressive.',
    use: 'Treat it as constructive pressure inside the base, but avoid chasing if price is already extended above the trigger.',
  }), 80, scores => firesAt(scores, 'ascending_support', 0.80)),
  tag(
    'worked_equilibrium',
    '⚖️ Worked Equilibrium',
    'consolidation',
    explainTip({
      what: 'The base has traveled between support and resistance repeatedly instead of living near one rail.',
      why: 'Repeated two-sided tests make the rails more meaningful and reduce the chance that the box is just dead space.',
      use: 'Give more trust to the detected support and resistance, then verify the latest action is tightening near the trigger.',
    }),
    56,
    (_scores, flags) => typeof flags.traversalDensity === 'number' && flags.traversalDensity >= 0.33,
  ),
  tag(
    'phase_c_test',
    '🪝 Spring/Test',
    'lps',
    (_scores, flags) => {
      const depth = `Measured undercut: ${fmt(flags.binCUndercutAtr)} ATR.`;
      const recovery = typeof flags.binCRecoveryBars === 'number'
        ? ` Recovery: closed back inside after ${flags.binCRecoveryBars} bar${flags.binCRecoveryBars === 1 ? '' : 's'}.`
        : ' Recovery timing not available.';
      const volume = typeof flags.binCSpringVolZ === 'number'
        ? ` Event volume z-score: ${fmt(flags.binCSpringVolZ, 2)} vs the base.`
        : '';
      return `${explainTip({
        what: 'A late Phase C support undercut and recovery was measured near the base floor.',
        why: 'A spring or test can show remaining supply being shaken out before price returns to the range.',
        use: 'Only treat it as constructive when price recovers and holds support; without recovery, it is a breakdown risk.',
      })} ${depth}${recovery}${volume}`;
    },
    82,
    (_scores, flags) => !!flags.binCPresent,
  ),
  tag('tight_lps', '🪶 Tight LPS', 'lps', explainTip({
    what: 'The final last-point-of-support pullback is unusually narrow and calm.',
    why: 'A tight LPS can show sellers are not pushing price far from the trigger.',
    use: 'Use it to define risk around the recent support area; it weakens if support fails or price stretches away.',
  }), 80, scores => firesAt(scores, 'lps_tightness', 1.00)),
  tag(
    'no_supply',
    '🤫 No Supply',
    'volume',
    explainTip({
      what: 'Resistance was tested on below-average volume.',
      why: 'Light volume at the ceiling can mean fewer sellers are defending resistance.',
      use: 'Treat it as constructive context, then require breakout demand to confirm buyers can actually clear the level.',
    }),
    78,
    (_scores, flags) => typeof flags.rTouchVolZ === 'number' && flags.rTouchVolZ < TOUCH_VOL_Z_NO_SUPPLY,
  ),
  tag('vol_dryup', '🌊 Vol Dry-up', 'volume', explainTip({
    what: 'Volume in the final pause is well below its recent baseline.',
    why: 'Drying volume can show supply pressure fading as price tightens.',
    use: 'Prefer it before the trigger, then look for volume expansion on the breakout to confirm demand.',
  }), 75, scores => firesAt(scores, 'vol_contraction', 0.80)),
  tag(
    'demand_at_s',
    '💪 Demand at S',
    'volume',
    explainTip({
      what: 'Support was tested on above-average volume while price held or recovered the floor.',
      why: 'That can show active demand absorbing selling at the bottom of the range.',
      use: 'Use it as support-quality evidence, separate from the Spring/Test chip, and watch for a later tightening near resistance.',
    }),
    72,
    (_scores, flags) => typeof flags.sTouchVolZ === 'number' && flags.sTouchVolZ > TOUCH_VOL_Z_SPRING,
  ),
  tag('strong_rs', '🥇 Strong RS', 'trend', explainTip({
    what: 'The stock is outperforming SPY over the lookback window.',
    why: 'Relative-strength leaders often hold up better and attract attention when the market turns supportive.',
    use: 'Prefer leaders over laggards when the structure is also clean; do not use RS alone as an entry signal.',
  }), 65, scores => firesAt(scores, 'rs_bonus', 0.95)),
  tag('uptrend', '🚀 Uptrend', 'trend', explainTip({
    what: 'The detected base sits inside an established longer-term uptrend — a continuation (markup) context.',
    why: 'Continuation setups usually have better context than bottom-fishing attempts.',
    use: 'Favor the setup when the base forms as a pause in the trend, while still respecting support and trigger behavior.',
  }), 60, scores => firesAt(scores, 'uptrend_bonus', 0.95)),
  tag(
    'weekly_reaccum',
    '⬆ Weekly Re-accum',
    'trend',
    (_scores, flags) => {
      let s = explainTip({
        what: 'The daily base sits inside a weekly uptrend consolidation or Wyckoff re-accumulation read.',
        why: 'This aligns the daily setup with a larger uptrend pause instead of an isolated short-term pattern.',
        use: 'Give it more priority when the daily box nests inside the weekly box and monthly context also agrees.',
      });
      if (flags.htfWeeklyPhase) s += ` Weekly phase: ${flags.htfWeeklyPhase}.`;
      if (flags.htfDailyNested) s += ' Daily nesting: the daily box sits cleanly inside the weekly box.';
      if (flags.htfMonthlyReaccum) s += ' Monthly context: the monthly chart is also re-accumulating.';
      return s;
    },
    63,
    (_scores, flags) => !!flags.htfWeeklyReaccum,
  ),
  tag('high_adr', '⚡ High ADR', 'trend', explainTip({
    what: 'The stock has high ADR%, the Qullamaggie-style 20-session average daily range relative to price.',
    why: 'High ADR can create more room for momentum, but it also means larger normal swings.',
    use: 'Match position size and stop distance to the volatility; a tight base matters more when ADR is high.',
  }), 62, scores => firesAt(scores, 'adr', 0.80)),
  tag(
    'last_supper',
    'Last Supper',
    'warning',
    (_scores, flags) => {
      const stretch = typeof flags.lpsStretchBox === 'number'
        ? ` Stretch: ${fmt(flags.lpsStretchBox, 2)} box.`
        : '';
      const pullback = typeof flags.lastSupperPullbackPct === 'number'
        ? ` Pullback: ${fmtPct(flags.lastSupperPullbackPct)}.`
        : '';
      const age = typeof flags.lastSupperSourceBoxAge === 'number'
        ? ` Source-box age: ${flags.lastSupperSourceBoxAge} bar${flags.lastSupperSourceBoxAge === 1 ? '' : 's'}.`
        : '';
      const reclaim = typeof flags.lastSupperReclaimQuality === 'number'
        ? ` Reclaim quality: ${fmt(flags.lastSupperReclaimQuality, 2)}.`
        : '';
      return `${explainTip({
        what: 'The LPS foot formed above the box that produced the move.',
        why: 'That can be a Last Supper risk: a valid-looking support test may already be stretched away from its energy source.',
        use: 'Treat it as a caution tag only. It does not reject, score, or filter the setup by itself.',
      })}${stretch}${pullback}${age}${reclaim}`;
    },
    94,
    (_scores, flags) => (
      (typeof flags.lpsStretchBox === 'number' && flags.lpsStretchBox > 0)
      || (typeof flags.lpsStretchAtr === 'number' && flags.lpsStretchAtr > 0)
    ),
  ),
  tag(
    'heavy_resistance',
    '⚠️ Heavy Resistance',
    'warning',
    explainTip({
      what: 'Resistance is being tested on above-average volume.',
      why: 'Heavy volume at the ceiling can mean sellers are still active there.',
      use: 'Treat it as a caution flag: require stronger breakout demand and be quicker to reject the setup if price stalls.',
    }),
    95,
    (_scores, flags) => typeof flags.rTouchVolZ === 'number' && flags.rTouchVolZ > TOUCH_VOL_Z_HEAVY_R,
  ),
];

export function deriveTags(subScores, flags = {}) {
  if (!subScores) return [];
  return TAG_DEFS
    .filter(tagDef => tagDef.fires(subScores, flags))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, MAX_TAGS)
    .sort((a, b) => (
      GROUP_ORDER[a.group] - GROUP_ORDER[b.group] || b.weight - a.weight
    ))
    // Resolve dynamic titles (a tag may compute its tooltip from scores/flags —
    // e.g. VCP Coil folds in the contraction volume-trend read) down to plain
    // strings, so every consumer keeps seeing `title` as a string.
    .map(tagDef => (
      typeof tagDef.title === 'function'
        ? { ...tagDef, title: tagDef.title(subScores, flags) }
        : tagDef
    ));
}

export const TAG_CATALOG = [...TAG_DEFS]
  .sort((a, b) => GROUP_ORDER[a.group] - GROUP_ORDER[b.group] || b.weight - a.weight)
  .map(({ id, label, group }) => ({ id, label, group }));
