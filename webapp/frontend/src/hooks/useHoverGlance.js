import { useCallback, useEffect, useRef, useState } from 'react';
import { glanceChartKey } from '../components/glanceMath';

// useHoverGlance — ONE glass per surface, owned here.
//
// The host renders a single <HoverGlass> and spreads `anchorProps(key, arg)`
// onto each ticker cell. That is the whole adoption cost: the table primitives
// learn nothing about hovers, and there is exactly one open overlay, one timer
// and one set of document listeners no matter how many rows are on screen.
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

export default function useHoverGlance(resolve, { suspended = false } = {}) {
  const [glance, setGlance] = useState(null);
  const [viewport, setViewport] = useState(() => currentViewport());
  const [scale, setScale] = useState(() => currentScale());

  const timerRef = useRef(null);
  const openRef = useRef(false);   // is the glass currently up (drives instant swaps)
  const genRef = useRef(0);        // stale-async guard, per useCalibrationChart's idiom
  const resolveRef = useRef(resolve);
  resolveRef.current = resolve;

  const clearTimer = () => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const close = useCallback(() => {
    // Bump FIRST so an in-flight resolve can never re-open what we just closed.
    genRef.current += 1;
    clearTimer();
    openRef.current = false;
    setGlance(null);
  }, []);

  const show = useCallback((key, rect, arg) => {
    const gen = ++genRef.current;
    const settle = (result) => {
      if (gen !== genRef.current) return; // the pointer moved on; this answer is stale
      if (!result) { close(); return; }
      openRef.current = true;
      setGlance({
        key,
        rect,
        status: result.status,
        entry: result.entry ?? null,
        header: result.header ?? null,
        note: result.note ?? null,
        chartKey: result.chartKey || glanceChartKey(result.header?.ticker || key, result.stamp),
      });
    };

    let result;
    try {
      result = resolveRef.current(arg);
    } catch {
      settle({ status: 'error' });
      return;
    }
    if (result && typeof result.then === 'function') {
      // Paint the pending frame immediately so a slow answer is never a void.
      settle({ status: 'pending', header: result.header ?? { ticker: key } });
      result.then(settle, () => settle({ status: 'error' }));
      return;
    }
    settle(result);
  }, [close]);

  const anchorProps = useCallback((key, arg) => ({
    onMouseEnter: (event) => {
      if (suspended) return;
      const rect = readRect(event.currentTarget);
      clearTimer();
      if (openRef.current) {
        show(key, rect, arg); // already reading — swap with no delay
        return;
      }
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        show(key, rect, arg);
      }, INTENT_MS);
    },
    onMouseLeave: () => {
      clearTimer();
      close();
    },
  }), [close, show, suspended]);

  // A suspended surface (its modal just opened) drops the glass at once.
  useEffect(() => { if (suspended) close(); }, [suspended, close]);

  useEffect(() => {
    // Scroll does NOT bubble, and this app scrolls in three different boxes
    // (.content-scroll, a table's own well, the window) — so listen in the
    // CAPTURE phase at the document, which sees all of them. A fixed glass
    // would otherwise hang in place while its anchor slid away.
    const onScroll = () => close();
    const onKeyDown = (event) => { if (event.key === 'Escape') close(); };
    const onPointerDown = () => close();
    const onViewportChange = () => {
      setViewport(currentViewport());
      setScale(currentScale());
      close();
    };

    document.addEventListener('scroll', onScroll, true);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown, true);
    window.addEventListener('resize', onViewportChange);
    return () => {
      document.removeEventListener('scroll', onScroll, true);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown, true);
      window.removeEventListener('resize', onViewportChange);
      clearTimer();
    };
  }, [close]);

  // Never leave a timer behind on unmount (a setTimeout no cleanup can clear is
  // a documented trap in this codebase).
  useEffect(() => clearTimer, []);

  return { glance, glassProps: { glance, scale, viewport }, anchorProps, closeGlance: close };
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
