import { useState } from 'react';
import useArchiveAddSetup from '../hooks/useArchiveAddSetup';
import useArchiveChart from '../hooks/useArchiveChart';
import useArchiveData from '../hooks/useArchiveData';
import useArchiveGrid from '../hooks/useArchiveGrid';
import useArchiveMaintenance from '../hooks/useArchiveMaintenance';
import AddSetupModal from './archive/AddSetupModal';
import ArchiveCalibrationPanels from './archive/ArchiveCalibrationPanels';
import ArchiveEquityCurve from './archive/ArchiveEquityCurve';
import ArchiveFilters from './archive/ArchiveFilters';
import ArchiveHeader from './archive/ArchiveHeader';
import ArchiveReweightingStrip from './archive/ArchiveReweightingStrip';
import ArchiveSummary from './archive/ArchiveSummary';
import ArchiveTable from './archive/ArchiveTable';
import ArchiveTierCards from './archive/ArchiveTierCards';
import { ArchiveAnalysisModal, ScanHistoryModal } from './ArchiveMaintenanceModals';
import ScreenerModal from './ScreenerModal';

export default function ArchiveTab() {
  const [tierFilter, setTierFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('curated');
  const [sortBy, setSortBy] = useState('scan_date');
  const [sortDir, setSortDir] = useState('desc');
  const data = useArchiveData({ sortBy, sortDir, sourceFilter, tierFilter, typeFilter });
  const maintenance = useArchiveMaintenance();
  const addSetup = useArchiveAddSetup(data.fetchAll);
  const grid = useArchiveGrid(data.setups);
  const chart = useArchiveChart();

  if (data.loading && data.setups.length === 0) {
    return <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>Loading archive...</div>;
  }

  const filters = {
    searchTerm: grid.searchTerm,
    sortBy,
    sortDir,
    sourceFilter,
    tierFilter,
    typeFilter,
  };

  const setFilters = (patch) => {
    if (patch.searchTerm !== undefined) grid.setSearchTerm(patch.searchTerm);
    if (patch.sortBy !== undefined) setSortBy(patch.sortBy);
    if (patch.sortDir !== undefined) setSortDir(patch.sortDir);
    if (patch.sourceFilter !== undefined) setSourceFilter(patch.sourceFilter);
    if (patch.tierFilter !== undefined) setTierFilter(patch.tierFilter);
    if (patch.typeFilter !== undefined) setTypeFilter(patch.typeFilter);
  };

  const handleSort = (key) => {
    if (sortBy === key) {
      setSortDir(dir => (dir === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('desc');
    }
    grid.resetPage();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <ChartViewer chart={chart} />
      <ArchiveHeader
        onAddSetup={addSetup.openModal}
        onOpenAnalysis={maintenance.openAnalysis}
        onOpenHistory={maintenance.openHistory}
        onUpdateReturns={data.updateReturns}
        stats={data.stats}
        updateMsg={data.updateMsg}
        updating={data.updating}
      />
      <ArchiveModals addSetup={addSetup} maintenance={maintenance} />
      <ArchiveTierCards performance={data.calibration?.tier_performance} />
      <ArchiveCalibrationPanels calibration={data.calibration} />
      <ArchiveReweightingStrip data={data.calibration?.suggested_weights} basis={data.calibration?.weights_basis} />
      {data.equityCurve && <ArchiveEquityCurve data={data.equityCurve} />}
      <ArchiveFilters filters={filters} resetPage={grid.resetPage} setFilters={setFilters} />
      <ArchiveTable
        currentPage={grid.currentPage}
        filteredSetups={grid.filteredSetups}
        onLabelChange={data.updateSetupLabel}
        onOpenChart={chart.openChart}
        onSort={handleSort}
        onTogglePassed={data.togglePassed}
        pageSetups={grid.pageSetups}
        setCurrentPage={grid.setCurrentPage}
        sortBy={sortBy}
        sortDir={sortDir}
        totalPages={grid.totalPages}
      />
    </div>
  );
}

function ChartViewer({ chart }) {
  if (chart.chartLoading) {
    return (
      <div style={{
        alignItems: 'center',
        background: 'rgba(10,10,15,0.8)',
        bottom: 0,
        color: '#fff',
        display: 'flex',
        justifyContent: 'center',
        left: 0,
        position: 'fixed',
        right: 0,
        top: 0,
        zIndex: 5000,
      }}>
        Loading historical data for {chart.chartTicker}...
      </div>
    );
  }
  if (!chart.chartData || !chart.chartTicker) return null;
  return (
    <ScreenerModal
      data={chart.chartData}
      footer={<ArchiveSummary setup={chart.chartSetup} linkedTrades={chart.linkedTrades} />}
      onClose={chart.closeChart}
      onNext={() => {}}
      onPrev={() => {}}
      ticker={chart.chartTicker}
    />
  );
}

function ArchiveModals({ addSetup, maintenance }) {
  return (
    <>
      <ScanHistoryModal
        loading={maintenance.historyLoading}
        onClose={maintenance.closeHistory}
        open={maintenance.historyOpen}
        runs={maintenance.historyRuns}
      />
      <ArchiveAnalysisModal
        error={maintenance.analysisError}
        loading={maintenance.analysisLoading}
        onClose={maintenance.closeAnalysis}
        onRefresh={() => maintenance.openAnalysis(true)}
        open={maintenance.analysisOpen}
        text={maintenance.analysisText}
      />
      <AddSetupModal form={addSetup} />
    </>
  );
}
