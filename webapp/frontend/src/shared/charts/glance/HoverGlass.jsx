import { useMemo } from 'react';
import ScreenerMiniChart from '../ScreenerMiniChart';
import { CHART_FRAMING } from '../chartGeometry';
import { GLANCE_HEIGHT, GLANCE_WIDTH, glancePlacement } from './glanceMath';
import { tierColor } from '../../presentation/theme';

// HoverGlass — read-only glass: the chart you were already going to open,
// shown where you are looking, without committing to anything. It has no
// buttons, no links, and `pointerEvents: none` — there is deliberately no
// corridor to hover INTO it, because it is not a menu. Click keeps whatever
// verb the host list already had.
//
// It sits BESIDE features/screener/components/Popover.jsx rather than extending it: that component is a
// click-toggled disclosure that SEATS FOCUS in its panel and restores focus on
// Escape (right for the Filters/Data panels, wrong for glass that must never
// take focus), and it anchors its panel with `position: absolute` inside the
// trigger — which every table here would clip, since InstrumentTable's well and
// the page both scroll. The genuinely shared part is a ~10-line dismissal
// idiom, not a component; that lives in useHoverGlance.
//
// Positioning is fixed + measured, beside the CURSOR (see
// glanceMath.glancePlacement for the --ui-scale zoom correction). z 400 sits in the empty band above sticky table
// headers (1) and the appearance popover (60), and below every scrim and modal
// (1000+), so the glass can never paint over a dialog.
export default function HoverGlass({ glance }) {
  // The frame (cursor point, zoom factor, viewport) is measured by the hook when
  // the glass opens and travels WITH the glance, so the placement can never be
  // computed from a scale sampled at some earlier moment.
  const place = useMemo(
    () => glancePlacement({ pointer: glance?.pointer, viewport: glance?.viewport, scale: glance?.scale }),
    [glance?.pointer, glance?.viewport, glance?.scale],
  );
  if (!glance || !place || glance.status === 'closed') return null;

  const { header, status, entry, chartKey } = glance;

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        left: place.left,
        top: place.top,
        width: GLANCE_WIDTH,
        height: GLANCE_HEIGHT,
        zIndex: 400,
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-strong, var(--border-color))',
        borderRadius: 'var(--radius-sm)',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05), 0 18px 44px -14px rgba(0,0,0,0.75)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      <GlassHeader header={header} />
      <div style={{ display: 'flex', flex: 1, minHeight: 0, position: 'relative' }}>
        {status === 'ready' && entry ? (
          <ScreenerMiniChart
            key={chartKey}
            ticker={header?.ticker}
            data={entry}
            profile={CHART_FRAMING.popover}
          />
        ) : (
          <GlassMessage status={status} note={glance.note} />
        )}
      </div>
    </div>
  );
}

// Header renders ONLY values that already crossed the wire (EC-28) — no tier
// re-derivation, no score math, no threshold. A missing field renders as an
// em dash rather than a computed stand-in.
function GlassHeader({ header }) {
  const tier = header?.tier;
  return (
    <div style={{
      alignItems: 'baseline',
      borderBottom: '1px solid var(--border-color)',
      display: 'flex',
      gap: 8,
      flexShrink: 0,
      padding: '6px 9px',
    }}>
      <span style={{
        color: tier ? tierColor(tier) : 'var(--text-main)',
        fontSize: 13,
        fontWeight: 850,
        letterSpacing: '-0.01em',
      }}>
        {header?.ticker || '—'}
      </span>
      {tier ? (
        <span style={{
          border: `1px solid ${tierColor(tier)}55`,
          borderRadius: 'var(--radius-xs)',
          color: tierColor(tier),
          fontSize: 9,
          fontWeight: 800,
          padding: '0 3px',
        }}>
          {tier}
        </span>
      ) : null}
      {header?.grade != null && (
        <span style={{
          color: 'var(--text-main)',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          fontVariantNumeric: 'tabular-nums',
        }}>
          {header.grade}<span style={{ color: 'var(--text-faint)', fontSize: 9 }}>/100</span>
        </span>
      )}
      <span style={{
        color: 'var(--text-faint)',
        fontSize: 10,
        marginLeft: 'auto',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {header?.context || ''}
      </span>
    </div>
  );
}

// Every miss answers IN FRAME, at glance size, in its own words — the three
// refusing states stay distinguishable (EC-27), because "loading…" and "this
// name isn't in the latest scan" are different facts about the world.
const STATUS_COPY = {
  pending: 'Loading…',
  empty: 'Nothing to show',
  error: "Couldn't load this chart",
};

function GlassMessage({ status, note }) {
  return (
    <div style={{
      alignItems: 'center',
      color: status === 'error' ? 'var(--danger)' : 'var(--text-muted)',
      display: 'flex',
      flexDirection: 'column',
      fontSize: 11.5,
      gap: 4,
      inset: 0,
      justifyContent: 'center',
      padding: '0 16px',
      position: 'absolute',
      textAlign: 'center',
    }}>
      <span>{STATUS_COPY[status] || STATUS_COPY.empty}</span>
      {note ? <span style={{ color: 'var(--text-faint)', fontSize: 10.5 }}>{note}</span> : null}
    </div>
  );
}
