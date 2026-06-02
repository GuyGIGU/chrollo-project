import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../api';

function useScanRunner(fetchScreener) {
  const [isScanning, setIsScanning] = useState(false);
  const [scanLogs, setScanLogs] = useState([]);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanPhase, setScanPhase] = useState('');
  const scanSourceRef = useRef(null);

  useEffect(() => () => closeScanSource(scanSourceRef), []);

  const handleRunScan = () => {
    closeScanSource(scanSourceRef);
    setIsScanning(true);
    setScanLogs([]);
    setScanProgress(0);
    setScanPhase('Initializing pipeline...');

    const eventSource = new EventSource(`${API_BASE}/run-scan-stream/`);
    scanSourceRef.current = eventSource;
    let resultsRevealed = false;

    const revealResults = async () => {
      if (resultsRevealed) return;
      resultsRevealed = true;
      setIsScanning(false);
      setScanProgress(0);
      setScanPhase('');
      await fetchScreener();
    };

    eventSource.onmessage = async (event) => {
      if (event.data === '[DONE]') {
        closeScanSource(scanSourceRef);
        await revealResults();
        return;
      }
      updateScanProgress(event.data, setScanProgress, setScanPhase);
      if (/Data exported to|UI update available/i.test(event.data)) {
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
      setIsScanning(false);
      setScanProgress(0);
      setScanPhase('');
    };
  };

  return { isScanning, scanLogs, scanProgress, scanPhase, handleRunScan };
}

function closeScanSource(scanSourceRef) {
  if (scanSourceRef.current) {
    scanSourceRef.current.close();
    scanSourceRef.current = null;
  }
}

function updateScanProgress(line, setScanProgress, setScanPhase) {
  const trimmed = line.trim();
  const progress = trimmed.match(/(\d+\.?\d*)%\s*Complete/i);
  if (progress) {
    setScanProgress(40 + parseFloat(progress[1]) * 0.55);
    setScanPhase('Evaluating tickers...');
    return;
  }

  const batch = trimmed.match(/(?:Download|Incremental) batch (\d+)\/(\d+)/i);
  if (batch) {
    const current = parseInt(batch[1], 10);
    const total = parseInt(batch[2], 10);
    setScanProgress(10 + (current / total) * 28);
    setScanPhase(`Downloading market data (batch ${current}/${total})...`);
    return;
  }

  for (const rule of SCAN_PHASE_RULES) {
    if (rule.pattern.test(trimmed)) {
      setScanProgress(rule.progress);
      setScanPhase(rule.phase);
      return;
    }
  }
}

const SCAN_PHASE_RULES = [
  { pattern: /Validating.*tickers/i, progress: 38, phase: 'Validating data integrity...' },
  { pattern: /Loaded \d+ tickers|Downloading master universe/i, progress: 5, phase: 'Loading ticker universe...' },
  { pattern: /Loading market data from local cache/i, progress: 35, phase: 'Loading cached market data...' },
  { pattern: /Starting quantitative scans/i, progress: 40, phase: 'Starting evaluation engine...' },
  { pattern: /Generating|Dashboard|chart data/i, progress: 96, phase: 'Generating dashboard charts...' },
];

export default useScanRunner;
