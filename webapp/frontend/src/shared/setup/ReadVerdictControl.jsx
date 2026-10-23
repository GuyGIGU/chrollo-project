import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/base';
import { createReadVerdictSession } from './readVerdictSession.js';

const READ_REASONS = ['rails', 'story', 'posture', 'phases', 'other'];
const GRADES = [['too_high', 'Too high'], ['agree', 'About right'], ['too_low', 'Too low']];

async function request(method, body) {
  const url = `${API_BASE}/archive/reviews/read-verdict`;
  const response = await fetch(method === 'GET' ? `${url}?${new URLSearchParams({
    ticker: body.ticker, scan_date: body.scan_date, universe_type: body.universe_type,
  })}` : url, method === 'GET' ? undefined : {
    method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Feedback ${method}: ${response.status}`);
  return response.json();
}

function Feedback({ ticker, scanIdentity }) {
  const [state, setState] = useState({ status: 'loading' });
  const [reasonOpen, setReasonOpen] = useState(false);
  const [otherText, setOtherText] = useState(null);
  const scanDate = scanIdentity?.scan_date;
  const universeType = scanIdentity?.universe_type;
  const engineVersion = scanIdentity?.engine_config_version;
  const session = useRef(null);
  useEffect(() => {
    const current = createReadVerdictSession({ ticker, scanIdentity: {
      scan_date: scanDate, universe_type: universeType, engine_config_version: engineVersion,
    }, request, onChange: setState });
    session.current = current;
    setState(current.getState());
    current.load();
    return () => current.dispose();
  }, [ticker, scanDate, universeType, engineVersion]);
  const disabled = state.status !== 'ready';
  const record = (changes) => session.current?.save(changes);
  const chooseRead = (verdict) => {
    const next = state.verdict === verdict ? null : verdict;
    setReasonOpen(next === 'disagree');
    record({ verdict: next, ...(next === 'agree' ? { note: null } : {}) });
  };
  return (
    <div aria-label="Chart feedback" style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <span style={{ color: 'var(--text-faint)' }}>The read:</span>
        {[['agree', 'Tells it right'], ['disagree', 'Reads it wrong']].map(([value, label]) => (
          <button key={value} type="button" disabled={disabled} aria-pressed={state.verdict === value}
            className={`narrative-verdict-btn${state.verdict === value ? ' is-active' : ''}`}
            onClick={() => chooseRead(value)}>{label}</button>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
        <span style={{ color: 'var(--text-faint)' }}>The grade:</span>
        {GRADES.map(([value, label]) => (
          <button key={value} type="button" disabled={disabled || !state.verdict}
            title={!state.verdict ? 'Judge the read first, then its grade' : undefined}
            aria-pressed={state.grade_verdict === value}
            className={`narrative-verdict-btn${state.grade_verdict === value ? ' is-active' : ''}`}
            onClick={() => record({ grade_verdict: state.grade_verdict === value ? null : value })}>{label}</button>
        ))}
      </div>
      {reasonOpen && state.verdict === 'disagree' && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
          <span>What&apos;s off?</span>
          {READ_REASONS.map((reason) => <button key={reason} type="button" disabled={disabled}
            className={`narrative-reason-chip${state.note === reason ? ' is-active' : ''}`}
            onClick={() => {
              if (reason === 'other') { setOtherText(''); return; }
              record({ note: reason }); setReasonOpen(false);
            }}>{reason}</button>)}
          {otherText !== null && <input aria-label="Read disagreement reason" className="narrative-reason-input"
            value={otherText} disabled={disabled} onChange={(event) => setOtherText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') { record({ note: otherText.trim() || null }); setReasonOpen(false); }
              if (event.key === 'Escape') setReasonOpen(false);
            }} />}
          <button type="button" className="narrative-reason-chip" onClick={() => setReasonOpen(false)}>Skip reason</button>
        </div>
      )}
      <div role="status" aria-live="polite" style={{ color: 'var(--text-faint)', marginTop: 6 }}>
        {state.status === 'loading' ? 'Loading feedback…' : null}
        {state.status === 'saving' ? 'Saving…' : null}
        {state.status === 'unavailable' ? 'Feedback needs a saved scan identity.' : null}
        {state.stale ? 'Previous feedback belongs to another engine version. Judge this reading again.' : null}
        {state.error}
        {state.status === 'error' && <button type="button" className="narrative-reason-chip" onClick={() => session.current.load()}>Retry</button>}
      </div>
    </div>
  );
}

export default function ReadVerdictControl({ ticker, scanIdentity }) {
  const key = JSON.stringify([ticker, scanIdentity?.scan_date, scanIdentity?.universe_type, scanIdentity?.engine_config_version]);
  return <Feedback key={key} ticker={ticker} scanIdentity={scanIdentity} />;
}
