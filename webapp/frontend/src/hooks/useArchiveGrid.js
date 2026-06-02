import { useEffect, useMemo, useState } from 'react';
import { API_BASE } from '../api';
import { ITEMS_PER_PAGE } from '../utils/archiveTabUtils';

export default function useArchiveGrid(setups) {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [bulkCharts, setBulkCharts] = useState({});
  const [bulkLoading, setBulkLoading] = useState(false);

  const filteredSetups = useMemo(() => {
    if (!searchTerm) return setups;
    const query = searchTerm.toLowerCase();
    return setups.filter(setup => setup.ticker.toLowerCase().includes(query));
  }, [searchTerm, setups]);

  const totalPages = Math.max(1, Math.ceil(filteredSetups.length / ITEMS_PER_PAGE));
  const pageSetups = useMemo(
    () => filteredSetups.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE),
    [currentPage, filteredSetups],
  );

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(1);
  }, [currentPage, totalPages]);

  useEffect(() => {
    const missing = pageSetups.map(setup => setup.id).filter(id => !bulkCharts[id]);
    if (missing.length === 0) return undefined;

    let cancelled = false;
    setBulkLoading(true);
    fetch(`${API_BASE}/archive/charts/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: missing }),
    })
      .then(response => (response.ok ? response.json() : {}))
      .then(data => {
        if (cancelled) return;
        setBulkCharts(previous => ({ ...previous, ...data }));
      })
      .catch(error => console.error('bulk chart fetch failed:', error))
      .finally(() => {
        if (!cancelled) setBulkLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [bulkCharts, pageSetups]);

  const resetPage = () => setCurrentPage(1);

  return {
    bulkCharts,
    bulkLoading,
    currentPage,
    filteredSetups,
    pageSetups,
    resetPage,
    searchTerm,
    setCurrentPage,
    setSearchTerm,
    totalPages,
  };
}
