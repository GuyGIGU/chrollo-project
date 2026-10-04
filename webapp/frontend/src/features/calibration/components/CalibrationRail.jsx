import { useEffect, useMemo, useRef, useState } from 'react';
import InstrumentTable from '../../../shared/components/InstrumentTable';
import CalibrationRailHeader from './CalibrationRailHeader';
import {
  adjacentSetupRow,
  buildSetupRows,
  filterSetupRows,
  pageCount,
  pageOfKey,
  pageSlice,
  setupDateLabel,
  sortSetupRows,
} from '../model/calibrationTables';
import { isMarkingKeystroke } from '../model/calibrationHotkeys';
import { dialogOpen } from '../../../shared/navigation/keyboardGuard';

// One-click engine test per setup: priority-ordered evidence, not a bare
// pass/fail token — Box/R/S first (the top priority), then LPS, then the
// operator's Trigger vs the engine's fire timing. Green/red are allowed here
// (engine agreement is the one place the doctrine permits them).
// Compact timing glyph for the tested chip — the full phrase lives in the
// tooltip. Kept to one character so the chip (box + Δ + timing) never widens
// the rail's Engine column past its edge: ≤ fired at/before your buy · > fired
// after (late) · ∅ never fired.
const TIMING_LABEL = {
  at_or_before: '≤', after: '>', never: '∅', no_trigger: '',
};

function GradeCell({ grade, testing, onTest }) {
  const test = (e) => { e.stopPropagation(); onTest(); }; // never trigger row-load
  if (grade == null || grade.kind === 'pending') {
    return testing || grade?.kind === 'pending'
      ? <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>testing…</span>
      : (
        <button type="button" className="cal-rail-test" onClick={test}
                title="Test this setup against the engine on its exact frozen snapshot">
          Test
        </button>
      );
  }
  if (grade.kind !== 'graded') {
    // A negative setup — no box for the engine to elect.
    return <span style={{ color: 'var(--text-faint)' }}>—</span>;
  }
  const { box, lps, timing } = grade;
  const state = box.elected ? 'ok' : 'miss';
  const delta = Number.isFinite(box?.rail_delta) ? ` Δ${box.rail_delta.toFixed(2)}` : '';
  const timeTxt = TIMING_LABEL[timing?.outcome] ? ` ${TIMING_LABEL[timing.outcome]}` : '';
  const title = `Box: ${box.elected ? 'elected at your rails' : 'NOT elected'}${delta}`
    + ` · LPS: ${lps?.operator_marked ? 'you marked one' : 'none'}`
    + (timing?.outcome === 'no_trigger' ? ' · no buy marked'
      : ` · engine fired ${timing?.fire_date ?? '—'} vs your buy ${timing?.trigger_date ?? '—'}`)
    + ' — click to re-test';
  return (
    <button type="button" className={`inst-chip ${state} cal-rail-grade`} onClick={test} title={title}>
      {box.elected ? 'box' : 'no box'}{delta}{timeTxt}
    </button>
  );
}

// The calibrated-list navigator (Task 7): a persistent RIGHT-SIDE rail of
// first-class SETUPS — one row per (ticker, as_of) — so the chart stays the
// protagonist and two setups on one symbol read as two distinct entries (never
// collapsed onto "the ticker"). Grouped by ticker like a TradingView watchlist.
// A click LOADS that setup for review/edit (which auto-enters edit mode on its
// box, so the Trigger is immediately editable). The active row is DERIVED from
// the loaded (ticker, as_of) — no store, no
// selectedSetupId. Rows are cheap static DOM (never a live chart). Element
// indicators answer the priority order Box/R/S → LPS → Trigger at a glance; the
// engine-test verdict lands in the Engine column.
//
// Search + pages of 20 (operator ask 2026-10-02, 40 setups and growing): the
// list runs filter -> sort -> page through pure, tested helpers. A new query or
// sort starts at page 1; loading a setup (a rail click or a lookup) turns to
// the page that holds it, and only then — he can still page away from it.
function CalibrationRail({ setups, activeTicker, activeAsOf, onPick,
                          grades = {}, testing = {}, onTest, onDeleteSetup }) {
  const [sort, setSort] = useState({ by: 'ticker', dir: 'asc' });
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);

  // Defensive: accept either prebuilt setup rows or raw marks, so the rail is
  // correct even if a caller hands it the marks array directly.
  const allRows = useMemo(
    () => (Array.isArray(setups) && setups.length && 'key' in setups[0]
      ? setups
      : buildSetupRows(setups)),
    [setups],
  );
  const rows = useMemo(
    () => sortSetupRows(filterSetupRows(allRows, query), sort.by, sort.dir),
    [allRows, query, sort],
  );
  const pages = pageCount(rows.length);
  const current = Math.min(Math.max(1, page), pages); // a delete can shrink the list under him
  // ...and the clamp is WRITTEN BACK (React's adjust-state-while-rendering
  // pattern, no effect): left stale, a later save that grows the list again
  // would turn the rail to a page he never chose (review 2026-10-02).
  if (page !== current) setPage(current);
  const shown = useMemo(() => pageSlice(rows, current), [rows, current]);

  // Turn to the loaded setup's page when the LOADED SETUP changes — keyed on
  // that alone (the rows ride a ref), so a save's summary refresh or his own
  // paging never yanks the page back.
  const activeKey = activeTicker && activeAsOf ? `${activeTicker}|${activeAsOf}` : null;
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const navRef = useRef(null);
  navRef.current = { activeKey, onPick };
  useEffect(() => {
    const holding = activeKey ? pageOfKey(rowsRef.current, activeKey) : null;
    if (holding != null) setPage(holding);
  }, [activeKey]);

  // ↑/↓ walk the list as shown (search + sort applied) and LOAD the setup exactly like a row click; the marking keys'
  // own guard, so typing in the lookup or this search never moves it, nor does a key pressed while a dialog (the
  // unsaved-marks confirm) is up. The page follows via the effect above.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      if (!isMarkingKeystroke(e) || dialogOpen()) return;
      const { activeKey: key, onPick: pick } = navRef.current;
      const row = adjacentSetupRow(rowsRef.current, key, e.key === 'ArrowDown' ? 1 : -1);
      if (!row) return;
      e.preventDefault();
      const focused = document.activeElement;
      rowFocusRef.current = focused?.tagName === 'TR' && Boolean(railRef.current?.contains(focused));
      pick(row.ticker, row.asOf);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Keep the loaded setup's row in the list's view as ↑/↓ (or a lookup) moves it.
  // A clicked row keeps keyboard focus, so focus moves WITH the loaded row: left on
  // the old row, Enter/Space there would reload the setup he just stepped away from
  // (review 2026-10-03). Only a focused row moves; the search box keeps its focus.
  // Across a page turn the row he pressed ↑/↓ on unmounts and focus falls to
  // <body>; rowFocusRef (set by that keypress) carries it to the new row anyway.
  const railRef = useRef(null);
  const rowFocusRef = useRef(false);
  useEffect(() => {
    const activeRow = railRef.current?.querySelector('tr.active-row');
    activeRow?.scrollIntoView({ block: 'nearest' });
    const focused = document.activeElement;
    const rowHeld = focused?.tagName === 'TR' && railRef.current.contains(focused);
    const rowLost = rowFocusRef.current && focused === document.body;
    if (activeRow && focused !== activeRow && (rowHeld || rowLost)) {
      activeRow.focus({ preventScroll: true });
    }
    if (activeRow) rowFocusRef.current = false;
  }, [activeKey, current]);

  const isActive = (row) => row.ticker === activeTicker && row.asOf === activeAsOf;

  const onSort = (key) => {
    setPage(1);
    setSort((prev) =>
      prev.by === key
        ? { by: key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { by: key, dir: key === 'ticker' ? 'asc' : 'desc' });
  };
  const onQuery = (value) => { setQuery(value); setPage(1); };

  const columns = [
    {
      key: 'ticker',
      label: 'Ticker',
      align: 'left',
      render: (row) => (
        <span style={{
          fontWeight: 700,
          color: isActive(row) ? 'var(--myth-bright)' : 'var(--text-main)',
        }}>
          {row.ticker}
        </span>
      ),
    },
    {
      // The as-of session IS the setup's identity — what tells two setups on one
      // symbol apart. A ·N badge flags the rare multi-mark session (extra label /
      // a negative alongside the box). The year shows (2026-10-02): the list now
      // spans more than one, and "Apr 13" alone no longer says which.
      key: 'asOf',
      label: 'Setup',
      align: 'left',
      render: (row) => (
        <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {setupDateLabel(row.asOf)}
          {row.count > 1 && (
            <span style={{ color: 'var(--text-faint)', marginLeft: 4 }}>·{row.count}</span>
          )}
        </span>
      ),
    },
    {
      // His label, given the width the wider rail freed (2026-10-02): the one
      // fluid column — it takes what the others leave and ellipsizes, the full
      // text one hover away (the .cal-rail-label rule sizes the cell).
      key: 'label',
      label: 'Label',
      align: 'left',
      sortable: false,
      render: (row) => (
        <span className="cal-rail-label" title={row.label || undefined}>
          {row.label || <span style={{ color: 'var(--text-faint)' }}>—</span>}
        </span>
      ),
    },
    {
      // What's marked, in priority order Box/R/S → LPS → Trigger. Verdict pill in
      // the operator hue; a neutral LPS chip; the Trigger flag in its warm token.
      key: 'marked',
      label: 'Marked',
      align: 'left',
      sortable: false,
      render: (row) => (
        <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', whiteSpace: 'nowrap' }}>
          <span className={`inst-pill ${row.isBox ? 'box' : 'neg'}`}>{row.verdict}</span>
          {row.hasLps && (
            <span className="cal-rail-tag" title="An LPS is marked on this setup">LPS</span>
          )}
          {row.hasTrigger && (
            <span className="cal-rail-tag trig"
                  title={`Trigger (buy) marked${row.triggerDate ? ` @ ${row.triggerDate}` : ''}`}>
              T
            </span>
          )}
          {row.note && (
            // The operator's note (why it might miss / what would make it hit):
            // a ✎ hint whose full text is one hover away — kept compact so the
            // Engine column beside it never crops.
            <span className="cal-rail-tag" title={row.note} style={{ cursor: 'help' }}>✎</span>
          )}
        </span>
      ),
    },
    {
      // One-click engine test on the exact frozen snapshot — the whole point of
      // the workbench. Lazy: nothing computes until Test is clicked.
      key: 'engine',
      label: 'Engine',
      align: 'left',
      sortable: false,
      render: (row) => (
        <GradeCell
          grade={grades[row.raw?.id]}
          testing={!!testing[row.ticker]}
          onTest={() => onTest?.(row.ticker)}
        />
      ),
    },
    {
      // Per-setup cascade delete (operator ask 2026-07-21): the shared .row-remove
      // × atom, stopPropagation so it never doubles as a row-load. The confirm
      // (a whole setup's marks go at once) lives in the parent handler.
      key: 'del',
      label: '',
      align: 'right',
      sortable: false,
      render: (row) => (
        <button type="button" className="row-remove"
                aria-label={`Delete setup ${row.ticker} ${row.asOf}`}
                title="Delete this setup (removes its saved marks)"
                onClick={(e) => { e.stopPropagation(); onDeleteSetup?.(row); }}>
          ×
        </button>
      ),
    },
  ];

  return (
    <div ref={railRef} style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%' }}>
      <CalibrationRailHeader
        shown={rows.length}
        total={allRows.length}
        query={query}
        onQuery={onQuery}
        page={current}
        pages={pages}
        onPage={setPage}
      />
      {shown.length ? (
        // Fill the rail's remaining height and scroll inside the well (the table
        // owns its own scroll when handed a maxHeight; '100%' resolves against
        // this flex:1 min-height:0 wrapper).
        <div style={{ flex: 1, minHeight: 0 }}>
          <InstrumentTable
            columns={columns}
            rows={shown}
            rowKey={(row) => row.key}
            sortBy={sort.by}
            sortDir={sort.dir}
            onSort={onSort}
            onRowClick={(row) => onPick(row.ticker, row.asOf)}
            rowClassName={(row) => (isActive(row) ? 'active-row' : '')}
            ariaLabel="Calibrated setups"
            maxHeight="100%"
          />
        </div>
      ) : (
        <div style={{ color: 'var(--text-faint)', fontSize: 12, padding: '8px 2px' }}>
          {allRows.length
            ? `No setup matches “${query.trim()}”.`
            : 'No setups yet — load a chart and mark one; it appears here.'}
        </div>
      )}
    </div>
  );
}

export default CalibrationRail;
