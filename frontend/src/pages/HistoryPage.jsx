import React, { useEffect, useState } from 'react';
import { LineChart } from 'lucide-react';
import { radarApi, formatBRL, formatDateTimeSP } from '../services/api';

const PERIODS = [
  { id: '24h', label: '24 horas' },
  { id: '7d', label: '7 dias' },
  { id: '30d', label: '30 dias' },
  { id: '90d', label: '90 dias' },
  { id: 'all', label: 'Completo' },
];

export default function HistoryPage() {
  const [category, setCategory] = useState('PS5');
  const [period, setPeriod] = useState('90d');
  const [paymentFilter, setPaymentFilter] = useState('ALL');
  const [includeShipping, setIncludeShipping] = useState(true);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    radarApi
      .getHistory(category, period, paymentFilter, includeShipping)
      .then(setData)
      .finally(() => setLoading(false));
  }, [category, period, paymentFilter, includeShipping]);

  const stats = data?.statistics || {};

  return (
    <div className="space-y-6 sm:space-y-7">
      {/* Cabeçalho e Seletor de Produto */}
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-3 sm:gap-4">
        <div className="space-y-1">
          <h2 className="text-base sm:text-xl font-extrabold text-white flex items-center gap-2">
            <LineChart className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>Histórico de Preços & Comparação Estatística</span>
          </h2>
          <p className="text-[11px] sm:text-sm text-slate-400">
            Todas as coletas anteriores ficam registradas para comparar se o preço de hoje está próximo do menor valor da história.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:flex items-center gap-2 w-full sm:w-auto shrink-0">
          <button
            onClick={() => setCategory('PS5')}
            className={`px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl text-xs font-extrabold transition border whitespace-nowrap text-center ${
              category === 'PS5'
                ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-md'
                : 'bg-[#080d11] text-slate-300 border-[#182631] hover:border-emerald-500/40'
            }`}
          >
            PlayStation 5 Novo
          </button>
          <button
            onClick={() => setCategory('DUALSENSE')}
            className={`px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl text-xs font-extrabold transition border whitespace-nowrap text-center ${
              category === 'DUALSENSE'
                ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-md'
                : 'bg-[#080d11] text-slate-300 border-[#182631] hover:border-emerald-500/40'
            }`}
          >
            DualSense Oficial
          </button>
        </div>
      </div>

      {/* Controles de Período e Condição de Pagamento */}
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3.5 sm:p-4 flex flex-wrap items-center justify-between gap-3 sm:gap-4">
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 w-full sm:w-auto">
          {PERIODS.map((p) => (
            <button
              key={p.id}
              onClick={() => setPeriod(p.id)}
              className={`px-3 py-1.5 sm:px-3.5 sm:py-2 rounded-xl text-[11px] sm:text-xs font-mono font-bold transition whitespace-nowrap border shrink-0 ${
                period === p.id
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-[#080d11] text-slate-400 hover:text-slate-200 border-[#182631]'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs w-full sm:w-auto">
          <select
            value={paymentFilter}
            onChange={(e) => setPaymentFilter(e.target.value)}
            className="flex-1 sm:flex-initial bg-[#080d11] border border-[#182631] rounded-xl px-3 py-2 text-slate-200 font-medium text-[11px] sm:text-xs"
          >
            <option value="ALL">Todas as Condições</option>
            <option value="PIX">Somente Preço à Vista / PIX</option>
            <option value="CARD">Somente Parcelado Cartão</option>
            <option value="COUPON">Somente Ofertas com Cupom</option>
          </select>

          <label className="flex items-center gap-2 cursor-pointer text-slate-300 bg-[#080d11] border border-[#182631] rounded-xl px-3 py-2 whitespace-nowrap text-[11px] sm:text-xs">
            <input
              type="checkbox"
              checked={includeShipping}
              onChange={(e) => setIncludeShipping(e.target.checked)}
              className="accent-emerald-500"
            />
            <span>Somar Frete</span>
          </label>
        </div>
      </div>

      {/* 8 Métricas Estatísticas em Grade 2x4 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3.5">
        <div className="bg-[#0b1116] border border-emerald-500/40 rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Menor Preço</span>
          <span className="text-base sm:text-lg font-extrabold font-mono text-emerald-400 whitespace-nowrap mt-1 block">
            {formatBRL(stats.min_price)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Maior Preço</span>
          <span className="text-base sm:text-lg font-bold font-mono text-rose-400 whitespace-nowrap mt-1 block">
            {formatBRL(stats.max_price)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Preço Médio</span>
          <span className="text-base sm:text-lg font-bold font-mono text-amber-300 whitespace-nowrap mt-1 block">
            {formatBRL(stats.mean_price)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Mediana</span>
          <span className="text-base sm:text-lg font-bold font-mono text-slate-100 whitespace-nowrap mt-1 block">
            {formatBRL(stats.median_price)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Desvio Padrão</span>
          <span className="text-base sm:text-lg font-bold font-mono text-slate-200 whitespace-nowrap mt-1 block">
            {formatBRL(stats.std_dev)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Variação</span>
          <span
            className={`text-base sm:text-lg font-bold font-mono whitespace-nowrap mt-1 block ${
              (stats.variation_pct || 0) <= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {stats.variation_pct !== null && stats.variation_pct !== undefined
              ? `${stats.variation_pct}%`
              : '0%'}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Freq. Quedas</span>
          <span className="text-base sm:text-lg font-bold font-mono text-emerald-300 whitespace-nowrap mt-1 block">
            {stats.drops_count || 0} ({stats.drop_frequency_pct || 0}%)
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3 sm:p-4">
          <span className="text-[10px] sm:text-[11px] text-slate-400 block font-mono uppercase">Freq. Aumentos</span>
          <span className="text-base sm:text-lg font-bold font-mono text-amber-400 whitespace-nowrap mt-1 block">
            {stats.increases_count || 0} ({stats.increase_frequency_pct || 0}%)
          </span>
        </div>
      </div>

      {/* Diferenciação explícita por condição: PIX vs Cartão vs Cupom */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 sm:gap-4">
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3.5 sm:p-4 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-400">Menor Preço no PIX:</span>
          <span className="font-mono font-extrabold text-xs sm:text-sm text-emerald-400 whitespace-nowrap">
            {formatBRL(stats.lowest_pix_price)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3.5 sm:p-4 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-400">Menor c/ Cupom:</span>
          <span className="font-mono font-extrabold text-xs sm:text-sm text-emerald-300 whitespace-nowrap">
            {formatBRL(stats.lowest_coupon_price)}
          </span>
        </div>
        <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-3.5 sm:p-4 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-400">Menor no Cartão:</span>
          <span className="font-mono font-extrabold text-xs sm:text-sm text-sky-400 whitespace-nowrap">
            {formatBRL(stats.lowest_card_price)}
          </span>
        </div>
      </div>

      {/* Log de Registros Históricos (Leve, sem gráficos pesados) */}
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl overflow-hidden shadow-lg">
        <div className="p-3.5 sm:p-5 border-b border-[#182631]">
          <h3 className="font-bold text-white text-xs sm:text-base">
            Auditoria de Coletas Registradas no Histórico
          </h3>
        </div>

        {/* Visão Mobile: Histórico em Cards (md:hidden) */}
        <div className="md:hidden divide-y divide-[#182631] max-h-96 overflow-y-auto">
          {[...(data?.history || [])].reverse().map((h) => (
            <div key={h.id} className="p-3 space-y-1.5 bg-[#0b1116] text-xs">
              <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>{formatDateTimeSP(h.recorded_at)}</span>
                <span className="font-semibold text-white">{h.store_name}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-300">{h.payment_condition}</span>
                <span className="font-mono font-extrabold text-emerald-400 text-sm">
                  {formatBRL(h.final_price)}
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>À vista: {formatBRL(h.price_cash)} • Frete: {h.shipping_cost > 0 ? formatBRL(h.shipping_cost) : 'Grátis'}</span>
                {h.coupon_code && <span className="text-emerald-400 font-bold">{h.coupon_code}</span>}
              </div>
            </div>
          ))}
        </div>

        {/* Visão Desktop: Tabela Completa (hidden md:block) - 100% INTACTA PARA PC */}
        <div className="hidden md:block overflow-x-auto max-h-96">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#080d11] text-slate-400 font-mono uppercase border-b border-[#182631] whitespace-nowrap sticky top-0">
                <th className="py-3 px-4">Data / Horário</th>
                <th className="py-3 px-4">Loja</th>
                <th className="py-3 px-4">Condição</th>
                <th className="py-3 px-4">Preço à Vista</th>
                <th className="py-3 px-4">Preço Cartão</th>
                <th className="py-3 px-4">Frete</th>
                <th className="py-3 px-4">Cupom</th>
                <th className="py-3 px-4 text-right">Valor Final</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#182631]">
              {[...(data?.history || [])].reverse().map((h) => (
                <tr key={h.id} className="hover:bg-[#101921]/80 transition whitespace-nowrap">
                  <td className="py-2.5 px-4 font-mono text-slate-300">
                    {formatDateTimeSP(h.recorded_at)}
                  </td>
                  <td className="py-2.5 px-4 text-white font-semibold">{h.store_name}</td>
                  <td className="py-2.5 px-4 text-slate-300">{h.payment_condition}</td>
                  <td className="py-2.5 px-4 font-mono">{formatBRL(h.price_cash)}</td>
                  <td className="py-2.5 px-4 font-mono text-sky-300">{formatBRL(h.price_card)}</td>
                  <td className="py-2.5 px-4 font-mono">
                    {h.shipping_cost > 0 ? formatBRL(h.shipping_cost) : 'Grátis'}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-emerald-400">
                    {h.coupon_code ? `${h.coupon_code} (-${formatBRL(h.coupon_discount)})` : '—'}
                  </td>
                  <td className="py-2.5 px-4 font-mono font-extrabold text-emerald-400 text-right">
                    {formatBRL(h.final_price)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
