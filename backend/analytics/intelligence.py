"""
Módulo INTELIGÊNCIA DO RADAR (Seção 7).
Calcula o Índice de Oportunidade de 0 a 100 baseado nos 10 fatores exigidos:
1. Comparação com a média histórica (0–22 pts)
2. Comparação com o menor preço histórico (0–23 pts)
3. Velocidade da queda (0–8 pts)
4. Diferença entre lojas (0–8 pts)
5. Disponibilidade do produto (bloqueador se sem estoque)
6. Reputação do vendedor / loja (0–12 pts)
7. Custo do frete (0–7 pts)
8. Condições de pagamento (0–6 pts)
9. Cupons disponíveis (0–7 pts)
10. Histórico de promoções / Confiabilidade (0–7 pts)

Regras estritas:
- Classificações:
  * 90 a 100: Oportunidade excepcional
  * 75 a 89: Excelente oportunidade
  * 60 a 74: Boa oportunidade
  * 40 a 59: Preço interessante, mas pode melhorar
  * 0 a 39: Não recomendado no momento
- Não atribui pontuações altas a ofertas sem histórico suficiente (< 3 registros históricos limitam o score máximo a 55).
- Gera explicação em linguagem natural transparente e documentada.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class OpportunityEvaluation:
    score: int  # 0 a 100
    classification: str
    reasoning: str
    worth_buying_now: str  # "SIM, EXCELENTE MOMENTO", "PODE COMPRAR COM SEGURANÇA", "AGUARDAR QUEDA MAIOR", "NÃO RECOMENDADO"
    factors_breakdown: Dict[str, float] = field(default_factory=dict)


def classify_score(score: int) -> str:
    if score >= 90:
        return "Oportunidade excepcional"
    if score >= 75:
        return "Excelente oportunidade"
    if score >= 60:
        return "Boa oportunidade"
    if score >= 40:
        return "Preço interessante, mas pode melhorar"
    return "Não recomendado no momento"


def calculate_opportunity_index(
    final_price: float,
    historical_prices_30d: List[float],
    all_historical_prices: Optional[List[float]] = None,
    other_stores_current_prices: Optional[List[float]] = None,
    previous_price: Optional[float] = None,
    shipping_cost: float = 0.0,
    store_reputation: float = 90.0,
    is_marketplace: bool = False,
    has_official_warranty: bool = True,
    payment_condition: str = "PIX",
    coupon_code: Optional[str] = None,
    coupon_discount: float = 0.0,
    in_stock: bool = True,
    is_fake_discount: bool = False,
    target_price: Optional[float] = None,
    excellent_price: Optional[float] = None,
) -> OpportunityEvaluation:
    """
    Calcula o Índice de Oportunidade (0–100) com regras estatísticas transparentes e auditáveis.
    """
    if not in_stock or final_price <= 0:
        return OpportunityEvaluation(
            score=0,
            classification="Não recomendado no momento",
            reasoning="Produto indisponível (sem estoque) no momento da consulta.",
            worth_buying_now="NÃO RECOMENDADO (SEM ESTOQUE)",
            factors_breakdown={},
        )

    hist_30 = [float(p) for p in historical_prices_30d if p is not None and p > 0]
    hist_all = [float(p) for p in (all_historical_prices or hist_30) if p is not None and p > 0]
    other_stores = [float(p) for p in (other_stores_current_prices or []) if p is not None and p > 0]

    has_sufficient_history = len(hist_all) >= 3

    breakdown: Dict[str, float] = {}
    explanation_parts: List[str] = []

    # 1. Comparação com a média histórica de 30 dias (0 a 22 pts)
    if hist_30:
        avg_30 = sum(hist_30) / len(hist_30)
        diff_avg_pct = ((avg_30 - final_price) / avg_30) * 100.0 if avg_30 > 0 else 0.0
        if diff_avg_pct >= 18.0:
            pts_avg = 22.0
        elif diff_avg_pct >= 0:
            # 8 pts por estar na média + até 14 pts proporcionalmente até 18% de desconto
            pts_avg = 8.0 + (diff_avg_pct / 18.0) * 14.0
        else:
            # Acima da média: perde pontos proporcionalmente
            pts_avg = max(0.0, 8.0 + (diff_avg_pct / 10.0) * 8.0)
        breakdown["vs_media_30d"] = round(pts_avg, 1)

        if diff_avg_pct >= 1.0:
            explanation_parts.append(f"Esta oferta está {diff_avg_pct:.1f}% abaixo da média dos últimos 30 dias (R$ {avg_30:.2f})")
        elif diff_avg_pct <= -1.0:
            explanation_parts.append(f"O valor atual está {abs(diff_avg_pct):.1f}% acima da média dos últimos 30 dias (R$ {avg_30:.2f})")
        else:
            explanation_parts.append(f"O preço está alinhado à média dos últimos 30 dias (R$ {avg_30:.2f})")
    else:
        avg_30 = final_price
        diff_avg_pct = 0.0
        breakdown["vs_media_30d"] = 8.0

    # 2. Comparação com o menor preço histórico (0 a 23 pts)
    if hist_all:
        min_hist = min(hist_all)
        above_min_pct = ((final_price - min_hist) / min_hist) * 100.0 if min_hist > 0 else 0.0
        if final_price <= min_hist * 1.005:
            pts_min = 23.0
            explanation_parts.append(f"atingiu ou superou o menor preço histórico registrado (R$ {min_hist:.2f})")
        elif above_min_pct <= 5.0:
            pts_min = 17.0 + ((5.0 - above_min_pct) / 5.0) * 6.0
            explanation_parts.append(f"está muito próxima ({above_min_pct:.1f}%) do menor preço histórico (R$ {min_hist:.2f})")
        elif above_min_pct <= 15.0:
            pts_min = 6.0 + ((15.0 - above_min_pct) / 10.0) * 11.0
            explanation_parts.append(f"está {above_min_pct:.1f}% acima do mínimo histórico (R$ {min_hist:.2f})")
        else:
            pts_min = max(0.0, 6.0 - ((above_min_pct - 15.0) / 15.0) * 6.0)
            explanation_parts.append(f"está distante ({above_min_pct:.1f}% acima) do menor preço histórico (R$ {min_hist:.2f})")
        breakdown["vs_minimo_historico"] = round(pts_min, 1)
    else:
        min_hist = final_price
        breakdown["vs_minimo_historico"] = 8.0

    # 3. Velocidade da queda (0 a 8 pts)
    ref_prev = previous_price if (previous_price and previous_price > 0) else (hist_30[-2] if len(hist_30) >= 2 else None)
    if ref_prev and ref_prev > final_price:
        drop_speed_pct = ((ref_prev - final_price) / ref_prev) * 100.0
        pts_speed = min(8.0, (drop_speed_pct / 12.0) * 8.0)
        if drop_speed_pct >= 5.0:
            explanation_parts.append(f"Apresentou queda rápida de {drop_speed_pct:.1f}% em relação à consulta anterior.")
    else:
        pts_speed = 2.0
    breakdown["velocidade_queda"] = round(pts_speed, 1)

    # 4. Diferença entre lojas (0 a 8 pts)
    if other_stores:
        avg_competitors = sum(other_stores) / len(other_stores)
        diff_comp_pct = ((avg_competitors - final_price) / avg_competitors) * 100.0 if avg_competitors > 0 else 0.0
        if diff_comp_pct > 0:
            pts_stores = min(8.0, 3.0 + (diff_comp_pct / 10.0) * 5.0)
            if diff_comp_pct >= 4.0:
                explanation_parts.append(f"Custa {diff_comp_pct:.1f}% menos que a média das outras lojas monitoradas.")
        else:
            pts_stores = max(0.0, 3.0 + (diff_comp_pct / 10.0) * 3.0)
    else:
        pts_stores = 4.0
    breakdown["diferenca_entre_lojas"] = round(pts_stores, 1)

    # 5 & 6. Reputação do vendedor e garantia oficial (0 a 12 pts)
    pts_rep = (min(100.0, max(0.0, store_reputation)) / 100.0) * 8.0
    if not is_marketplace:
        pts_rep += 2.0
    if has_official_warranty:
        pts_rep += 2.0
    breakdown["reputacao_vendedor"] = round(pts_rep, 1)
    if store_reputation >= 90 and not is_marketplace:
        explanation_parts.append("Venda direta por loja oficial de alta reputação e com garantia nacional.")
    elif is_marketplace:
        explanation_parts.append("Oferta comercializada via marketplace.")

    # 7. Custo do frete (0 a 7 pts)
    if shipping_cost <= 0.01:
        pts_ship = 7.0
        explanation_parts.append("Frete grátis incluso no valor final.")
    elif shipping_cost <= 30.0:
        pts_ship = 4.5
    elif shipping_cost <= 60.0:
        pts_ship = 2.0
    else:
        pts_ship = 0.0
    breakdown["custo_frete"] = round(pts_ship, 1)

    # 8. Condições de pagamento (0 a 6 pts)
    cond_upper = (payment_condition or "").upper()
    if "10X" in cond_upper or "12X" in cond_upper or ("PIX" in cond_upper and "CART" in cond_upper):
        pts_pay = 6.0
    elif "PIX" in cond_upper or "VISTA" in cond_upper:
        pts_pay = 5.0
    else:
        pts_pay = 3.5
    breakdown["condicao_pagamento"] = round(pts_pay, 1)

    # 9. Cupons disponíveis (0 a 7 pts)
    if coupon_code or coupon_discount > 0:
        pts_coupon = 7.0
        explanation_parts.append(f"Cupom ativo ({coupon_code or 'Aplicado'}) reduzindo o preço final.")
    else:
        pts_coupon = 2.5
    breakdown["cupons_disponiveis"] = round(pts_coupon, 1)

    # 10. Histórico de promoções e Confiabilidade (0 a 7 pts)
    if is_fake_discount:
        pts_promo = 0.0
    else:
        # Verificar em que percentil histórico o preço atual se encontra
        lower_or_equal = sum(1 for p in hist_all if p >= final_price)
        percentile_goodness = (lower_or_equal / len(hist_all)) if hist_all else 0.5
        pts_promo = round(percentile_goodness * 7.0, 1)
    breakdown["historico_promocoes"] = pts_promo

    raw_score = sum(breakdown.values())

    # Bônus se atingiu preço-alvo ou preço excelente configurado pelo usuário
    if excellent_price and final_price <= excellent_price:
        raw_score = max(raw_score, 92.0)
        explanation_parts.append(f"Atingiu sua meta de Preço Excelente (R$ {excellent_price:.2f})!")
    elif target_price and final_price <= target_price:
        raw_score = max(raw_score, 80.0)
        explanation_parts.append(f"Atingiu seu Preço-Alvo configurado (R$ {target_price:.2f}).")

    # Penalidade severa para falso desconto
    if is_fake_discount:
        raw_score = min(raw_score * 0.45, 35.0)
        explanation_parts.append("ALERTA: Suspeita de falso desconto detectada — pontuação reduzida por segurança.")

    # Regra estrita da Seção 7: Não atribuir pontuações altas a ofertas sem histórico suficiente
    if not has_sufficient_history:
        raw_score = min(raw_score, 55.0)
        explanation_parts.append(
            f"Histórico ainda em formação ({len(hist_all)} registro(s)); pontuação limitada a 55 até acumular base histórica."
        )

    final_score = int(round(max(0.0, min(100.0, raw_score))))
    classification = classify_score(final_score)

    # Indicador "Vale a pena comprar agora?" (Seção 12)
    if is_fake_discount or final_score < 40:
        worth_now = "NÃO RECOMENDADO NO MOMENTO"
    elif final_score >= 90:
        worth_now = "SIM! OPORTUNIDADE EXCEPCIONAL DE COMPRA"
    elif final_score >= 75:
        worth_now = "SIM! EXCELENTE MOMENTO PARA COMPRAR"
    elif final_score >= 60:
        worth_now = "BOA OFERTA — COMPRA SEGURA SE TIVER PRESSA"
    else:
        worth_now = "AGUARDAR — PREÇO PODE MELHORAR NA BLACK FRIDAY"

    # Formatar texto fluido como no exemplo da Seção 7
    if len(explanation_parts) >= 2:
        first_sentence = f"{explanation_parts[0]} e {explanation_parts[1]}."
        rest = " ".join(explanation_parts[2:])
        full_reason = f"{first_sentence} {rest} Classificação: {classification} ({final_score}/100).".strip()
    elif explanation_parts:
        full_reason = f"{explanation_parts[0]}. Classificação: {classification} ({final_score}/100)."
    else:
        full_reason = f"Classificação: {classification} ({final_score}/100)."

    return OpportunityEvaluation(
        score=final_score,
        classification=classification,
        reasoning=full_reason,
        worth_buying_now=worth_now,
        factors_breakdown=breakdown,
    )
