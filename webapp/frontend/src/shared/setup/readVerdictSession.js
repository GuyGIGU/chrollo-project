// One chart's feedback requests. A new identity gets a new session; writes
// serialize so a slow response cannot overwrite a newer judgment.
export function createReadVerdictSession({ ticker, scanIdentity, request, onChange }) {
  const identity = {
    ticker,
    scan_date: scanIdentity?.scan_date,
    universe_type: scanIdentity?.universe_type,
    engine_config_version: scanIdentity?.engine_config_version,
  };
  const empty = { verdict: null, grade_verdict: null, note: null };
  const valid = Boolean(ticker && identity.scan_date && identity.universe_type && identity.engine_config_version);
  let state = { ...empty, status: valid ? 'loading' : 'unavailable', stale: false, error: null };
  let disposed = false;
  const publish = (next) => {
    if (disposed) return;
    state = next;
    onChange(state);
  };
  async function load() {
    if (!valid || disposed || state.status === 'saving') return;
    publish({ ...state, status: 'loading', error: null });
    try {
      const body = await request('GET', identity);
      const stale = Boolean(body.verdict && body.engine_config_version !== identity.engine_config_version);
      publish({ ...(stale ? empty : body), status: 'ready', stale, error: null });
    } catch {
      publish({ ...state, status: 'error', error: 'Feedback could not be loaded. Retry before editing.' });
    }
  }
  async function save(changes) {
    if (disposed || state.status !== 'ready') return false;
    const previous = state;
    const next = { verdict: state.verdict, grade_verdict: state.grade_verdict, note: state.note, ...changes };
    if (!next.verdict) Object.assign(next, empty);
    publish({ ...next, status: 'saving', stale: false, error: null });
    try {
      await request('POST', { ...identity, ...next });
      publish({ ...next, status: 'ready', stale: false, error: null });
      return true;
    } catch {
      publish({ ...previous, error: 'Feedback did not save. Your previous judgment was restored.' });
      return false;
    }
  }
  return { load, save, dispose: () => { disposed = true; }, getState: () => state };
}
