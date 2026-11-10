"""
Rotas REST completas do RADAR BF 2026 para alimentar as 10 páginas da plataforma:
1. /api/dashboard — Indicadores gerais e Cards em destaque (PS5 Slim Digital e DualSense)
2. /api/products — Produtos monitorados, bundles, revisões e seção separada de alternativas (Fat, Pro, Disco, Paralelos)
3. /api/comparator — Comparador de preços entre lojas com cálculo de frete, cupom, PIX vs Cartão
4. /api/history — Histórico de preços (24h, 7d, 30d, 90d, completo) e estatísticas descritivas
5. /api/intelligence — Inteligência de ofertas (Score 0-100, breakdown dos 10 fatores e detecção de falsos descontos)
6. /api/predictions — Previsão de mercado (24h, 3d, 7d)
7. /api/best-times — Análise de melhores horários (hora, dia da semana, dia do mês, semanas da BF)
8. /api/alerts — Central de notificações internas (ler, arquivar, filtrar)
9. /api/reports — Relatórios diários e semanais
10. /api/settings, /api/monitoring, /api/backups — Configurações, Preço-Alvo, Agendador, Logs e Backups
"""
import json
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db, now_sp, format_sp_iso
from backend.models.models import (
    Product,
    Store,
    Offer,
    PriceHistory,
    Alert,
    MonitoringLog,
    Coupon,
    Setting,
)
from backend.models.schemas import SettingUpdateSchema, CouponCreateSchema, ManualOfferInputSchema
from backend.collectors.base import CollectedOfferDTO
from backend.analytics.statistics import get_product_history_and_stats
from backend.analytics.intelligence import calculate_opportunity_index
from backend.analytics.predictions import generate_product_predictions
from backend.analytics.best_times import analyze_best_times
from backend.analytics.reports import generate_reports
from backend.analytics.event_mode import parse_events_json, evaluate_event_mode
from backend.services.monitoring_service import (
    ensure_initial_catalog_and_settings,
    run_monitoring_cycle,
    recalculate_all_offers_intelligence,
    upsert_collected_offer,
)
from backend.services.backup_service import create_database_backup, list_database_backups
from backend.scheduler.radar_scheduler import radar_scheduler

router = APIRouter(prefix="/api")


def _serialize_offer(offer: Offer, min_hist: Optional[float] = None, avg_30d: Optional[float] = None, stale_threshold_minutes: int = 90) -> dict:
    prod = offer.product
    store = offer.store
    var_pct = None
    if avg_30d and avg_30d > 0:
        var_pct = round(((offer.final_price - avg_30d) / avg_30d) * 100.0, 2)

    diff_vs_min_hist = None
    diff_vs_min_hist_pct = None
    if min_hist and min_hist > 0:
        diff_vs_min_hist = round(offer.final_price - min_hist, 2)
        diff_vs_min_hist_pct = round(((offer.final_price - min_hist) / min_hist) * 100.0, 2)

    now = now_sp()
    chk_dt = offer.last_checked_at
    if chk_dt:
        if chk_dt.tzinfo is None:
            chk_dt = chk_dt.replace(tzinfo=now.tzinfo)
        age_minutes = max(0, int((now - chk_dt).total_seconds() // 60))
    else:
        age_minutes = 9999

    is_stale = age_minutes > stale_threshold_minutes
    is_sudden_drop = bool(
        offer.previous_price
        and offer.previous_price > offer.final_price
        and ((offer.previous_price - offer.final_price) / offer.previous_price) >= 0.04
    )
    is_temporary_offer = bool(offer.coupon_code) or is_sudden_drop or (var_pct is not None and var_pct <= -6.0)

    cat = prod.category if prod else "PS5"
    subcat = prod.subcategory if prod else "MAIN"
    ed_type = prod.edition_type if prod else ""
    t_lower = offer.title.lower()

    has_disc_drive = False
    disc_badge = None
    if cat == "PS5":
        has_disc_drive = (
            subcat == "DISC_EDITION"
            or "com leitor" in ed_type.lower()
            or "com leitor" in t_lower
            or "leitor de disco" in t_lower
            or "slim disk" in t_lower
            or "disc console" in t_lower
        )
        disc_badge = "COM LEITOR DE DISCO (MÍDIA FÍSICA)" if has_disc_drive else "EDIÇÃO DIGITAL (SEM LEITOR)"

    # Observação automática de confiabilidade e veracidade para o usuário
    if offer.is_fake_discount:
        reliability_observation = f"🚨 OFERTA SUSPEITA / SOBREPREÇO: {offer.fake_discount_reason}"
    elif not offer.is_national or not offer.has_official_warranty:
        reliability_observation = "⚠️ ATENÇÃO (VERSÃO IMPORTADA): Produto novo, porém importado (sem garantia oficial Sony Brasil de 1 ano)."
    elif offer.is_marketplace:
        reliability_observation = f"⚠️ ATENÇÃO (MARKETPLACE): Vendido por '{offer.seller_name}'. Confira a reputação do vendedor antes de fechar."
    else:
        reliability_observation = f"✅ COMPRA SEGURA (LOJA CONFIÁVEL): Venda oficial verificada ({offer.seller_name}) • Produto 100% Novo Nacional."

    return {
        "id": offer.id,
        "external_id": offer.external_id,
        "product_id": offer.product_id,
        "product_slug": prod.slug if prod else "",
        "product_name": prod.name if prod else offer.title,
        "category": cat,
        "subcategory": subcat,
        "edition_type": ed_type,
        "has_disc_drive": has_disc_drive,
        "disc_badge": disc_badge,
        "color": prod.color if prod else "Branco",
        "is_priority": prod.is_priority if prod else True,
        "is_official": prod.is_official if prod else True,
        "store_id": offer.store_id,
        "store_slug": store.slug if store else "",
        "store_name": store.name if store else offer.seller_name,
        "store_reputation": store.reputation_score if store else 90.0,
        "title": offer.title,
        "url": offer.url,
        "image_url": offer.image_url or (prod.image_url if prod else None),
        "price_cash": offer.price_cash,
        "price_card": offer.price_card or offer.price_cash,
        "original_declared_price": offer.original_declared_price,
        "shipping_cost": offer.shipping_cost,
        "coupon_code": offer.coupon_code,
        "coupon_discount": offer.coupon_discount,
        "final_price": offer.final_price,
        "previous_price": offer.previous_price,
        "payment_condition": offer.payment_condition,
        "installments_text": offer.installments_text,
        "seller_name": offer.seller_name,
        "is_marketplace": offer.is_marketplace,
        "is_national": offer.is_national,
        "has_official_warranty": offer.has_official_warranty,
        "model_revision": offer.model_revision_detected or (prod.model_revision if prod else None),
        "in_stock": offer.in_stock,
        "data_origin": offer.data_origin,
        "opportunity_score": offer.opportunity_score,
        "opportunity_level": offer.opportunity_level,
        "opportunity_reason": offer.opportunity_reason,
        "reliability_score": offer.reliability_score,
        "reliability_label": offer.reliability_label,
        "reliability_observation": reliability_observation,
        "is_fake_discount": offer.is_fake_discount,
        "fake_discount_reason": offer.fake_discount_reason,
        "declared_discount_pct": offer.declared_discount_pct,
        "real_discount_vs_avg_pct": offer.real_discount_vs_avg_pct,
        "min_historical_price": min_hist,
        "diff_vs_historical_low": diff_vs_min_hist,
        "diff_vs_historical_low_pct": diff_vs_min_hist_pct,
        "avg_30d_price": round(avg_30d, 2) if avg_30d else None,
        "variation_vs_avg_30d_pct": var_pct,
        "data_age_minutes": age_minutes,
        "is_stale": is_stale,
        "is_sudden_drop": is_sudden_drop,
        "is_temporary_offer": is_temporary_offer,
        "last_checked_at": format_sp_iso(offer.last_checked_at),
        "first_seen_at": format_sp_iso(offer.first_seen_at),
    }


def _category_metrics(db: Session, category: str) -> dict:
    now = now_sp()
    cutoff_30d = (now - timedelta(days=30)).replace(tzinfo=None)

    priority_prods = (
        db.query(Product)
        .filter(Product.category == category, Product.is_priority.is_(True))
        .all()
    )
    prod_ids = [p.id for p in priority_prods]

    offers = (
        db.query(Offer)
        .filter(Offer.product_id.in_(prod_ids), Offer.in_stock.is_(True))
        .order_by(Offer.final_price.asc())
        .all()
    )
    valid_offers = [o for o in offers if not o.is_fake_discount] or offers

    min_hist_val = (
        db.query(func.min(PriceHistory.final_price))
        .filter(PriceHistory.product_id.in_(prod_ids))
        .scalar()
    )
    avg_30d_val = (
        db.query(func.avg(PriceHistory.final_price))
        .filter(
            PriceHistory.product_id.in_(prod_ids),
            PriceHistory.recorded_at >= cutoff_30d,
        )
        .scalar()
    )
    if avg_30d_val is None:
        avg_30d_val = (
            db.query(func.avg(PriceHistory.final_price))
            .filter(PriceHistory.product_id.in_(prod_ids))
            .scalar()
        )

    min_hist = float(min_hist_val) if min_hist_val is not None else None
    avg_30d = float(avg_30d_val) if avg_30d_val is not None else None
    current_mean = (
        sum(float(o.final_price) for o in valid_offers) / len(valid_offers)
        if valid_offers
        else None
    )

    serialized_all = [_serialize_offer(o, min_hist, avg_30d) for o in offers]
    serialized_valid = [x for x in serialized_all if not x["is_fake_discount"]] or serialized_all

    best_price_offer = serialized_valid[0] if serialized_valid else None
    best_opp_offer = max(serialized_valid, key=lambda o: o["opportunity_score"]) if serialized_valid else None

    lowest_digital_offer = None
    lowest_disc_offer = None
    if category == "PS5":
        dig_all = [x for x in serialized_all if not x.get("has_disc_drive")]
        disc_all = [x for x in serialized_all if x.get("has_disc_drive")]
        dig_valid = [x for x in dig_all if not x["is_fake_discount"]] or dig_all
        disc_valid = [x for x in disc_all if not x["is_fake_discount"]] or disc_all
        lowest_digital_offer = dig_valid[0] if dig_valid else None
        lowest_disc_offer = disc_valid[0] if disc_valid else None

    return {
        "min_hist": round(min_hist, 2) if min_hist else None,
        "avg_30d": round(avg_30d, 2) if avg_30d else None,
        "current_mean": round(current_mean, 2) if current_mean else None,
        "best_price_offer": best_price_offer,
        "best_opp_offer": best_opp_offer,
        "lowest_digital_offer": lowest_digital_offer,
        "lowest_disc_offer": lowest_disc_offer,
        "all_priority_offers": serialized_all,
    }


def _get_event_mode_status(db: Session) -> dict:
    setting = db.query(Setting).first()
    if not setting:
        return evaluate_event_mode(events_list=parse_events_json(None))
    return evaluate_event_mode(
        events_list=parse_events_json(setting.custom_events_json),
        lead_days=setting.event_lead_days,
        event_mode_enabled=setting.event_mode_enabled,
        interval_normal_minutes=setting.interval_normal_minutes,
        interval_warmup_minutes=setting.interval_warmup_minutes,
        interval_event_minutes=setting.interval_high_minutes,
        interval_night_minutes=setting.interval_night_minutes,
        prioritize_ps5_in_event=setting.prioritize_ps5_in_event,
    )


@router.get("/dashboard")
def get_dashboard_data(db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    setting = db.query(Setting).first()
    event_mode = _get_event_mode_status(db)

    products_count = db.query(Product).count()
    priority_products_count = db.query(Product).filter(Product.is_priority.is_(True)).count()
    stores = db.query(Store).all()
    offers = db.query(Offer).filter(Offer.in_stock.is_(True)).all()
    unread_alerts_count = db.query(Alert).filter(Alert.is_read.is_(False), Alert.is_archived.is_(False)).count()

    ps5_data = _category_metrics(db, "PS5")
    ds_data = _category_metrics(db, "DUALSENSE")

    # Ordenar sempre buscando o MENOR PREÇO REAL (incluindo os melhores PS5 Novos e os melhores DualSense Novos)
    ps5_sorted = sorted(
        ps5_data["all_priority_offers"],
        key=lambda x: (1 if x["is_fake_discount"] else 0, x["final_price"]),
    )
    ds_sorted = sorted(
        ds_data["all_priority_offers"],
        key=lambda x: (1 if x["is_fake_discount"] else 0, x["final_price"]),
    )
    top_sorted = ps5_sorted[:12] + ds_sorted[:8]

    best_overall = ps5_data["best_price_offer"] or (top_sorted[0] if top_sorted else None)
    last_offer_check = max((o.last_checked_at for o in offers if o.last_checked_at), default=now_sp())

    now = now_sp()
    chk_dt = last_offer_check if last_offer_check.tzinfo else last_offer_check.replace(tzinfo=now.tzinfo)
    data_age_minutes = max(0, int((now - chk_dt).total_seconds() // 60))
    stale_threshold = setting.stale_data_threshold_minutes if setting else 90

    # Indicador "Vale a pena comprar agora?" comparado ao Menor Preço da História do PS5
    ps5_featured = ps5_data["best_price_offer"]
    ds_featured = ds_data["best_price_offer"]

    def _worth_buying_verdict(feat: Optional[dict]) -> dict:
        if not feat:
            return {"verdict": "SEM DADOS", "status": "NEUTRAL", "summary": "Nenhuma oferta ativa."}
        score = feat["opportunity_score"]
        if feat["is_fake_discount"]:
            return {"verdict": "NÃO COMPRAR (FALSO DESCONTO / SOBREPREÇO)", "status": "DANGER", "summary": feat["fake_discount_reason"]}
        if score >= 85:
            return {"verdict": "SIM! PRÓXIMO DO MENOR PREÇO DA HISTÓRIA", "status": "SUCCESS", "summary": feat["opportunity_reason"]}
        if score >= 70:
            return {"verdict": "BOM PREÇO EM LOJA CONFIÁVEL (ABAIXO DA MÉDIA)", "status": "SUCCESS", "summary": feat["opportunity_reason"]}
        if score >= 55:
            return {"verdict": "MENOR PREÇO ATUAL, MAS AINDA ACIMA DO RECORDE HISTÓRICO", "status": "WARNING", "summary": feat["opportunity_reason"]}
        return {"verdict": "AGUARDAR QUEDA MAIS PRÓXIMA DO RECORDE HISTÓRICO", "status": "DANGER", "summary": feat["opportunity_reason"]}

    return {
        "indicators": {
            "monitored_products_count": products_count,
            "priority_products_count": priority_products_count,
            "stores_consulted_count": len(stores),
            "stores_online_count": sum(1 for s in stores if s.status == "ONLINE"),
            "lowest_ps5_price": ps5_featured["final_price"] if ps5_featured else None,
            "lowest_ps5_digital_price": ps5_data["lowest_digital_offer"]["final_price"] if ps5_data["lowest_digital_offer"] else None,
            "lowest_ps5_disc_price": ps5_data["lowest_disc_offer"]["final_price"] if ps5_data["lowest_disc_offer"] else None,
            "ps5_historical_low": ps5_data["min_hist"],
            "average_ps5_price": ps5_data["current_mean"],
            "lowest_dualsense_price": ds_featured["final_price"] if ds_featured else None,
            "dualsense_historical_low": ds_data["min_hist"],
            "average_dualsense_price": ds_data["current_mean"],
            "best_opportunity": best_overall,
            "offers_identified_count": len(offers),
            "unread_alerts_count": unread_alerts_count,
            "last_updated_at": format_sp_iso(last_offer_check),
            "data_age_minutes": data_age_minutes,
            "is_data_stale": data_age_minutes > stale_threshold,
            "stale_threshold_minutes": stale_threshold,
        },
        "event_mode": event_mode,
        "featured_products": {
            "ps5": ps5_featured,
            "ps5_lowest_digital": ps5_data["lowest_digital_offer"],
            "ps5_lowest_disc": ps5_data["lowest_disc_offer"],
            "ps5_worth_buying": _worth_buying_verdict(ps5_featured),
            "dualsense": ds_featured,
            "dualsense_worth_buying": _worth_buying_verdict(ds_featured),
        },
        "top_offers": top_sorted,
        "scheduler": radar_scheduler.get_status(),
    }


@router.get("/products")
def get_monitored_products(db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    ps5_metrics = _category_metrics(db, "PS5")
    ds_metrics = _category_metrics(db, "DUALSENSE")

    # Oportunidades Alternativas (PS5 Fat, PS5 Pro, PS5 Slim com Disco, Controles Paralelos/Edge)
    alt_products = db.query(Product).filter(Product.is_priority.is_(False)).all()
    alt_prod_ids = [p.id for p in alt_products]
    alt_offers = (
        db.query(Offer)
        .filter(Offer.product_id.in_(alt_prod_ids), Offer.in_stock.is_(True))
        .order_by(Offer.final_price.asc())
        .all()
    )

    all_products = db.query(Product).all()

    return {
        "catalog": [
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "category": p.category,
                "subcategory": p.subcategory,
                "edition_type": p.edition_type,
                "model_revision": p.model_revision,
                "color": p.color,
                "is_official": p.is_official,
                "is_priority": p.is_priority,
                "image_url": p.image_url,
                "description": p.description,
                "offers_count": sum(1 for o in p.offers if o.in_stock),
            }
            for p in all_products
        ],
        "ps5_priority_offers": ps5_metrics["all_priority_offers"],
        "dualsense_priority_offers": ds_metrics["all_priority_offers"],
        "alternative_opportunities": [_serialize_offer(o) for o in alt_offers],
    }


@router.get("/comparator")
def get_price_comparator(
    category: str = Query(default="ALL", description="PS5, DUALSENSE ou ALL"),
    include_alternatives: bool = Query(default=False),
    only_official_warranty: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    ensure_initial_catalog_and_settings(db)
    ps5_m = _category_metrics(db, "PS5")
    ds_m = _category_metrics(db, "DUALSENSE")

    offers = db.query(Offer).join(Product, Product.id == Offer.product_id).filter(Offer.in_stock.is_(True))
    if category in ("PS5", "DUALSENSE"):
        offers = offers.filter(Product.category == category)
    if not include_alternatives:
        offers = offers.filter(Product.is_priority.is_(True))
    if only_official_warranty:
        offers = offers.filter(Offer.has_official_warranty.is_(True), Offer.is_national.is_(True))

    offer_list = offers.order_by(Offer.final_price.asc()).all()
    serialized = []
    for o in offer_list:
        m = ps5_m if (o.product and o.product.category == "PS5") else ds_m
        serialized.append(_serialize_offer(o, m["min_hist"], m["avg_30d"]))

    stores = db.query(Store).order_by(Store.name.asc()).all()
    coupons = db.query(Coupon).filter(Coupon.is_active.is_(True)).all()

    return {
        "offers": serialized,
        "stores": [
            {
                "id": s.id,
                "slug": s.slug,
                "name": s.name,
                "website_url": s.website_url,
                "store_type": s.store_type,
                "connector_type": s.connector_type,
                "reputation_score": s.reputation_score,
                "status": s.status,
                "status_message": s.status_message,
                "integration_docs": s.integration_docs,
                "last_check_at": format_sp_iso(s.last_check_at),
                "last_success_at": format_sp_iso(s.last_success_at),
            }
            for s in stores
        ],
        "active_coupons": [
            {
                "id": c.id,
                "store_name": c.store.name if c.store else "",
                "code": c.code,
                "description": c.description,
                "discount_type": c.discount_type,
                "discount_value": c.discount_value,
                "min_order_value": c.min_order_value,
                "applicable_category": c.applicable_category,
            }
            for c in coupons
        ],
    }


@router.get("/history")
def get_price_history(
    category: str = Query(default="PS5", description="PS5 ou DUALSENSE"),
    product_id: Optional[int] = Query(default=None),
    period: str = Query(default="30d", description="24h, 7d, 30d, 90d, all"),
    payment_filter: str = Query(default="ALL", description="ALL, PIX, CARD, COUPON"),
    include_shipping: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    ensure_initial_catalog_and_settings(db)
    data = get_product_history_and_stats(
        db=db,
        product_id=product_id,
        category=category if product_id is None else None,
        period=period,
        payment_filter=payment_filter,
        include_shipping=include_shipping,
    )
    return data


@router.get("/intelligence")
def get_radar_intelligence(db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    ps5_m = _category_metrics(db, "PS5")
    ds_m = _category_metrics(db, "DUALSENSE")

    all_offers = db.query(Offer).filter(Offer.in_stock.is_(True)).order_by(Offer.final_price.asc()).all()
    evaluated_list = []

    for o in all_offers:
        cat = o.product.category if o.product else "PS5"
        m = ps5_m if cat == "PS5" else ds_m
        item = _serialize_offer(o, m["min_hist"], m["avg_30d"])
        evaluated_list.append(item)

    evaluated_list.sort(key=lambda x: (0 if x["category"] == "PS5" else 1, x["final_price"]))
    fake_discounts_detected = [x for x in evaluated_list if x["is_fake_discount"]]

    return {
        "methodology": {
            "scale": [
                {"range": "90 a 100", "label": "Oportunidade excepcional", "color": "#10b981"},
                {"range": "75 a 89", "label": "Excelente oportunidade", "color": "#22c55e"},
                {"range": "60 a 74", "label": "Boa oportunidade", "color": "#84cc16"},
                {"range": "40 a 59", "label": "Preço interessante, mas pode melhorar", "color": "#eab308"},
                {"range": "0 a 39", "label": "Não recomendado no momento", "color": "#ef4444"},
            ],
            "factors_weights": {
                "Comparação com a média de 30 dias": 22,
                "Comparação com o menor preço histórico": 23,
                "Reputação da loja/vendedor e Garantia Oficial": 12,
                "Velocidade da queda recente": 8,
                "Diferença competitiva entre lojas": 8,
                "Custo do frete": 7,
                "Cupons disponíveis": 7,
                "Histórico de promoções e Confiabilidade": 7,
                "Condições de pagamento (PIX / Parcelamento)": 6,
            },
            "safety_rules": [
                "Ofertas com menos de 3 registros históricos têm pontuação máxima travada em 55/100.",
                "Ofertas com suspeita de falso desconto sofrem penalização automática e nunca recebem recomendação de compra.",
                "O desconto percentual anunciado pela loja ('De/Por') nunca é usado como prova de economia real.",
            ],
        },
        "offers_ranked": evaluated_list,
        "fake_discounts_detected": fake_discounts_detected,
    }


@router.get("/predictions")
def get_market_predictions(db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    priority_products = db.query(Product).filter(Product.is_priority.is_(True)).all()
    all_predictions = []
    for p in priority_products:
        preds = generate_product_predictions(db, p)
        all_predictions.append(
            {
                "product_id": p.id,
                "product_slug": p.slug,
                "product_name": p.name,
                "category": p.category,
                "subcategory": p.subcategory,
                "horizons": preds,
            }
        )
    return {
        "generated_at": format_sp_iso(now_sp()),
        "disclaimer": (
            "IMPORTANTE: As previsões utilizam métodos estatísticos interpretáveis (Médias Móveis de 7 e 30 dias, "
            "Regressão Linear Amortecida e Volatilidade Histórica). Correlações passadas não garantem promoções "
            "futuras em horários específicos."
        ),
        "products_predictions": all_predictions,
    }


@router.get("/best-times")
def get_best_times(
    category: Optional[str] = Query(default=None, description="PS5 ou DUALSENSE"),
    db: Session = Depends(get_db),
):
    ensure_initial_catalog_and_settings(db)
    return analyze_best_times(db, category=category)


@router.get("/alerts")
def get_internal_alerts(
    include_archived: bool = Query(default=False),
    only_unread: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    ensure_initial_catalog_and_settings(db)
    query = db.query(Alert)
    if not include_archived:
        query = query.filter(Alert.is_archived.is_(False))
    if only_unread:
        query = query.filter(Alert.is_read.is_(False))

    alerts = query.order_by(Alert.created_at.desc()).all()
    return {
        "unread_count": db.query(Alert).filter(Alert.is_read.is_(False), Alert.is_archived.is_(False)).count(),
        "total_active": db.query(Alert).filter(Alert.is_archived.is_(False)).count(),
        "alerts": [
            {
                "id": a.id,
                "product_id": a.product_id,
                "product_name": a.product.name if a.product else "Produto Monitorado",
                "category": a.product.category if a.product else "",
                "store_name": a.store.name if a.store else "Loja",
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "price": a.price,
                "historical_comparison": a.historical_comparison,
                "reason": a.reason,
                "offer_url": a.offer_url,
                "is_read": a.is_read,
                "is_archived": a.is_archived,
                "created_at": format_sp_iso(a.created_at),
            }
            for a in alerts
        ],
    }


@router.patch("/alerts/{alert_id}/read")
@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, is_read: bool = True, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")
    alert.is_read = bool(is_read)
    db.commit()
    db.refresh(alert)
    unread_count = db.query(Alert).filter(Alert.is_read.is_(False), Alert.is_archived.is_(False)).count()
    return {"status": "OK", "id": alert.id, "is_read": alert.is_read, "unread_count": unread_count}


@router.patch("/alerts/{alert_id}/archive")
@router.post("/alerts/{alert_id}/archive")
def archive_alert(alert_id: int, is_archived: bool = True, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")
    alert.is_archived = bool(is_archived)
    if is_archived:
        alert.is_read = True
    db.commit()
    db.refresh(alert)
    unread_count = db.query(Alert).filter(Alert.is_read.is_(False), Alert.is_archived.is_(False)).count()
    return {"status": "OK", "id": alert.id, "is_archived": alert.is_archived, "is_read": alert.is_read, "unread_count": unread_count}


@router.post("/alerts/mark-all-read")
def mark_all_alerts_read(db: Session = Depends(get_db)):
    db.query(Alert).filter(Alert.is_read.is_(False)).update({"is_read": True}, synchronize_session=False)
    db.commit()
    unread_count = db.query(Alert).filter(Alert.is_read.is_(False), Alert.is_archived.is_(False)).count()
    return {"status": "OK", "unread_count": unread_count}


@router.get("/reports")
def get_system_reports(db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    return generate_reports(db)


@router.get("/settings")
def get_user_settings(db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    s = db.query(Setting).first()
    ev_mode = _get_event_mode_status(db)
    return {
        "ps5_target_price": s.ps5_target_price,
        "ps5_excellent_price": s.ps5_excellent_price,
        "ps5_payment_preference": s.ps5_payment_preference,
        "ps5_preferred_stores": json.loads(s.ps5_preferred_stores or "[]"),
        "ps5_include_bundles": s.ps5_include_bundles,
        "dualsense_target_price": s.dualsense_target_price,
        "dualsense_excellent_price": s.dualsense_excellent_price,
        "dualsense_desired_colors": json.loads(s.dualsense_desired_colors or "[]"),
        "dualsense_preferred_stores": json.loads(s.dualsense_preferred_stores or "[]"),
        "scheduler_mode": s.scheduler_mode,
        "interval_normal_minutes": s.interval_normal_minutes,
        "interval_warmup_minutes": s.interval_warmup_minutes,
        "interval_high_minutes": s.interval_high_minutes,
        "interval_night_minutes": s.interval_night_minutes,
        "event_mode_enabled": s.event_mode_enabled,
        "event_lead_days": s.event_lead_days,
        "prioritize_ps5_in_event": s.prioritize_ps5_in_event,
        "stale_data_threshold_minutes": s.stale_data_threshold_minutes,
        "promotional_events": parse_events_json(s.custom_events_json),
        "browser_notifications_enabled": s.browser_notifications_enabled,
        "only_official_warranty": s.only_official_warranty,
        "updated_at": format_sp_iso(s.updated_at),
        "scheduler_status": radar_scheduler.get_status(),
        "event_mode": ev_mode,
    }


@router.put("/settings")
def update_user_settings(payload: SettingUpdateSchema, db: Session = Depends(get_db)):
    ensure_initial_catalog_and_settings(db)
    s = db.query(Setting).first()
    s.ps5_target_price = payload.ps5_target_price
    s.ps5_excellent_price = payload.ps5_excellent_price
    s.ps5_payment_preference = payload.ps5_payment_preference
    s.ps5_preferred_stores = json.dumps(payload.ps5_preferred_stores, ensure_ascii=False)
    s.ps5_include_bundles = payload.ps5_include_bundles

    s.dualsense_target_price = payload.dualsense_target_price
    s.dualsense_excellent_price = payload.dualsense_excellent_price
    s.dualsense_desired_colors = json.dumps(payload.dualsense_desired_colors, ensure_ascii=False)
    s.dualsense_preferred_stores = json.dumps(payload.dualsense_preferred_stores, ensure_ascii=False)

    s.scheduler_mode = payload.scheduler_mode
    s.interval_normal_minutes = payload.interval_normal_minutes
    s.interval_warmup_minutes = payload.interval_warmup_minutes
    s.interval_high_minutes = payload.interval_high_minutes
    s.interval_night_minutes = payload.interval_night_minutes
    s.event_mode_enabled = payload.event_mode_enabled
    s.event_lead_days = payload.event_lead_days
    s.prioritize_ps5_in_event = payload.prioritize_ps5_in_event
    s.stale_data_threshold_minutes = payload.stale_data_threshold_minutes
    if payload.promotional_events is not None:
        s.custom_events_json = json.dumps([e.model_dump() for e in payload.promotional_events], ensure_ascii=False)
    s.browser_notifications_enabled = payload.browser_notifications_enabled
    s.only_official_warranty = payload.only_official_warranty
    db.commit()

    # Reconfigurar agendador imediatamente com base no Modo de Evento / Configuração
    target_mode, target_interval = radar_scheduler.compute_effective_schedule(s)
    radar_scheduler.reschedule(target_mode, target_interval)

    recalculate_all_offers_intelligence(db)

    return get_user_settings(db)


@router.post("/monitoring/run")
async def trigger_manual_monitoring(
    store_slug: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    result = await run_monitoring_cycle(db, store_slug_filter=store_slug)
    return result


@router.get("/monitoring/logs")
def get_monitoring_logs(limit: int = Query(default=40, le=200), db: Session = Depends(get_db)):
    logs = db.query(MonitoringLog).order_by(MonitoringLog.started_at.desc()).limit(limit).all()
    stores = db.query(Store).order_by(Store.name.asc()).all()
    return {
        "scheduler": radar_scheduler.get_status(),
        "stores_status": [
            {
                "slug": s.slug,
                "name": s.name,
                "status": s.status,
                "status_message": s.status_message,
                "connector_type": s.connector_type,
                "integration_docs": s.integration_docs,
                "last_check_at": format_sp_iso(s.last_check_at),
                "last_success_at": format_sp_iso(s.last_success_at),
            }
            for s in stores
        ],
        "logs": [
            {
                "id": l.id,
                "store_name": l.store_name,
                "status": l.status,
                "offers_found": l.offers_found,
                "offers_updated": l.offers_updated,
                "error_message": l.error_message,
                "duration_ms": l.duration_ms,
                "started_at": format_sp_iso(l.started_at),
                "finished_at": format_sp_iso(l.finished_at),
            }
            for l in logs
        ],
    }


@router.post("/offers/manual")
def register_manual_offer(payload: ManualOfferInputSchema, db: Session = Depends(get_db)):
    """
    Permite cadastrar/registrar manualmente uma oferta vista em uma loja ou promoção relâmpago,
    passando pelo mesmo classificador, cálculo de oportunidade e detecção de falso desconto.
    """
    ensure_initial_catalog_and_settings(db)
    store = db.query(Store).filter(Store.slug == payload.store_slug).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")

    ext_id = f"MANUAL-{abs(hash(payload.url + payload.title)) % 10000000}"
    dto = CollectedOfferDTO(
        external_id=ext_id,
        title=payload.title,
        url=payload.url,
        price_cash=payload.price_cash,
        price_card=payload.price_card,
        original_declared_price=payload.original_declared_price,
        shipping_cost=payload.shipping_cost,
        coupon_code=payload.coupon_code,
        coupon_discount=payload.coupon_discount,
        payment_condition=payload.payment_condition,
        seller_name=payload.seller_name,
        is_marketplace=payload.is_marketplace,
        in_stock=True,
        data_origin="MANUAL_USER_ENTRY",
    )
    offer = upsert_collected_offer(db, store, dto)
    if not offer:
        raise HTTPException(
            status_code=400,
            detail="O título informado não foi reconhecido como Console PS5 nem como Controle DualSense.",
        )
    db.commit()
    recalculate_all_offers_intelligence(db)
    return {"status": "SUCCESS", "offer": _serialize_offer(offer)}


@router.post("/coupons")
def add_coupon(payload: CouponCreateSchema, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.slug == payload.store_slug).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")
    cp = Coupon(
        store_id=store.id,
        code=payload.code.strip().upper(),
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_value=payload.min_order_value,
        max_discount_value=payload.max_discount_value,
        applicable_category=payload.applicable_category,
        is_active=True,
    )
    db.add(cp)
    db.commit()
    recalculate_all_offers_intelligence(db)
    return {"status": "SUCCESS", "coupon_id": cp.id}


@router.post("/backups")
def trigger_backup():
    return create_database_backup()


@router.get("/backups")
def get_backups():
    return {"backups": list_database_backups()}
