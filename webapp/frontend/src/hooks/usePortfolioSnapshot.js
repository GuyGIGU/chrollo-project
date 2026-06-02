import { useEffect, useMemo, useState } from 'react';
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

const normalizeSnapshot = (snapshot) => ({
  ...emptyPortfolioSnapshot,
  ...snapshot,
  account_summary: snapshot?.account_summary || emptyPortfolioSnapshot.account_summary,
  positions: snapshot?.positions || [],
  open_orders: snapshot?.open_orders || [],
  recent_executions: snapshot?.recent_executions || [],
});

const withCachedPortfolioData = (incoming, cached) => {
  const incomingSnapshot = normalizeSnapshot(incoming);
  if (!cached || hasPortfolioData(incomingSnapshot)) return incomingSnapshot;
  const cachedSnapshot = normalizeSnapshot(cached);
  return {
    ...incomingSnapshot,
    account_summary: cachedSnapshot.account_summary,
    positions: cachedSnapshot.positions,
    open_orders: cachedSnapshot.open_orders,
    recent_executions: cachedSnapshot.recent_executions,
    last_update: cachedSnapshot.last_update || incomingSnapshot.last_update,
  };
};

export default function usePortfolioSnapshot(enabled) {
  const { data, status: sseStatus } = useSSE(
    enabled ? `${API_BASE}/stream/portfolio` : null,
    { enabled },
  );
  const [snapshot, setSnapshot] = useState(() => (
    normalizeSnapshot(readStoredSnapshot())
  ));

  useEffect(() => {
    if (!data || typeof data !== 'object' || Object.keys(data).length === 0) return;
    setSnapshot((current) => withCachedPortfolioData(data, current));
  }, [data]);

  useEffect(() => {
    if (hasPortfolioData(snapshot)) writeStoredSnapshot(snapshot);
  }, [snapshot]);

  const hasData = useMemo(() => hasPortfolioData(snapshot), [snapshot]);

  return { snapshot, sseStatus, hasData };
}
