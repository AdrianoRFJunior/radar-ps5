import React, { useCallback, useEffect, useState } from 'react';
import NavigationLayout from './components/NavigationLayout';
import DashboardPage from './pages/DashboardPage';
import ProductsPage from './pages/ProductsPage';
import ComparatorPage from './pages/ComparatorPage';
import HistoryPage from './pages/HistoryPage';
import IntelligencePage from './pages/IntelligencePage';
import PredictionsPage from './pages/PredictionsPage';
import BestTimesPage from './pages/BestTimesPage';
import AlertsPage from './pages/AlertsPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import { radarApi } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dashboardData, setDashboardData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await radarApi.getDashboard();
      setDashboardData(res);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
    // Atualização silenciosa da interface a cada 45 segundos
    const timer = setInterval(loadDashboard, 45000);
    return () => clearInterval(timer);
  }, [loadDashboard]);

  const handleTriggerScan = async () => {
    setScanning(true);
    try {
      await radarApi.triggerMonitoring();
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
    }
  };

  return (
    <NavigationLayout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      indicators={dashboardData?.indicators}
      scheduler={dashboardData?.scheduler}
      onTriggerScan={handleTriggerScan}
      scanning={scanning}
    >
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-200 text-xs font-mono">
          Aviso de comunicação com o servidor: {error}
        </div>
      )}

      {activeTab === 'dashboard' && (
        <DashboardPage
          data={dashboardData}
          setActiveTab={setActiveTab}
          onTriggerScan={handleTriggerScan}
          scanning={scanning}
        />
      )}
      {activeTab === 'products' && <ProductsPage />}
      {activeTab === 'comparator' && <ComparatorPage />}
      {activeTab === 'history' && <HistoryPage />}
      {activeTab === 'intelligence' && <IntelligencePage />}
      {activeTab === 'predictions' && <PredictionsPage />}
      {activeTab === 'best-times' && <BestTimesPage />}
      {activeTab === 'alerts' && <AlertsPage onAlertsChanged={loadDashboard} />}
      {activeTab === 'reports' && <ReportsPage />}
      {activeTab === 'settings' && <SettingsPage onSettingsSaved={loadDashboard} />}
    </NavigationLayout>
  );
}
