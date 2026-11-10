import React, { useEffect, useState } from 'react';
import {
  ExternalLink,
  HelpCircle,
  Truck,
  Disc,
  Award,
  Scale,
} from 'lucide-react';
import { radarApi, formatBRL, formatDateTimeSP, getScoreBadgeStyle } from '../services/api';

export default function ComparatorPage() {
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [includeAlternatives, setIncludeAlternatives] = useState(false);
  const [onlyOfficialWarranty, setOnlyOfficialWarranty] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const backendCategory =
    categoryFilter === 'PS5_DIGITAL' || categoryFilter === 'PS5_DISC' || categoryFilter === 'PS5'
      ? 'PS5'
      : categoryFilter === 'DUALSENSE'
      ? 'DUALSENSE'
      : 'ALL';

  useEffect(() => {
    setLoading(true);
    radarApi
      .getComparator(backendCategory, includeAlternatives, onlyOfficialWarranty)
      .then(setData)
      .finally(() => setLoading(false));
  }, [backendCategory, includeAlternatives, onlyOfficialWarranty]);

  const displayedOffers = (data?.offers || []).filter((o) => {
    if (categoryFilter === 'PS5_DIGITAL') return o.category === 'PS5' && !o.has_disc_drive;
    if (categoryFilter === 'PS5_DISC') return o.category === 'PS5' && o.has_disc_drive;
    return true;
  });

  return (
    <div className="space-y-6 sm:space-y-7">
      {/* Cabeçalho e Filtros */}
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-4 sm:p-5 flex flex-col xl:flex-row xl:items-center justify-between gap-3 sm:gap-4">
        <div className="space-y-1">
          <h2 className="text-base sm:text-xl font-extrabold text-white flex items-center gap-2">
            <Scale className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>Comparador de Lojas Confiáveis — Busca pelo Menor Preço Real</span>
          </h2>
          <p className="text-[11px] sm:text-sm text-slate-400">
            Compara lado a lado os menores preços de PlayStation 5 Novo (Digital e Com Leitor) e DualSense em varejistas verificados.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 text-xs shrink-0">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full sm:w-auto bg-[#080d11] border border-[#182631] rounded-xl px-3 sm:px-3.5 py-2 sm:py-2.5 text-white font-medium focus:outline-none focus:border-emerald-500/50"
          >
            <option value="ALL">Todos (PS5 Digital + Disco + DualSense)</option>
            <option value="PS5">Todos os PlayStation 5 Novos</option>
            <option value="PS5_DIGITAL">Apenas PS5 Slim Digital (Sem Leitor)</option>
            <option value="PS5_DISC">Apenas PS5 Slim Com Leitor de Disco</option>
            <option value="DUALSENSE">Apenas Controle DualSense Oficial</option>
          </select>

          <label className="flex items-center gap-2 bg-[#080d11] border border-[#182631] rounded-xl px-3 sm:px-3.5 py-2 sm:py-2.5 cursor-pointer whitespace-nowrap text-slate-200 text-[11px] sm:text-xs">
            <input
              type="checkbox"
              checked={onlyOfficialWarranty}
              onChange={(e) => setOnlyOfficialWarranty(e.target.checked)}
              className="accent-emerald-500"
            />
            <span>Somente Nacional Anatel</span>
          </label>

          <label className="flex items-center gap-2 bg-[#080d11] border border-[#182631] rounded-xl px-3 sm:px-3.5 py-2 sm:py-2.5 cursor-pointer whitespace-nowrap text-slate-200 text-[11px] sm:text-xs">
            <input
              type="checkbox"
              checked={includeAlternatives}
              onChange={(e) => setIncludeAlternatives(e.target.checked)}
              className="accent-emerald-500"
            />
            <span>Incluir PS5 Pro / Edge</span>
          </label>
        </div>
      </div>

      {/* Tabela Comparativa Ordenada pelo Menor Preço */}
      <section className="bg-[#0b1116] border border-[#182631] rounded-2xl overflow-hidden shadow-lg">
        {/* Visão Mobile Otimizada para Celular: Cards Verticais Elegantes (md:hidden) */}
        <div className="md:hidden divide-y divide-[#182631]">
          {loading ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              Carregando comparativo de lojas confiáveis...
            </div>
          ) : (
            displayedOffers.map((o) => (
              <div key={o.id} className="p-3.5 space-y-2.5 bg-[#0b1116] hover:bg-[#101921]/60 transition">
                {/* Linha 1: Loja e Score */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="font-extrabold text-white text-xs truncate">{o.store_name}</span>
                    <span className="text-[10px] text-slate-400 truncate">({o.seller_name})</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold shrink-0 border ${getScoreBadgeStyle(
                      o.opportunity_score
                    )}`}
                  >
                    Score {o.opportunity_score}/100
                  </span>
                </div>

                {/* Linha 2: Título */}
                <div className="font-semibold text-slate-100 text-xs leading-snug line-clamp-2">
                  {o.title}
                </div>

                {/* Linha 3: Badges */}
                <div className="flex flex-wrap items-center gap-1 text-[10px] font-mono">
                  {o.category === 'PS5' ? (
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-bold border ${
                        o.has_disc_drive
                          ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                          : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                      }`}
                    >
                      <Disc className="w-2.5 h-2.5 shrink-0" />
                      <span>{o.disc_badge}</span>
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-500/40 text-purple-300 font-bold">
                      DUALSENSE • {o.color}
                    </span>
                  )}
                  <span className="text-slate-400">• {o.is_national ? 'Nacional Anatel' : 'Importado'}</span>
                </div>

                {/* Linha 4: Preços */}
                <div className="p-2.5 rounded-xl bg-[#080d11] border border-[#182631] flex items-center justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-mono uppercase text-slate-400 block">Menor Preço (PIX)</span>
                    <div className="text-base font-extrabold font-mono text-emerald-400">
                      {formatBRL(o.final_price)}
                    </div>
                    <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                      <Truck className="w-3 h-3 text-emerald-400 shrink-0" />
                      <span>{o.shipping_cost > 0 ? `+Frete ${formatBRL(o.shipping_cost)}` : 'Frete Grátis'}</span>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-[10px] font-mono uppercase text-amber-300 block">vs Recorde</span>
                    <div className="text-xs font-bold font-mono text-amber-300 flex items-center justify-end gap-1">
                      <Award className="w-3 h-3 shrink-0" />
                      <span>{formatBRL(o.min_historical_price)}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">
                      {o.diff_vs_historical_low && o.diff_vs_historical_low > 0
                        ? `+${formatBRL(o.diff_vs_historical_low)}`
                        : 'No piso!'}
                    </span>
                  </div>
                </div>

                {/* Linha 5: Observação e Botão */}
                <div className="flex items-center justify-between gap-2 pt-0.5">
                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-[11px] font-semibold truncate ${
                        o.is_fake_discount
                          ? 'text-rose-400'
                          : o.is_marketplace || !o.is_national
                          ? 'text-amber-300'
                          : 'text-emerald-400'
                      }`}
                    >
                      {o.reliability_observation}
                    </p>
                    {o.price_card && (
                      <span className="text-[10px] text-slate-400 font-mono">
                        Cartão: {formatBRL(o.price_card)}
                      </span>
                    )}
                  </div>
                  <a
                    href={o.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs shrink-0 whitespace-nowrap shadow-sm"
                  >
                    <span>Ir à Loja</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Visão Desktop: Tabela Completa (hidden md:block) - 100% INTACTA PARA PC */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs sm:text-sm">
            <thead>
              <tr className="bg-[#080d11] text-slate-400 font-mono text-[11px] uppercase border-b border-[#182631] whitespace-nowrap">
                <th className="py-3.5 px-4">Loja & Vendedor</th>
                <th className="py-3.5 px-4">Produto Novo & Versão</th>
                <th className="py-3.5 px-4">Menor Preço (PIX)</th>
                <th className="py-3.5 px-4">Preço Cartão</th>
                <th className="py-3.5 px-4">vs Recorde Histórico</th>
                <th className="py-3.5 px-4">Auditoria de Confiabilidade</th>
                <th className="py-3.5 px-4">Score</th>
                <th className="py-3.5 px-4 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#182631]">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-400">
                    Carregando comparativo de lojas confiáveis...
                  </td>
                </tr>
              ) : (
                displayedOffers.map((o) => (
                  <tr key={o.id} className="hover:bg-[#101921]/80 transition">
                    <td className="py-3.5 px-4 align-middle whitespace-nowrap">
                      <div className="font-bold text-white">{o.store_name}</div>
                      <div className="text-[11px] text-slate-400">{o.seller_name}</div>
                    </td>

                    <td className="py-3.5 px-4 align-middle max-w-md">
                      <div className="font-semibold text-slate-100 leading-snug">{o.title}</div>
                      <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono mt-1.5">
                        {o.category === 'PS5' ? (
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-bold border whitespace-nowrap ${
                              o.has_disc_drive
                                ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
                                : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                            }`}
                          >
                            <Disc className="w-3 h-3 shrink-0" />
                            <span>{o.disc_badge}</span>
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-purple-500/15 border border-purple-500/40 text-purple-300 font-bold whitespace-nowrap">
                            DUALSENSE OFICIAL • {o.color}
                          </span>
                        )}
                        <span className="text-slate-400 whitespace-nowrap">
                          • {o.is_national ? 'Nacional Anatel' : 'Importado'}
                        </span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 align-middle font-mono whitespace-nowrap">
                      <div className="font-extrabold text-base text-emerald-400">
                        {formatBRL(o.final_price)}
                      </div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                        <Truck className="w-3 h-3 text-emerald-400 shrink-0" />
                        <span>
                          {o.shipping_cost > 0 ? `+Frete ${formatBRL(o.shipping_cost)}` : 'Frete Grátis'}
                        </span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 align-middle font-mono text-slate-300 whitespace-nowrap">
                      <div>{formatBRL(o.price_card)}</div>
                      {o.installments_text && (
                        <div className="text-[10px] text-slate-400">{o.installments_text}</div>
                      )}
                    </td>

                    <td className="py-3.5 px-4 align-middle font-mono text-xs whitespace-nowrap">
                      <div className="text-amber-300 font-bold flex items-center gap-1">
                        <Award className="w-3.5 h-3.5 shrink-0" />
                        <span>{formatBRL(o.min_historical_price)}</span>
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {o.diff_vs_historical_low && o.diff_vs_historical_low > 0
                          ? `+${formatBRL(o.diff_vs_historical_low)} acima`
                          : 'No piso histórico!'}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 align-middle max-w-xs">
                      <div
                        className={`text-xs font-semibold leading-snug ${
                          o.is_fake_discount
                            ? 'text-rose-400'
                            : o.is_marketplace || !o.is_national
                            ? 'text-amber-300'
                            : 'text-emerald-400'
                        }`}
                      >
                        {o.reliability_observation}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 align-middle whitespace-nowrap">
                      <span
                        className={`px-2.5 py-1 rounded-full text-xs font-mono font-bold border ${getScoreBadgeStyle(
                          o.opportunity_score
                        )}`}
                      >
                        {o.opportunity_score}/100
                      </span>
                    </td>

                    <td className="py-3.5 px-4 align-middle text-right whitespace-nowrap">
                      <a
                        href={o.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs transition"
                      >
                        <span>Ir à Loja</span>
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Status Transparente dos Conectores */}
      <section className="space-y-3.5">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Status dos Módulos de Coleta das Lojas Varejistas Confiáveis</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5 sm:gap-4">
          {(data?.stores || []).map((st) => (
            <div
              key={st.id}
              className="bg-[#0b1116] border border-[#182631] rounded-2xl p-4 flex flex-col justify-between gap-2.5 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-white text-sm">{st.name}</span>
                <span
                  className={`px-2.5 py-0.5 rounded-full font-mono font-bold text-[11px] whitespace-nowrap ${
                    st.status === 'ONLINE'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  }`}
                >
                  {st.status}
                </span>
              </div>
              <p className="text-slate-300 leading-relaxed">{st.status_message}</p>
              <p className="text-slate-400 text-[11px] bg-[#080d11] p-2.5 rounded-xl border border-[#182631]">
                <strong>Integração:</strong> {st.integration_docs}
              </p>
              <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 font-mono">
                <span>Reputação: {st.reputation_score}/100</span>
                <span>{formatDateTimeSP(st.last_check_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
