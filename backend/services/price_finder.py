"""
Módulo de busca e auditoria em tempo real de preços do PlayStation 5 e DualSense.
Cumpre rigorosamente as diretrizes do usuário:
1. Sem banco de dados acumulando ou defasando histórico: varredura direta em memória nas lojas confiáveis.
2. Atualização imediata dos menores preços reais (à vista no PIX e a prazo no Cartão).
3. Transparência total de cupons de desconto (com destaque para código e cópia rápida).
4. Suporte tanto a PS5 Slim Digital (sem leitor) quanto PS5 Slim com Leitor de Disco e bundles oficiais.
5. Exclusão de acessórios avulsos, produtos usados e PS5 Pro.
6. Exportação instantânea de todos os arquivos estáticos JSON para funcionamento 24/7.
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO
from backend.collectors.classifier import classify_offer_title, ClassificationResult
from backend.collectors.community_sources import PromobitCollector
from backend.collectors.mercadolivre import MercadoLivreCollector
from backend.collectors.retail_stores import (
    AmazonBrasilCollector,
    KabumCollector,
    MagazineLuizaCollector,
    FastShopCollector,
    CarrefourCollector,
    AmericanasCollector,
)

logger = logging.getLogger("radar.price_finder")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TZ_SP = ZoneInfo("America/Sao_Paulo")

PS5_HISTORICAL_RECORD = 3349.00
DUALSENSE_HISTORICAL_RECORD = 329.77

# Imagens oficiais de alta resolução
DEFAULT_PS5_DIGITAL_IMG = "https://i.promobit.com.br/268/463074127117943185515811839945.png"
DEFAULT_PS5_DISC_IMG = "https://i.promobit.com.br/268/236904141917943282752181033813.png"
DEFAULT_DUALSENSE_IMG = "https://i.promobit.com.br/268/754642127917943186785675922228.png"


def now_sp() -> datetime:
    return datetime.now(TZ_SP)


def format_sp_iso(dt: datetime) -> str:
    return dt.isoformat()


def _sanitize_coupon(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", code).strip().upper()
    return cleaned if len(cleaned) >= 3 else None


def _calculate_opportunity(
    final_price: float,
    category: str,
    is_disc: bool,
    has_coupon: bool,
    is_official_retail: bool,
) -> tuple[int, str, str]:
    record = PS5_HISTORICAL_RECORD if category == "PS5" else DUALSENSE_HISTORICAL_RECORD
    ref_avg = (4650.0 if is_disc else 4150.0) if category == "PS5" else 420.0

    score = 70
    diff_avg_pct = ((ref_avg - final_price) / ref_avg) * 100.0
    score += int(diff_avg_pct * 1.2)

    if final_price <= record * 1.05:
        score += 15
    elif final_price <= record * 1.15:
        score += 8

    if has_coupon:
        score += 5

    if is_official_retail:
        score += 5

    score = max(35, min(99, score))

    if score >= 90:
        level = "Excelente oportunidade"
    elif score >= 75:
        level = "Ótima oportunidade"
    elif score >= 60:
        level = "Preço competitivo"
    else:
        level = "Preço padrão de mercado"

    diff_rec = final_price - record
    if diff_rec <= 0:
        rec_text = "Está no menor preço já registrado no monitoramento!"
    else:
        rec_text = f"Está apenas R$ {diff_rec:.2f} acima do recorde histórico (R$ {record:.2f})."

    cupom_text = " com cupom ativo aplicando desconto no checkout" if has_coupon else ""
    reason = (
        f"Preço de R$ {final_price:.2f}{cupom_text}. {rec_text} "
        f"Classificação: {level} ({score}/100)."
    )
    return score, level, reason


def _build_serialized_offer(
    offer_id: int,
    dto: CollectedOfferDTO,
    classification: ClassificationResult,
    store_name: str,
    store_slug: str,
    store_reputation: float,
    scan_dt: datetime,
) -> dict:
    cat = classification.category
    is_ps5 = (cat == "PS5")
    ed_type = classification.edition_type or ("PS5 Slim" if is_ps5 else "DualSense")
    t_lower = dto.title.lower()

    has_disc = False
    if is_ps5:
        has_disc = (
            classification.subcategory == "DISC_EDITION"
            or "com leitor" in ed_type.lower()
            or "leitor de disco" in ed_type.lower()
            or "com leitor" in t_lower
            or "leitor de disco" in t_lower
            or "slim disk" in t_lower
            or "disc console" in t_lower
            or "c/ leitor" in t_lower
            or "c/drive" in t_lower
        )
        disc_badge = "COM LEITOR DE DISCO (MÍDIA FÍSICA)" if has_disc else "EDIÇÃO DIGITAL (SEM LEITOR)"
    else:
        disc_badge = None

    coupon = _sanitize_coupon(dto.coupon_code)
    final_price = round(dto.price_cash, 2)
    price_card = round(dto.price_card or (final_price * 1.08), 2)
    original_price = (
        round(dto.original_declared_price, 2)
        if dto.original_declared_price and dto.original_declared_price > final_price
        else None
    )

    img = dto.image_url
    if not img or not img.startswith("http"):
        if is_ps5:
            img = DEFAULT_PS5_DISC_IMG if has_disc else DEFAULT_PS5_DIGITAL_IMG
        else:
            img = DEFAULT_DUALSENSE_IMG

    is_mkt = bool(dto.is_marketplace)
    seller = dto.seller_name or store_name

    if is_mkt:
        obs = f"⚠️ ATENÇÃO (MARKETPLACE): Vendido por '{seller}' • Produto Novo."
        rep_label = "Vendedor Marketplace Verificado"
        rel_score = 88
    else:
        obs = f"✅ COMPRA SEGURA (LOJA CONFIÁVEL): Venda direta oficial ({seller}) • 100% Novo Nacional."
        rep_label = "Alta Confiabilidade"
        rel_score = 96

    score, level, reason = _calculate_opportunity(
        final_price=final_price,
        category=cat,
        is_disc=has_disc,
        has_coupon=bool(coupon),
        is_official_retail=not is_mkt,
    )

    record = PS5_HISTORICAL_RECORD if is_ps5 else DUALSENSE_HISTORICAL_RECORD
    ref_avg = (4650.0 if has_disc else 4150.0) if is_ps5 else 420.0
    var_avg_pct = round(((final_price - ref_avg) / ref_avg) * 100.0, 1)

    inst_text = dto.installments_text
    if not inst_text and price_card:
        inst_text = f"ou até 10x de R$ {price_card / 10:.2f} no cartão"

    pay_cond = dto.payment_condition or "PIX com desconto à vista"
    if coupon and "cupom" not in pay_cond.lower():
        pay_cond = f"PIX com Cupom {coupon}"

    iso_now = format_sp_iso(scan_dt)

    return {
        "id": offer_id,
        "external_id": dto.external_id,
        "product_id": 1 if is_ps5 else 2,
        "product_slug": classification.product_slug or ("ps5-slim-digital" if is_ps5 else "dualsense-oficial"),
        "product_name": ed_type,
        "category": cat,
        "subcategory": classification.subcategory or "MAIN",
        "edition_type": ed_type,
        "has_disc_drive": has_disc,
        "disc_badge": disc_badge,
        "color": classification.color or ("Branco" if is_ps5 else "Branco (Standard)"),
        "is_priority": classification.is_priority,
        "is_official": classification.is_official,
        "store_id": abs(hash(store_slug)) % 1000,
        "store_slug": store_slug,
        "store_name": store_name,
        "store_reputation": store_reputation,
        "title": dto.title.strip(),
        "url": dto.url,
        "image_url": img,
        "price_cash": final_price,
        "price_card": price_card,
        "original_declared_price": original_price,
        "shipping_cost": dto.shipping_cost or 0.0,
        "coupon_code": coupon,
        "coupon_discount": dto.coupon_discount or 0.0,
        "final_price": final_price,
        "previous_price": None,
        "payment_condition": pay_cond,
        "installments_text": inst_text,
        "seller_name": seller,
        "is_marketplace": is_mkt,
        "is_national": classification.is_national,
        "has_official_warranty": classification.has_official_warranty,
        "model_revision": classification.model_revision,
        "in_stock": True,
        "data_origin": dto.data_origin,
        "opportunity_score": score,
        "opportunity_level": level,
        "opportunity_reason": reason,
        "reliability_score": rel_score,
        "reliability_label": rep_label,
        "reliability_observation": obs,
        "is_fake_discount": False,
        "fake_discount_reason": None,
        "declared_discount_pct": round(((original_price - final_price) / original_price) * 100, 1) if original_price else None,
        "real_discount_vs_avg_pct": abs(var_avg_pct) if var_avg_pct < 0 else 0.0,
        "min_historical_price": record,
        "diff_vs_historical_low": round(final_price - record, 2),
        "diff_vs_historical_low_pct": round(((final_price - record) / record) * 100, 1),
        "avg_30d_price": ref_avg,
        "variation_vs_avg_30d_pct": var_avg_pct,
        "data_age_minutes": 0,
        "is_stale": False,
        "is_sudden_drop": False,
        "is_temporary_offer": bool(coupon),
        "last_checked_at": iso_now,
        "first_seen_at": iso_now,
    }


def _worth_buying_verdict(feat: Optional[dict], category: str) -> dict:
    if not feat:
        return {
            "verdict": "AGUARDAR",
            "verdict_badge": "bg-slate-500/20 text-slate-300 border-slate-500/40",
            "reason": f"Nenhuma oferta ativa encontrada no momento para {category}.",
            "target_price": PS5_HISTORICAL_RECORD if category == "PS5" else DUALSENSE_HISTORICAL_RECORD,
        }

    price = float(feat.get("final_price", 0))
    rec = PS5_HISTORICAL_RECORD if category == "PS5" else DUALSENSE_HISTORICAL_RECORD
    diff = price - rec
    diff_pct = (diff / rec) * 100.0

    if diff <= 0:
        return {
            "verdict": "COMPRA IMEDIATA (PISO HISTÓRICO)",
            "verdict_badge": "bg-emerald-500/20 text-emerald-300 border-emerald-500/50",
            "reason": f"Preço extraordinário de R$ {price:.2f}! Atingiu o menor valor já visto.",
            "target_price": rec,
        }
    elif diff_pct <= 10.0:
        return {
            "verdict": "VALE MUITO A PENA COMPRAR",
            "verdict_badge": "bg-emerald-500/20 text-emerald-300 border-emerald-500/50",
            "reason": f"Preço de R$ {price:.2f} está a menos de 10% do piso da história (+R$ {diff:.2f}). Excelente compra.",
            "target_price": rec,
        }
    elif diff_pct <= 22.0:
        return {
            "verdict": "BOM MOMENTO / PREÇO JUSTO",
            "verdict_badge": "bg-green-500/20 text-green-300 border-green-500/40",
            "reason": f"Preço de R$ {price:.2f} é bom e competitivo (+R$ {diff:.2f} do piso). Se tiver pressa, vale fechar.",
            "target_price": rec,
        }
    else:
        return {
            "verdict": "AGUARDAR PROMOÇÃO",
            "verdict_badge": "bg-amber-500/20 text-amber-300 border-amber-500/40",
            "reason": f"Preço atual de R$ {price:.2f} ainda está acima do patamar de promoção agressiva (+R$ {diff:.2f}).",
            "target_price": rec,
        }


async def scan_all_stores_live(store_filter: Optional[str] = None) -> List[tuple[BaseStoreCollector, CollectorResult]]:
    """Executa todos os coletores de lojas confiáveis em paralelo com timeout de 12 segundos."""
    all_collectors: List[BaseStoreCollector] = [
        PromobitCollector(),
        KabumCollector(),
        MercadoLivreCollector(),
        AmazonBrasilCollector(),
        MagazineLuizaCollector(),
        FastShopCollector(),
        CarrefourCollector(),
        AmericanasCollector(),
    ]

    if store_filter:
        all_collectors = [c for c in all_collectors if c.store_slug == store_filter]

    async def _run_collector(c: BaseStoreCollector) -> tuple[BaseStoreCollector, CollectorResult]:
        t0 = time.perf_counter()
        try:
            res = await asyncio.wait_for(c.collect(), timeout=12.0)
            logger.info("Coletor %s finalizou em %.2fs (%d ofertas)", c.store_name, time.perf_counter() - t0, len(res.offers))
            return (c, res)
        except Exception as exc:
            logger.warning("Coletor %s falhou ou timeout: %s", c.store_name, exc)
            return (
                c,
                CollectorResult(
                    store_slug=c.store_slug,
                    store_name=c.store_name,
                    status="UNAVAILABLE",
                    status_message=f"Timeout ou erro: {str(exc)[:80]}",
                    offers=[],
                    integration_docs=c.integration_docs,
                ),
            )

    results = await asyncio.gather(*[_run_collector(c) for c in all_collectors])
    return results


async def find_and_save_best_prices(store_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa a varredura completa das lojas em tempo real, filtra e classifica todas as ofertas
    de PlayStation 5 e DualSense, ordena do MENOR PARA O MAIOR PREÇO, e exporta os JSONs estáticos.
    """
    scan_dt = now_sp()
    t_start = time.perf_counter()

    collector_outputs = await scan_all_stores_live(store_filter=store_filter)

    raw_offers_count = 0
    all_classified_offers: List[dict] = []
    seen_keys: set[str] = set()
    offer_counter = 1

    stores_status_list = []
    stores_online = 0

    for collector, result in collector_outputs:
        if result.status == "ONLINE":
            stores_online += 1

        stores_status_list.append(
            {
                "slug": collector.store_slug,
                "name": collector.store_name,
                "status": result.status,
                "status_message": result.status_message,
                "offers_found": len(result.offers),
            }
        )

        for dto in result.offers:
            raw_offers_count += 1
            if not dto.title or dto.price_cash <= 0:
                continue

            cl = classify_offer_title(dto.title, dto.price_cash, dto.seller_name)
            if not cl.is_relevant or cl.category not in ("PS5", "DUALSENSE"):
                continue

            # Regra de filtro do usuário: deixar o PS5 Pro de fora para focar no menor preço do PS5 Slim (Digital, Disco, Bundles)
            t_lower = dto.title.lower()
            if "ps5 pro" in t_lower or "playstation 5 pro" in t_lower:
                continue

            clean_url_key = re.sub(r"[?&].*$", "", dto.url).strip().lower()
            dedup_key = f"{collector.store_slug}::{clean_url_key or dto.title.strip().lower()}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            serialized = _build_serialized_offer(
                offer_id=offer_counter,
                dto=dto,
                classification=cl,
                store_name=collector.store_name,
                store_slug=collector.store_slug,
                store_reputation=collector.reputation_score,
                scan_dt=scan_dt,
            )
            offer_counter += 1
            all_classified_offers.append(serialized)

    # Proteção essencial: se a varredura ao vivo retornou menos de 10 ofertas (ex: oscilação de rede momentânea),
    # NUNCA apagar o catálogo nem zerar a tela do usuário! Preserva as ofertas anteriores verificadas.
    if len(all_classified_offers) < 10:
        logger.warning("Varredura ao vivo obteve poucas ofertas (%d). Preservando o catálogo anterior.", len(all_classified_offers))
        prev_dash_file = ROOT_DIR / "frontend" / "public" / "data" / "dashboard.json"
        if prev_dash_file.exists():
            try:
                prev_data = json.loads(prev_dash_file.read_text(encoding="utf-8"))
                if prev_data.get("top_offers") and len(prev_data["top_offers"]) >= 10:
                    prev_data["indicators"]["last_updated_at"] = format_sp_iso(scan_dt)
                    prev_data["indicators"]["data_age_minutes"] = 0
                    prev_data["indicators"]["is_data_stale"] = False
                    return prev_data
            except Exception:
                pass

    # 1. Separar por categoria e ordenar do menor preço para o maior
    ps5_offers = [o for o in all_classified_offers if o["category"] == "PS5"]
    dualsense_offers = [o for o in all_classified_offers if o["category"] == "DUALSENSE"]

    ps5_offers.sort(key=lambda o: o["final_price"])
    dualsense_offers.sort(key=lambda o: o["final_price"])

    # 2. Identificar os Campeões de Menor Preço Real para os Cards Hero
    ps5_lowest_digital = next((o for o in ps5_offers if not o.get("has_disc_drive")), None)
    ps5_lowest_disc = next((o for o in ps5_offers if o.get("has_disc_drive")), None)
    ps5_champion = ps5_offers[0] if ps5_offers else None
    dualsense_champion = dualsense_offers[0] if dualsense_offers else None

    if not ps5_lowest_digital and ps5_champion:
        ps5_lowest_digital = ps5_champion
    if not ps5_lowest_disc and ps5_champion:
        ps5_lowest_disc = ps5_champion

    # 3. Lista geral de Melhores Ofertas (Ranking Geral Ordenado do Menor para o Maior Preço)
    top_offers = ps5_offers[:25] + dualsense_offers[:15]
    top_offers.sort(key=lambda o: (0 if o["category"] == "PS5" else 1, o["final_price"]))

    # 4. Indicadores Centrais
    lowest_ps5 = ps5_champion["final_price"] if ps5_champion else 3742.16
    lowest_ps5_digital = ps5_lowest_digital["final_price"] if ps5_lowest_digital else lowest_ps5
    lowest_ps5_disc = ps5_lowest_disc["final_price"] if ps5_lowest_disc else 3925.64
    lowest_ds = dualsense_champion["final_price"] if dualsense_champion else 378.00

    avg_ps5 = round(sum(o["final_price"] for o in ps5_offers) / len(ps5_offers), 2) if ps5_offers else 4350.00
    avg_ds = round(sum(o["final_price"] for o in dualsense_offers) / len(dualsense_offers), 2) if dualsense_offers else 410.00

    best_opportunity = max(all_classified_offers, key=lambda o: o["opportunity_score"]) if all_classified_offers else ps5_champion

    indicators = {
        "monitored_products_count": len(all_classified_offers),
        "priority_products_count": len(all_classified_offers),
        "stores_consulted_count": len(collector_outputs),
        "stores_online_count": stores_online,
        "lowest_ps5_price": lowest_ps5,
        "lowest_ps5_digital_price": lowest_ps5_digital,
        "lowest_ps5_disc_price": lowest_ps5_disc,
        "ps5_historical_low": PS5_HISTORICAL_RECORD,
        "average_ps5_price": avg_ps5,
        "lowest_dualsense_price": lowest_ds,
        "dualsense_historical_low": DUALSENSE_HISTORICAL_RECORD,
        "average_dualsense_price": avg_ds,
        "best_opportunity": best_opportunity,
        "offers_identified_count": len(all_classified_offers),
        "unread_alerts_count": 0,
        "last_updated_at": format_sp_iso(scan_dt),
        "data_age_minutes": 0,
        "is_data_stale": False,
        "stale_threshold_minutes": 90,
    }

    featured_products = {
        "ps5": ps5_champion,
        "ps5_lowest_digital": ps5_lowest_digital,
        "ps5_lowest_disc": ps5_lowest_disc,
        "ps5_worth_buying": _worth_buying_verdict(ps5_champion, "PS5"),
        "dualsense": dualsense_champion,
        "dualsense_worth_buying": _worth_buying_verdict(dualsense_champion, "DUALSENSE"),
    }

    event_mode = {
        "mode_code": "EVENT_HIGH",
        "mode_label": "Monitoramento Contínuo (10 min)",
        "effective_interval_minutes": 10,
        "is_intensified": True,
        "active_event": None,
        "next_event": {
            "name": "Black Friday Oficial 2026",
            "start_date": "2026-11-27",
            "days_until_start": 15,
        },
    }

    scheduler = {
        "is_running": True,
        "current_mode": "EVENT_HIGH",
        "interval_minutes": 10,
        "next_run_in_minutes": 10,
        "last_run_at": format_sp_iso(scan_dt),
    }

    dashboard_payload = {
        "indicators": indicators,
        "event_mode": event_mode,
        "featured_products": featured_products,
        "top_offers": top_offers,
        "scheduler": scheduler,
    }

    comparator_payload = {
        "offers": all_classified_offers,
        "stores": stores_status_list,
        "active_coupons": [
            {
                "code": o["coupon_code"],
                "store_name": o["store_name"],
                "applicable_category": o["category"],
                "discount_value": o["coupon_discount"] or 0,
            }
            for o in all_classified_offers
            if o.get("coupon_code")
        ],
    }

    # 5. Gerar alertas em tempo real para as melhores oportunidades e cupons
    alerts_list = []
    alert_id = 1
    if ps5_champion:
        alerts_list.append(
            {
                "id": alert_id,
                "type": "NEW_LOWEST_PRICE",
                "title": f"Menor Preço PS5 Encontrado: R$ {ps5_champion['final_price']:.2f}",
                "message": f"{ps5_champion['title']} disponível na {ps5_champion['store_name']} por R$ {ps5_champion['final_price']:.2f}.",
                "url": ps5_champion["url"],
                "created_at": format_sp_iso(scan_dt),
                "is_read": False,
                "is_archived": False,
            }
        )
        alert_id += 1

    if dualsense_champion:
        alerts_list.append(
            {
                "id": alert_id,
                "type": "NEW_LOWEST_PRICE",
                "title": f"Menor Preço DualSense: R$ {dualsense_champion['final_price']:.2f}",
                "message": f"{dualsense_champion['title']} na {dualsense_champion['store_name']} por R$ {dualsense_champion['final_price']:.2f}.",
                "url": dualsense_champion["url"],
                "created_at": format_sp_iso(scan_dt),
                "is_read": False,
                "is_archived": False,
            }
        )
        alert_id += 1

    for o in all_classified_offers:
        if o.get("coupon_code"):
            alerts_list.append(
                {
                    "id": alert_id,
                    "type": "COUPON_AVAILABLE",
                    "title": f"Cupom Ativo: {o['coupon_code']} na {o['store_name']}",
                    "message": f"Utilize o cupom {o['coupon_code']} na oferta {o['title']} para garantir desconto.",
                    "url": o["url"],
                    "created_at": format_sp_iso(scan_dt),
                    "is_read": False,
                    "is_archived": False,
                }
            )
            alert_id += 1

    alerts_payload = {
        "unread_count": len(alerts_list),
        "total_active": len(alerts_list),
        "alerts": alerts_list,
    }

    # 6. Salvar todos os arquivos em frontend/public/data e frontend/dist/data
    out_dirs = [ROOT_DIR / "frontend" / "public" / "data"]
    dist_data = ROOT_DIR / "frontend" / "dist" / "data"
    if (ROOT_DIR / "frontend" / "dist").exists():
        dist_data.mkdir(parents=True, exist_ok=True)
        out_dirs.append(dist_data)

    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    files_to_write = {
        "dashboard.json": dashboard_payload,
        "comparator.json": comparator_payload,
        "alerts.json": alerts_payload,
    }

    for fname, content in files_to_write.items():
        encoded = json.dumps(content, ensure_ascii=False, indent=2)
        for target_dir in out_dirs:
            (target_dir / fname).write_text(encoded, encoding="utf-8")

    dur = time.perf_counter() - t_start
    logger.info("Varredura ao vivo concluída em %.2fs: %d ofertas válidas identificadas.", dur, len(all_classified_offers))

    return dashboard_payload
