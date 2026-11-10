import React, { useEffect, useState } from 'react';
import {
  FileBarChart2,
  Calendar,
  TrendingDown,
  Award,
  ExternalLink,
  CheckCircle2,
} from 'lucide-react';
import { radarApi, formatBRL, formatDateTimeSP } from '../services/api';

export default function ReportsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    radarApi
      .getReports()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading && !data) {
    return <div className="text-slate-400 text-sm">Gerando relatórios diário e semanal...</div>;
  }

  const daily = data?.daily_report || {};
  const weekly = data?.weekly_report || {};

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-white flex items-center gap-2">
            <FileBarChart2 className="w-6 h-6 text-emerald-400" />
            9. Relatórios Executivos Diário e Semanal
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Síntese consolidada dos menores preços, quedas detectadas, comparativo entre lojas e recomendações de compra.
          </p>
        </div>
        <span className="text-xs font-mono text-slate-400">
          Gerado em: {formatDateTimeSP(data?.generated_at)}
        </span>
      </div>

      {/* RELATÓRIO DIÁRIO (Seção 13) */}
      <section className="bg-[#0d141a] border border-emerald-500/30 rounded-xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-[#1c2d38] pb-3">
          <h3 className="font-bold text-white text-base flex items-center gap-2">
            <Calendar className="w-5 h-5 text-emerald-400" />
            Relatório Diário ({daily.date_reference})
          </h3>
          <span className="px-2.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-mono text-xs font-bold">
            RESUMO 24 HORAS
          </span>
        </div>

        {/* Menores Preços Encontrados Hoje */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[#080d11] border border-[#1c2d38] rounded-xl p-4">
            <span className="text-xs font-mono text-emerald-400 uppercase font-bold">
              Menor Preço PS5 Slim Digital Hoje
            </span>
            {daily.lowest_prices?.ps5 ? (
              <div className="mt-2 space-y-1">
                <p className="text-2xl font-extrabold font-mono text-white">
                  {formatBRL(daily.lowest_prices.ps5.final_price)}
                </p>
                <p className="text-xs text-slate-300">{daily.lowest_prices.ps5.title}</p>
                <p className="text-xs text-slate-400">
                  Loja: {daily.lowest_prices.ps5.store} • Score: {daily.lowest_prices.ps5.opportunity_score}/100
                </p>
              </div>
            ) : (
              <p className="text-xs text-slate-400 mt-2">Sem ofertas registradas.</p>
            )}
          </div>

          <div className="bg-[#080d11] border border-[#1c2d38] rounded-xl p-4">
            <span className="text-xs font-mono text-emerald-400 uppercase font-bold">
              Menor Preço DualSense Oficial Hoje
            </span>
            {daily.lowest_prices?.dualsense ? (
              <div className="mt-2 space-y-1">
                <p className="text-2xl font-extrabold font-mono text-white">
                  {formatBRL(daily.lowest_prices.dualsense.final_price)}
                </p>
                <p className="text-xs text-slate-300">{daily.lowest_prices.dualsense.title}</p>
                <p className="text-xs text-slate-400">
                  Loja: {daily.lowest_prices.dualsense.store} • Score:{' '}
                  {daily.lowest_prices.dualsense.opportunity_score}/100
                </p>
              </div>
            ) : (
              <p className="text-xs text-slate-400 mt-2">Sem ofertas registradas.</p>
            )}
          </div>
        </div>

        {/* Produtos com Queda de Preço */}
        <div>
          <h4 className="font-bold text-white text-sm flex items-center gap-1.5 mb-3">
            <TrendingDown className="w-4 h-4 text-emerald-400" />
            Produtos com Queda de Preço Identificada ({daily.price_drops?.length || 0})
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(daily.price_drops || []).map((d) => (
              <div
                key={d.offer_id}
                className="p-3.5 rounded-lg bg-[#080d11] border border-[#1c2d38] flex items-center justify-between gap-3 text-xs"
              >
                <div>
                  <span className="font-bold text-white block">{d.title}</span>
                  <span className="text-slate-400">
                    {d.store_name} • De {formatBRL(d.previous_price)} para{' '}
                    <strong className="text-emerald-400">{formatBRL(d.current_price)}</strong>
                  </span>
                </div>
                <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold shrink-0">
                  -{d.drop_pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* RELATÓRIO SEMANAL (Seção 13) */}
      <section className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-[#1c2d38] pb-3">
          <h3 className="font-bold text-white text-base flex items-center gap-2">
            <Award className="w-5 h-5 text-emerald-400" />
            Relatório Semanal ({weekly.period_label})
          </h3>
          <span className="text-xs font-mono text-slate-400">
            {weekly.total_weekly_checks || 0} registros históricos avaliados
          </span>
        </div>

        {/* Recomendações Estratégicas de Compra */}
        <div className="space-y-3">
          <h4 className="font-bold text-white text-sm">Recomendações Finais de Compra</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(weekly.purchase_recommendations || []).map((rec, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-emerald-950/25 border border-emerald-500/40 flex flex-col justify-between gap-3"
              >
                <div>
                  <div className="flex items-center justify-between text-xs font-mono mb-1">
                    <span className="text-emerald-300 font-bold uppercase">{rec.category}</span>
                    <span className="text-white font-bold">Score {rec.opportunity_score}/100</span>
                  </div>
                  <p className="font-bold text-white text-sm flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    {rec.verdict}
                  </p>
                  <p className="text-xs text-slate-300 mt-1">{rec.reasoning}</p>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-emerald-500/20 text-xs">
                  <span className="font-mono font-bold text-emerald-400 text-base">
                    {formatBRL(rec.final_price)} ({rec.store_name})
                  </span>
                  <a
                    href={rec.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-emerald-300 hover:underline font-bold"
                  >
                    <span>Ver Oferta</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Comparação Consolidada entre Lojas */}
        <div>
          <h4 className="font-bold text-white text-sm mb-3">Comparação Semanal entre Lojas</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#090f14] text-slate-400 font-mono uppercase border-b border-[#1c2d38]">
                  <th className="py-2.5 px-4">Loja / Fonte</th>
                  <th className="py-2.5 px-4">Reputação</th>
                  <th className="py-2.5 px-4">Ofertas Ativas</th>
                  <th className="py-2.5 px-4">Menor PS5 Slim Digital</th>
                  <th className="py-2.5 px-4">Menor DualSense</th>
                  <th className="py-2.5 px-4">Score Médio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1c2d38]">
                {(weekly.store_comparison || []).map((st, idx) => (
                  <tr key={idx} className="hover:bg-[#111b22]">
                    <td className="py-2.5 px-4 font-bold text-white">{st.store_name}</td>
                    <td className="py-2.5 px-4 font-mono text-slate-300">{st.reputation_score}/100</td>
                    <td className="py-2.5 px-4 font-mono">{st.active_offers_count}</td>
                    <td className="py-2.5 px-4 font-mono text-emerald-400 font-bold">
                      {formatBRL(st.min_ps5_price)}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-emerald-300 font-bold">
                      {formatBRL(st.min_dualsense_price)}
                    </td>
                    <td className="py-2.5 px-4 font-mono">{st.avg_opportunity_score}/100</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
