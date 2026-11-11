import React from 'react';
import { formatBRL } from '../services/api';
import CouponBadge from './CouponBadge';
import { CreditCard, Sparkles, Tag } from 'lucide-react';

export default function PriceBreakdown({
  finalPrice,
  originalPrice,
  priceCard,
  installmentsText,
  couponCode,
  shippingCost = 0,
  paymentCondition,
  layout = 'compact',
}) {
  const hasCoupon = Boolean(couponCode);
  const showWithoutCoupon =
    originalPrice && originalPrice > finalPrice && (hasCoupon || originalPrice - finalPrice > 20);
  const savings = showWithoutCoupon ? originalPrice - finalPrice : 0;

  // Cálculo de parcelamento padrão caso não venha installmentsText
  const cardValue = priceCard || finalPrice;
  const installmentsFallback = `ou 10x de ${formatBRL(cardValue / 10)} sem juros`;
  const effectiveInstallments = installmentsText || installmentsFallback;

  if (layout === 'hero') {
    return (
      <div className="space-y-3">
        {/* Bloco de Cupom Ativo em Destaque */}
        {hasCoupon && (
          <div className="p-2.5 sm:p-3 rounded-xl bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-transparent border border-amber-500/30 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400" />
              </span>
              <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-amber-400" />
                <span>Cupom obrigatório para este preço:</span>
              </span>
            </div>
            <CouponBadge couponCode={couponCode} size="default" />
          </div>
        )}

        {/* Linha de Preços: Com Cupom vs Sem Cupom vs Cartão */}
        <div className="p-3.5 rounded-xl bg-[#080d11] border border-[#182631] space-y-2.5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <span className="text-[10px] font-mono uppercase text-slate-400 font-bold block">
                {hasCoupon ? 'Preço com Cupom Aplicado (PIX)' : 'Preço à Vista (PIX)'}
              </span>
              <div className="text-2xl sm:text-3xl font-extrabold font-mono text-emerald-400 tracking-tight flex items-baseline gap-2">
                <span>{formatBRL(finalPrice)}</span>
                {hasCoupon && (
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                    C/ CUPOM
                  </span>
                )}
              </div>
            </div>

            {showWithoutCoupon && (
              <div className="text-right">
                <span className="text-[10px] font-mono uppercase text-slate-400 block">
                  Sem cupom / Preço original
                </span>
                <div className="text-sm sm:text-base font-bold font-mono text-slate-400 line-through">
                  {formatBRL(originalPrice)}
                </div>
                <div className="text-[11px] font-bold text-emerald-400 flex items-center justify-end gap-1">
                  <Sparkles className="w-3 h-3 text-emerald-400 shrink-0" />
                  <span>Economia de {formatBRL(savings)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Linha de Parcelamento no Cartão */}
          <div className="pt-2 border-t border-[#182631] flex flex-wrap items-center justify-between gap-2 text-xs text-slate-300">
            <div className="flex items-center gap-1.5 font-mono">
              <CreditCard className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="font-semibold text-slate-200">Parcelado:</span>
              <span className="text-slate-300">{effectiveInstallments}</span>
            </div>
            {priceCard && (
              <span className="text-[11px] font-mono text-slate-400">
                (Total no cartão: {formatBRL(priceCard)})
              </span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Layout para Tabelas Desktop
  if (layout === 'table') {
    return (
      <div className="space-y-1.5 font-mono">
        {/* Preço à vista principal */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-base sm:text-lg font-extrabold text-emerald-400">
            {formatBRL(finalPrice)}
          </span>
          <span className="text-[10px] text-slate-400 uppercase font-bold">PIX</span>
        </div>

        {/* Preço sem cupom riscado se houver */}
        {showWithoutCoupon && (
          <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
            <span className="line-through">{formatBRL(originalPrice)}</span>
            <span className="text-emerald-400 text-[10px] font-bold font-sans">
              (-{formatBRL(savings)})
            </span>
          </div>
        )}

        {/* Cupom copiável */}
        {hasCoupon && (
          <div className="pt-0.5">
            <CouponBadge couponCode={couponCode} size="sm" />
          </div>
        )}

        {/* Parcelado no Cartão */}
        <div className="text-[10px] text-slate-400 flex items-center gap-1 pt-0.5">
          <CreditCard className="w-3 h-3 text-cyan-400 shrink-0" />
          <span className="truncate" title={effectiveInstallments}>
            {effectiveInstallments}
          </span>
        </div>
      </div>
    );
  }

  // Layout Compacto (Cards Mobile / Grids)
  return (
    <div className="space-y-2 p-2.5 rounded-xl bg-[#080d11] border border-[#182631]">
      {/* Bloco de Cupom no topo do card se houver */}
      {hasCoupon && (
        <div className="flex items-center justify-between gap-1 pb-1.5 border-b border-[#182631]">
          <span className="text-[10px] font-bold text-amber-300 flex items-center gap-1">
            <Tag className="w-3 h-3 text-amber-400 shrink-0" />
            <span>Use o cupom:</span>
          </span>
          <CouponBadge couponCode={couponCode} size="sm" />
        </div>
      )}

      <div className="flex items-baseline justify-between gap-2">
        <div>
          <span className="text-[10px] font-mono uppercase text-slate-400 block font-semibold">
            {hasCoupon ? 'Preço c/ Cupom (PIX)' : 'Preço à Vista (PIX)'}
          </span>
          <div className="text-lg font-black font-mono text-emerald-400">
            {formatBRL(finalPrice)}
          </div>
        </div>

        {showWithoutCoupon && (
          <div className="text-right">
            <span className="text-[10px] font-mono uppercase text-slate-400 block">Sem cupom</span>
            <div className="text-xs font-mono text-slate-400 line-through">
              {formatBRL(originalPrice)}
            </div>
            <div className="text-[10px] font-bold text-emerald-400">
              Economize {formatBRL(savings)}
            </div>
          </div>
        )}
      </div>

      {/* Parcelamento */}
      <div className="text-[10px] font-mono text-slate-300 pt-1 border-t border-[#141f27] flex items-center gap-1">
        <CreditCard className="w-3 h-3 text-cyan-400 shrink-0" />
        <span className="truncate">{effectiveInstallments}</span>
      </div>
    </div>
  );
}
