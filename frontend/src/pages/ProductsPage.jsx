import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  AlertCircle,
  ExternalLink,
  PlusCircle,
  PackageCheck,
  Layers,
} from 'lucide-react';
import { radarApi, formatBRL, getScoreBadgeStyle } from '../services/api';

export default function ProductsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualForm, setManualForm] = useState({
    store_slug: 'amazon-br',
    title: 'Console Sony PlayStation 5 Slim Digital Edition 1TB CFI-2014B',
    url: 'https://www.amazon.com.br',
    price_cash: '',
    price_card: '',
    original_declared_price: '',
    shipping_cost: '0',
    coupon_code: '',
    coupon_discount: '0',
    payment_condition: 'PIX à vista',
    seller_name: 'Loja Oficial',
    is_marketplace: false,
  });
  const [submitStatus, setSubmitStatus] = useState(null);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const res = await radarApi.getProducts();
      setData(res);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setSubmitStatus(null);
    try {
      await radarApi.registerManualOffer({
        ...manualForm,
        price_cash: Number(manualForm.price_cash),
        price_card: manualForm.price_card ? Number(manualForm.price_card) : null,
        original_declared_price: manualForm.original_declared_price
          ? Number(manualForm.original_declared_price)
          : null,
        shipping_cost: Number(manualForm.shipping_cost || 0),
        coupon_discount: Number(manualForm.coupon_discount || 0),
        coupon_code: manualForm.coupon_code || null,
      });
      setSubmitStatus({ type: 'success', text: 'Oferta registrada e analisada pelo Radar!' });
      setShowManualModal(false);
      loadProducts();
    } catch (err) {
      setSubmitStatus({ type: 'error', text: err.message });
    }
  };

  if (loading && !data) {
    return <div className="text-slate-400 text-sm">Carregando produtos monitorados...</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-white">
            2. Produtos Monitorados & Separação Estrita de Versões
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            O RADAR BF 2026 separa rigorosamente o PS5 Slim Digital de versões Fat, Pro ou com Leitor de Disco,
            bem como diferencia controles DualSense oficiais Sony de controles paralelos.
          </p>
        </div>
        <button
          onClick={() => setShowManualModal(!showManualModal)}
          className="px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-2"
        >
          <PlusCircle className="w-4 h-4" />
          Registrar Oferta Manual / Flash Deal
        </button>
      </div>

      {submitStatus && (
        <div
          className={`p-3.5 rounded-xl border text-xs font-medium ${
            submitStatus.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
          }`}
        >
          {submitStatus.text}
        </div>
      )}

      {/* Formulário opcional para inserir oferta avulsa */}
      {showManualModal && (
        <form
          onSubmit={handleManualSubmit}
          className="bg-[#0d141a] border border-emerald-500/40 rounded-xl p-5 space-y-4"
        >
          <h3 className="font-bold text-white text-sm">
            Testar / Inserir Oferta Manualmente no Classificador do Radar
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <label className="block text-slate-400 mb-1">Loja</label>
              <select
                value={manualForm.store_slug}
                onChange={(e) => setManualForm({ ...manualForm, store_slug: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white"
              >
                <option value="amazon-br">Amazon Brasil</option>
                <option value="mercado-livre">Mercado Livre</option>
                <option value="kabum">KaBuM!</option>
                <option value="magazine-luiza">Magazine Luiza</option>
                <option value="fast-shop">Fast Shop</option>
                <option value="casas-bahia">Casas Bahia</option>
                <option value="ponto">Ponto</option>
                <option value="carrefour">Carrefour</option>
                <option value="promobit">Promobit</option>
                <option value="pelando">Pelando</option>
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="block text-slate-400 mb-1">
                Título Completo do Produto (O classificador detectará edição, revisão e oficialidade)
              </label>
              <input
                type="text"
                required
                value={manualForm.title}
                onChange={(e) => setManualForm({ ...manualForm, title: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Preço à Vista / PIX (R$)</label>
              <input
                type="number"
                step="0.01"
                required
                value={manualForm.price_cash}
                onChange={(e) => setManualForm({ ...manualForm, price_cash: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Frete (R$)</label>
              <input
                type="number"
                step="0.01"
                value={manualForm.shipping_cost}
                onChange={(e) => setManualForm({ ...manualForm, shipping_cost: e.target.value })}
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-400 mb-1">Preço "De:" Declarado (Opcional)</label>
              <input
                type="number"
                step="0.01"
                value={manualForm.original_declared_price}
                onChange={(e) =>
                  setManualForm({ ...manualForm, original_declared_price: e.target.value })
                }
                className="w-full bg-[#080d11] border border-[#1c2d38] rounded-lg px-3 py-2 text-white"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowManualModal(false)}
              className="px-4 py-2 rounded-lg bg-[#15222c] text-slate-300 text-xs"
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-emerald-500 text-slate-950 font-bold text-xs"
            >
              Classificar e Salvar Oferta
            </button>
          </div>
        </form>
      )}

      {/* CATEGORIA A — PLAYSTATION 5 SLIM DIGITAL (PRIORITÁRIO) */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 border-b border-[#1c2d38] pb-2">
          <PackageCheck className="w-5 h-5 text-emerald-400" />
          <h3 className="font-bold text-base text-white">
            PRODUTO A — Sony PlayStation 5 Slim Digital Edition (Console Puro, Bundles com Jogos e Controle Extra)
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(data?.ps5_priority_offers || []).map((o) => (
            <div
              key={o.id}
              className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 flex flex-col justify-between gap-4"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="px-2.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-mono text-xs font-semibold">
                    {o.edition_type} • Rev: {o.model_revision || 'CFI-2014B'}
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold border ${getScoreBadgeStyle(
                      o.opportunity_score
                    )}`}
                  >
                    Score {o.opportunity_score}/100
                  </span>
                </div>
                <h4 className="font-bold text-white text-sm sm:text-base">{o.title}</h4>
                <div className="flex flex-wrap gap-2 mt-2 text-xs text-slate-300">
                  <span className="px-2 py-0.5 rounded bg-[#142029]">Loja: {o.store_name}</span>
                  <span className="px-2 py-0.5 rounded bg-[#142029]">
                    Vendedor: {o.seller_name} ({o.is_marketplace ? 'Marketplace' : 'Venda Direta 1P'})
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#142029] text-emerald-400 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    {o.is_national ? 'Nacional Anatel' : 'Importado'} •{' '}
                    {o.has_official_warranty ? 'Garantia Oficial Sony' : 'Garantia Loja'}
                  </span>
                </div>
              </div>

              <div className="flex items-end justify-between border-t border-[#1c2d38] pt-3">
                <div>
                  <span className="text-[11px] text-slate-400 block">
                    Preço Final (À vista {formatBRL(o.price_cash)} + Frete {formatBRL(o.shipping_cost)}
                    {o.coupon_discount > 0 ? ` - Cupom ${formatBRL(o.coupon_discount)}` : ''})
                  </span>
                  <span className="text-xl font-extrabold font-mono text-emerald-400">
                    {formatBRL(o.final_price)}
                  </span>
                </div>
                <a
                  href={o.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs inline-flex items-center gap-1.5"
                >
                  <span>Ver na Loja</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CATEGORIA B — CONTROLE SONY DUALSENSE OFICIAL */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 border-b border-[#1c2d38] pb-2">
          <Layers className="w-5 h-5 text-emerald-400" />
          <h3 className="font-bold text-base text-white">
            PRODUTO B — Controle Sem Fio Sony DualSense Oficial (Branco, Preto, Cores e Edições Especiais)
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(data?.dualsense_priority_offers || []).map((o) => (
            <div
              key={o.id}
              className="bg-[#0d141a] border border-[#1c2d38] rounded-xl p-5 flex flex-col justify-between gap-4"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="px-2.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 font-mono text-xs font-semibold">
                    Cor: {o.color} • Oficial Sony
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold border ${getScoreBadgeStyle(
                      o.opportunity_score
                    )}`}
                  >
                    Score {o.opportunity_score}/100
                  </span>
                </div>
                <h4 className="font-bold text-white text-sm sm:text-base">{o.title}</h4>
                <p className="text-xs text-slate-400 mt-1">
                  {o.store_name} ({o.seller_name}) • {o.payment_condition}
                </p>
              </div>

              <div className="flex items-end justify-between border-t border-[#1c2d38] pt-3">
                <div>
                  <span className="text-[11px] text-slate-400 block">Preço Final c/ Frete</span>
                  <span className="text-xl font-extrabold font-mono text-emerald-400">
                    {formatBRL(o.final_price)}
                  </span>
                </div>
                <a
                  href={o.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs inline-flex items-center gap-1.5"
                >
                  <span>Ver na Loja</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ÁREA DE OPORTUNIDADES ALTERNATIVAS (Isoladas conforme Seção 2) */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 border-b border-amber-500/30 pb-2">
          <AlertCircle className="w-5 h-5 text-amber-400" />
          <div>
            <h3 className="font-bold text-base text-amber-300">
              Área de Oportunidades Alternativas (Isoladas do Produto Principal)
            </h3>
            <p className="text-xs text-slate-400">
              Contém PS5 Slim com Leitor de Disco, PS5 Pro, PS5 Fat e Controles Paralelos/Similares. Estes itens
              não entram no cálculo de média ou menor preço do PS5 Slim Digital ou DualSense Oficial.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(data?.alternative_opportunities || []).map((o) => (
            <div
              key={o.id}
              className="bg-[#0d141a]/70 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between gap-4"
            >
              <div>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono text-[11px] font-bold">
                  ALTERNATIVO: {o.edition_type} {o.is_official ? '(Oficial Sony)' : '(PARALELO / SIMILAR)'}
                </span>
                <h4 className="font-semibold text-white text-sm mt-1.5">{o.title}</h4>
                <p className="text-xs text-slate-400 mt-0.5">
                  {o.store_name} • Preço Final: <strong className="text-amber-300">{formatBRL(o.final_price)}</strong>
                </p>
              </div>
              <a
                href={o.url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-lg bg-[#15222c] hover:bg-[#1c2d3a] text-slate-200 text-xs font-medium shrink-0"
              >
                Consultar
              </a>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
