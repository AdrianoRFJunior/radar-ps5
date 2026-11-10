import React, { useState } from 'react';
import {
  LayoutDashboard,
  Scale,
  LineChart,
  BrainCircuit,
  TrendingDown,
  Bell,
  RefreshCw,
  ShieldCheck,
  Radio,
  ChevronDown,
  ChevronUp,
  Clock,
  FileBarChart2,
  Gamepad2,
  Calendar,
  Award,
  Disc,
} from 'lucide-react';
import { formatBRL, formatDateTimeSP } from '../services/api';

const PRIMARY_NAV_ITEMS = [
  { id: 'dashboard', label: 'Menores Preços Hoje', badgeText: 'PS5 & DualSense', icon: LayoutDashboard },
  { id: 'comparator', label: 'Comparador de Lojas', icon: Scale },
  { id: 'predictions', label: 'Estimativa & Momento', icon: TrendingDown },
  { id: 'alerts', label: 'Alertas de Queda', icon: Bell, badgeKey: 'unread_alerts_count' },
];

const ADVANCED_NAV_ITEMS = [
  { id: 'history', label: 'Resumo Estatístico', icon: LineChart },
  { id: 'intelligence', label: 'Auditoria Anti-Fraude', icon: BrainCircuit },
  { id: 'best-times', label: 'Melhores Horários', icon: Clock },
  { id: 'products', label: 'Catálogo Monitorado', icon: Gamepad2 },
  { id: 'reports', label: 'Relatórios Executivos', icon: FileBarChart2 },
  { id: 'settings', label: 'Modo de Evento & Logs', icon: Calendar },
];

export default function NavigationLayout({
  activeTab,
  setActiveTab,
  indicators,
  scheduler,
  onTriggerScan,
  scanning,
  children,
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const unreadAlerts = indicators?.unread_alerts_count || 0;
  const allNavItems = [...PRIMARY_NAV_ITEMS, ...ADVANCED_NAV_ITEMS];

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#070b0e] text-slate-100 antialiased selection:bg-emerald-500 selection:text-slate-950">
      {/* Sidebar Desktop / Topo Mobile */}
      <aside className="w-full lg:w-64 xl:w-72 bg-[#0b1116] border-b lg:border-b-0 lg:border-r border-[#182631] flex flex-col shrink-0 lg:sticky lg:top-0 lg:h-screen z-30">
        {/* Identidade Visual */}
        <div className="px-3.5 py-3 sm:px-5 sm:py-4 border-b border-[#182631] flex items-center justify-between">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-950/50">
              <Radio className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400 animate-pulse" />
            </div>
            <div className="min-w-0">
              <h1 className="font-extrabold tracking-tight text-sm sm:text-lg text-white leading-tight truncate">
                RADAR <span className="text-emerald-400">BF 2026</span>
              </h1>
              <p className="text-[10px] sm:text-[11px] font-mono text-slate-400 truncate">
                MENOR PREÇO • PS5 NOVO
              </p>
            </div>
          </div>

          {/* Botão rápido no mobile */}
          <div className="flex items-center gap-1.5 sm:gap-2 lg:hidden">
            <button
              onClick={() => setActiveTab('alerts')}
              className="relative p-1.5 sm:p-2 rounded-lg bg-[#111b22] border border-[#1c2d38] text-slate-300"
              title="Alertas"
            >
              <Bell className="w-4 h-4 text-emerald-400" />
              {unreadAlerts > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 text-slate-950 text-[10px] font-bold flex items-center justify-center">
                  {unreadAlerts}
                </span>
              )}
            </button>
            <button
              onClick={onTriggerScan}
              disabled={scanning}
              className="py-1.5 px-2.5 sm:py-2 sm:px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-1.5 whitespace-nowrap"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin' : ''}`} />
              <span>{scanning ? 'Buscando...' : 'Atualizar'}</span>
            </button>
          </div>
        </div>

        {/* Status do Monitoramento Automático (Desktop) */}
        <div className="hidden lg:block px-4 py-3.5 bg-[#080d11] border-b border-[#182631] text-xs space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-slate-400 flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    scheduler?.scheduler_running ? 'bg-emerald-400' : 'bg-amber-400'
                  }`}
                />
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    scheduler?.scheduler_running ? 'bg-emerald-400' : 'bg-amber-400'
                  }`}
                />
              </span>
              Monitoramento:
            </span>
            <span className="font-mono font-bold text-emerald-400 whitespace-nowrap">
              {scheduler?.scheduler_running
                ? `ATIVO (${scheduler?.current_interval_minutes || 15}m)`
                : 'PAUSADO'}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400">
            <span>Meta:</span>
            <span className="font-mono text-emerald-300 font-semibold whitespace-nowrap">
              Menor Preço Histórico
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400">
            <span>Última Coleta:</span>
            <span className="font-mono text-slate-300 whitespace-nowrap">
              {formatDateTimeSP(indicators?.last_updated_at)}
            </span>
          </div>
        </div>

        {/* Navegação Mobile (Barra Horizontal Deslizante com toque suave) */}
        <nav className="flex lg:hidden items-center gap-1.5 px-3 py-2 overflow-x-auto bg-[#090e13] no-scrollbar border-b border-[#182631]">
          {allNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            const showBadge = item.badgeKey && unreadAlerts > 0;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition shrink-0 border ${
                  isActive
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                    : 'text-slate-400 hover:text-slate-200 bg-[#0d141a] border-[#182631]'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
                {showBadge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold rounded-full bg-emerald-500 text-slate-950">
                    {unreadAlerts}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Navegação Desktop (Coluna Vertical) */}
        <nav className="hidden lg:flex lg:flex-col p-3 gap-1 flex-1 overflow-y-auto">
          <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-bold">
            Visão Principal
          </div>
          {PRIMARY_NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            const showBadge = item.badgeKey && unreadAlerts > 0;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all text-left border ${
                  isActive
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-sm'
                    : 'text-slate-300 hover:text-white hover:bg-[#121c24] border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                  <span className="truncate">{item.label}</span>
                </div>
                {showBadge ? (
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-emerald-500 text-slate-950 shrink-0">
                    {unreadAlerts}
                  </span>
                ) : item.badgeText ? (
                  <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-[#142029] text-emerald-400 border border-[#1f313f] shrink-0">
                    {item.badgeText}
                  </span>
                ) : null}
              </button>
            );
          })}

          {/* Seção Avançada */}
          <div className="pt-3 mt-2 border-t border-[#182631]">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-[11px] font-mono uppercase tracking-wider text-slate-400 hover:text-slate-200 hover:bg-[#121c24] transition"
            >
              <span>Auditoria & Mais Abas</span>
              {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {(showAdvanced || ADVANCED_NAV_ITEMS.some((i) => i.id === activeTab)) && (
              <div className="space-y-1 mt-1">
                {ADVANCED_NAV_ITEMS.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setActiveTab(item.id)}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all text-left border ${
                        isActive
                          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-[#121c24] border-transparent'
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                      <span className="truncate">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </nav>

        {/* Rodapé da Sidebar Desktop */}
        <div className="p-4 border-t border-[#182631] space-y-2.5 hidden lg:block bg-[#090e13]">
          <button
            onClick={onTriggerScan}
            disabled={scanning}
            className="w-full py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-extrabold text-xs flex items-center justify-center gap-2 transition shadow-lg shadow-emerald-950/50 whitespace-nowrap"
          >
            <RefreshCw className={`w-4 h-4 shrink-0 ${scanning ? 'animate-spin' : ''}`} />
            <span>{scanning ? 'VARRENDO LOJAS...' : 'BUSCAR MENOR PREÇO'}</span>
          </button>
          <div className="flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span className="truncate">PS5 100% Novo • Lojas Oficiais</span>
          </div>
        </div>
      </aside>

      {/* Área Principal de Conteúdo */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Barra Superior de Indicadores Rápidos */}
        <header className="bg-[#0b1116]/95 backdrop-blur-md border-b border-[#182631] px-3 sm:px-6 lg:px-8 py-2.5 sm:py-3 sticky top-0 z-20">
          <div className="max-w-[1440px] mx-auto flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto py-0.5 no-scrollbar">
              {/* Pill 1: Menor PS5 Digital */}
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg bg-[#101920] border border-[#1c2d38] whitespace-nowrap shrink-0">
                <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                <span className="text-[10px] sm:text-[11px] font-mono text-slate-400 uppercase">PS5 Digital:</span>
                <span className="text-xs sm:text-sm font-mono font-extrabold text-emerald-400">
                  {indicators?.lowest_ps5_digital_price
                    ? formatBRL(indicators.lowest_ps5_digital_price)
                    : '—'}
                </span>
              </div>

              {/* Pill 2: Menor PS5 Com Leitor */}
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg bg-[#101920] border border-[#1c2d38] whitespace-nowrap shrink-0">
                <Disc className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span className="text-[10px] sm:text-[11px] font-mono text-slate-400 uppercase">PS5 c/ Leitor:</span>
                <span className="text-xs sm:text-sm font-mono font-extrabold text-cyan-400">
                  {indicators?.lowest_ps5_disc_price
                    ? formatBRL(indicators.lowest_ps5_disc_price)
                    : '—'}
                </span>
              </div>

              {/* Pill 3: Menor da História PS5 */}
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg bg-[#101920] border border-amber-500/30 whitespace-nowrap shrink-0">
                <Award className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span className="text-[10px] sm:text-[11px] font-mono text-slate-400 uppercase">Recorde PS5:</span>
                <span className="text-xs sm:text-sm font-mono font-extrabold text-amber-300">
                  {formatBRL(indicators?.ps5_historical_low || 3349)}
                </span>
              </div>

              {/* Pill 4: Menor DualSense */}
              <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg bg-[#101920] border border-[#1c2d38] whitespace-nowrap shrink-0">
                <Gamepad2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span className="text-[10px] sm:text-[11px] font-mono text-slate-400 uppercase">DualSense:</span>
                <span className="text-xs sm:text-sm font-mono font-extrabold text-emerald-400">
                  {indicators?.lowest_dualsense_price
                    ? formatBRL(indicators.lowest_dualsense_price)
                    : '—'}
                </span>
              </div>
            </div>

            {/* Ações Rápidas Desktop */}
            <div className="hidden lg:flex items-center gap-2.5 shrink-0">
              <button
                onClick={() => setActiveTab('alerts')}
                className="relative px-3 py-1.5 rounded-lg bg-[#101920] border border-[#1c2d38] hover:border-emerald-500/40 text-slate-300 flex items-center gap-2 text-xs font-mono transition whitespace-nowrap"
                title="Central de Alertas Internos"
              >
                <Bell className="w-3.5 h-3.5 text-emerald-400" />
                <span>Alertas</span>
                {unreadAlerts > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-emerald-500 text-slate-950 text-[10px] font-extrabold">
                    {unreadAlerts}
                  </span>
                )}
              </button>
            </div>
          </div>
        </header>

        {/* Conteúdo Principal */}
        <main className="p-3.5 sm:p-6 lg:p-8 flex-1 w-full max-w-[1440px] mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
