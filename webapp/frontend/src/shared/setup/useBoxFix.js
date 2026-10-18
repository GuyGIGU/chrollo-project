import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE } from '../../api/base';
import { EMPTY_FIX, applyRailClick, fixComplete, fixPayload, readerPair } from './boxFix';
import {
  EMPTY_EVENTS, allEvents, applyToolClick, armTool, eventsPayload, labelEvent, removeEvent, removeMiniPart,
} from './boxFixEvents';
import { drawFixLayer, removeLayer } from './boxFixDraw';

// The fix page's editing (Fri 17/10/2026, widened Sat 18/10/2026): a tool armed by its button, the
// clicks on the page's daily chart placing the box's two lines (boxFix.js), the mini's lines and
// span and his events (boxFixEvents.js), the draft drawn red on the live chart, and Save: the two
// lines go first (his, or the reader's pair under events alone: "the box is right, here are its
// events"), then the events as a whole; `onSaved(fix)` gets the backend's answer, and the page
// returns to the chart. The chart hands clicks in through `clickRef` (useDailyStructureChart
// subscribes once per build and reads the ref); every line is a series removed when the draft
// changes, so a click never rebuilds the chart and never costs his zoom.
const WRITE_HEADERS = { 'Content-Type': 'application/json', 'X-Chrollo-Client': 'chrollo-dashboard' };
const DRAFT_RED = '#e5484d';

const refusal = (body, status) => {
  const detail = body?.detail;
  return detail?.problems ? detail.problems.join('; ') : detail?.message || `save failed (${status})`;
};

export default function useBoxFix(ticker, data, scanIdentity, chartRef, clickRef, onSaved) {
  const [draft, setDraft] = useState(EMPTY_FIX);
  const [marks, setMarks] = useState(EMPTY_EVENTS);
  const [saved, setSaved] = useState(null);      // the saved fix's revision after a save this sitting, or null
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const draftSeries = useRef([]);
  const lastDay = data?.candles?.length ? data.candles[data.candles.length - 1].time : null;

  // A new chart: everything starts over.
  useEffect(() => {
    setDraft(EMPTY_FIX);
    setMarks(EMPTY_EVENTS);
    setSaved(null);
    setError(null);
  }, [ticker]);

  // The chart's clicks: the box's line tools move the draft, every other tool the marks. The ref
  // carries the armed tool into the handler without re-subscribing it on every click.
  const marksRef = useRef(marks);
  marksRef.current = marks;
  useEffect(() => {
    if (!clickRef) return undefined;
    clickRef.current = (click) => {
      const tool = marksRef.current.tool;
      if (!tool) return;
      if (tool === 'rail-r' || tool === 'rail-s') {
        setDraft((now) => applyRailClick(now, tool === 'rail-r' ? 'r' : 's', click));
        marksRef.current = armTool(marksRef.current, null);
        setMarks((now) => armTool(now, null));
      } else {
        setMarks((now) => applyToolClick(now, click, data?.candles || []));
      }
      setSaved(null);
    };
    return () => { clickRef.current = null; };
  }, [clickRef, data]);

  // Everything placed, as the save and the drawing see it: the events with the mini among them when
  // both its lines stand, and a lone mini line drawn from its day to the edge meanwhile.
  const events = useMemo(() => allEvents(marks, lastDay), [marks, lastDay]);
  const loneMiniLines = useMemo(() => {
    const { mini } = marks;
    if (mini.r != null && mini.s != null) return [];
    return [[mini.rDay, mini.r], [mini.sDay, mini.s]].filter(([day, price]) => day && price != null);
  }, [marks]);

  // His draft on the live chart, red: redrawn from the draft and the marks, removed with them.
  useEffect(() => {
    const chart = chartRef?.current;
    removeLayer(chart, draftSeries.current);
    draftSeries.current = chart && data?.candles?.length
      ? drawFixLayer(chart, data.candles, { ...draft, events, lines: loneMiniLines }, DRAFT_RED, { lastValueVisible: true }) : [];
  }, [draft, events, loneMiniLines, chartRef, data]);

  // The ref is moved at once too, so a click that lands before the next render still sees the armed tool.
  const arm = useCallback((tool) => {
    marksRef.current = armTool(marksRef.current, tool);
    setMarks((now) => armTool(now, tool));
    setError(null);
  }, []);
  const remove = useCallback((index) => setMarks((now) => removeEvent(now, index)), []);
  const removeMini = useCallback((part) => setMarks((now) => removeMiniPart(now, part)), []);
  const label = useCallback((index, text) => setMarks((now) => labelEvent(now, index, text)), []);
  const clearLine = useCallback((which) => setDraft((now) => (which === 'r'
    ? { ...now, r: null, rDay: null } : { ...now, s: null, sDay: null })), []);

  const clear = useCallback(() => {
    setDraft(EMPTY_FIX);
    setMarks(EMPTY_EVENTS);
    setSaved(null);
    setError(null);
  }, []);

  // What the save sends as his two lines: the draft when both stand, else the reader's pair under his
  // events alone; nothing to save without one or the other.
  const lines = useMemo(() => {
    if (fixComplete(draft)) return draft;
    const reader = readerPair(data);
    return events.length && reader ? { r: reader.r, rDay: reader.rDay, s: reader.s, sDay: reader.sDay } : null;
  }, [draft, data, events.length]);
  const complete = Boolean(lines);

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
      const payload = eventsPayload(events);
      if (payload.length || (body?.events?.length ?? 0) > 0) {
        response = await fetch(`${API_BASE}/calibration/box-fixes/${body.id}/events`, {
          method: 'PUT', headers: WRITE_HEADERS, body: JSON.stringify(payload),
        });
        const withEvents = await response.json().catch(() => null);
        if (!response.ok) { setError(refusal(withEvents, response.status)); return; }
        body = withEvents;
      }
      setSaved(body?.revision ?? 1);
      setDraft(EMPTY_FIX);
      setMarks(EMPTY_EVENTS);
      onSaved?.(body);
    } catch (err) {
      setError(err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }, [lines, saving, ticker, data, scanIdentity, events, onSaved]);

  return {
    draft, marks, tool: marks.tool, events: marks.events, mini: marks.mini, saved, error, saving, complete,
    arm, remove, removeMini, label, clearLine, clear, save,
  };
}
