import { useRef } from 'react';
import { API_BASE } from '../api';
import useSSE from './useSSE';

const STORAGE_KEY = 'chrollo:lastPortfolioSnapshot';

export const emptyPortfolioSnapshot = {
  account_summary: { values: {}, currency: {}, raw: {} },
  positions: [],
  open_orders: [],
  recent_executions: [],
};

const readStoredSnapshot = () => {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const writeStoredSnapshot = (snapshot) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* storage can be unavailable in private sessions */
  }
};

const hasSummaryData = (summary) => {
  if (!summary) return false;
  if (Object.keys(summary.values || {}).length > 0) return true;
  return Object.values(summary.raw || {}).some((bucket) => Object.keys(bucket || {}).length > 0);
};

const hasPortfolioData = (snapshot) => (
  hasSummaryData(snapshot?.account_summary) ||
  (snapshot?.positions || []).length > 0 ||
  (snapshot?.open_orders || []).length > 0 ||
  (snapshot?.recent_executions || []).length > 0
);

const withCachedPortfolioData = (incoming, cached) => {
  if (!cached || hasPortfolioData(incoming)) return incoming;
  return {
    ...incoming,
    account_summary: cached.account_summary || emptyPortfolioSnapshot.account_summary,
    positions: cached.positions || [],
    open_orders: cached.open_orders || [],
    recent_executions: cached.recent_executions || [],
    last_update: cached.last_update || incoming.last_update,
  };
};

export default function usePortfolioSnapshot(enabled) {
  const { data, status: sseStatus } = useSSE(
    enabled ? `${API_BASE}/stream/portfolio` : null,
    { enabled },
  );
  const snapshotRef = useRef(readStoredSnapshot() || emptyPortfolioSnapshot);

  if (data && typeof data === 'object' && Object.keys(data).length > 0) {
    const nextSnapshot = withCachedPortfolioData(data, snapshotRef.current);
    snapshotRef.current = nextSnapshot;
    if (hasPortfolioData(nextSnapshot)) writeStoredSnapshot(nextSnapshot);
  }

  return { snapshot: snapshotRef.current, sseStatus };
}
