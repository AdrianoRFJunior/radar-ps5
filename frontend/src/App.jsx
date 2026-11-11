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
import { CheckCircle2, Sparkles } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dashboardData, setDashboardData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [scanSuccess, setScanSuccess] = useState(null);

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
    setError(null);
    setScanSuccess(null);
    try {
      const res = await radarApi.triggerMonitoring();
      if (res?.dashboard) {
        setDashboardData(res.dashboard);
      } else {
        await loadDashboard();
      }
      setScanSuccess('Preços e cupons atualizados com sucesso em todas as lojas!');
      setTimeout(() => setScanSuccess(null), 4500);
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
      {scanSuccess && (
        <div className="mb-4 sm:mb-6 p-3 sm:p-4 rounded-xl bg-emerald-950/60 border border-emerald-500/50 text-emerald-200 text-xs sm:text-sm font-semibold flex items-center justify-between gap-3 shadow-lg shadow-emerald-950/40 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400 shrink-0" />
            <span>{scanSuccess}</span>
          </div>
          <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-mono font-bold">
            <Sparkles className="w-3 h-3" /> Ao Vivo
          </span>
        </div>
      )}

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
