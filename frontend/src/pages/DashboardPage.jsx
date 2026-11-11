import React, { useState } from 'react';
import {
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Truck,
  TrendingDown,
  TrendingUp,
  Store,
  Clock,
  Scale,
  Zap,
  Calendar,
  RefreshCw,
  Disc,
  Award,
  LineChart,
} from 'lucide-react';
import { formatBRL, formatDateTimeSP, getScoreBadgeStyle } from '../services/api';
import PriceBreakdown from '../components/PriceBreakdown';
import CouponBadge from '../components/CouponBadge';

function EventModeBanner({ eventMode, indicators, onTriggerScan, scanning }) {
  if (!eventMode) return null;

  const isIntensified = eventMode.is_intensified;
  const activeEv = eventMode.active_event;
  const nextEv = eventMode.next_event;

  return (
    <div
      className={`rounded-2xl p-3.5 sm:p-5 border transition shadow-lg ${
        activeEv
          ? 'bg-gradient-to-r from-emerald-950/60 via-[#0d211f] to-[#0b1116] border-emerald-500/50'
          : isIntensified
          ? 'bg-gradient-to-r from-[#0d1d20] via-[#0e2024] to-[#0b1116] border-emerald-500/35'
          : 'bg-[#0b1116] border-[#182631]'
      }`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3.5 sm:gap-4">
        <div className="space-y-2 sm:space-y-2.5 min-w-0">
          {/* Linha de Badges de Status */}
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-0.5 sm:py-1 rounded-full text-[11px] sm:text-xs font-mono font-extrabold uppercase border whitespace-nowrap ${
                activeEv
                  ? 'bg-emerald-500 text-slate-950 border-emerald-300'
                  : isIntensified
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-[#131f28] text-slate-300 border-[#223544]'
              }`}
            >
              <Zap className="w-3.5 h-3.5 shrink-0" />
              <span>{eventMode.mode_label}</span>
            </span>

            <span className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-lg bg-[#080d11] border border-[#182631] text-[11px] sm:text-xs font-mono text-emerald-300 whitespace-nowrap">
              <span>Ciclo: a cada {eventMode.effective_interval_minutes} min</span>
            </span>

            <span className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/25 text-[11px] sm:text-xs font-mono text-emerald-300 font-semibold whitespace-nowrap">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>PS5 Novo • Lojas Confiáveis</span>
            </span>

            {indicators?.is_data_stale ? (
              <span className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-300 text-[11px] sm:text-xs font-mono font-bold whitespace-nowrap">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                <span>Atualizado há {indicators.data_age_minutes} min</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-lg bg-[#080d11] border border-[#182631] text-slate-300 text-[11px] sm:text-xs font-mono whitespace-nowrap">
                <Clock className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>
                  Há {indicators?.data_age_minutes ?? 0} min ({formatDateTimeSP(indicators?.last_updated_at)})
                </span>
              </span>
            )}
          </div>

          {/* Linha de Próximo Evento / Evento Ativo */}
          <div className="text-xs sm:text-sm text-slate-300 flex items-start sm:items-center gap-2 leading-relaxed">
            <Calendar className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5 sm:mt-0" />
            {activeEv ? (
              <span>
                <strong className="text-white">Evento Ativo:</strong>{' '}
                <span className="text-emerald-300 font-bold">{activeEv.name}</span> ({activeEv.start_date} a{' '}
                {activeEv.end_date}) — {activeEv.description}
              </span>
            ) : nextEv ? (
              <span>
                <strong className="text-white">Próximo Evento:</strong>{' '}
                <span className="text-emerald-300 font-bold">{nextEv.name}</span> em{' '}
                <span className="font-mono font-bold text-white">{nextEv.days_until_start} dia(s)</span> ({nextEv.start_date}).{' '}
                Referência histórica: <strong className="text-amber-300 font-mono">{formatBRL(indicators?.ps5_historical_low || 3349)}</strong>.
              </span>
            ) : (
              <span>
                Monitoramento contínuo ativo buscando o menor preço histórico do PlayStation 5 e DualSense.
              </span>
            )}
          </div>
        </div>

        {/* Botão de Ação */}
        <div className="shrink-0">
          <button
            onClick={onTriggerScan}
            disabled={scanning}
            className="w-full lg:w-auto px-4 sm:px-5 py-2.5 sm:py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-extrabold text-xs flex items-center justify-center gap-2 transition shadow-md whitespace-nowrap"
          >
            <RefreshCw className={`w-4 h-4 shrink-0 ${scanning ? 'animate-spin' : ''}`} />
            <span>{scanning ? 'Varrendo Lojas...' : 'Atualizar Preços Agora'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function LowestPriceHeroCard({
  rankLabel,
  categoryBadge,
  accentColor = 'emerald',
  offer,
  onOpenHistory,
  onOpenPredictions,
}) {
  if (!offer) {
    return (
      <div className="bg-[#0b1116] border border-[#182631] rounded-2xl p-6 flex items-center justify-center text-slate-400 text-xs min-h-[360px]">
        Nenhuma oferta ativa encontrada para {categoryBadge}.
      </div>
    );
  }

  const varPct = offer.variation_vs_avg_30d_pct || 0;
  const isBelowAvg = varPct <= 0;
  const diffHist = offer.diff_vs_historical_low;
  const isCyan = accentColor === 'cyan';

  return (
    <div className="bg-[#0b1116] border border-[#182631] hover:border-emerald-500/40 rounded-2xl p-4 sm:p-5 flex flex-col justify-between transition shadow-xl shadow-black/30 relative overflow-hidden">
      {/* Barra de Destaque no Topo */}
      <div
        className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${
          isCyan
            ? 'from-cyan-500 via-teal-400 to-emerald-500'
            : 'from-emerald-500 via-emerald-400 to-teal-500'
        }`}
      />

      <div className="space-y-3.5 sm:space-y-4">
        {/* Linha 1: Categoria e Score */}
        <div className="flex items-center justify-between gap-2 pt-0.5">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className={`px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-md font-mono text-[10px] sm:text-[11px] font-extrabold uppercase tracking-wide border truncate ${
                isCyan
                  ? 'bg-cyan-500/15 border-cyan-500/35 text-cyan-300'
                  : 'bg-emerald-500/15 border-emerald-500/35 text-emerald-300'
              }`}
            >
              {rankLabel} • {categoryBadge}
            </span>
          </div>

          <span
            className={`px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full text-[10px] sm:text-[11px] font-mono font-bold border whitespace-nowrap shrink-0 ${getScoreBadgeStyle(
              offer.opportunity_score
            )}`}
          >
            Score {offer.opportunity_score}/100
          </span>
        </div>

        {/* Linha 2: Miniatura e Título do Produto */}
        <div className="flex gap-3 sm:gap-3.5 items-start">
          <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-xl bg-white p-1 sm:p-1.5 flex items-center justify-center shrink-0 border border-slate-700/80 shadow-inner">
            <img
              src={offer.image_url}
              alt={offer.title}
              className="max-h-full max-w-full object-contain"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
          </div>

          <div className="min-w-0 flex-1 space-y-1 sm:space-y-1.5">
            <h3
              className="text-xs sm:text-sm font-bold text-white leading-snug line-clamp-2 min-h-[2rem] sm:min-h-[2.5rem]"
              title={offer.title}
            >
              {offer.title}
            </h3>

            <div className="flex flex-wrap items-center gap-1 sm:gap-1.5 text-xs">
              <span className="inline-flex items-center gap-1 px-1.5 sm:px-2 py-0.5 rounded-md bg-[#131f28] border border-[#223544] text-slate-100 font-semibold whitespace-nowrap text-[11px] sm:text-xs">
                <Store className="w-3 h-3 text-emerald-400 shrink-0" />
                <span>{offer.store_name}</span>
              </span>

              {offer.category === 'PS5' && (
                <span
                  className={`inline-flex items-center gap-1 px-1.5 sm:px-2 py-0.5 rounded-md text-[10px] font-mono font-bold border whitespace-nowrap ${
                    offer.has_disc_drive
                      ? 'bg-cyan-500/15 border-cyan-500/35 text-cyan-300'
                      : 'bg-emerald-500/15 border-emerald-500/35 text-emerald-300'
                  }`}
                >
                  <Disc className="w-2.5 h-2.5 sm:w-3 sm:h-3 shrink-0" />
                  <span>{offer.has_disc_drive ? 'COM LEITOR' : 'DIGITAL'}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Linha 3: Bloco Principal de Preço com Cupom e Parcelamento */}
        <PriceBreakdown
          finalPrice={offer.final_price}
          originalPrice={offer.original_declared_price}
          priceCard={offer.price_card}
          installmentsText={offer.installments_text}
          couponCode={offer.coupon_code}
          shippingCost={offer.shipping_cost}
          paymentCondition={offer.payment_condition}
          layout="hero"
        />

        {/* Linha 4: Comparação Dupla (Recorde Histórico vs Média 30 Dias) */}
        <div className="grid grid-cols-2 gap-2 sm:gap-2.5">
          <div className="p-2.5 sm:p-3 rounded-xl bg-[#080d11] border border-[#182631] flex flex-col justify-between">
            <span className="text-[10px] text-amber-300/90 font-mono uppercase font-bold flex items-center gap-1 whitespace-nowrap">
              <Award className="w-3 h-3 shrink-0" />
              <span>Recorde Histórico</span>
            </span>
            <p className="text-sm sm:text-base font-extrabold font-mono text-amber-300 mt-1 whitespace-nowrap">
              {formatBRL(offer.min_historical_price)}
            </p>
            <span className="text-[10px] text-slate-400 mt-0.5 font-mono truncate">
              {diffHist && diffHist > 0
                ? `+${formatBRL(diffHist)} vs recorde`
                : 'No recorde histórico!'}
            </span>
          </div>

          <div className="p-2.5 sm:p-3 rounded-xl bg-[#080d11] border border-[#182631] flex flex-col justify-between">
            <div className="flex items-center justify-between gap-1">
              <span className="text-[10px] text-slate-400 font-mono uppercase font-bold whitespace-nowrap">
                Média 30 Dias
              </span>
              <span
                className={`text-[10px] font-mono font-bold inline-flex items-center gap-0.5 whitespace-nowrap ${
                  isBelowAvg ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {isBelowAvg ? (
                  <TrendingDown className="w-3 h-3 shrink-0" />
                ) : (
                  <TrendingUp className="w-3 h-3 shrink-0" />
                )}
                {varPct > 0 ? `+${varPct}%` : `${varPct}%`}
              </span>
            </div>
            <p className="text-sm sm:text-base font-bold font-mono text-slate-200 mt-1 whitespace-nowrap">
              {formatBRL(offer.avg_30d_price)}
            </p>
            <span className="text-[10px] text-slate-400 mt-0.5 font-mono truncate">
              {isBelowAvg ? 'Abaixo da média' : 'Acima da média'}
            </span>
          </div>
        </div>

        {/* Linha 5: Diagnóstico de Confiabilidade */}
        <div
          className={`p-2.5 sm:p-3 rounded-xl border text-xs space-y-1 ${
            offer.is_fake_discount
              ? 'bg-rose-950/25 border-rose-500/40 text-rose-200'
              : offer.is_marketplace || !offer.is_national
              ? 'bg-amber-950/25 border-amber-500/40 text-amber-200'
              : 'bg-[#081312] border-emerald-500/25 text-emerald-200'
          }`}
        >
          <div className="font-bold text-[11px] sm:text-xs leading-snug line-clamp-1" title={offer.reliability_observation}>
            {offer.reliability_observation}
          </div>
          <p className="text-[10px] sm:text-[11px] text-slate-300 leading-relaxed line-clamp-2" title={offer.opportunity_reason}>
            {offer.opportunity_reason}
          </p>
        </div>
      </div>

      {/* Rodapé de Ações */}
      <div className="flex items-center gap-1.5 sm:gap-2 pt-3 mt-3 sm:mt-4 border-t border-[#182631]">
        <a
          href={offer.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 sm:py-2.5 px-2.5 sm:px-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs flex items-center justify-center gap-1.5 transition shadow-md whitespace-nowrap min-w-0"
        >
          <span className="truncate">Abrir na {offer.store_name}</span>
          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
        </a>
        <button
          onClick={onOpenPredictions}
          className="py-2 sm:py-2.5 px-2.5 sm:px-3.5 rounded-xl bg-[#121d26] hover:bg-[#182734] text-slate-200 text-xs font-semibold border border-[#223544] transition whitespace-nowrap"
          title="Ver previsão estatística"
        >
          Estimativa
        </button>
      </div>
    </div>
  );
}

export default function DashboardPage({ data, setActiveTab, onTriggerScan, scanning }) {
  const [filterMode, setFilterMode] = useState('ALL');
  if (!data) return null;
  const { indicators, event_mode, featured_products, top_offers } = data;

  const filteredOffers = (top_offers || []).filter((o) => {
    if (filterMode === 'PS5_ALL') return o.category === 'PS5';
    if (filterMode === 'PS5_DIGITAL') return o.category === 'PS5' && !o.has_disc_drive;
    if (filterMode === 'PS5_DISC') return o.category === 'PS5' && o.has_disc_drive;
    if (filterMode === 'DUALSENSE') return o.category === 'DUALSENSE';
    return true;
  });

  return (
    <div className="space-y-6 sm:space-y-7">
      {/* Banner do Modo de Evento */}
      <EventModeBanner
        eventMode={event_mode}
        indicators={indicators}
        onTriggerScan={onTriggerScan}
        scanning={scanning}
      />

      {/* Os 3 Cards Campeões de Menor Preço Real */}
      <section className="space-y-3 sm:space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-2">
          <h2 className="text-xs sm:text-base font-extrabold text-white uppercase tracking-wide flex items-center gap-2">
            <Award className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400 shrink-0" />
            <span>Menores Preços Reais Encontrados Agora</span>
          </h2>
          <span className="text-[11px] sm:text-xs font-mono text-slate-400">
            Varejistas: KaBuM! • Magalu • Amazon • Fast Shop
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5">
          <LowestPriceHeroCard
            rankLabel="#1"
            categoryBadge="PS5 SLIM DIGITAL"
            accentColor="emerald"
            offer={featured_products.ps5_lowest_digital || featured_products.ps5}
            onOpenHistory={() => setActiveTab('history')}
            onOpenPredictions={() => setActiveTab('predictions')}
          />
          <LowestPriceHeroCard
            rankLabel="#2"
            categoryBadge="PS5 COM LEITOR DE DISCO"
            accentColor="cyan"
            offer={featured_products.ps5_lowest_disc}
            onOpenHistory={() => setActiveTab('history')}
            onOpenPredictions={() => setActiveTab('predictions')}
          />
          <LowestPriceHeroCard
            rankLabel="#3"
            categoryBadge="CONTROLE DUALSENSE"
            accentColor="emerald"
            offer={featured_products.dualsense}
            onOpenHistory={() => setActiveTab('history')}
            onOpenPredictions={() => setActiveTab('predictions')}
          />
        </div>
      </section>

      {/* Ranking Geral pelo Menor Preço */}
      <section className="bg-[#0b1116] border border-[#182631] rounded-2xl overflow-hidden shadow-lg">
        <div className="p-3.5 sm:p-5 border-b border-[#182631] flex flex-col xl:flex-row xl:items-center justify-between gap-3 sm:gap-4">
          <div className="space-y-1">
            <h3 className="font-bold text-white text-xs sm:text-base flex items-center gap-2">
              <Scale className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Ranking Geral pelo Menor Preço — Auditoria de Confiabilidade</span>
            </h3>
            <p className="text-[11px] sm:text-xs text-slate-400">
              Ofertas ordenadas do menor para o maior preço à vista (PIX), com verificação de procedência e histórico.
            </p>
          </div>

          {/* Botões Rápidos de Filtro */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs shrink-0">
            {[
              { id: 'ALL', label: 'Todos' },
              { id: 'PS5_ALL', label: 'Todos PS5' },
              { id: 'PS5_DIGITAL', label: 'PS5 Digital' },
              { id: 'PS5_DISC', label: 'PS5 c/ Leitor' },
              { id: 'DUALSENSE', label: 'DualSense' },
            ].map((btn) => (
              <button
                key={btn.id}
                onClick={() => setFilterMode(btn.id)}
                className={`px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg font-mono text-[11px] sm:text-xs transition border whitespace-nowrap ${
                  filterMode === btn.id
                    ? 'bg-emerald-500 text-slate-950 font-extrabold border-emerald-400'
                    : 'bg-[#080d11] text-slate-300 border-[#182631] hover:border-emerald-500/40'
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>

        {/* Visão Mobile Otimizada para Celular: Cards Verticais Elegantes (md:hidden) */}
        <div className="md:hidden divide-y divide-[#182631]">
          {filteredOffers.map((o) => {
            const diffHist = o.diff_vs_historical_low;
            return (
              <div key={o.id} className="p-3.5 space-y-2.5 bg-[#0b1116] hover:bg-[#101921]/60 transition">
                {/* Linha 1: Loja + Versão + Score */}
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

                {/* Linha 2: Título do Produto */}
                <div className="font-semibold text-slate-100 text-xs leading-snug line-clamp-2">
                  {o.title}
                </div>

                {/* Linha 3: Tags de Versão e Procedência */}
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

                {/* Linha 4: Bloco de Preços no Celular com Cupom e Parcelamento */}
                <PriceBreakdown
                  finalPrice={o.final_price}
                  originalPrice={o.original_declared_price}
                  priceCard={o.price_card}
                  installmentsText={o.installments_text}
                  couponCode={o.coupon_code}
                  shippingCost={o.shipping_cost}
                  paymentCondition={o.payment_condition}
                  layout="compact"
                />

                {/* Linha 5: Observação de Confiabilidade & Botão Abrir */}
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
                    <span className="text-[10px] text-slate-400">
                      Confiabilidade: {o.reliability_score}%
                    </span>
                  </div>
                  <a
                    href={o.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs shrink-0 whitespace-nowrap shadow-sm"
                  >
                    <span>Ver Oferta</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>

        {/* Visão Desktop: Tabela Completa (hidden md:block) - 100% INTACTA PARA PC */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs sm:text-sm">
            <thead>
              <tr className="bg-[#080d11] text-slate-400 font-mono text-[11px] uppercase border-b border-[#182631] whitespace-nowrap">
                <th className="py-3.5 px-4">Produto Novo & Versão</th>
                <th className="py-3.5 px-4">Loja</th>
                <th className="py-3.5 px-4">Menor Preço & Condições</th>
                <th className="py-3.5 px-4">vs Recorde Histórico</th>
                <th className="py-3.5 px-4">Auditoria de Confiabilidade</th>
                <th className="py-3.5 px-4 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#182631]">
              {filteredOffers.map((o) => {
                const diffHist = o.diff_vs_historical_low;
                return (
                  <tr key={o.id} className="hover:bg-[#101921]/80 transition">
                    <td className="py-3.5 px-4 align-middle max-w-md">
                      <div className="font-semibold text-white leading-snug">{o.title}</div>
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
                          • {o.is_national ? 'Nacional Anatel' : 'Versão Importada'}
                        </span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 align-middle whitespace-nowrap">
                      <div className="font-bold text-slate-100">{o.store_name}</div>
                      <div className="text-[11px] text-slate-400">{o.seller_name}</div>
                    </td>

                    <td className="py-3.5 px-4 align-middle whitespace-nowrap min-w-[200px]">
                      <PriceBreakdown
                        finalPrice={o.final_price}
                        originalPrice={o.original_declared_price}
                        priceCard={o.price_card}
                        installmentsText={o.installments_text}
                        couponCode={o.coupon_code}
                        shippingCost={o.shipping_cost}
                        paymentCondition={o.payment_condition}
                        layout="table"
                      />
                    </td>

                    <td className="py-3.5 px-4 align-middle font-mono text-xs whitespace-nowrap">
                      <div className="text-amber-300 font-bold">
                        Recorde: {formatBRL(o.min_historical_price)}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {diffHist && diffHist > 0
                          ? `+${formatBRL(diffHist)} acima`
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
                      <div className="text-[11px] text-slate-400 mt-0.5 font-mono whitespace-nowrap">
                        Confiabilidade: {o.reliability_score}% • Score: {o.opportunity_score}/100
                      </div>
                    </td>

                    <td className="py-3.5 px-4 align-middle text-right whitespace-nowrap">
                      <a
                        href={o.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs transition shadow-sm"
                      >
                        <span>Ver Oferta</span>
                        <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
