"""
Módulo de Detecção de Falsos Descontos (Seção 10).
Identifica práticas como "metade do dobro":
1. Aumento recente antes da promoção (inflação artificial pré-desconto).
2. Preço promocional superior à média histórica.
3. Desconto calculado sobre preço de referência ("De:") suspeito.
4. Ofertas com valores muito diferentes do mercado (anomalia extrema ou sobrepreço).
5. Produtos com descrição ou versão divergente (ex: PS5 Fat/Usado anunciado como oportunidade de Slim).

Nunca considera o percentual de desconto anunciado pela loja como prova de economia real.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FakeDiscountEvaluation:
    is_fake_discount: bool
    reliability_score: int  # 0 a 100
    reliability_label: str  # "Alta Confiabilidade", "Confiabilidade Moderada", "Suspeita de Falso Desconto", "Baixa Confiabilidade"
    declared_discount_pct: Optional[float]
    real_discount_vs_avg_pct: Optional[float]
    reasons: List[str] = field(default_factory=list)

    @property
    def summary_reason(self) -> Optional[str]:
        if not self.reasons:
            return None
        return " | ".join(self.reasons)


def evaluate_fake_discount(
    current_final_price: float,
    original_declared_price: Optional[float],
    historical_prices: List[float],
    store_reputation: float = 90.0,
    is_marketplace: bool = False,
    has_official_warranty: bool = True,
    is_national: bool = True,
    title: str = "",
    expected_category: str = "PS5",
) -> FakeDiscountEvaluation:
    """
    Analisa uma oferta em busca de indícios de falso desconto ou baixa confiabilidade.
    """
    reasons: List[str] = []
    is_fake = False
    reliability = int(min(100, max(30, store_reputation)))

    if is_marketplace:
        reliability -= 8
    if not has_official_warranty:
        reliability -= 18
        reasons.append("Produto sem confirmação de garantia oficial Sony Brasil.")
    if not is_national:
        reliability -= 10
        reasons.append("Produto importado ou recondicionado/seminovo.")

    declared_discount_pct: Optional[float] = None
    if original_declared_price and original_declared_price > current_final_price:
        declared_discount_pct = round(
            ((original_declared_price - current_final_price) / original_declared_price) * 100.0, 1
        )

    clean_hist = [float(p) for p in historical_prices if p is not None and p > 0]
    real_discount_vs_avg_pct: Optional[float] = None

    if len(clean_hist) >= 2:
        avg_hist = sum(clean_hist) / len(clean_hist)
        max_hist = max(clean_hist)
        min_hist = min(clean_hist)

        if avg_hist > 0:
            # Positivo = economia real abaixo da média; Negativo = acima da média
            real_discount_vs_avg_pct = round(((avg_hist - current_final_price) / avg_hist) * 100.0, 2)

        # Regra 1: Aumento recente antes da promoção ("metade do dobro")
        # Ex: preço base era R$ 2.500, subiu para R$ 3.200 recentemente e caiu para R$ 2.560 dizendo ter 20% off
        if len(clean_hist) >= 3:
            baseline_prices = clean_hist[:-2]
            recent_peak = max(clean_hist[-2:])
            baseline_avg = sum(baseline_prices) / len(baseline_prices)
            if baseline_avg > 0 and recent_peak >= baseline_avg * 1.10:
                # Houve pico recente > 10% acima da linha de base
                if current_final_price >= baseline_avg * 0.97:
                    is_fake = True
                    reliability -= 35
                    reasons.append(
                        f"Aumento recente artificial detectado: o preço subiu para R$ {recent_peak:.2f} "
                        f"(média anterior R$ {baseline_avg:.2f}) antes de anunciar a queda atual para R$ {current_final_price:.2f}."
                    )

        # Regra 2: Loja anuncia "desconto" agressivo sobre original_declared_price, mas preço atual é superior à média histórica
        if declared_discount_pct and declared_discount_pct >= 15.0 and current_final_price > avg_hist * 1.08:
            is_fake = True
            reliability -= 30
            reasons.append(
                f"Preço promocional anunciado ({declared_discount_pct}% OFF) de R$ {current_final_price:.2f} "
                f"é superior à média histórica real de R$ {avg_hist:.2f}."
            )

        # Regra 3: Desconto calculado sobre preço de referência ("De:") suspeito/inflado
        ref_ceiling = max(max_hist * 1.15, 5799.0 if expected_category == "PS5" else 620.0)
        if original_declared_price and original_declared_price > ref_ceiling:
            is_fake = True
            reliability -= 25
            reasons.append(
                f"Preço de referência 'De: R$ {original_declared_price:.2f}' é suspeito e excede o teto "
                f"normal praticado no mercado (R$ {max_hist:.2f})."
            )

        # Regra 4: Oferta com valor muito diferente do mercado / Sobrepreço
        if current_final_price > avg_hist * 1.18:
            is_fake = True
            reliability -= 30
            reasons.append(
                f"Preço muito acima do praticado no mercado (+{abs(real_discount_vs_avg_pct or 0):.1f}% sobre a média histórica de R$ {avg_hist:.2f}) — não é uma promoção real."
            )
        elif current_final_price < min_hist * 0.55 and is_marketplace:
            is_fake = True
            reliability -= 45
            reasons.append(
                "Preço excessivamente abaixo do mercado em vendedor de marketplace — alto risco de anúncio incorreto ou fraude."
            )

    else:
        # Sem histórico suficiente, verificar se o preço "De:" é irrealista para a categoria
        if expected_category == "PS5" and original_declared_price and original_declared_price > 4699.0:
            is_fake = True
            reliability -= 25
            reasons.append(
                f"Preço 'De: R$ {original_declared_price:.2f}' inflado acima do preço sugerido oficial para PS5 Slim Digital."
            )
        elif expected_category == "DUALSENSE" and original_declared_price and original_declared_price > 649.0:
            is_fake = True
            reliability -= 25
            reasons.append(
                f"Preço 'De: R$ {original_declared_price:.2f}' inflado para controle DualSense."
            )

    # Regra 5: Divergência de versão ou condição na descrição
    t_lower = title.lower()
    if any(w in t_lower for w in ["mostruário", "mostruario", "vitrine", "open box", "recondicionado", "caixa danificada"]):
        reliability -= 20
        reasons.append("Atenção: descrição indica produto de vitrine/open box/recondicionado.")

    reliability = max(0, min(100, reliability))

    if is_fake:
        label = "Suspeita de Falso Desconto"
    elif reliability >= 85:
        label = "Alta Confiabilidade"
    elif reliability >= 65:
        label = "Confiabilidade Moderada"
    else:
        label = "Baixa Confiabilidade"

    return FakeDiscountEvaluation(
        is_fake_discount=is_fake,
        reliability_score=reliability,
        reliability_label=label,
        declared_discount_pct=declared_discount_pct,
        real_discount_vs_avg_pct=real_discount_vs_avg_pct,
        reasons=reasons,
    )
