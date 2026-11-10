import React, { useEffect, useState } from 'react';
import {
  Save,
  Database,
  Bell,
  CheckCircle2,
  RefreshCw,
  Zap,
  Calendar,
  Award,
} from 'lucide-react';
import { radarApi, formatDateTimeSP } from '../services/api';
import { useBrowserNotifications } from '../hooks/useBrowserNotifications';

export default function SettingsPage({ onSettingsSaved }) {
  const [form, setForm] = useState(null);
  const [logsData, setLogsData] = useState(null);
  const [backups, setBackups] = useState([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const { permission, requestPermission, notifyBrowser } = useBrowserNotifications(
    form?.browser_notifications_enabled
  );

  const loadAll = async () => {
    const [s, l, b] = await Promise.all([
      radarApi.getSettings(),
      radarApi.getMonitoringLogs(),
      radarApi.getBackups(),
    ]);
    setForm({
      ...s,
      promotional_events: s.promotional_events || [],
    });
    setLogsData(l);
    setBackups(b.backups || []);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleEventChange = (idx, field, val) => {
    const updated = [...(form.promotional_events || [])];
    updated[idx] = { ...updated[idx], [field]: val };
    setForm({ ...form, promotional_events: updated });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const payload = {
        ...form,
        ps5_target_price: null,
        ps5_excellent_price: null,
        dualsense_target_price: null,
        dualsense_excellent_price: null,
        interval_normal_minutes: Number(form.interval_normal_minutes || 30),
        interval_warmup_minutes: Number(form.interval_warmup_minutes || 15),
        interval_high_minutes: Number(form.interval_high_minutes || 10),
        interval_night_minutes: Number(form.interval_night_minutes || 60),
        event_lead_days: Number(form.event_lead_days || 7),
        stale_data_threshold_minutes: Number(form.stale_data_threshold_minutes || 90),
      };
      await radarApi.updateSettings(payload);
      setMessage('Calendário do Modo de Evento e Agendador atualizados com sucesso!');
      if (payload.browser_notifications_enabled) {
        notifyBrowser('Modo de Evento Atualizado', 'Busca automática pelo menor preço histórico ativa.');
      }
      if (onSettingsSaved) onSettingsSaved();
      loadAll();
    } catch (err) {
      setMessage(`Erro: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateBackup = async () => {
    await radarApi.triggerBackup();
    const b = await radarApi.getBackups();
    setBackups(b.backups || []);
    setMessage('Backup do banco de dados SQLite criado com sucesso!');
  };

  if (!form) {
    return <div className="text-slate-400 text-sm">Carregando parâmetros do Modo de Evento...</div>;
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-extrabold text-white flex items-center gap-2">
          <Calendar className="w-6 h-6 text-emerald-400" />
          Modo de Evento, Frequência de Coleta & Logs do Sistema
        </h2>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          O sistema busca <strong>automaticamente o menor preço possível da história do PlayStation 5 Novo (Digital e Com Leitor de Disco)</strong> em lojas confiáveis, sem necessidade de definir teto ou preço-alvo manual.
        </p>
      </div>

      {/* Aviso de Busca Automática pelo Menor Preço da História */}
      <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 text-xs text-slate-200 flex items-start gap-3">
        <Award className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="font-bold text-emerald-300">
            Política Automática de Busca pelo Menor Preço Histórico (Ativa Permanentemente)
          </div>
          <p className="text-slate-300 leading-relaxed">
            O Radar monitora exclusivamente consoles PlayStation 5 <strong>100% Novos</strong> (tanto a versão <strong>Edição Digital</strong> quanto a versão <strong>Com Leitor de Disco</strong>) e controles <strong>DualSense Oficiais</strong> em grandes varejistas confiáveis (KaBuM!, Magazine Luiza, Amazon Brasil, Fast Shop, Casas Bahia, Ponto e Carrefour — evitando anúncios de usados/Mercado Livre) e adiciona observações automáticas caso uma oferta seja de marketplace, importada ou tenha falso desconto.
          </p>
        </div>
      </div>

      {message && (
        <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* MODO DE EVENTO AUTOMÁTICO E CALENDÁRIO CONFIGURÁVEL */}
        <div className="bg-[#0d141a] border border-emerald-500/40 rounded-xl p-5 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1c2d38] pb-3">
            <h3 className="font-bold text-white text-base flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400" />
              Modo de Evento Promocional (Integrado ao Monitoramento Principal)
            </h3>
            <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 font-mono text-xs font-bold">
              {form.event_mode?.mode_label}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <label className="flex items-center gap-2.5 p-3 rounded-lg bg-[#080d11] border border-[#1c2d38] cursor-pointer text-slate-200 font-medium">
              <input
                type="checkbox"
                checked={form.event_mode_enabled}
                onChange={(e) => setForm({ ...form, event_mode_enabled: e.target.checked })}
                className="accent-emerald-500 w-4 h-4"
              />
              <span>Detectar Eventos Automaticamente</span>
            </label>

            <label className="flex items-center gap-2.5 p-3 rounded-lg bg-[#080d11] border border-[#1c2d38] cursor-pointer text-slate-200 font-medium">
              <input
                type="checkbox"
                checked={form.prioritize_ps5_in_event}
                onChange={(e) => setForm({ ...form, prioritize_ps5_in_event: e.target.checked })}
                className="accent-emerald-500 w-4 h-4"
              />
              <span>Priorizar PS5 Novo Durante Eventos</span>
            </label>

            <div>
              <label className="block text-slate-400 mb-1">
                Antecedência para Aquecimento (Dias antes do evento)
              </label>
              <input
                type="number"
                min="1"
                max="60"
                value={form.event_lead_days}
                onChange={(e) => setForm({ ...form, event_lead_days: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>
          </div>

          {/* Frequências Configuráveis */}
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Modo do Agendador</label>
              <select
                value={form.scheduler_mode}
                onChange={(e) => setForm({ ...form, scheduler_mode: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white font-mono"
              >
                <option value="AUTO_EVENT">Automático (Modo de Evento)</option>
                <option value="NORMAL">Fixo Normal</option>
                <option value="HIGH_ACTIVITY">Fixo Intensivo</option>
                <option value="NIGHT">Fixo Noturno</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Intervalo Normal (min)</label>
              <input
                type="number"
                min="5"
                value={form.interval_normal_minutes}
                onChange={(e) => setForm({ ...form, interval_normal_minutes: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Intervalo Aquecimento (min)</label>
              <input
                type="number"
                min="5"
                value={form.interval_warmup_minutes}
                onChange={(e) => setForm({ ...form, interval_warmup_minutes: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Intervalo Evento Ativo (min)</label>
              <input
                type="number"
                min="5"
                value={form.interval_high_minutes}
                onChange={(e) => setForm({ ...form, interval_high_minutes: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Alerta Dado Desatualizado (min)</label>
              <input
                type="number"
                min="15"
                value={form.stale_data_threshold_minutes}
                onChange={(e) => setForm({ ...form, stale_data_threshold_minutes: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>
          </div>

          {/* Calendário Configurável de Datas Promocionais */}
          <div className="space-y-2 pt-2">
            <h4 className="text-xs font-mono uppercase text-emerald-400 font-bold flex items-center gap-1.5">
              <Calendar className="w-4 h-4" />
              Datas Promocionais Monitoradas (Singles' Day 11/11, Black Friday, Cyber Monday, Prime Day)
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {(form.promotional_events || []).map((ev, idx) => (
                <div
                  key={ev.slug || idx}
                  className="p-3 rounded-lg bg-[#080d11] border border-[#1c2d38] space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      value={ev.name}
                      onChange={(e) => handleEventChange(idx, 'name', e.target.value)}
                      className="bg-[#0d141a] border border-[#1c2d38] rounded px-2.5 py-1 text-white font-bold flex-1"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-[10px] text-slate-400 block">Data Início</span>
                      <input
                        type="date"
                        value={ev.start_date}
                        onChange={(e) => handleEventChange(idx, 'start_date', e.target.value)}
                        className="w-full bg-[#0d141a] border border-[#1c2d38] rounded px-2 py-1 text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block">Data Término</span>
                      <input
                        type="date"
                        value={ev.end_date}
                        onChange={(e) => handleEventChange(idx, 'end_date', e.target.value)}
                        className="w-full bg-[#0d141a] border border-[#1c2d38] rounded px-2 py-1 text-slate-200 font-mono"
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Botão Salvar e Notificações */}
        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3 text-xs">
            <label className="flex items-center gap-2 cursor-pointer text-slate-200">
              <input
                type="checkbox"
                checked={form.browser_notifications_enabled}
                onChange={(e) =>
                  setForm({ ...form, browser_notifications_enabled: e.target.checked })
                }
                className="accent-emerald-500"
              />
              <Bell className="w-4 h-4 text-emerald-400" />
              <span>Habilitar Alerta Visual no Navegador (Opcional)</span>
            </label>
            {form.browser_notifications_enabled && permission !== 'granted' && (
              <button
                type="button"
                onClick={requestPermission}
                className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 font-mono"
              >
                Autorizar no Navegador
              </button>
            )}
          </div>

          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Salvando...' : 'Salvar Parâmetros do Modo de Evento'}
          </button>
        </div>
      </form>

      {/* Backups e Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              Backups do Banco de Dados Único (SQLite)
            </h3>
            <button
              type="button"
              onClick={handleCreateBackup}
              className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold"
            >
              Criar Backup Agora
            </button>
          </div>
          <div className="space-y-2 text-xs font-mono max-h-56 overflow-y-auto">
            {backups.map((b, i) => (
              <div
                key={i}
                className="p-2.5 rounded bg-[#080d11] border border-[#1c2d38] flex items-center justify-between"
              >
                <span className="text-slate-200">{b.filename}</span>
                <span className="text-emerald-400">{b.size_kb} KB</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <RefreshCw className="w-4 h-4 text-emerald-400" />
              Últimos Logs de Consulta às Lojas Confiáveis
            </h3>
          </div>
          <div className="space-y-2 text-xs max-h-56 overflow-y-auto">
            {(logsData?.logs || []).slice(0, 12).map((l) => (
              <div
                key={l.id}
                className="p-2.5 rounded bg-[#080d11] border border-[#1c2d38] flex items-center justify-between gap-2"
              >
                <div>
                  <span className="font-bold text-white">{l.store_name}</span>
                  <span className="text-slate-400 block text-[11px]">
                    {formatDateTimeSP(l.started_at)} • {l.duration_ms}ms
                  </span>
                </div>
                <span
                  className={`px-2 py-0.5 rounded font-mono text-[11px] font-bold ${
                    l.status === 'ONLINE'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-amber-500/20 text-amber-300'
                  }`}
                >
                  {l.status} ({l.offers_updated} ofertas)
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
