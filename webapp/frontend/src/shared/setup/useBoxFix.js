import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE } from '../../api/base';
import { CHART_COLORS } from '../charts/chartTheme';
import { EMPTY_FIX, applyFixClick, fixComplete, fixPayload, readerPair } from './boxFix';
import { EMPTY_EVENTS, applyEventClick, armEvent, eventsPayload, labelEvent, removeEvent } from './boxFixEvents';
import { drawFixLayer, removeLayer } from './boxFixDraw';

// The lens's "fix the box" (Fri 17/10/2026): arm it, click the resistance bar and the support bar
// on the daily chart (boxFix.js snaps each to the bar's end point), see the two red lines, save.
// Widened Sat 18/10/2026 on his words ("lets widen it by letting me put events ... and add an
// indicator that this box was edited/fixed"): while armed, a letter arms one of his events and
// the clicks place it (boxFixEvents.js); the events are saved beside the fix, and the fix saved
// on this chart before (the latest for the ticker) is drawn in the operator colour over the
// reader's read, with the backend's one sentence for it (`fixed.summary`, EC-28).
// The chart hands clicks in through `clickRef` (useDailyStructureChart subscribes once per build
// and reads the ref), and every line is drawn on the live chart (`chartRef`) as series that are
// removed when the draft changes, so a click never rebuilds the chart and never costs his zoom.
const WRITE_HEADERS = { 'Content-Type': 'application/json', 'X-Chrollo-Client': 'chrollo-dashboard' };
const DRAFT_RED = '#e5484d';

const latestFix = (fixes) => (Array.isArray(fixes) && fixes.length
  ? [...fixes].sort((a, b) => String(b.scan_day).localeCompare(String(a.scan_day)))[0] : null);

const savedLayer = (fix) => (fix ? { r: fix.resistance, rDay: fix.r_day, s: fix.support, sDay: fix.s_day, events: fix.events || [] } : null);

const refusal = (body, status) => {
  const detail = body?.detail;
  return detail?.problems ? detail.problems.join('; ') : detail?.message || `save failed (${status})`;
};

export default function useBoxFix(ticker, data, scanIdentity, chartRef, clickRef) {
  const [armed, setArmed] = useState(false);
  const [draft, setDraft] = useState(EMPTY_FIX);
  const [marks, setMarks] = useState(EMPTY_EVENTS);
  const [fixed, setFixed] = useState(null);      // the fix saved for this ticker, from the backend, or null
  const [saved, setSaved] = useState(null);      // the saved fix's revision after a save this sitting, or null
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const draftSeries = useRef([]);
  const fixedSeries = useRef([]);

  // A new chart: everything starts over, and the fix saved on it before is fetched.
  useEffect(() => {
    setArmed(false);
    setDraft(EMPTY_FIX);
    setMarks(EMPTY_EVENTS);
    setSaved(null);
    setError(null);
    setFixed(null);
    if (!ticker) return undefined;
    let live = true;
    fetch(`${API_BASE}/calibration/box-fixes?ticker=${encodeURIComponent(ticker)}`)
      .then((response) => (response.ok ? response.json() : []))
      .then((body) => { if (live) setFixed(latestFix(body)); })
      .catch(() => {});
    return () => { live = false; };
  }, [ticker]);

  // The chart's clicks reach the draft only while armed: an armed event takes them, else the two lines.
  // The ref carries the armed tool into the handler without re-subscribing it on every click.
  const marksRef = useRef(marks);
  marksRef.current = marks;
  useEffect(() => {
    if (!clickRef) return undefined;
    clickRef.current = armed ? (click) => {
      if (marksRef.current.tool) setMarks((now) => applyEventClick(now, click, data?.candles || []));
      else setDraft((now) => applyFixClick(now, click));
      setSaved(null);
    } : null;
    return () => { clickRef.current = null; };
  }, [armed, clickRef, data]);

  // His draft on the live chart, red: redrawn from the draft and the placed events, removed with them.
  useEffect(() => {
    const chart = chartRef?.current;
    removeLayer(chart, draftSeries.current);
    draftSeries.current = chart && data?.candles?.length
      ? drawFixLayer(chart, data.candles, { ...draft, events: marks.events }, DRAFT_RED, { lastValueVisible: true }) : [];
  }, [draft, marks.events, chartRef, data]);

  // The fix saved before, in the operator colour, over the reader's read.
  useEffect(() => {
    const chart = chartRef?.current;
    removeLayer(chart, fixedSeries.current);
    fixedSeries.current = chart && data?.candles?.length && fixed
      ? drawFixLayer(chart, data.candles, savedLayer(fixed), CHART_COLORS.operator) : [];
  }, [fixed, chartRef, data]);

  const toggle = useCallback(() => {
    setArmed((now) => !now);
    setMarks((now) => armEvent(now, null));
    setError(null);
  }, []);

  // The ref is moved at once too, so a click that lands before the next render still sees the armed tool.
  const arm = useCallback((kind) => {
    marksRef.current = armEvent(marksRef.current, kind);
    setMarks((now) => armEvent(now, kind));
  }, []);
  const remove = useCallback((index) => setMarks((now) => removeEvent(now, index)), []);
  const label = useCallback((index, text) => setMarks((now) => labelEvent(now, index, text)), []);

  const clear = useCallback(() => {
    setDraft(EMPTY_FIX);
    setMarks(EMPTY_EVENTS);
    setSaved(null);
    setError(null);
  }, []);

  // What the save sends as his two lines: the draft when both stand, else the reader's pair under his
  // events alone ("the box is right, here are its events"); nothing to save without one or the other.
  const lines = useMemo(() => {
    if (fixComplete(draft)) return draft;
    const reader = readerPair(data);
    return marks.events.length && reader ? { r: reader.r, rDay: reader.rDay, s: reader.s, sDay: reader.sDay } : null;
  }, [draft, data, marks.events.length]);
  const canSave = Boolean(lines) && (fixComplete(draft) || marks.events.length > 0);

  const save = useCallback(async () => {
    if (!lines || saving) return;
    setSaving(true);
    setError(null);
    try {
      let response = await fetch(`${API_BASE}/calibration/box-fixes`, {
        method: 'POST', headers: WRITE_HEADERS, body: JSON.stringify(fixPayload(ticker, data, lines, scanIdentity)),
      });
      let body = await response.json().catch(() => null);
      if (!response.ok) { setError(refusal(body, response.status)); return; }
      const events = eventsPayload(marks.events);
      if (events.length || (body?.events?.length ?? 0) > 0) {
        response = await fetch(`${API_BASE}/calibration/box-fixes/${body.id}/events`, {
          method: 'PUT', headers: WRITE_HEADERS, body: JSON.stringify(events),
        });
        const withEvents = await response.json().catch(() => null);
        if (!response.ok) { setError(refusal(withEvents, response.status)); return; }
        body = withEvents;
      }
      setFixed(body);
      setSaved(body?.revision ?? 1);
      setDraft(EMPTY_FIX);
      setMarks(EMPTY_EVENTS);
      setArmed(false);
    } catch (err) {
      setError(err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }, [lines, saving, ticker, data, scanIdentity, marks.events]);

  return {
    armed, draft, events: marks.events, tool: marks.tool, marks, fixed, saved, error, saving,
    complete: canSave, toggle, arm, remove, label, clear, save,
  };
}
