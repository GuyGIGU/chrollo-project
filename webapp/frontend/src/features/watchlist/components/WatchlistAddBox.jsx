import { useState } from 'react';

// Type any ticker onto this week's list, long or short. The server checks the
// symbol; a refused one comes back as the store's "not saved" toast.
export default function WatchlistAddBox({ onAdd }) {
  const [ticker, setTicker] = useState('');
  const [side, setSide] = useState('L');
  const submit = (event) => {
    event.preventDefault();
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;
    onAdd(symbol, side);
    setTicker('');
  };
  return (
    <form className="wl-add" onSubmit={submit} aria-label="Add a ticker to this week's list">
      <input type="text" value={ticker} onChange={(event) => setTicker(event.target.value)}
        placeholder="Add ticker…" aria-label="Ticker" maxLength={10} autoComplete="off" spellCheck={false} />
      <div className="wl-add-side" role="group" aria-label="Long or short">
        {['L', 'S'].map((value) => (
          <button key={value} type="button" className={`wl-side wl-side-${value}`} aria-pressed={side === value}
            onClick={() => setSide(value)}>{value}</button>
        ))}
      </div>
      <button type="submit" className="btn btn-sm" disabled={!ticker.trim()}>Add</button>
    </form>
  );
}
