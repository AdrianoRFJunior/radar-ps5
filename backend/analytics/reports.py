"""
Módulo de Relatórios Diários e Semanais (Seção 13).
Gera dentro do próprio sistema:
1. Relatório Diário:
   - Menores preços encontrados
   - Melhores oportunidades
   - Alterações relevantes
   - Produtos com queda de preço
   - Ofertas que desapareceram (sem estoque)
   - Previsão e tendência
2. Relatório Semanal:
   - Evolução dos preços
   - Comparação entre lojas
   - Histórico de promoções
   - Estatísticas de horários
   - Recomendações de compra
"""
from datetime import timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.database import now_sp, format_sp_iso
from backend.models.models import Offer, PriceHistory, Product, Store
from backend.analytics.best_times import analyze_best_times
from backend.analytics.predictions import generate_product_predictions


def generate_reports(db: Session) -> Dict[str, Any]:
    now = now_sp()
    cutoff_24h = (now - timedelta(hours=24)).replace(tzinfo=None)
    cutoff_7d = (now - timedelta(days=7)).replace(tzinfo=None)

    priority_products = db.query(Product).filter(Product.is_priority.is_(True)).all()
    priority_ids = [p.id for p in priority_products]

    active_offers: List[Offer] = (
        db.query(Offer)
        .filter(Offer.product_id.in_(priority_ids), Offer.in_stock.is_(True))
        .order_by(Offer.opportunity_score.desc(), Offer.final_price.asc())
        .all()
    )

    disappeared_offers: List[Offer] = (
        db.query(Offer)
        .filter(Offer.product_id.in_(priority_ids), Offer.in_stock.is_(False))
        .order_by(Offer.last_checked_at.desc())
        .all()
    )

    # Menores preços encontrados por categoria principal
    ps5_offers = [o for o in active_offers if o.product and o.product.category == "PS5"]
    ds_offers = [o for o in active_offers if o.product and o.product.category == "DUALSENSE"]

    lowest_ps5 = min(ps5_offers, key=lambda o: o.final_price) if ps5_offers else None
    lowest_ds = min(ds_offers, key=lambda o: o.final_price) if ds_offers else None

    # Produtos/ofertas com queda de preço recente
    price_drops = []
    relevant_changes = []
    for o in active_offers:
        if o.previous_price and o.previous_price > o.final_price + 0.01:
            drop_val = round(o.previous_price - o.final_price, 2)
            drop_pct = round((drop_val / o.previous_price) * 100.0, 2)
            item = {
                "offer_id": o.id,
                "title": o.title,
                "store_name": o.store.name if o.store else o.seller_name,
                "previous_price": o.previous_price,
                "current_price": o.final_price,
                "drop_amount": drop_val,
                "drop_pct": drop_pct,
                "opportunity_score": o.opportunity_score,
                "url": o.url,
            }
            price_drops.append(item)
            relevant_changes.append(item)
        elif o.previous_price and o.final_price > o.previous_price + 0.01:
            inc_val = round(o.final_price - o.previous_price, 2)
            inc_pct = round((inc_val / o.previous_price) * 100.0, 2)
            relevant_changes.append(
                {
                    "offer_id": o.id,
                    "title": o.title,
                    "store_name": o.store.name if o.store else o.seller_name,
                    "previous_price": o.previous_price,
                    "current_price": o.final_price,
                    "drop_amount": -inc_val,
                    "drop_pct": -inc_pct,
                    "opportunity_score": o.opportunity_score,
                    "url": o.url,
                }
            )

    # Previsão e tendência consolidada
    predictions_summary = []
    for p in priority_products:
        preds = generate_product_predictions(db, p)
        if preds:
            predictions_summary.append(preds[0])  # Horizonte 24h para diário, mais 7d para semanal

    # Comparação entre lojas (Relatório Semanal)
    stores = db.query(Store).all()
    store_comparison = []
    for st in stores:
        st_offers = [o for o in active_offers if o.store_id == st.id]
        st_ps5 = [o.final_price for o in st_offers if o.product and o.product.category == "PS5"]
        st_ds = [o.final_price for o in st_offers if o.product and o.product.category == "DUALSENSE"]
        avg_score = round(sum(o.opportunity_score for o in st_offers) / len(st_offers), 1) if st_offers else 0.0
        store_comparison.append(
            {
                "store_name": st.name,
                "status": st.status,
                "reputation_score": st.reputation_score,
                "active_offers_count": len(st_offers),
                "min_ps5_price": min(st_ps5) if st_ps5 else None,
                "min_dualsense_price": min(st_ds) if st_ds else None,
                "avg_opportunity_score": avg_score,
            }
        )

    # Evolução semanal dos preços
    weekly_history = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id.in_(priority_ids), PriceHistory.recorded_at >= cutoff_7d)
        .order_by(PriceHistory.recorded_at.asc())
        .all()
    )

    promo_history = [
        {
            "recorded_at": format_sp_iso(h.recorded_at),
            "store_name": h.store.name if h.store else h.seller_name,
            "product_name": h.product.name if h.product else "",
            "final_price": h.final_price,
            "coupon_code": h.coupon_code,
            "payment_condition": h.payment_condition,
        }
        for h in weekly_history
        if h.is_promotional or h.coupon_code
    ]

    best_times_summary = analyze_best_times(db)

    # Recomendações estratégicas de compra
    recommendations = []
    if lowest_ps5:
        recommendations.append(
            {
                "category": "PS5 Slim Digital",
                "best_offer_title": lowest_ps5.title,
                "store_name": lowest_ps5.store.name if lowest_ps5.store else lowest_ps5.seller_name,
                "final_price": lowest_ps5.final_price,
                "opportunity_score": lowest_ps5.opportunity_score,
                "classification": lowest_ps5.opportunity_level,
                "verdict": (
                    "COMPRAR AGORA — Preço e índice de oportunidade altamente favoráveis."
                    if lowest_ps5.opportunity_score >= 75 and not lowest_ps5.is_fake_discount
                    else "MONITORAR E AGUARDAR — Há margem para queda adicional ou cupom na Black Friday."
                ),
                "reasoning": lowest_ps5.opportunity_reason,
                "url": lowest_ps5.url,
            }
        )
    if lowest_ds:
        recommendations.append(
            {
                "category": "Controle DualSense",
                "best_offer_title": lowest_ds.title,
                "store_name": lowest_ds.store.name if lowest_ds.store else lowest_ds.seller_name,
                "final_price": lowest_ds.final_price,
                "opportunity_score": lowest_ds.opportunity_score,
                "classification": lowest_ds.opportunity_level,
                "verdict": (
                    "COMPRAR AGORA — Excelente relação preço/histórico para DualSense oficial."
                    if lowest_ds.opportunity_score >= 75 and not lowest_ds.is_fake_discount
                    else "AGUARDAR — Monitorar quedas relâmpago ou cupons."
                ),
                "reasoning": lowest_ds.opportunity_reason,
                "url": lowest_ds.url,
            }
        )

    return {
        "generated_at": format_sp_iso(now),
        "daily_report": {
            "date_reference": now.strftime("%d/%m/%Y"),
            "lowest_prices": {
                "ps5": {
                    "title": lowest_ps5.title,
                    "store": lowest_ps5.store.name if lowest_ps5.store else lowest_ps5.seller_name,
                    "final_price": lowest_ps5.final_price,
                    "shipping_cost": lowest_ps5.shipping_cost,
                    "opportunity_score": lowest_ps5.opportunity_score,
                    "url": lowest_ps5.url,
                }
                if lowest_ps5
                else None,
                "dualsense": {
                    "title": lowest_ds.title,
                    "store": lowest_ds.store.name if lowest_ds.store else lowest_ds.seller_name,
                    "final_price": lowest_ds.final_price,
                    "shipping_cost": lowest_ds.shipping_cost,
                    "opportunity_score": lowest_ds.opportunity_score,
                    "url": lowest_ds.url,
                }
                if lowest_ds
                else None,
            },
            "best_opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "category": o.product.category if o.product else "",
                    "store_name": o.store.name if o.store else o.seller_name,
                    "final_price": o.final_price,
                    "opportunity_score": o.opportunity_score,
                    "opportunity_level": o.opportunity_level,
                    "reason": o.opportunity_reason,
                    "url": o.url,
                }
                for o in active_offers[:6]
            ],
            "price_drops": price_drops,
            "relevant_changes": relevant_changes,
            "disappeared_offers": [
                {
                    "id": o.id,
                    "title": o.title,
                    "store_name": o.store.name if o.store else o.seller_name,
                    "last_final_price": o.final_price,
                    "last_checked_at": format_sp_iso(o.last_checked_at),
                }
                for o in disappeared_offers
            ],
            "predictions_and_trends": predictions_summary,
        },
        "weekly_report": {
            "period_label": f"{(now - timedelta(days=7)).strftime('%d/%m/%Y')} a {now.strftime('%d/%m/%Y')}",
            "total_weekly_checks": len(weekly_history),
            "store_comparison": store_comparison,
            "promotions_history": promo_history[-25:],
            "top_hours": best_times_summary["top_quality_hours"],
            "by_weekday": best_times_summary["by_weekday"],
            "purchase_recommendations": recommendations,
        },
    }
