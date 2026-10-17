import { useCallback, useEffect, useRef, useState } from 'react';
import { LineSeries } from 'lightweight-charts';
import { API_BASE } from '../../api/base';
import { EMPTY_FIX, applyFixClick, fixComplete, fixPayload } from './boxFix';

// The lens's "fix the box" (Fri 17/10/2026): arm it, click the resistance bar and the support bar
// on the daily chart (boxFix.js snaps each to the bar's end point), see the two red lines, save.
// The chart hands clicks in through `clickRef` (useDailyStructureChart subscribes once per build
// and reads the ref), and his lines are drawn on the live chart (`chartRef`) as two series that
// are removed when the draft changes, so a click never rebuilds the chart and never costs his zoom.
const WRITE_HEADERS = { 'Content-Type': 'application/json', 'X-Chrollo-Client': 'chrollo-dashboard' };
const HIS_LINE = { color: '#e5484d', lineWidth: 2, lineStyle: 0, priceLineVisible: false, lastValueVisible: true,
                   crosshairMarkerVisible: false };

const lineData = (candles, fromDay, price) => {
  const from = candles.findIndex((candle) => candle.time >= fromDay);
  if (from < 0) return [];
  return candles.slice(from).map((candle) => ({ time: candle.time, value: price }));
};

export default function useBoxFix(ticker, data, scanIdentity, chartRef, clickRef) {
  const [armed, setArmed] = useState(false);
  const [draft, setDraft] = useState(EMPTY_FIX);
  const [saved, setSaved] = useState(null);     // the saved fix's revision, or null
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const seriesRef = useRef([]);

  // A new chart: everything starts over.
  useEffect(() => {
    setArmed(false);
    setDraft(EMPTY_FIX);
    setSaved(null);
    setError(null);
  }, [ticker]);

  // The chart's clicks reach the draft only while armed.
  useEffect(() => {
    if (!clickRef) return undefined;
    clickRef.current = armed ? (click) => { setDraft((now) => applyFixClick(now, click)); setSaved(null); } : null;
    return () => { clickRef.current = null; };
  }, [armed, clickRef]);

  // His lines on the live chart: redrawn from the draft, removed with it.
  useEffect(() => {
    const chart = chartRef?.current;
    for (const series of seriesRef.current) {
      try { chart?.removeSeries(series); } catch { /* the chart may already be gone */ }
    }
    seriesRef.current = [];
    if (!chart || !data?.candles?.length) return undefined;
    const lines = [];
    if (draft.r != null) lines.push([draft.rDay, draft.r]);
    if (draft.s != null) lines.push([draft.sDay, draft.s]);
    for (const [day, price] of lines) {
      try {
        const series = chart.addSeries(LineSeries, HIS_LINE);
        series.setData(lineData(data.candles, day, price));
        seriesRef.current.push(series);
      } catch { /* a line is decoration: never let it cost the chart */ }
    }
    return undefined;
  }, [draft, chartRef, data]);

  const toggle = useCallback(() => {
    setArmed((now) => !now);
    setError(null);
  }, []);

  const clear = useCallback(() => {
    setDraft(EMPTY_FIX);
    setSaved(null);
    setError(null);
  }, []);

  const save = useCallback(async () => {
    if (!fixComplete(draft) || saving) return;
    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/calibration/box-fixes`, {
        method: 'POST', headers: WRITE_HEADERS, body: JSON.stringify(fixPayload(ticker, data, draft, scanIdentity)),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = body?.detail;
        setError(detail?.problems ? detail.problems.join('; ') : detail?.message || `save failed (${response.status})`);
        return;
      }
      setSaved(body?.revision ?? 1);
      setArmed(false);
    } catch (err) {
      setError(err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }, [draft, saving, ticker, data, scanIdentity]);

  return { armed, draft, saved, error, saving, complete: fixComplete(draft), toggle, clear, save };
}
