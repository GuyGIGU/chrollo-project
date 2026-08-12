import { useCallback, useEffect, useRef, useState } from 'react';
import { glanceAction, glanceChartKey } from '../components/glanceMath';

// useHoverGlance — ONE glass per surface, owned here.
//
// The host renders a single <HoverGlass> and spreads `anchorProps(key, arg,
// label)` onto each ROW. That is the whole adoption cost: the table primitives
// learn nothing about hovers, and there is exactly one open overlay, one timer
// and one set of document listeners no matter how many rows are on screen.
//
// WHERE THE CURSOR IS, not what it entered. The first cut drove everything off
// React's onMouseEnter/onMouseLeave, and an event-driven glass has one failure
// the operator hit immediately: anything that swallows or pre-empts the enter
// leaves the surface dark while the pointer sits on a row waiting for it. A
// wheel scroll is the clearest case — it dismisses the glass and moves the page
// UNDER a motionless pointer, so no further enter is ever delivered and the row
// is dead until the mouse is jiggled. Sampling the pointer instead makes every
// frame self-correcting: whatever the cursor is over is what shows, so the worst
// case is one late frame rather than a wedged surface. It also deletes the whole
// leave-then-enter ordering problem that made the instant swap unreachable.
//
// Physics (plan Task 10): a short intent delay before the first open, so a
// pointer crossing the table on its way somewhere else never summons anything;
// then row-to-row moves are INSTANT, because once the glass is up the operator
// is reading and re-arming the delay would just make it stutter. It closes when
// the cursor leaves every anchor, on any pointer-down, on Escape, on resize, and
// whenever the host says a modal opened.
//
// `resolve(arg)` is the per-surface seam: it returns a glance object
// synchronously (the artifact surfaces, zero network) or a promise of one (a
// stored snapshot, a bounded archive window). The hook never fetches and the
// resolvers never render.

// Short enough that resting on a row feels like the chart was already there
// (operator 2026-08-12: "shorten the delay"), long enough that sweeping the
// pointer across a table on the way to a button summons nothing.
const INTENT_MS = 100;
// Leaving every anchor closes the glass — but not in the same frame, so
// crossing the hairline between two rows doesn't blink the chart off and on.
const LEAVE_GRACE_MS = 90;
// After a scroll, look again at what is under the cursor. See onScroll.
const SCROLL_SETTLE_MS = 140;

// `swapDwellMs` — how long the pointer must settle on a NEW row before the glass
// retargets, once it is already open. Zero on the surfaces whose resolver reads
// the artifact already in memory: a swap there costs nothing, so it should be
// instant. The archive sets it, because its resolver goes to the SERVER, and an
// instant swap turns one downward flick across 24 rows into 24 bounded-chart
// requests against the bucket the nightly scans share (review 2026-08-12) — the
// exact sweep glanceCache's header says the design exists to prevent. During the
// dwell the glass keeps showing the row it was already on; it never blanks.
export default function useHoverGlance(resolve, { suspended = false, swapDwellMs = 0 } = {}) {
  const [glance, setGlance] = useState(null);

  const openTimerRef = useRef(null);
  const closeTimerRef = useRef(null);
  const settleTimerRef = useRef(null);
  const openRef = useRef(false);   // is the glass up (drives instant swaps)
  const keyRef = useRef(null);     // the anchor we are armed for / showing
  const genRef = useRef(0);        // stale-async guard, per useCalibrationChart's idiom
  const pointerRef = useRef(null); // last seen cursor, in client px

  // Everything the document listeners need, read at call time.
  const resolveRef = useRef(resolve);
  resolveRef.current = resolve;
  const suspendedRef = useRef(suspended);
  suspendedRef.current = suspended;
  const swapDwellRef = useRef(swapDwellMs);
  swapDwellRef.current = swapDwellMs;
  const anchorsRef = useRef(new Map());  // key -> { arg, label }
  const propsRef = useRef(new Map());    // key -> stable { data-glance-key }

  const clearTimers = () => {
    stopTimer(openTimerRef);
    stopTimer(closeTimerRef);
    stopTimer(settleTimerRef);
  };

  const close = useCallback(() => {
    // Bump FIRST so an in-flight resolve can never re-open what we just closed.
    genRef.current += 1;
    stopTimer(openTimerRef);
    stopTimer(closeTimerRef);
    openRef.current = false;
    keyRef.current = null;
    setGlance(null);
  }, []);

  const show = useCallback((key, element) => {
    const anchor = anchorsRef.current.get(key) || {};
    // Measure the world at OPEN time, not at mount: the operator's scale knob
    // re-zooms .app-layout by setting a CSS variable, which fires no resize
    // event — a factor cached at mount would send the glass a quarter-screen
    // away for the rest of the session.
    const rect = readRect(element);
    if (!rect) {
      // The row was re-rendered out from under the pointer between the sample
      // and this frame. Forget it rather than placing the glass off a zeroed
      // rect; the next pointer sample re-arms on whatever is really there.
      keyRef.current = null;
      return;
    }
    const gen = ++genRef.current;
    const frame = { rect, scale: currentScale(), viewport: currentViewport() };

    const settle = (result) => {
      if (gen !== genRef.current) return; // the pointer moved on; this answer is stale
      if (!result) { close(); return; }
      openRef.current = true;
      setGlance({
        key,
        ...frame,
        status: result.status,
        entry: result.entry ?? null,
        header: result.header ?? null,
        note: result.note ?? null,
        chartKey: result.chartKey || glanceChartKey(result.header?.ticker || anchor.label || key, result.stamp),
      });
    };

    let result;
    try {
      result = resolveRef.current(anchor.arg);
    } catch {
      settle({ status: 'error', header: { ticker: anchor.label || key } });
      return;
    }
    if (result && typeof result.then === 'function') {
      // Paint the pending frame immediately so a slow answer is never a void.
      // It is labelled from the anchor's OWN label — the key can be a row id
      // (the archive keys by setup, since one ticker owns several episodes),
      // and a numeric id in the ticker slot would be a lie for the whole fetch.
      settle({ status: 'pending', header: { ticker: anchor.label || key } });
      result.then(
        (value) => settle(value || { status: 'empty', header: { ticker: anchor.label || key } }),
        () => settle({ status: 'error', header: { ticker: anchor.label || key } }),
      );
      return;
    }
    settle(result);
  }, [close]);

  // ONE pointer sample: what is under the cursor, and what that means for what
  // is on screen. Every entry point (mouse move, scroll settle) funnels through
  // here, so there is a single place where "show this" is decided.
  const sample = useCallback((target) => {
    if (suspendedRef.current) {
      if (openRef.current || keyRef.current) close();
      return;
    }
    const element = target?.closest?.('[data-glance-key]') || null;
    const found = element?.getAttribute('data-glance-key') || null;
    // Only OUR anchors: two surfaces can be mounted at once and both hear every
    // move, so an unregistered key reads exactly like empty space.
    const next = found && anchorsRef.current.has(found) ? found : null;

    switch (glanceAction({ current: keyRef.current, next, open: openRef.current })) {
      case 'none':
        return;
      case 'close':
        stopTimer(openTimerRef);
        keyRef.current = null;
        if (!openRef.current || closeTimerRef.current) return;
        closeTimerRef.current = window.setTimeout(close, LEAVE_GRACE_MS);
        return;
      case 'swap':
        stopTimer(closeTimerRef);
        stopTimer(openTimerRef);
        keyRef.current = next;
        // Instant when the answer is free; a short settle when it costs a
        // request. The open glass stays on its current row meanwhile, so a
        // traversal never blanks it and never fetches what it passed over.
        if (swapDwellRef.current > 0) {
          openTimerRef.current = window.setTimeout(() => {
            openTimerRef.current = null;
            show(next, element);
          }, swapDwellRef.current);
          return;
        }
        show(next, element);
        return;
      default: // 'arm'
        stopTimer(closeTimerRef);
        stopTimer(openTimerRef);
        keyRef.current = next;
        openTimerRef.current = window.setTimeout(() => {
          openTimerRef.current = null;
          show(next, element);
        }, INTENT_MS);
    }
  }, [close, show]);

  // Registration only — the row carries a key, and the pointer does the rest.
  // The returned object is cached per key so a memoized row (archive's SetupRow)
  // is not re-rendered by a fresh props identity on every parent render.
  const anchorProps = useCallback((key, arg, label) => {
    anchorsRef.current.set(key, { arg, label });
    let props = propsRef.current.get(key);
    if (!props) {
      props = { 'data-glance-key': key };
      propsRef.current.set(key, props);
    }
    return props;
  }, []);

  // A suspended surface (its modal just opened) drops the glass at once.
  useEffect(() => { if (suspended) close(); }, [suspended, close]);

  useEffect(() => {
    // CAPTURE for both: a chart canvas or a control that stops propagation on
    // mousemove would otherwise blind the sampler, and scroll does NOT bubble at
    // all — this app scrolls in three different boxes (.content-scroll, a
    // table's own well, the window) and only the document capture phase sees
    // every one of them.
    const onMove = (event) => {
      pointerRef.current = { x: event.clientX, y: event.clientY };
      sample(event.target);
    };
    // The pointer left the WINDOW. Sampling alone cannot see this: the browser
    // stops sending mousemove at the edge, so the last sample is still the row
    // and the glass would sit there over the table until the pointer came back
    // and crossed something that is not a row. A null relatedTarget is the
    // reliable "gone" signal. The stale point dies with it — otherwise the
    // scroll-settle below could re-open the glass at a coordinate the cursor
    // left minutes ago (review 2026-08-12).
    const onMouseOut = (event) => {
      if (event.relatedTarget) return;
      pointerRef.current = null;
      close();
    };
    const onScroll = () => {
      // A fixed glass would hang in place while its anchor slid away, so drop it
      // now — then look again once the scroll settles. That second look is the
      // point: a WHEEL scroll moves the page, not the pointer, so there is no
      // further mouse event to recover from and the row under the cursor would
      // stay dark until the operator jiggled the mouse.
      close();
      stopTimer(settleTimerRef);
      settleTimerRef.current = window.setTimeout(() => {
        settleTimerRef.current = null;
        const point = pointerRef.current;
        if (point) sample(document.elementFromPoint(point.x, point.y));
      }, SCROLL_SETTLE_MS);
    };
    // Hard dismissals: the operator is doing something else now.
    const onKeyDown = (event) => { if (event.key === 'Escape') close(); };
    const onPointerDown = () => close();
    const onResize = () => close();

    document.addEventListener('mousemove', onMove, { capture: true, passive: true });
    document.addEventListener('mouseout', onMouseOut, { capture: true, passive: true });
    document.addEventListener('scroll', onScroll, true);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown, true);
    window.addEventListener('resize', onResize);
    return () => {
      document.removeEventListener('mousemove', onMove, { capture: true });
      document.removeEventListener('mouseout', onMouseOut, { capture: true });
      document.removeEventListener('scroll', onScroll, true);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown, true);
      window.removeEventListener('resize', onResize);
      clearTimers();
    };
  }, [close, sample]);

  // Never leave a timer behind on unmount (a setTimeout no cleanup can clear is
  // a documented trap in this codebase).
  useEffect(() => clearTimers, []);

  return { glance, glassProps: { glance }, anchorProps, closeGlance: close };
}

function stopTimer(ref) {
  if (ref.current) {
    window.clearTimeout(ref.current);
    ref.current = null;
  }
}

// The rect the glass is placed against: the row is the TARGET (hovering
// anywhere on it summons the chart), but a full-width row is a useless anchor —
// "beside it" would mean the screen edge. So the row names its own datum with
// data-glance-anchor (the ticker cell), and the glass sits beside THAT.
function readRect(element) {
  if (!element?.isConnected) return null;
  const target = element.querySelector?.('[data-glance-anchor]') || element;
  const { left, right, top, bottom } = target.getBoundingClientRect();
  if (right - left <= 0 && bottom - top <= 0) return null;
  return { left, right, top, bottom };
}

function currentViewport() {
  if (typeof window === 'undefined') return { width: 0, height: 0 };
  return { width: window.innerWidth, height: window.innerHeight };
}

// The app zooms itself via `--ui-scale` on .app-layout; the glass measures in
// screen px and positions in pre-zoom px, so it has to know the factor.
function currentScale() {
  if (typeof document === 'undefined') return 1;
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--ui-scale');
  const value = Number(String(raw).trim());
  return Number.isFinite(value) && value > 0 ? value : 1;
}
