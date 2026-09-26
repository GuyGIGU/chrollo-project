import { useEffect, useMemo, useState } from 'react';
import { ITEMS_PER_PAGE } from '../presentation/archiveTabUtils';

export default function useArchiveGrid(setups) {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

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

  const resetPage = () => setCurrentPage(1);

  return {
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
