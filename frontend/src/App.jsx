import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import { radarApi, formatBRL } from './services/api';
import { CheckCircle2, Sparkles, Flame } from 'lucide-react';

function playAlertBeep() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.18);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.36);
  } catch {
    // ignore audio restrictions
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dashboardData, setDashboardData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [scanSuccess, setScanSuccess] = useState(null);
  const [flashDropBanner, setFlashDropBanner] = useState(null);
  const [notifPermission, setNotifPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'unsupported'
  );

  const bestPricesRef = useRef({ ps5: null, ds: null, coupons: new Set() });

  const checkAndNotifyNewDeals = useCallback((fresh) => {
    if (!fresh?.indicators) return;
    const newPs5 = fresh.indicators.lowest_ps5_price;
    const newDs = fresh.indicators.lowest_dualsense_price;
    const prev = bestPricesRef.current;

    const currentCoupons = new Set(
      (fresh.flash_deals || []).map((o) => o.coupon_code).filter(Boolean)
    );

    if (prev.ps5 !== null && newPs5 && newPs5 < prev.ps5 - 1) {
      const champ = fresh.featured_products?.ps5;
      const msg = `🔥 NOVO MENOR PREÇO PS5 NA BLACK FRIDAY: ${formatBRL(newPs5)} na ${champ?.store_name || 'Loja Oficial'}${champ?.coupon_code ? ` (Cupom: ${champ.coupon_code})` : ''}!`;
      setFlashDropBanner({ text: msg, url: champ?.url });
      playAlertBeep();
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('🚨 QUEDA DE PREÇO PS5 — BLACK FRIDAY!', { body: msg });
      }
    } else if (prev.ds !== null && newDs && newDs < prev.ds - 1) {
      const champDs = fresh.featured_products?.dualsense;
      const msg = `🎮 NOVO MENOR PREÇO DUALSENSE: ${formatBRL(newDs)} na ${champDs?.store_name || 'Loja Oficial'}!`;
      setFlashDropBanner({ text: msg, url: champDs?.url });
      playAlertBeep();
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('🎮 QUEDA DE PREÇO DUALSENSE!', { body: msg });
      }
    } else if (prev.ps5 !== null) {
      for (const cp of currentCoupons) {
        if (!prev.coupons.has(cp)) {
          const deal = (fresh.flash_deals || []).find((o) => o.coupon_code === cp);
          const msg = `🎟️ NOVO CUPOM BLACK FRIDAY DETECTADO: ${cp} na ${deal?.store_name || 'Loja'} (${formatBRL(deal?.final_price)})!`;
          setFlashDropBanner({ text: msg, url: deal?.url });
          playAlertBeep();
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`🎟️ Novo Cupom: ${cp}`, { body: msg });
          }
          break;
        }
      }
    }

    bestPricesRef.current = {
      ps5: newPs5 ?? prev.ps5,
      ds: newDs ?? prev.ds,
      coupons: currentCoupons,
    };
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await radarApi.getDashboard();
      checkAndNotifyNewDeals(res);
      setDashboardData(res);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [checkAndNotifyNewDeals]);

  useEffect(() => {
    loadDashboard();
    // Modo Turbo Black Friday: atualização silenciosa na tela a cada 20 segundos!
    const timer = setInterval(loadDashboard, 20000);
    return () => clearInterval(timer);
  }, [loadDashboard]);

  const handleEnableNotifications = async () => {
    if (!('Notification' in window)) return;
    try {
      const perm = await Notification.requestPermission();
      setNotifPermission(perm);
      if (perm === 'granted') {
        playAlertBeep();
        setScanSuccess('🔔 Alertas instantâneos ativados! Você será avisado na hora quando cair o preço ou surgir cupom.');
        setTimeout(() => setScanSuccess(null), 5000);
      }
    } catch {
      // ignore
    }
  };

  const handleTriggerScan = async () => {
    setScanning(true);
    setError(null);
    setScanSuccess(null);
    try {
      const res = await radarApi.triggerMonitoring();
      if (res?.dashboard) {
        checkAndNotifyNewDeals(res.dashboard);
        setDashboardData(res.dashboard);
      } else {
        await loadDashboard();
      }
      const totalOffers = res?.dashboard?.indicators?.offers_identified_count || dashboardData?.indicators?.offers_identified_count || '';
      setScanSuccess(
        `Varredura Black Friday concluída! ${totalOffers ? `${totalOffers} promoções verificadas` : 'Preços e cupons atualizados'} em tempo real!`
      );
      setTimeout(() => setScanSuccess(null), 5000);
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
      {flashDropBanner && (
        <div className="mb-4 sm:mb-6 p-3.5 sm:p-4 rounded-xl bg-gradient-to-r from-amber-500/25 via-emerald-950/80 to-[#0b1116] border border-amber-400/60 text-amber-100 text-xs sm:text-sm font-bold flex flex-wrap items-center justify-between gap-3 shadow-xl">
          <div className="flex items-center gap-2.5">
            <Flame className="w-5 h-5 text-amber-400 shrink-0 animate-pulse" />
            <span>{flashDropBanner.text}</span>
          </div>
          <div className="flex items-center gap-2">
            {flashDropBanner.url && (
              <a
                href={flashDropBanner.url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 font-extrabold text-xs"
              >
                Abrir Promoção Agora
              </a>
            )}
            <button
              onClick={() => setFlashDropBanner(null)}
              className="px-2 py-1 rounded-lg bg-slate-800/80 text-slate-300 text-xs hover:text-white"
            >
              Fechar
            </button>
          </div>
        </div>
      )}

      {scanSuccess && (
        <div className="mb-4 sm:mb-6 p-3 sm:p-4 rounded-xl bg-emerald-950/60 border border-emerald-500/50 text-emerald-200 text-xs sm:text-sm font-semibold flex items-center justify-between gap-3 shadow-lg shadow-emerald-950/40 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400 shrink-0" />
            <span>{scanSuccess}</span>
          </div>
          <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-mono font-bold">
            <Sparkles className="w-3 h-3" /> Black Friday Ao Vivo
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
          notifPermission={notifPermission}
          onEnableNotifications={handleEnableNotifications}
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
