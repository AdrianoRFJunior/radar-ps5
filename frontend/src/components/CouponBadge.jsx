import React, { useState } from 'react';
import { Ticket, Copy, Check } from 'lucide-react';

export default function CouponBadge({ couponCode, size = 'default' }) {
  const [copied, setCopied] = useState(false);

  if (!couponCode) return null;

  const handleCopy = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(couponCode);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = couponCode;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        textArea.remove();
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Erro ao copiar cupom:', err);
    }
  };

  const isSmall = size === 'sm';

  return (
    <div
      onClick={handleCopy}
      role="button"
      tabIndex={0}
      title="Clique para copiar o cupom de desconto"
      className={`inline-flex items-center gap-1.5 rounded-lg border border-dashed cursor-pointer transition select-none group shadow-sm ${
        copied
          ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300 shadow-emerald-950/40'
          : 'bg-amber-500/15 border-amber-400/50 text-amber-300 hover:bg-amber-500/25 hover:border-amber-400'
      } ${isSmall ? 'px-2 py-0.5 text-[11px]' : 'px-3 py-1.5 text-xs'}`}
    >
      <Ticket className={`${isSmall ? 'w-3 h-3' : 'w-3.5 h-3.5'} shrink-0 ${copied ? 'text-emerald-400' : 'text-amber-400 animate-pulse'}`} />
      
      <span className="font-mono font-black tracking-wider uppercase">
        {couponCode}
      </span>

      <span
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-bold text-[10px] uppercase font-mono transition ml-0.5 ${
          copied
            ? 'bg-emerald-500 text-slate-950 font-black'
            : 'bg-amber-400/20 text-amber-200 group-hover:bg-amber-400 group-hover:text-slate-950'
        }`}
      >
        {copied ? (
          <>
            <Check className="w-2.5 h-2.5 shrink-0 stroke-[3]" />
            <span>Copiado!</span>
          </>
        ) : (
          <>
            <Copy className="w-2.5 h-2.5 shrink-0" />
            <span>Copiar</span>
          </>
        )}
      </span>
    </div>
  );
}
