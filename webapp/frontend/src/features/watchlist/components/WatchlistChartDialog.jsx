import { useEffect, useMemo, useState } from 'react';
import Modal from '../../../shared/components/Modal';
import { hasCommandModifier, isTypingTarget } from '../../../shared/navigation/keyboardGuard';
import { resolvePaneData } from '../presentation/watchlistChartData';
import { useCandleEnvelopes } from '../hooks/useWatchlistCandles';
import { fetchTickerCandles } from '../hooks/watchlistCandlesStore';
import WatchlistChartCluster from './WatchlistChartCluster';

// The existing D/W/M viewer opens from a row; the list stays mounted underneath.
export default function WatchlistChartDialog({ record, scan, onClose, onNext, onPrev }) {
  const [overlayOn, setOverlayOn] = useState(true);
  const envelopes = useCandleEnvelopes();
  const ticker = record.ticker;
  useEffect(() => { fetchTickerCandles(ticker, record.pin_universe_key || null); }, [ticker, record.pin_universe_key]);
  const endpointEntry = envelopes[ticker];
  const pane = useMemo(() => resolvePaneData({ scanEntry: scan?.entry, scanDate: scan?.scanDate, endpointEntry, overlayOn }),
    [scan, endpointEntry, overlayOn]);
  return (
    <Modal onClose={onClose} contentClassName="wl-chart-dialog"
      contentProps={{ 'aria-label': `${ticker} watchlist charts`, onKeyDown: (event) => {
        if (isTypingTarget(event.target) || hasCommandModifier(event)) return;   // Alt+Left is the browser's Back
        if (event.key === 'ArrowDown' || event.key === 'ArrowRight') { event.preventDefault(); onNext?.(); }
        if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') { event.preventDefault(); onPrev?.(); }
      } }}>
      <header className="wl-chart-header">
        <strong className="wl-chart-ticker">{ticker}</strong>
        <button type="button" className="btn btn-sm" aria-pressed={overlayOn} onClick={() => setOverlayOn((value) => !value)}>Engine read</button>
        {overlayOn && !pane.overlayAvailable && <span className="wl-toggle-note">No engine read — price and volume only</span>}
        <span className="wl-chart-stamp">
          {pane.source === 'scan' && `As scanned ${pane.provenance.scanDate || '—'}`}
          {pane.source === 'endpoint' && `Last session ${pane.provenance.lastBarDate || '—'}`}
        </span>
        {pane.reason === 'error' && <button type="button" className="btn btn-sm"
          onClick={() => fetchTickerCandles(ticker, record.pin_universe_key || null)}>Retry candles</button>}
        {onPrev && <button type="button" className="btn btn-sm" onClick={onPrev}>Prev</button>}
        {onNext && <button type="button" className="btn btn-sm" onClick={onNext}>Next</button>}
        <button type="button" className="btn btn-sm" aria-label="Close watchlist charts" onClick={onClose}>Close</button>
      </header>
      <WatchlistChartCluster pane={pane} ticker={ticker} />
    </Modal>
  );
}
