import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';
import { confirmDialog, toast } from '../../../shared/components/feedback';
import {
  activeStreamUrl,
  attachStreamUrl,
  cancelStreamUrl,
  reattachTarget,
  startStreamUrl,
} from '../api/scanStream.js';

function useScanRunner(fetchScreener, universe) {
  const [activeJob, setActiveJob] = useState(null);
  const [scanLogs, setScanLogs] = useState([]);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanPhase, setScanPhase] = useState('');
  const [scanError, setScanError] = useState(null);
  const [marketDataStatus, setMarketDataStatus] = useState(null);
  const scanSourceRef = useRef(null);
  const lastJobRef = useRef('evaluation');

  const fetchMarketDataStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/market-data/status`);
      if (response.ok) {
        setMarketDataStatus(await response.json());
      } else {
        console.error(`market-data/status ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to load market data status', error);
    }
  }, []);

  useEffect(() => {
    fetchMarketDataStatus();
  }, [fetchMarketDataStatus]);

  // Closing the stream on unmount is the house rule — and since the backend job
  // now outlives its reader (council review 2026-09-07, finding 4), closing it
  // no longer kills the scan. Navigating away pauses the readout, not the work.
  useEffect(() => () => closeScanSource(scanSourceRef), []);

  const openStream = useCallback((job, url) => {
    lastJobRef.current = job;
    closeScanSource(scanSourceRef);
    setActiveJob(job);
    setScanError(null);
    setScanLogs([]);
    setScanProgress(0);
    setScanPhase(job === 'download' ? 'Preparing data refresh...' : 'Preparing cached evaluation...');

    const eventSource = new EventSource(url);
    scanSourceRef.current = eventSource;
    let resultsRevealed = false;
    let jobFinished = false;
    let jobHadError = false;

    const revealResults = async () => {
      if (resultsRevealed || jobHadError) return;
      resultsRevealed = true;
      setActiveJob(null);
      setScanProgress(0);
      setScanPhase('');
      await fetchMarketDataStatus();
      await fetchScreener(universe);
    };

    const finishJob = async () => {
      if (jobFinished) return;
      jobFinished = true;
      closeScanSource(scanSourceRef);
      setActiveJob(null);
      setScanProgress(0);
      setScanPhase('');
      await fetchMarketDataStatus();
      if (job === 'evaluation' && !resultsRevealed && !jobHadError) {
        await fetchScreener(universe);
      }
    };

    eventSource.onmessage = async (event) => {
      if (event.data === '[DONE]') {
        await finishJob();
        return;
      }

      if (/^ERROR:/i.test(event.data)) {
        jobHadError = true;
        setScanError(errorMessageForJob(job, event.data));
      }

      updateJobProgress(event.data, job, setScanProgress, setScanPhase);
      if (job === 'download' && /^DOWNLOAD_RESULT_JSON:/i.test(event.data)) {
        const payload = parseJobJson(event.data, 'DOWNLOAD_RESULT_JSON:');
        if (payload?.partial) {
          setScanPhase('Partial cache available; repair cooldown active.');
        }
      }
      if (job === 'evaluation' && /Data exported to|UI update available/i.test(event.data)) {
        await revealResults();
        return;
      }
      if (!resultsRevealed) {
        setScanLogs(previous => [...previous, event.data].slice(-4));
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource failed.', error);
      closeScanSource(scanSourceRef);
      setActiveJob(null);
      setScanProgress(0);
      setScanPhase('');
      if (!resultsRevealed && !jobHadError) {
        setScanError(errorMessageForJob(job));
      }
    };
  }, [fetchMarketDataStatus, fetchScreener, universe]);

  const startJob = useCallback(
    (job) => openStream(job, startStreamUrl(API_BASE, job)),
    [openStream],
  );

  // Re-attach on mount to a job that is still running server-side. Without this,
  // one click on the top nav ended the operator's only view of a 12-17 minute
  // scan — and used to end the scan itself. Read through a ref so the check runs
  // exactly once per mount, not on every `universe` change.
  const openStreamRef = useRef(openStream);
  openStreamRef.current = openStream;
  useEffect(() => {
    let cancelled = false;
    fetch(activeStreamUrl(API_BASE))
      .then(response => (response.ok ? response.json() : Promise.reject(new Error('scan-stream/active'))))
      .then(state => {
        const job = cancelled ? null : reattachTarget(state, Boolean(scanSourceRef.current));
        if (job) openStreamRef.current(job, attachStreamUrl(API_BASE));
      })
      .catch(error => console.error('Failed to check for a running scan', error));
    return () => { cancelled = true; };
  }, []);

  // Stop the run. Closing the page used to be this lever by accident; now that
  // the job outlives its reader (finding 4) it needs a real one, or a wedged
  // child holds SCAN_LOCK until the service restarts (council review A3). The
  // server decides whether anything was actually stopped — the client only asks.
  const handleStopJob = useCallback(async () => {
    const ok = await confirmDialog({
      title: 'Stop the run?',
      message: 'The work done so far is discarded and the run is recorded as stopped.',
      confirmLabel: 'Stop it',
      cancelLabel: 'Keep running',
      danger: true,
    });
    if (!ok) return;
    try {
      const response = await fetch(cancelStreamUrl(API_BASE), { method: 'POST' });
      if (!response.ok) throw new Error(`scan-stream/cancel ${response.status}`);
    } catch (error) {
      console.error('Failed to stop the running job', error);
      toast('Could not stop the run — it is still going.', { tone: 'danger' });
    }
  }, []);

  const handleEvaluateCached = useCallback(() => startJob('evaluation'), [startJob]);
  const handleDownloadData = useCallback(() => startJob('download'), [startJob]);
  const handleRetryLastJob = useCallback(() => startJob(lastJobRef.current), [startJob]);

  return {
    activeJob,
    isScanning: activeJob != null,
    isEvaluating: activeJob === 'evaluation',
    isDownloading: activeJob === 'download',
    scanLogs,
    scanProgress,
    scanPhase,
    scanError,
    marketDataStatus,
    fetchMarketDataStatus,
    handleEvaluateCached,
    handleDownloadData,
    handleRetryLastJob,
    handleStopJob,
  };
}

function closeScanSource(scanSourceRef) {
  if (scanSourceRef.current) {
    scanSourceRef.current.close();
    scanSourceRef.current = null;
  }
}

function errorMessageForJob(job, line = '') {
  const suffix = line.replace(/^ERROR:\s*/i, '').trim();
  const detail = suffix ? ` ${suffix}` : '';
  if (job === 'download') {
    return `The data refresh stopped before the cache was ready.${detail}`;
  }
  return `Cached evaluation stopped before results were ready.${detail}`;
}

function updateJobProgress(line, job, setScanProgress, setScanPhase) {
  const trimmed = line.trim();
  const progress = trimmed.match(/(\d+\.?\d*)%\s*Complete/i);
  if (progress) {
    setScanProgress(40 + parseFloat(progress[1]) * 0.55);
    setScanPhase('Evaluating tickers...');
    return;
  }

  const fetched = trimmed.match(/(?:Download|Incremental):\s*(\d+)\/(\d+)\s+fetched/i);
  if (fetched) {
    const current = parseInt(fetched[1], 10);
    const total = parseInt(fetched[2], 10);
    setScanProgress(10 + (current / total) * (job === 'download' ? 76 : 28));
    setScanPhase(`Downloading market data (${current}/${total})...`);
    return;
  }

  const batch = trimmed.match(/(?:Download|Incremental) batch (\d+)\/(\d+)/i);
  if (batch) {
    const current = parseInt(batch[1], 10);
    const total = parseInt(batch[2], 10);
    setScanProgress(10 + (current / total) * (job === 'download' ? 76 : 28));
    setScanPhase(`Downloading market data (batch ${current}/${total})...`);
    return;
  }

  for (const rule of JOB_PHASE_RULES[job] || []) {
    if (rule.pattern.test(trimmed)) {
      setScanProgress(rule.progress);
      setScanPhase(rule.phase);
      return;
    }
  }
}

function parseJobJson(line, prefix) {
  try {
    return JSON.parse(line.slice(prefix.length));
  } catch {
    return null;
  }
}

const COMMON_PHASE_RULES = [
  { pattern: /Loaded \d+ cached tickers|Loaded \d+ tickers|Downloading master universe/i, progress: 5, phase: 'Loading ticker universe...' },
  { pattern: /Loading market data from local cache/i, progress: 28, phase: 'Loading cached market data...' },
  { pattern: /Validating.*tickers/i, progress: 38, phase: 'Validating data integrity...' },
];

const JOB_PHASE_RULES = {
  evaluation: [
    ...COMMON_PHASE_RULES,
    { pattern: /Starting quantitative scans/i, progress: 40, phase: 'Starting evaluation engine...' },
    { pattern: /Generating|Dashboard|chart data/i, progress: 96, phase: 'Generating dashboard charts...' },
  ],
  download: [
    ...COMMON_PHASE_RULES,
    { pattern: /Downloading data for|Incremental update/i, progress: 12, phase: 'Refreshing market data...' },
    { pattern: /partial coverage|Repair cooldown active/i, progress: 98, phase: 'Partial cache available...' },
    { pattern: /Saved incremental update|Saved optimized cache|Market-data cache refreshed/i, progress: 96, phase: 'Saving market data cache...' },
    { pattern: /DOWNLOAD_RESULT_JSON/i, progress: 100, phase: 'Market data cache ready.' },
  ],
};

export default useScanRunner;
