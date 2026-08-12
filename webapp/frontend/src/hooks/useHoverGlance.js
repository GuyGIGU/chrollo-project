import { useCallback, useEffect, useRef, useState } from 'react';
import { glanceChartKey } from '../components/glanceMath';

// useHoverGlance — ONE glass per surface, owned here.
//
// The host renders a single <HoverGlass> and spreads `anchorProps(key, arg,
// label)` onto each ticker cell. That is the whole adoption cost: the table
// primitives learn nothing about hovers, and there is exactly one open overlay,
// one timer and one set of document listeners no matter how many rows are on
// screen.
//
// Physics (plan Task 10): an intent delay before the first open, so a pointer
// crossing the table on its way somewhere else never summons anything; then
// row-to-row swaps are INSTANT, because once the glass is up the operator is
// reading and re-arming the delay would just make it stutter. It closes on
// mouse-out, on any scroll, on any pointer-down, on Escape, and whenever the
// host says a modal opened.
//
// `resolve(arg)` is the per-surface seam: it returns a glance object
// synchronously (the artifact surfaces, zero network) or a promise of one (a
// stored snapshot, a bounded archive window). The hook never fetches and the
// resolvers never render.

const INTENT_MS = 180;
// Leaving an anchor closes the glass — but not in the same tick. React
// synthesizes a pointer move between two cells as leave(A) THEN enter(B), so an
// immediate close would set "not open" a beat before the next cell asks to swap,
// making the instant-swap path unreachable and re-arming the full delay for
// every row (the glass would blank and rebuild its chart on each one). This
// grace is just long enough to cross the gap between two cells.
const LEAVE_GRACE_MS = 90;

export default function useHoverGlance(resolve, { suspended = false } = {}) {
  const [glance, setGlance] = useState(null);

  const openTimerRef = useRef(null);
  const closeTimerRef = useRef(null);
  const openRef = useRef(false);   // is the glass up (drives instant swaps)
  const genRef = useRef(0);        // stale-async guard, per useCalibrationChart's idiom

  // Everything the (deliberately stable) handlers need, read at call time.
  const resolveRef = useRef(resolve);
  resolveRef.current = resolve;
  const suspendedRef = useRef(suspended);
  suspendedRef.current = suspended;
  const anchorsRef = useRef(new Map());   // key -> { arg, label }
  const handlersRef = useRef(new Map());  // key -> stable { onMouseEnter, onMouseLeave }

  const clearTimers = () => {
    if (openTimerRef.current) { window.clearTimeout(openTimerRef.current); openTimerRef.current = null; }
    if (closeTimerRef.current) { window.clearTimeout(closeTimerRef.current); closeTimerRef.current = null; }
  };

  const close = useCallback(() => {
    // Bump FIRST so an in-flight resolve can never re-open what we just closed.
    genRef.current += 1;
    clearTimers();
    openRef.current = false;
    setGlance(null);
  }, []);

  const show = useCallback((key, rect) => {
    const anchor = anchorsRef.current.get(key) || {};
    const gen = ++genRef.current;
    // Measure the world at OPEN time, not at mount: the operator's scale knob
    // re-zooms .app-layout by setting a CSS variable, which fires no resize
    // event — a factor cached at mount would send the glass a quarter-screen
    // away for the rest of the session.
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

  // Stable per key, so a memoized row (archive's SetupRow) is not re-rendered
  // by every hover: the handlers are created once and read the live arg from a
  // ref, instead of a fresh closure per render.
  const anchorProps = useCallback((key, arg, label) => {
    anchorsRef.current.set(key, { arg, label });
    const existing = handlersRef.current.get(key);
    if (existing) return existing;

    const handlers = {
      onMouseEnter: (event) => {
        if (suspendedRef.current) return;
        const rect = readRect(event.currentTarget);
        clearTimers();
        if (openRef.current) {
          show(key, rect); // already reading — swap with no delay
          return;
        }
        openTimerRef.current = window.setTimeout(() => {
          openTimerRef.current = null;
          show(key, rect);
        }, INTENT_MS);
      },
      onMouseLeave: () => {
        if (openTimerRef.current) {
          window.clearTimeout(openTimerRef.current);
          openTimerRef.current = null;
        }
        if (closeTimerRef.current) window.clearTimeout(closeTimerRef.current);
        closeTimerRef.current = window.setTimeout(close, LEAVE_GRACE_MS);
      },
    };
    handlersRef.current.set(key, handlers);
    return handlers;
  }, [close, show]);

  // A suspended surface (its modal just opened) drops the glass at once.
  useEffect(() => { if (suspended) close(); }, [suspended, close]);

  useEffect(() => {
    // Scroll does NOT bubble, and this app scrolls in three different boxes
    // (.content-scroll, a table's own well, the window) — so listen in the
    // CAPTURE phase at the document, which sees all of them. A fixed glass
    // would otherwise hang in place while its anchor slid away. These are hard
    // dismissals: they close now, with no grace.
    const onScroll = () => close();
    const onKeyDown = (event) => { if (event.key === 'Escape') close(); };
    const onPointerDown = () => close();
    const onResize = () => close();

    document.addEventListener('scroll', onScroll, true);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown, true);
    window.addEventListener('resize', onResize);
    return () => {
      document.removeEventListener('scroll', onScroll, true);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown, true);
      window.removeEventListener('resize', onResize);
      clearTimers();
    };
  }, [close]);

  // Never leave a timer behind on unmount (a setTimeout no cleanup can clear is
  // a documented trap in this codebase).
  useEffect(() => clearTimers, []);

  return { glance, glassProps: { glance }, anchorProps, closeGlance: close };
}

function readRect(element) {
  if (!element?.getBoundingClientRect) return null;
  const { left, right, top, bottom } = element.getBoundingClientRect();
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
