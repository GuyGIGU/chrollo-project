import Modal from '../../../shared/components/Modal';
import { failingChecks, scanStatusColor } from '../../../shared/formatting/appFormat';
import { fmtInt } from '../../../shared/formatting/format.js';
import {
  RUN_KIND_LABELS, RUN_STATUS_LABELS, RUN_TRIGGER_LABELS,
  RUN_VERDICT_LABELS, RUN_VERDICT_TONES,
} from '../../../shared/presentation/wireVocabulary';

// The one scan-run diagnostics registry. Reached from the topbar status pills
// ("why is this Degraded?") and from the Archive header's Scan History button —
// one component, one fetch, two doors.
//
// Every judgment here arrives already resolved by the backend: `run.verdict`,
// `run.reason`, `run.solution`, `check.*` and `notice` are server text rendered
// verbatim. This file holds only tone, ordering, headings and the slug -> words
// lookup — it never works out which verdict a run or the app is in (EC-28).
export default function ScanHistoryModal({ open, runs, notice, loading, health, onClose }) {
  if (!open) return null;

  const checks = failingChecks(health);

  return (
    <Modal onClose={onClose} overlayStyle={backdropStyle} contentClassName="glass-panel" contentStyle={panelStyle} contentProps={{ 'aria-label': 'Scan runs' }}>
      <div style={headerStyle}>
        <div style={{ fontWeight: 700 }}>🕒 Scan runs</div>
        <button onClick={onClose} style={closeButtonStyle} aria-label="Close">✕</button>
      </div>

      <div style={sectionLabelStyle}>What is wrong right now</div>
      {checks.length ? (
        <div style={{ display: 'grid', gap: '8px', marginBottom: '14px' }}>
          <Verdict verdict={health?.verdict} style={appVerdictStyle} />
          {checks.map(check => (
            <div key={check.key} style={checkRowStyle}>
              <div style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{check.label || check.key}</div>
              <div style={{ color: 'var(--text-main)' }}>{check.reason || ''}</div>
              {check.solution && <div style={solutionStyle}>Do this: {check.solution}</div>}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ ...mutedTextStyle, marginBottom: '14px' }}>Everything is healthy right now.</div>
      )}

      {notice && <div style={noticeStyle}>{notice}</div>}

      <div style={sectionLabelStyle}>Recent runs</div>
      {loading ? (
        <div style={mutedTextStyle}>Loading…</div>
      ) : (runs && runs.length) ? (
        <table style={tableStyle}>
          <thead>
            <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border-color)' }}>
              <th style={leftCellStyle}>Started</th>
              <th style={leftCellStyle}>Job</th>
              <th style={leftCellStyle}>Trigger</th>
              <th style={rightCellStyle}>Setups</th>
              <th style={leftCellStyle}>Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map(run => (
              <RunRows key={run.id} run={run} />
            ))}
          </tbody>
        </table>
      ) : (
        <div style={mutedTextStyle}>No scan runs recorded yet.</div>
      )}
    </Modal>
  );
}

// The two-state headline, in the operator's words. Renders NOTHING for an
// unknown or absent slug rather than inventing one.
function Verdict({ verdict, style }) {
  const label = RUN_VERDICT_LABELS[verdict];
  if (!label) return null;
  return <div style={{ ...style, color: RUN_VERDICT_TONES[verdict] }}>{label}</div>;
}

// A clean run stays one dense line; only a run that went wrong pays for the
// second line, so a healthy history reads exactly as tight as it did before.
function RunRows({ run }) {
  const explained = run.verdict || run.reason || run.solution;
  return (
    <>
      <tr style={{ borderBottom: explained ? 'none' : '1px solid rgba(255,255,255,0.03)' }}>
        <td style={leftCellStyle} title={run.finished_at ? `recorded ${run.finished_at}` : ''}>
          {formatRunTime(run)}
        </td>
        <td style={leftCellStyle}>{RUN_KIND_LABELS[run.kind] || run.kind || '—'}</td>
        <td style={leftCellStyle}>{RUN_TRIGGER_LABELS[run.trigger] || run.trigger || '—'}</td>
        {/* Only a screener scan produces setups; a backfill or a download has no
            count to be unknown about, so its cell stays empty. */}
        <td style={rightCellStyle}>{run.kind === 'scan' ? fmtInt(run.n_setups, 'unknown') : '—'}</td>
        <td style={{ ...leftCellStyle, color: scanStatusColor(run.status) }}>
          {RUN_STATUS_LABELS[run.status] || run.status}
        </td>
      </tr>
      {explained && (
        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
          <td colSpan={5} style={explainCellStyle}>
            {/* The verdict LEADS the row; the reason and the remedy sit under
                it. He asked for the two states up front, not the taxonomy. */}
            <Verdict verdict={run.verdict} style={runVerdictStyle} />
            {run.reason && <div style={{ color: 'var(--text-main)' }}>{run.reason}</div>}
            {run.solution && <div style={solutionStyle}>Do this: {run.solution}</div>}
            {run.error && run.error !== run.reason && (
              <details style={{ marginTop: '4px' }}>
                <summary style={{ color: 'var(--text-faint)', cursor: 'pointer' }}>Developer detail</summary>
                <div style={rawErrorStyle}>{run.error}</div>
              </details>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// started_at, never finished_at: on a run that was killed mid-flight finished_at
// is the moment the dead row was DETECTED, which can be days after the death.
const formatRunTime = (run) => (run.started_at || run.finished_at || '—').replace('T', ' ').slice(0, 19);

const backdropStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', zIndex: 1000,
};

const panelStyle = { width: 'min(760px, 94vw)', maxHeight: '82vh', overflow: 'auto', padding: '18px' };
const headerStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' };
const sectionLabelStyle = {
  color: 'var(--text-muted)', fontSize: '10px', fontWeight: 600,
  letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px',
};
const checkRowStyle = { fontSize: '12px', lineHeight: 1.45 };
const appVerdictStyle = { fontSize: '15px', fontWeight: 700 };
const runVerdictStyle = { fontWeight: 700 };
const solutionStyle = { color: 'var(--text-muted)', lineHeight: 1.45 };
const noticeStyle = {
  border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 10px',
  color: 'var(--warning)', fontSize: '12px', lineHeight: 1.45, marginBottom: '14px',
};
const mutedTextStyle = { color: 'var(--text-muted)', fontSize: '12px' };
const closeButtonStyle = { background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px' };
const tableStyle = { width: '100%', fontSize: '11px', fontFamily: "'JetBrains Mono', monospace" };
const leftCellStyle = { textAlign: 'left', padding: '4px 6px' };
const rightCellStyle = { textAlign: 'right', padding: '4px 6px' };
const explainCellStyle = { padding: '0 6px 6px 6px', fontSize: '11px', lineHeight: 1.5 };
const rawErrorStyle = {
  color: 'var(--text-faint)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
  maxHeight: '160px', overflow: 'auto', marginTop: '4px',
};
