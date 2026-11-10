import React, { useEffect, useState } from 'react';
import {
  TrendingDown,
  TrendingUp,
  Minus,
  AlertTriangle,
  Activity,
  Database,
} from 'lucide-react';
import { radarApi, formatBRL } from '../services/api';

export default function PredictionsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    radarApi
      .getPredictions()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading && !data) {
    return (
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-8 text-center text-slate-400 text-sm">
        Calculando modelos estatísticos de previsão...
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-7">
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-4 sm:p-5">
        <h2 className="text-base sm:text-xl font-extrabold text-white flex items-center gap-2">
          <TrendingDown className="w-5 h-5 text-emerald-400 shrink-0" />
          <span>Previsão de Mercado — Tendências para 24h, 3 Dias e 7 Dias</span>
        </h2>
        <p className="text-[11px] sm:text-sm text-slate-400 mt-1">
          Análise estatística interpretável via Médias Móveis (7d e 30d), Regressão Linear Amortecida (OLS) e Volatilidade.
        </p>
      </div>

      {/* Aviso Metodológico */}
      <div className="bg-amber-950/25 border border-amber-500/40 rounded-2xl p-3.5 sm:p-4 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-200 leading-relaxed">
          <strong>Nota de Transparência Estatística:</strong> {data?.disclaimer} Quando não existem registros
          históricos suficientes, o sistema informa explicitamente que a estimativa não é confiável.
        </div>
      </div>

      {/* Cards de Previsão por Produto */}
      <div className="space-y-5 sm:space-y-6">
        {(data?.products_predictions || []).map((prod) => (
          <section
            key={prod.product_id}
            className="bg-[#0b1116] border border-[#182631] rounded-2xl p-4 sm:p-5 space-y-4 sm:space-y-5 shadow-lg"
          >
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 border-b border-[#182631] pb-3.5 sm:pb-4">
              <div>
                <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-mono text-[11px] sm:text-xs font-bold">
                  {prod.category}
                </span>
                <h3 className="font-bold text-white text-sm sm:text-lg mt-1.5">{prod.product_name}</h3>
              </div>
              {prod.horizons?.[0] && (
                <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2 sm:gap-3 text-xs font-mono">
                  <span className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#080d11] border border-[#182631] text-slate-400 whitespace-nowrap text-[11px] sm:text-xs">
                    Média 7d:{' '}
                    <strong className="text-emerald-300">{formatBRL(prod.horizons[0].moving_avg_7d)}</strong>
                  </span>
                  <span className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#080d11] border border-[#182631] text-slate-400 whitespace-nowrap text-[11px] sm:text-xs">
                    Média 30d:{' '}
                    <strong className="text-slate-200">{formatBRL(prod.horizons[0].moving_avg_30d)}</strong>
                  </span>
                  <span className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#080d11] border border-[#182631] text-slate-400 flex items-center gap-1.5 whitespace-nowrap text-[11px] sm:text-xs">
                    <Activity className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>
                      Volatilidade: <strong className="text-white">{prod.horizons[0].volatility_pct}%</strong>
                    </span>
                  </span>
                  <span className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-[#080d11] border border-[#182631] text-slate-400 flex items-center gap-1.5 whitespace-nowrap text-[11px] sm:text-xs">
                    <Database className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>
                      Amostra: <strong className="text-white">{prod.horizons[0].data_points_used} coletas</strong>
                    </span>
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 sm:gap-4">
              {(prod.horizons || []).map((h) => {
                const isDrop = h.trend.includes('QUEDA');
                const isRise = h.trend.includes('AUMENTO');
                return (
                  <div
                    key={h.horizon_hours}
                    className="bg-[#080d11] border border-[#182631] rounded-2xl p-3.5 sm:p-4 flex flex-col justify-between space-y-3"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="font-mono text-xs text-slate-400 uppercase font-bold whitespace-nowrap">
                          {h.horizon_label}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] sm:text-xs font-mono font-bold whitespace-nowrap ${
                            isDrop
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : isRise
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                              : 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                          }`}
                        >
                          {isDrop ? (
                            <TrendingDown className="w-3.5 h-3.5 shrink-0" />
                          ) : isRise ? (
                            <TrendingUp className="w-3.5 h-3.5 shrink-0" />
                          ) : (
                            <Minus className="w-3.5 h-3.5 shrink-0" />
                          )}
                          <span>{h.trend}</span>
                        </span>
                      </div>

                      <div className="my-2.5 sm:my-3 p-3 rounded-xl bg-[#0b1116] border border-[#182631]">
                        <span className="text-[10px] sm:text-[11px] text-slate-400 block">
                          Faixa Central Estimada ({h.methodology})
                        </span>
                        <span className="text-xl sm:text-2xl font-extrabold font-mono text-white whitespace-nowrap block mt-0.5">
                          {formatBRL(h.estimated_price)}
                        </span>
                        <span className="text-[11px] sm:text-xs text-slate-400 block mt-0.5 font-mono whitespace-nowrap">
                          Preço base atual: {formatBRL(h.current_price)}
                        </span>
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed">{h.explanation}</p>
                    </div>

                    <div className="pt-2.5 sm:pt-3 border-t border-[#182631] flex items-center justify-between gap-2 text-[11px] sm:text-xs font-mono">
                      <span className="text-slate-400">Confiança:</span>
                      <span
                        className={`font-bold whitespace-nowrap ${
                          h.is_reliable ? 'text-emerald-400' : 'text-amber-400'
                        }`}
                      >
                        {h.confidence_pct}% ({h.is_reliable ? 'Amostra Válida' : 'Baixa Amostra'})
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
