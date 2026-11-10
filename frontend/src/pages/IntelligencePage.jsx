import React, { useEffect, useState } from 'react';
import {
  BrainCircuit,
  ShieldAlert,
  ShieldCheck,
  ExternalLink,
  CheckCircle2,
  AlertOctagon,
} from 'lucide-react';
import { radarApi, formatBRL, getScoreBadgeStyle } from '../services/api';

export default function IntelligencePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    radarApi
      .getIntelligence()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading && !data) {
    return <div className="text-slate-400 text-sm">Carregando Inteligência do Radar...</div>;
  }

  const { methodology, offers_ranked, fake_discounts_detected } = data || {};

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-extrabold text-white flex items-center gap-2">
          <BrainCircuit className="w-6 h-6 text-emerald-400" />
          5. Inteligência do Radar (Índice 0–100) & Detecção de Falsos Descontos
        </h2>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Avaliação multi-fatorial transparente baseada em 10 critérios estatísticos e auditoria anti-fraude ("metade do dobro").
        </p>
      </div>

      {/* Escala Oficial e Pesos Documentados (Seção 7) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-white text-sm">Escala de Classificação de Oportunidade</h3>
          <div className="space-y-2 text-xs">
            {(methodology?.scale || []).map((s, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 rounded-lg bg-[#080d11] border border-[#1c2d38]"
              >
                <span className="font-mono font-bold" style={{ color: s.color }}>
                  {s.range} pontos
                </span>
                <span className="font-semibold text-slate-200">{s.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 space-y-3">
          <h3 className="font-bold text-white text-sm">
            Pesos Estatísticos Auditáveis (10 Fatores) & Travas de Segurança
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {Object.entries(methodology?.factors_weights || {}).map(([k, v]) => (
              <div
                key={k}
                className="flex items-center justify-between px-3 py-1.5 rounded bg-[#080d11] border border-[#1c2d38]"
              >
                <span className="text-slate-300 truncate pr-2">{k}</span>
                <span className="font-mono font-bold text-emerald-400">{v} pts</span>
              </div>
            ))}
          </div>
          <ul className="text-[11px] text-slate-400 space-y-1 pt-2 border-t border-[#1c2d38]">
            {(methodology?.safety_rules || []).map((r, i) => (
              <li key={i} className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Seção 10: Detecção de Falsos Descontos ("Metade do Dobro") */}
      <section className="bg-rose-950/20 border border-rose-500/40 rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 text-rose-300">
          <AlertOctagon className="w-5 h-5 text-rose-400" />
          <h3 className="font-bold text-base">
            Radar Anti-Fraude: Ofertas com Suspeita de Falso Desconto Detectadas ({fake_discounts_detected?.length || 0})
          </h3>
        </div>
        <p className="text-xs text-slate-300">
          O sistema jamais considera o desconto anunciado pela loja ("De/Por") como economia real. Abaixo estão ofertas onde o preço foi inflado antes da promoção ou o valor de referência é incompatível com o histórico:
        </p>

        <div className="space-y-3">
          {(fake_discounts_detected || []).map((f) => (
            <div
              key={f.id}
              className="bg-[#0d141a] border border-rose-500/40 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono text-xs font-bold">
                    SUSPEITA DE FALSO DESCONTO • Confiabilidade {f.reliability_score}%
                  </span>
                  <span className="text-xs text-slate-400">
                    {f.store_name} ({f.seller_name})
                  </span>
                </div>
                <h4 className="font-bold text-white text-sm">{f.title}</h4>
                <p className="text-xs text-rose-300 font-medium">{f.fake_discount_reason}</p>
                <div className="text-[11px] font-mono text-slate-400">
                  Preço "De:" Declarado: {formatBRL(f.original_declared_price)} | Preço Final Cobrado:{' '}
                  <strong className="text-white">{formatBRL(f.final_price)}</strong> | Média 30d Real:{' '}
                  {formatBRL(f.avg_30d_price)}
                </div>
              </div>
              <div className="shrink-0 flex flex-col items-end gap-2">
                <span className="px-3 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 font-mono text-xs font-bold">
                  Score Travado: {f.opportunity_score}/100
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Análise Individual Explicada de Todas as Ofertas */}
      <section className="space-y-4">
        <h3 className="font-bold text-white text-base">
          Diagnóstico Completo de Oportunidades (Justificativa Estatística por Oferta)
        </h3>
        <div className="space-y-4">
          {(offers_ranked || []).map((o) => (
            <div
              key={o.id}
              className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4"
            >
              <div className="space-y-2 max-w-4xl">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-mono font-bold border ${getScoreBadgeStyle(
                      o.opportunity_score
                    )}`}
                  >
                    ÍNDICE {o.opportunity_score}/100 — {o.opportunity_level.toUpperCase()}
                  </span>
                  <span className="px-2.5 py-0.5 rounded bg-[#142029] text-slate-300 text-xs font-mono">
                    {o.store_name}
                  </span>
                  {o.is_fake_discount ? (
                    <span className="inline-flex items-center gap-1 text-rose-400 text-xs font-bold">
                      <ShieldAlert className="w-4 h-4" /> {o.reliability_label}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
                      <ShieldCheck className="w-4 h-4" /> {o.reliability_label} ({o.reliability_score}%)
                    </span>
                  )}
                </div>

                <h4 className="font-bold text-white text-base">{o.title}</h4>

                {/* Motivo detalhado da classificação conforme exemplo da Seção 7 */}
                <div className="p-3 rounded-lg bg-[#080d11] border border-[#1c2d38] text-xs text-slate-200 leading-relaxed">
                  <strong className="text-emerald-400">Parecer do Radar: </strong>
                  "{o.opportunity_reason}"
                </div>
              </div>

              <div className="flex lg:flex-col items-end justify-between w-full lg:w-auto gap-3 shrink-0 border-t lg:border-t-0 pt-3 lg:pt-0 border-[#1c2d38]">
                <div className="text-right">
                  <span className="text-[11px] text-slate-400 block">Preço Final c/ Frete</span>
                  <span className="text-2xl font-extrabold font-mono text-emerald-400">
                    {formatBRL(o.final_price)}
                  </span>
                </div>
                <a
                  href={o.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs inline-flex items-center gap-1.5"
                >
                  <span>Abrir Oferta</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
