import React, { useEffect, useState } from 'react';
import {
  Bell,
  Check,
  Archive,
  ExternalLink,
  AlertTriangle,
  Award,
  TrendingDown,
  CheckCheck,
} from 'lucide-react';
import { radarApi, formatBRL, formatDateTimeSP } from '../services/api';

export default function AlertsPage({ onAlertsChanged }) {
  const [includeArchived, setIncludeArchived] = useState(false);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const res = await radarApi.getAlerts(includeArchived, onlyUnread);
      setData(res);
      if (onAlertsChanged) onAlertsChanged();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [includeArchived, onlyUnread]);

  const handleMarkRead = async (id, isRead) => {
    setData((prev) => {
      if (!prev) return prev;
      const updatedAlerts = (prev.alerts || [])
        .map((item) => (item.id === id ? { ...item, is_read: isRead } : item))
        .filter((item) => (onlyUnread ? !item.is_read : true));
      const delta = isRead ? -1 : 1;
      return {
        ...prev,
        unread_count: Math.max(0, (prev.unread_count || 0) + delta),
        alerts: updatedAlerts,
      };
    });
    await radarApi.markAlertRead(id, isRead);
    await loadAlerts();
  };

  const handleArchive = async (id) => {
    setData((prev) => {
      if (!prev) return prev;
      const target = (prev.alerts || []).find((item) => item.id === id);
      const wasUnread = target && !target.is_read;
      const updatedAlerts = (prev.alerts || []).filter((item) => item.id !== id);
      return {
        ...prev,
        unread_count: wasUnread ? Math.max(0, (prev.unread_count || 0) - 1) : prev.unread_count,
        alerts: updatedAlerts,
      };
    });
    await radarApi.archiveAlert(id, true);
    await loadAlerts();
  };

  const handleMarkAllRead = async () => {
    setData((prev) => {
      if (!prev) return prev;
      const updatedAlerts = onlyUnread
        ? []
        : (prev.alerts || []).map((item) => ({ ...item, is_read: true }));
      return {
        ...prev,
        unread_count: 0,
        alerts: updatedAlerts,
      };
    });
    await radarApi.markAllAlertsRead();
    await loadAlerts();
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-4 sm:p-5 flex flex-col xl:flex-row xl:items-center justify-between gap-3 sm:gap-4">
        <div className="space-y-1">
          <h2 className="text-base sm:text-xl font-extrabold text-white flex items-center gap-2">
            <Bell className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>Central de Alertas Internos do Radar</span>
          </h2>
          <p className="text-[11px] sm:text-sm text-slate-400">
            Notificações geradas dentro do dashboard para quedas reais, menor preço histórico e avisos de falso desconto.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 text-xs shrink-0 w-full xl:w-auto">
          <label className="flex-1 sm:flex-initial flex items-center justify-center gap-2 bg-[#080d11] border border-[#182631] rounded-xl px-3 py-2 sm:px-3.5 sm:py-2.5 cursor-pointer whitespace-nowrap text-slate-200 text-[11px] sm:text-xs">
            <input
              type="checkbox"
              checked={onlyUnread}
              onChange={(e) => setOnlyUnread(e.target.checked)}
              className="accent-emerald-500"
            />
            <span>Apenas Não Lidos ({data?.unread_count || 0})</span>
          </label>

          <label className="flex-1 sm:flex-initial flex items-center justify-center gap-2 bg-[#080d11] border border-[#182631] rounded-xl px-3 py-2 sm:px-3.5 sm:py-2.5 cursor-pointer whitespace-nowrap text-slate-200 text-[11px] sm:text-xs">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
              className="accent-emerald-500"
            />
            <span>Arquivados</span>
          </label>

          <button
            onClick={handleMarkAllRead}
            className="w-full sm:w-auto px-3.5 py-2 sm:px-4 sm:py-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 font-bold flex items-center justify-center gap-1.5 whitespace-nowrap transition text-[11px] sm:text-xs"
          >
            <CheckCheck className="w-4 h-4 shrink-0" />
            <span>Marcar Todos como Lidos</span>
          </button>
        </div>
      </div>

      {loading && !data ? (
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-8 text-center text-slate-400 text-sm">
          Carregando alertas...
        </div>
      ) : (data?.alerts || []).length === 0 ? (
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-8 text-center text-slate-400 text-sm">
          Nenhum alerta encontrado para o filtro selecionado.
        </div>
      ) : (
        <div className="space-y-3.5">
          {(data?.alerts || []).map((a) => {
            const isDanger = a.severity === 'DANGER' || a.alert_type === 'FAKE_DISCOUNT';
            return (
              <div
                key={a.id}
                className={`rounded-2xl p-3.5 sm:p-5 border transition flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3.5 sm:gap-4 ${
                  !a.is_read
                    ? isDanger
                      ? 'bg-rose-950/20 border-rose-500/50'
                      : 'bg-[#0d1c21] border-emerald-500/50'
                    : 'bg-[#0b1116]/90 border-[#182631] opacity-85'
                }`}
              >
                <div className="space-y-2 max-w-4xl min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                    {!a.is_read && (
                      <span className="px-2 py-0.5 rounded bg-emerald-500 text-slate-950 font-mono text-[10px] font-extrabold uppercase whitespace-nowrap">
                        NOVO
                      </span>
                    )}
                    <span
                      className={`px-2 sm:px-2.5 py-0.5 rounded-md font-mono text-[11px] sm:text-xs font-bold flex items-center gap-1 whitespace-nowrap ${
                        isDanger
                          ? 'bg-rose-500/20 text-rose-300'
                          : 'bg-emerald-500/20 text-emerald-300'
                      }`}
                    >
                      {isDanger ? (
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                      ) : a.alert_type === 'PRICE_DROP' ? (
                        <TrendingDown className="w-3.5 h-3.5 shrink-0" />
                      ) : (
                        <Award className="w-3.5 h-3.5 shrink-0" />
                      )}
                      <span>{a.alert_type}</span>
                    </span>
                    <span className="text-[11px] sm:text-xs font-semibold text-slate-300">
                      {a.product_name} • Loja: {a.store_name}
                    </span>
                    <span className="text-[10px] sm:text-xs font-mono text-slate-400 whitespace-nowrap">
                      {formatDateTimeSP(a.created_at)}
                    </span>
                  </div>

                  <h3 className="font-bold text-white text-sm sm:text-base leading-snug">{a.title}</h3>
                  <p className="text-xs sm:text-sm text-slate-200 leading-relaxed">{a.message}</p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-2.5 pt-1 text-xs">
                    <div className="p-2 sm:p-2.5 rounded-xl bg-[#080d11] border border-[#182631] text-slate-300 font-mono text-[11px] sm:text-xs">
                      <strong>Comparação Histórica:</strong> {a.historical_comparison}
                    </div>
                    <div className="p-2 sm:p-2.5 rounded-xl bg-[#080d11] border border-[#182631] text-slate-300 text-[11px] sm:text-xs">
                      <strong>Motivo do Alerta:</strong> {a.reason}
                    </div>
                  </div>
                </div>

                <div className="flex items-center lg:flex-col lg:items-end justify-between w-full lg:w-auto gap-3 shrink-0 border-t lg:border-t-0 pt-2.5 lg:pt-0 border-[#182631]">
                  <div className="text-left lg:text-right">
                    <span className="text-[10px] sm:text-[11px] text-slate-400 block">Preço Registrado</span>
                    <span
                      className={`text-lg sm:text-xl font-extrabold font-mono whitespace-nowrap ${
                        isDanger ? 'text-rose-400' : 'text-emerald-400'
                      }`}
                    >
                      {formatBRL(a.price)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {a.offer_url && (
                      <a
                        href={a.offer_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={() => {
                          if (!a.is_read) handleMarkRead(a.id, true);
                        }}
                        className="px-3 sm:px-3.5 py-1.5 sm:py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs inline-flex items-center gap-1.5 whitespace-nowrap transition"
                      >
                        <span>Ver Oferta</span>
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                      </a>
                    )}
                    <button
                      onClick={() => handleMarkRead(a.id, !a.is_read)}
                      className={`px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-xl text-[11px] sm:text-xs font-bold inline-flex items-center gap-1.5 border whitespace-nowrap transition ${
                        !a.is_read
                          ? 'bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border-emerald-500/40'
                          : 'bg-[#121d26] hover:bg-[#182734] text-slate-400 border-[#223544]'
                      }`}
                      title={a.is_read ? 'Clique para marcar como não lido' : 'Clique para marcar como lido'}
                    >
                      <Check className={`w-3.5 h-3.5 shrink-0 ${!a.is_read ? 'text-emerald-400' : 'text-slate-400'}`} />
                      <span>{a.is_read ? 'Lido' : 'Marcar Lido'}</span>
                    </button>
                    {!a.is_archived && (
                      <button
                        onClick={() => handleArchive(a.id)}
                        className="p-1.5 sm:p-2 rounded-xl bg-[#121d26] hover:bg-[#182734] text-slate-200 border border-[#223544] transition"
                        title="Arquivar alerta"
                      >
                        <Archive className="w-4 h-4 text-slate-400" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
