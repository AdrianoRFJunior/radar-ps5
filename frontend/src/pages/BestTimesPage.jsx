import React, { useEffect, useState } from 'react';
import { Clock, Award, TrendingDown, Info } from 'lucide-react';
import { radarApi } from '../services/api';
import { BestTimesBarChart } from '../charts/RadarCharts';

export default function BestTimesPage() {
  const [category, setCategory] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    radarApi
      .getBestTimes(category)
      .then(setData)
      .finally(() => setLoading(false));
  }, [category]);

  if (loading && !data) {
    return <div className="text-slate-400 text-sm">Analisando padrões por horário e dia da semana...</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-white flex items-center gap-2">
            <Clock className="w-6 h-6 text-emerald-400" />
            7. Melhores Horários — Análise de Padrões por Hora, Dia e Semana da Black Friday
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Diferenciação entre quantidade bruta de ofertas e qualidade real das oportunidades (ponderada pelo total de consultas realizadas).
          </p>
        </div>

        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="bg-[#0d141a] border border-[#1c2d38] rounded-lg px-3.5 py-2 text-xs text-white font-semibold"
        >
          <option value="">Ambos Produtos (PS5 + DualSense)</option>
          <option value="PS5">Somente PS5 Slim Digital</option>
          <option value="DUALSENSE">Somente Controle DualSense</option>
        </select>
      </div>

      {/* Nota Metodológica contra viés de volume */}
      <div className="bg-[#0d141a] border border-emerald-500/30 rounded-xl p-4 flex items-start gap-3 text-xs text-slate-300">
        <Info className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        <span>{data?.methodology_note}</span>
      </div>

      {/* Top 3 Horários por Eficiência de Qualidade vs Magnitude de Queda */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Award className="w-4 h-4 text-emerald-400" />
            Horários com Maior Frequência Proporcional de Oportunidades Reais
          </h3>
          <div className="space-y-2.5">
            {(data?.top_quality_hours || []).map((h, i) => (
              <div
                key={h.hour}
                className="p-3 rounded-lg bg-[#080d11] border border-[#1c2d38] flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-300 font-mono font-bold flex items-center justify-center">
                    #{i + 1}
                  </span>
                  <div>
                    <span className="font-mono font-bold text-white text-sm">{h.hour_label}</span>
                    <span className="text-slate-400 block text-[11px]">
                      {h.checks_count} consultas realizadas • {h.opportunities_count} oportunidades de alta qualidade
                    </span>
                  </div>
                </div>
                <div className="text-right font-mono">
                  <span className="text-emerald-400 font-bold block">
                    Taxa: {h.opportunity_rate_pct}%
                  </span>
                  <span className="text-slate-400 text-[11px]">
                    Desconto médio: {h.avg_discount_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-emerald-400" />
            Horários com Maiores Quedas Percentuais de Preço
          </h3>
          <div className="space-y-2.5">
            {(data?.top_drop_hours || []).map((h, i) => (
              <div
                key={h.hour}
                className="p-3 rounded-lg bg-[#080d11] border border-[#1c2d38] flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-sky-500/20 text-sky-300 font-mono font-bold flex items-center justify-center">
                    #{i + 1}
                  </span>
                  <div>
                    <span className="font-mono font-bold text-white text-sm">{h.hour_label}</span>
                    <span className="text-slate-400 block text-[11px]">
                      {h.drops_count} quedas diretas detectadas em {h.checks_count} coletas
                    </span>
                  </div>
                </div>
                <div className="text-right font-mono">
                  <span className="text-emerald-300 font-bold block">
                    Maior queda: -{h.max_drop_pct}%
                  </span>
                  <span className="text-slate-400 text-[11px]">
                    Média desconto: -{h.avg_discount_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Gráfico 1: Quantidade de Quedas e Ofertas por Hora do Dia */}
      <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
        <h3 className="font-bold text-white text-sm">
          Distribuição por Hora do Dia (00h às 23h): Quedas de Preço vs Ofertas com Desconto
        </h3>
        <BestTimesBarChart
          data={(data?.by_hour || []).filter((x) => x.checks_count > 0 || x.hour % 2 === 0)}
          xKey="hour_label"
          bar1Key="drops_count"
          bar1Name="Quedas Reais de Preço"
          bar2Key="offers_count"
          bar2Name="Ofertas Promocionais"
        />
      </div>

      {/* Gráfico 2: Média de Desconto (%) e Taxa de Oportunidades por Hora */}
      <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
        <h3 className="font-bold text-white text-sm">
          Qualidade por Horário: Média de Desconto Real (%) vs Maior Queda (%)
        </h3>
        <BestTimesBarChart
          data={(data?.by_hour || []).filter((x) => x.checks_count > 0)}
          xKey="hour_label"
          bar1Key="avg_discount_pct"
          bar1Name="Média de Desconto (%)"
          bar2Key="max_drop_pct"
          bar2Name="Maior Queda Registrada (%)"
        />
      </div>

      {/* Gráfico 3 & 4: Dia da Semana e Semana da Black Friday */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-white text-sm">Comportamento por Dia da Semana</h3>
          <BestTimesBarChart
            data={data?.by_weekday || []}
            xKey="weekday"
            bar1Key="opportunities_count"
            bar1Name="Oportunidades Qualificadas"
            bar2Key="drops_count"
            bar2Name="Quedas de Preço"
          />
        </div>

        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-white text-sm">Comportamento por Semana de Novembro (Black Friday)</h3>
          <BestTimesBarChart
            data={data?.by_bf_week || []}
            xKey="label"
            bar1Key="opportunities_count"
            bar1Name="Oportunidades"
            bar2Key="avg_discount_pct"
            bar2Name="Desconto Médio (%)"
          />
        </div>
      </div>
    </div>
  );
}
