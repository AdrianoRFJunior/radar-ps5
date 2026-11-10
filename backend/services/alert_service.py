"""
Serviço de Alertas Internos (Seção 11).
Gera e gerencia alertas internos exibidos exclusivamente dentro do dashboard:
- "Excelente oportunidade encontrada para PS5 Slim Digital."
- "DualSense atingiu o menor preço registrado nos últimos 90 dias."
- "Preço do PS5 caiu X% em relação à última consulta."
- "Possível falso desconto identificado."
- "Meta de preço-alvo atingida."
Evita alertas duplicados consecutivos para o mesmo evento e preço.
"""
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.models import Alert, Offer, Product, Store


def create_internal_alert_if_needed(
    db: Session,
    offer: Offer,
    product: Product,
    store: Store,
    min_hist_90d: Optional[float],
    avg_hist_30d: Optional[float],
    previous_price: Optional[float],
) -> list[Alert]:
    """
    Avalia a oferta recém-atualizada e gera alertas internos relevantes sem duplicar alertas idênticos.
    """
    created_alerts: list[Alert] = []

    def _already_exists(alert_type: str, price_val: float) -> bool:
        existing_list = (
            db.query(Alert)
            .filter(
                Alert.offer_id == offer.id,
                Alert.alert_type == alert_type,
            )
            .order_by(Alert.created_at.desc())
            .limit(20)
            .all()
        )
        for existing in existing_list:
            if abs(existing.price - price_val) < 5.0:
                return True
        return False

    hist_comp_text = (
        f"Média 30d: R$ {avg_hist_30d:.2f} | Mínimo 90d: R$ {min_hist_90d:.2f}"
        if (avg_hist_30d and min_hist_90d)
        else "Comparado à série histórica monitorada"
    )

    # 1. Alerta de Falso Desconto (Seção 10 & 11)
    if offer.is_fake_discount and not _already_exists("FAKE_DISCOUNT", offer.final_price):
        a = Alert(
            product_id=product.id,
            offer_id=offer.id,
            store_id=store.id,
            alert_type="FAKE_DISCOUNT",
            severity="DANGER",
            title=f"Possível falso desconto identificado em {store.name}",
            message=f"Oferta '{offer.title}' por R$ {offer.final_price:.2f} apresenta indícios de desconto artificial.",
            price=offer.final_price,
            historical_comparison=hist_comp_text,
            reason=offer.fake_discount_reason or "Preço promocional incompatível com o histórico real.",
            offer_url=offer.url,
        )
        db.add(a)
        created_alerts.append(a)

    # Se não é produto prioritário (ex: PS5 Fat/Pro ou controle paralelo), não gerar alertas de compra principal
    if not product.is_priority or offer.is_fake_discount or not offer.in_stock:
        return created_alerts

    # 2. Menor preço registrado nos últimos 90 dias
    if min_hist_90d and offer.final_price <= min_hist_90d + 0.01:
        if not _already_exists("HISTORICAL_LOW", offer.final_price):
            label_prod = "PS5 Slim Digital" if product.category == "PS5" else f"DualSense ({product.color or 'Oficial'})"
            a = Alert(
                product_id=product.id,
                offer_id=offer.id,
                store_id=store.id,
                alert_type="HISTORICAL_LOW",
                severity="SUCCESS",
                title=f"{label_prod} atingiu o menor preço registrado nos últimos 90 dias.",
                message=f"R$ {offer.final_price:.2f} na loja {store.name} ({offer.payment_condition}).",
                price=offer.final_price,
                historical_comparison=hist_comp_text,
                reason=offer.opportunity_reason or "Novo piso histórico de preço atingido.",
                offer_url=offer.url,
            )
            db.add(a)
            created_alerts.append(a)

    # 3. Queda significativa em relação à última consulta (>= 5%)
    if previous_price and previous_price > offer.final_price:
        drop_pct = ((previous_price - offer.final_price) / previous_price) * 100.0
        if drop_pct >= 5.0 and not _already_exists("PRICE_DROP", offer.final_price):
            label_prod = "PS5 Slim Digital" if product.category == "PS5" else "DualSense"
            a = Alert(
                product_id=product.id,
                offer_id=offer.id,
                store_id=store.id,
                alert_type="PRICE_DROP",
                severity="HIGH",
                title=f"Preço do {label_prod} caiu {drop_pct:.1f}% em relação à última consulta.",
                message=f"Caiu de R$ {previous_price:.2f} para R$ {offer.final_price:.2f} na loja {store.name}.",
                price=offer.final_price,
                historical_comparison=f"Anterior: R$ {previous_price:.2f} (-{drop_pct:.1f}%) | {hist_comp_text}",
                reason=offer.opportunity_reason or f"Redução imediata de R$ {(previous_price - offer.final_price):.2f}.",
                offer_url=offer.url,
            )
            db.add(a)
            created_alerts.append(a)

    # 4. Oportunidade Excelente ou Excepcional (Score >= 75)
    if offer.opportunity_score >= 75:
        atype = "OPPORTUNITY_EXCEPTIONAL" if offer.opportunity_score >= 90 else "OPPORTUNITY_EXCELLENT"
        if not _already_exists(atype, offer.final_price):
            label_prod = "PS5 Slim Digital" if product.category == "PS5" else "DualSense"
            prefix = "Oportunidade excepcional" if offer.opportunity_score >= 90 else "Excelente oportunidade"
            a = Alert(
                product_id=product.id,
                offer_id=offer.id,
                store_id=store.id,
                alert_type=atype,
                severity="SUCCESS",
                title=f"{prefix} encontrada para {label_prod}.",
                message=f"{offer.title} por R$ {offer.final_price:.2f} na {store.name} (Índice: {offer.opportunity_score}/100).",
                price=offer.final_price,
                historical_comparison=hist_comp_text,
                reason=offer.opportunity_reason or f"Classificada como {offer.opportunity_level}.",
                offer_url=offer.url,
            )
            db.add(a)
            created_alerts.append(a)

    return created_alerts
