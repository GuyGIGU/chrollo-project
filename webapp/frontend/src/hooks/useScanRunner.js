import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../api';

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

  useEffect(() => () => closeScanSource(scanSourceRef), []);

  const startJob = useCallback((job) => {
    lastJobRef.current = job;
    closeScanSource(scanSourceRef);
    setActiveJob(job);
    setScanError(null);
    setScanLogs([]);
    setScanProgress(0);
    setScanPhase(job === 'download' ? 'Preparing data refresh...' : 'Preparing cached evaluation...');

    const eventSource = new EventSource(`${API_BASE}/${job === 'download' ? 'download-data-stream' : 'run-evaluation-stream'}/`);
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
