import { useEffect, useRef } from 'react';
import ChartZoomControls from '../charts/ChartZoomControls';
import { CHART_COLORS } from '../charts/chartTheme';
import useDailyStructureChart from '../charts/useDailyStructureChart';
import { readerPair } from './boxFix';
import { TOOLS, TOOL_HOW, TOOL_NAMES, eventWords, miniEvent, toolPrompt } from './boxFixEvents';
import { drawFixLayer, removeLayer } from './boxFixDraw';
import useBoxFix from './useBoxFix';
import { fixedLayer } from './useFixedBox';

// The fix page (Sat 18/10/2026, his word: "more like a pop chart (like calibration, a new page
// covers this one)"): the toolbar's "fix the box" button (or B) covers the lens with this page,
// the daily chart big, and a rail of buttons beside it: the box's two lines, the mini's two lines
// and its span (the mini works exactly like the box), his events, what is placed with a × each,
// Save and Back. Saving returns him to the chart he came from (`onSaved`), as does Back and Escape.
// The reader's read stays drawn under his lines; the fix saved before, if any, in the operator colour.
const GROUPS = [
  { name: 'The box', tools: ['rail-r', 'rail-s'] },
  { name: 'Mini consolidation', tools: ['mini-r', 'mini-s', 'mini-span'] },
  { name: 'Events', tools: ['spring', 'upthrust', 'sos', 'lps', 'former_lps', 'span'] },
];

export default function BoxFixPage({ ticker, data, scanIdentity, skin, fixed, onClose, onSaved }) {
  const containerRef = useRef(null);
  const clickRef = useRef(null);
  const daily = useDailyStructureChart(containerRef, ticker, data, null, 'main', skin, clickRef);
  const fix = useBoxFix(ticker, data, scanIdentity, daily.chartRef, clickRef, onSaved);
  const reader = readerPair(data);
  const lastDay = data?.candles?.length ? data.candles[data.candles.length - 1].time : null;
  const mini = miniEvent(fix.mini, lastDay);

  // The fix saved before, under his draft, in the operator colour.
  const fixedSeries = useRef([]);
  useEffect(() => {
    const chart = daily.chartRef.current;
    removeLayer(chart, fixedSeries.current);
    fixedSeries.current = chart && data?.candles?.length && fixed
      ? drawFixLayer(chart, data.candles, fixedLayer(fixed), CHART_COLORS.operator) : [];
    return () => { removeLayer(daily.chartRef.current, fixedSeries.current); fixedSeries.current = []; };
  }, [fixed, data, daily.chartRef]);

  // Escape: back to the chart, the page's own listener (the lens's closer stands down while the page is up).
  useEffect(() => {
    const onKey = (event) => { if (event.key === 'Escape') { event.preventDefault(); onClose?.(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const placed = [];
  if (fix.draft.r != null) placed.push({ key: 'r', words: `resistance ${fix.draft.r.toFixed(2)} (${fix.draft.rDay})`, remove: () => fix.clearLine('r') });
  if (fix.draft.s != null) placed.push({ key: 's', words: `support ${fix.draft.s.toFixed(2)} (${fix.draft.sDay})`, remove: () => fix.clearLine('s') });
  if (fix.mini.r != null) placed.push({ key: 'mini-r', words: `mini resistance ${fix.mini.r.toFixed(2)} (${fix.mini.rDay})`, remove: () => fix.removeMini('r') });
  if (fix.mini.s != null) placed.push({ key: 'mini-s', words: `mini support ${fix.mini.s.toFixed(2)} (${fix.mini.sDay})`, remove: () => fix.removeMini('s') });
  if (fix.mini.spanStart != null) placed.push({ key: 'mini-span', words: `mini span ${fix.mini.spanStart} to ${fix.mini.spanEnd}`, remove: () => fix.removeMini('span') });
  fix.events.forEach((event, index) => placed.push({ key: `${event.kind}-${event.first_day}-${index}`, words: eventWords(event), event, index, remove: () => fix.remove(index) }));

  return (
    <div className="box-fix-page" role="dialog" aria-modal="true" aria-label={`Fix the box: ${ticker}`}>
      <header className="box-fix-head">
        <button type="button" className="btn" onClick={onClose} title="Back to the chart (Escape)">← Back to the chart</button>
        <strong className="box-fix-ticker">{ticker}</strong>
        <span className="lens-fix-word">FIX THE BOX</span>
        <span className="lens-fix-prompt">{toolPrompt(fix.marks) ?? (fix.tool ? '' : 'choose what to place from the rail, then click the bars')}</span>
        <span className="box-fix-reader">
          {reader ? `reader: R ${reader.r.toFixed(2)} (${reader.rDay}) · S ${reader.s.toFixed(2)} (${reader.sDay})` : 'reader: no box shown'}
        </span>
        <span className="box-fix-acts">
          {fix.error && <span className="lens-fix-error">{fix.error}</span>}
          <button type="button" className="btn" disabled={placed.length === 0} onClick={fix.clear}>Clear</button>
          <button type="button" className="btn btn-primary" disabled={!fix.complete || fix.saving} onClick={fix.save}>{fix.saving ? 'Saving…' : 'Save fix'}</button>
        </span>
      </header>
      <div className="box-fix-body">
        <div className={fix.tool ? 'box-fix-chart is-armed' : 'box-fix-chart'}>
          <div ref={containerRef} className="lens-daily-canvas" />
          <ChartZoomControls chartRef={daily.chartRef} onHome={daily.home} />
        </div>
        <aside className="box-fix-rail">
          {GROUPS.map((group) => (
            <section key={group.name} className="box-fix-group">
              <div className="lens-fix-group-name">{group.name}</div>
              {group.tools.filter((tool) => TOOLS.includes(tool)).map((tool) => (
                <button
                  key={tool}
                  type="button"
                  className="btn lens-fix-option"
                  aria-pressed={fix.tool === tool}
                  onClick={() => fix.arm(tool)}
                >
                  <span className="lens-fix-option-name">{TOOL_NAMES[tool]}</span>
                  <span className="lens-fix-option-how">{TOOL_HOW[tool]}</span>
                </button>
              ))}
            </section>
          ))}
          <section className="box-fix-group">
            <div className="lens-fix-group-name">Placed{mini ? ' · the mini stands' : ''}</div>
            {placed.length === 0 && <span className="box-fix-empty">nothing yet</span>}
            <div className="lens-fix-events">
              {placed.map((item) => (
                <span key={item.key} className="lens-fix-chip">
                  {item.words}
                  {item.event?.kind === 'span' && (
                    <input
                      type="text"
                      className="lens-fix-label"
                      placeholder="name it"
                      aria-label="Name this span"
                      value={item.event.label ?? ''}
                      onChange={(e) => fix.label(item.index, e.target.value)}
                    />
                  )}
                  <button type="button" className="lens-fix-chip-x" aria-label={`Remove ${item.words}`} onClick={item.remove}>×</button>
                </span>
              ))}
            </div>
          </section>
          {fixed?.summary && <div className="box-fix-fixed" title={fixed.summary}>✎ {fixed.summary}</div>}
        </aside>
      </div>
    </div>
  );
}
