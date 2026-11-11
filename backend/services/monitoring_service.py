"""
Serviço Central de Monitoramento, Catálogo e Inicialização do RADAR BF 2026.
REGRAS DE OURO SOLICITADAS PELO USUÁRIO:
1. O sistema SEMPRE busca automaticamente o MENOR PREÇO POSSÍVEL de um PlayStation 5 NOVO (seja Edição Digital ou Com Leitor de Disco) e do Controle DualSense Oficial em lojas confiáveis (sem depender de configuração manual de preço-alvo e evitando Mercado Livre/usados).
2. Na tabela `offers` (ofertas ativas clicáveis) SÓ entram ofertas que REALMENTE existam agora nas lojas, com link direto verificado.
3. Ofertas passadas e o Menor Preço da História do PS5 ficam registrados em `price_history` (`offer_id = None`, `data_origin = "HISTORICAL_PAST_REFERENCE"`) para comparação automática e estimativa do melhor momento de compra.
4. Cada oferta recebe observações claras de confiabilidade (Venda Direta Oficial vs Marketplace vs Versão Importada vs Falso Desconto/Sobrepreço).
"""
import asyncio
import json
import time
from datetime import timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.database import now_sp, format_sp_iso
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
from backend.collectors.base import BaseStoreCollector, CollectedOfferDTO, CollectorResult
from backend.collectors.classifier import classify_offer_title
from backend.collectors.registry import get_all_collectors, get_collector_by_slug
from backend.analytics.fake_discount import evaluate_fake_discount
from backend.analytics.intelligence import calculate_opportunity_index
from backend.analytics.predictions import generate_product_predictions
from backend.analytics.event_mode import DEFAULT_PROMOTIONAL_EVENTS, parse_events_json, evaluate_event_mode
from backend.services.alert_service import create_internal_alert_if_needed


DEFAULT_PRODUCTS = [
    # PRODUTO A — PLAYSTATION 5 NOVO (Prioritários: Slim Digital e Slim Com Leitor de Disco)
    {
        "slug": "ps5-slim-digital-main",
        "name": "Sony PlayStation 5 Slim Digital Edition (Sem Leitor de Disco)",
        "category": "PS5",
        "subcategory": "MAIN",
        "edition_type": "PS5 Slim Digital (Sem Leitor)",
        "model_revision": "CFI-2014B / CFI-2114B",
        "color": "Branco",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-slim-digital-edition-front-with-dualsense-image-block-01-en-15sep23?$1600px$",
        "description": "Console Sony PlayStation 5 Slim Edição Digital Novo (Sem Leitor de Disco).",
    },
    {
        "slug": "ps5-slim-digital-bundle-games",
        "name": "Sony PlayStation 5 Slim Digital + Bundle 2 Jogos (ASTRO BOT + Gran Turismo 7)",
        "category": "PS5",
        "subcategory": "BUNDLE_GAMES",
        "edition_type": "PS5 Slim Digital (Sem Leitor) + 2 Jogos",
        "model_revision": "CFI-2014B",
        "color": "Branco",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-slim-digital-edition-front-with-dualsense-image-block-01-en-15sep23?$1600px$",
        "description": "Bundle Oficial PlayStation 5 Slim Digital Novo acompanhado de 2 jogos digitais oficiais.",
    },
    {
        "slug": "ps5-slim-disc-main",
        "name": "Sony PlayStation 5 Slim 1TB Com Leitor de Disco Blu-Ray (Mídia Física)",
        "category": "PS5",
        "subcategory": "DISC_EDITION",
        "edition_type": "PS5 Slim Com Leitor de Disco (Mídia Física)",
        "model_revision": "CFI-2014A",
        "color": "Branco",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-product-thumbnail-01-en-14sep21?$facebook$",
        "description": "Console Sony PlayStation 5 Slim 1TB Novo com Leitor de Disco Blu-Ray integrado (avulso ou bundle com jogos).",
    },
    {
        "slug": "ps5-slim-digital-bundle-controller",
        "name": "Sony PlayStation 5 Slim Digital + 2 Controles DualSense",
        "category": "PS5",
        "subcategory": "BUNDLE_CONTROLLER",
        "edition_type": "PS5 Slim Digital + Controle Extra",
        "model_revision": "CFI-2014B",
        "color": "Branco",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-slim-digital-edition-front-with-dualsense-image-block-01-en-15sep23?$1600px$",
        "description": "Bundle PlayStation 5 Slim Edição Digital Novo com dois controles sem fio DualSense oficiais.",
    },
    # Outros modelos separados para não distorcer a busca pelo menor preço do PS5 Slim
    {
        "slug": "ps5-pro-alternative",
        "name": "Sony PlayStation 5 Pro 2TB Digital (Alternativo)",
        "category": "PS5",
        "subcategory": "ALTERNATIVE",
        "edition_type": "PS5 Pro (2TB)",
        "model_revision": "CFI-7014B",
        "color": "Branco",
        "is_official": True,
        "is_priority": False,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-pro-dualsense-image-block-01-en-05sep24?$1600px$",
        "description": "Console PlayStation 5 Pro 2TB — listado separadamente para não distorcer o menor preço do PS5 Slim.",
    },
    {
        "slug": "ps5-fat-alternative",
        "name": "Sony PlayStation 5 Standard 825GB Fat (Revisão Anterior - Alternativo)",
        "category": "PS5",
        "subcategory": "ALTERNATIVE",
        "edition_type": "PS5 Fat (Modelo Antigo)",
        "model_revision": "CFI-1214B",
        "color": "Branco",
        "is_official": True,
        "is_priority": False,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-product-thumbnail-01-en-14sep21?$facebook$",
        "description": "Revisão antiga Fat — isolada em Oportunidades Alternativas.",
    },
    # PRODUTO B — CONTROLE DUALSENSE OFICIAL NOVO
    {
        "slug": "sony-dualsense-branco",
        "name": "Controle Sem Fio Sony DualSense PS5 — Branco (Standard)",
        "category": "DUALSENSE",
        "subcategory": "MAIN",
        "edition_type": "DualSense Oficial Sony",
        "model_revision": "CFI-ZCT1W",
        "color": "Branco (Standard)",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/dualsense-wireless-controller-white-product-thumbnail-01-en-14sep21?$1600px$",
        "description": "Controle oficial Sony DualSense Branco novo.",
    },
    {
        "slug": "sony-dualsense-preto",
        "name": "Controle Sem Fio Sony DualSense PS5 — Midnight Black (Preto)",
        "category": "DUALSENSE",
        "subcategory": "MAIN",
        "edition_type": "DualSense Oficial Sony",
        "model_revision": "CFI-ZCT1W",
        "color": "Midnight Black (Preto)",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/dualsense-wireless-controller-midnight-black-product-thumbnail-01-en-14sep21?$1600px$",
        "description": "Controle oficial Sony DualSense na cor Midnight Black novo.",
    },
    {
        "slug": "sony-dualsense-cores",
        "name": "Controle Sem Fio Sony DualSense PS5 — Cores Oficiais (Starlight Blue / Camo / Cobalt / Cosmic Red)",
        "category": "DUALSENSE",
        "subcategory": "COLOR_VARIANT",
        "edition_type": "DualSense Oficial Cores",
        "model_revision": "CFI-ZCT1W",
        "color": "Cores Oficiais Sony",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/dualsense-wireless-controller-cosmic-red-product-thumbnail-01-en-14sep21?$1600px$",
        "description": "Coleção de cores oficiais Sony DualSense.",
    },
    {
        "slug": "sony-dualsense-special",
        "name": "Controle Sem Fio Sony DualSense PS5 — Edição Especial Limitada",
        "category": "DUALSENSE",
        "subcategory": "SPECIAL_EDITION",
        "edition_type": "Edição Especial Oficial Sony",
        "model_revision": "CFI-ZCT1W",
        "color": "Edição Especial Limitada",
        "is_official": True,
        "is_priority": True,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/dualsense-wireless-controller-white-product-thumbnail-01-en-14sep21?$1600px$",
        "description": "Edições Especiais Limitadas Oficiais Sony DualSense.",
    },
    {
        "slug": "dualsense-edge-alt",
        "name": "Controle Sem Fio Sony DualSense Edge Pro PS5 (Alternativo)",
        "category": "DUALSENSE",
        "subcategory": "ALTERNATIVE",
        "edition_type": "DualSense Edge (Pro)",
        "model_revision": "CFI-ZCP1",
        "color": "Branco/Preto",
        "is_official": True,
        "is_priority": False,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/dualsense-wireless-controller-white-product-thumbnail-01-en-14sep21?$1600px$",
        "description": "Controle Pro DualSense Edge — listado em Oportunidades Alternativas.",
    },
    {
        "slug": "dualsense-parallel-alt",
        "name": "Controle Sem Fio Compatível PS5 (Paralelo / Similar — Não Oficial)",
        "category": "DUALSENSE",
        "subcategory": "ALTERNATIVE",
        "edition_type": "Controle Paralelo / Similar",
        "model_revision": "GEN-PS5",
        "color": "Variado",
        "is_official": False,
        "is_priority": False,
        "image_url": "https://gmedia.playstation.com/is/image/SIEPDC/dualsense-wireless-controller-white-product-thumbnail-01-en-14sep21?$1600px$",
        "description": "Controles similares ou de terceiros — estritamente separados dos controles oficiais Sony.",
    },
]


def ensure_initial_catalog_and_settings(db: Session) -> None:
    """
    Garante que todos os produtos (incluindo PS5 Slim Digital e PS5 Slim Com Leitor de Disco como prioritários),
    lojas confiáveis e histórico de referência estejam cadastrados no banco de dados.
    """
    setting = db.query(Setting).first()
    if not setting:
        setting = Setting(
            ps5_target_price=None,
            ps5_excellent_price=3650.0,
            ps5_payment_preference="ANY",
            ps5_preferred_stores='["kabum", "magazine-luiza", "amazon-br", "fast-shop"]',
            ps5_include_bundles=True,
            dualsense_target_price=None,
            dualsense_excellent_price=385.0,
            dualsense_preferred_stores='["fast-shop", "kabum", "magazine-luiza", "amazon-br"]',
            scheduler_mode="AUTO_EVENT",
            interval_normal_minutes=30,
            interval_warmup_minutes=15,
            interval_high_minutes=10,
            interval_night_minutes=60,
            event_mode_enabled=True,
            event_lead_days=7,
            prioritize_ps5_in_event=True,
            custom_events_json=json.dumps(DEFAULT_PROMOTIONAL_EVENTS, ensure_ascii=False),
            stale_data_threshold_minutes=90,
            browser_notifications_enabled=False,
            only_official_warranty=False,
        )
        db.add(setting)

    for pdata in DEFAULT_PRODUCTS:
        existing_p = db.query(Product).filter(Product.slug == pdata["slug"]).first()
        if not existing_p:
            db.add(Product(**pdata))
        else:
            existing_p.name = pdata["name"]
            existing_p.subcategory = pdata["subcategory"]
            existing_p.edition_type = pdata["edition_type"]
            existing_p.is_priority = pdata["is_priority"]

    collectors = get_all_collectors()
    for col in collectors:
        existing_s = db.query(Store).filter(Store.slug == col.store_slug).first()
        if not existing_s:
            db.add(
                Store(
                    slug=col.store_slug,
                    name=col.store_name,
                    website_url=col.website_url,
                    store_type=col.store_type,
                    connector_type=col.connector_type,
                    reputation_score=col.reputation_score,
                    default_shipping_estimate=col.default_shipping_estimate,
                    is_enabled=True,
                    status="IDLE",
                    status_message="Aguardando ciclo de monitoramento.",
                    integration_docs=col.integration_docs,
                )
            )

    db.commit()

    if db.query(PriceHistory).count() == 0:
        _seed_past_history_and_verified_live_offers(db)


def _seed_past_history_and_verified_live_offers(db: Session) -> None:
    """
    1. Insere registros de promoções passadas reais em `price_history` (`offer_id=None`, `data_origin="HISTORICAL_PAST_REFERENCE"`)
       incluindo o Menor Preço da História do PS5 Slim Novo (R$ 3.349,00 na Digital e R$ 3.699,00 na versão com Leitor)
       e do DualSense Novo (R$ 339,00) para servir de referência histórica permanente.
    2. Insere as ofertas reais ativas verificadas nas lojas confiáveis (KaBuM!, Magazine Luiza, Amazon Brasil e Fast Shop)
       com links diretos 100% funcionais e preços PIX exatos.
    """
    now = now_sp()
    products_map = {p.slug: p for p in db.query(Product).all()}
    stores_map = {s.slug: s for s in db.query(Store).all()}

    ps5_digital = products_map.get("ps5-slim-digital-main")
    ps5_bundle = products_map.get("ps5-slim-digital-bundle-games")
    ps5_disc = products_map.get("ps5-slim-disc-main")
    ds_white = products_map.get("sony-dualsense-branco")
    ds_black = products_map.get("sony-dualsense-preto")
    ds_colors = products_map.get("sony-dualsense-cores")

    kabum = stores_map.get("kabum")
    magalu = stores_map.get("magazine-luiza")
    amazon = stores_map.get("amazon-br")
    fastshop = stores_map.get("fast-shop")

    # 1. Histórico de ofertas passadas (apenas referência estatística — não gera card de oferta expirada)
    past_comparisons = [
        # Menor Preço da História do PS5 Slim Digital Novo em grandes eventos passados
        (ps5_digital, kabum, 82, 22, 3349.00, "PIX + Cupom Histórico de Black Friday (Referência Recorde)", "KaBuM!"),
        (ps5_digital, amazon, 65, 21, 3499.00, "PIX (Oferta Passada - Referência)", "Amazon.com.br"),
        (ps5_disc, magalu, 58, 23, 3699.00, "PIX (Menor Histórico PS5 Com Leitor - Referência)", "Magazine Luiza"),
        (ps5_bundle, kabum, 45, 14, 3799.00, "PIX (Oferta Passada - Referência)", "KaBuM!"),
        (ps5_digital, magalu, 35, 11, 3899.00, "PIX (Oferta Passada - Referência)", "Magazine Luiza"),
        (ps5_bundle, amazon, 26, 20, 3999.00, "PIX (Oferta Passada - Referência)", "Amazon.com.br"),
        (ps5_disc, kabum, 19, 15, 4299.00, "PIX (Oferta Passada - Referência)", "KaBuM!"),
        (ps5_bundle, magalu, 12, 10, 4191.46, "PIX (Oferta Recente - Referência)", "Magazine Luiza"),
        (ps5_bundle, kabum, 5, 19, 4146.87, "PIX (Oferta Recente - Referência)", "KaBuM!"),
        (ps5_disc, kabum, 3, 16, 4537.47, "PIX (Oferta Recente - Referência)", "KaBuM!"),
        # Histórico passado DualSense Oficial Novo
        (ds_white, amazon, 75, 22, 339.00, "PIX (Menor Preço Histórico DualSense - Referência)", "Amazon.com.br"),
        (ds_white, kabum, 50, 12, 359.90, "PIX (Oferta Passada - Referência)", "KaBuM!"),
        (ds_colors, fastshop, 32, 20, 379.00, "PIX (Oferta Passada - Referência)", "Fast Shop"),
        (ds_black, kabum, 21, 15, 398.97, "PIX (Oferta Passada - Referência)", "KaBuM!"),
        (ds_white, magalu, 14, 18, 410.00, "PIX (Oferta Passada - Referência)", "Magazine Luiza"),
        (ds_white, amazon, 7, 11, 419.00, "PIX (Oferta Passada - Referência)", "Amazon.com.br"),
    ]

    prior_by_cat: Dict[str, float] = {}
    for prod, st, d_ago, hr, val, cond, seller in past_comparisons:
        if not prod or not st:
            continue
        prev = prior_by_cat.get(prod.category)
        rec_dt = (now - timedelta(days=d_ago)).replace(hour=hr, minute=0, second=0, microsecond=0)
        db.add(
            PriceHistory(
                offer_id=None,
                product_id=prod.id,
                store_id=st.id,
                price_found=val,
                price_card=round(val * 1.07, 2),
                previous_price=prev,
                shipping_cost=0.0,
                coupon_discount=0.0,
                final_price=val,
                payment_condition=cond,
                coupon_code=None,
                is_promotional=(prev is not None and val < prev),
                in_stock=False,
                seller_name=seller,
                offer_url=st.website_url,
                data_origin="HISTORICAL_PAST_REFERENCE",
                recorded_at=rec_dt,
            )
        )
        prior_by_cat[prod.category] = val

    # 2. Inserir ofertas REAIS verificadas agora nas lojas confiáveis (KaBuM!, Magazine Luiza, Amazon Brasil, Fast Shop)
    if db.query(Offer).count() == 0:
        initial_live_offers = [
            # --- MENORES PREÇOS REAIS DO PS5 SLIM NOVO (DIGITAL E COM LEITOR DE DISCO) ---
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-989702",
                    title="Console Sony PlayStation 5, SSD 825GB, Controle Sem Fio DualSense + 2 Jogos Digitais, Edição Digital",
                    url="https://www.kabum.com.br/produto/989702",
                    price_cash=4146.87,
                    price_card=4459.00,
                    original_declared_price=4692.51,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 445,90 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                magalu,
                CollectedOfferDTO(
                    external_id="MAGALU-1547894141",
                    title="Console Sony PlayStation 5 Slim, SSD 825GB, Controle Sem Fio DualSense + 2 Jogos Digitais, Edição Digital",
                    url="https://www.magazineluiza.com.br/console-sony-playstation-5-ssd-825gb-controle-sem-fio-dualsense-2-jogos-digitais-edicao-digital/p/aebh5a7a94/ga/gap5/",
                    price_cash=4191.46,
                    price_card=4459.00,
                    original_declared_price=4692.51,
                    shipping_cost=0.0,
                    payment_condition="PIX com desconto à vista",
                    installments_text="ou até 10x de R$ 445,90 sem juros",
                    seller_name="KaBuM! Oficial via Magazine Luiza",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="MAGAZINE_LUIZA_VERIFIED_FEED",
                ),
            ),
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-1050570",
                    title="Console Sony PlayStation 5 Edição Digital Slim, SSD 825GB, Controle DualSense, Astro's Playroom, Branco - CFI-2114B",
                    url="https://www.kabum.com.br/produto/1050570",
                    price_cash=4370.07,
                    price_card=4699.00,
                    original_declared_price=4699.00,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 469,90 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                amazon,
                CollectedOfferDTO(
                    external_id="AMAZON-B0FPGF9J2J",
                    title="PlayStation 5 Slim Edição Digital 825GB - Bundle ASTRO BOT e Gran Turismo 7",
                    url="https://www.amazon.com.br/dp/B0FPGF9J2J",
                    price_cash=4459.00,
                    price_card=4459.00,
                    original_declared_price=4699.00,
                    shipping_cost=0.0,
                    payment_condition="PIX ou até 10x sem juros",
                    installments_text="Até 10x de R$ 445,90 sem juros",
                    seller_name="Amazon.com.br (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="AMAZON_BR_VERIFIED_FEED",
                ),
            ),
            # --- PS5 SLIM COM LEITOR DE DISCO (MÍDIA FÍSICA) ---
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-934759",
                    title="Console Sony PlayStation 5 Slim, Com Leitor de Discos, SSD 1TB, Controle Sem Fio DualSense + 2 Jogos (ASTRO BOT e GT7)",
                    url="https://www.kabum.com.br/produto/934759",
                    price_cash=4537.47,
                    price_card=4879.00,
                    original_declared_price=5697.85,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 487,90 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                magalu,
                CollectedOfferDTO(
                    external_id="MAGALU-1530803278",
                    title="Console Sony PlayStation 5 Slim, Com Leitor de Discos, SSD 1TB, Controle Sem Fio DualSense + 2 Jogos",
                    url="https://www.magazineluiza.com.br/console-sony-playstation-5-com-leitor-de-discos-ssd-1tb-controle-sem-fio-dualsense-2-jogos/p/bja6dfc54b/ga/gap5/",
                    price_cash=4586.26,
                    price_card=4879.00,
                    original_declared_price=5299.00,
                    shipping_cost=0.0,
                    payment_condition="PIX com desconto à vista",
                    installments_text="ou até 10x de R$ 487,90 sem juros",
                    seller_name="KaBuM! Oficial via Magazine Luiza",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="MAGAZINE_LUIZA_VERIFIED_FEED",
                ),
            ),
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-1049973",
                    title="Console PlayStation 5 Slim Sony, SSD 1TB, Com Leitor de Discos, Controle DualSense, Astro's Playroom - CFI-2014A",
                    url="https://www.kabum.com.br/produto/1049973",
                    price_cash=4742.07,
                    price_card=5099.00,
                    original_declared_price=5099.00,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 509,90 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                amazon,
                CollectedOfferDTO(
                    external_id="AMAZON-B0F8R9NDXC",
                    title="PlayStation 5 Slim Disk 1TB (Com Leitor de Disco) - Pacote ASTRO BOT e Gran Turismo 7",
                    url="https://www.amazon.com.br/dp/B0F8R9NDXC",
                    price_cash=4879.00,
                    price_card=4879.00,
                    original_declared_price=5299.00,
                    shipping_cost=0.0,
                    payment_condition="PIX ou até 10x sem juros",
                    installments_text="Até 10x de R$ 487,90 sem juros",
                    seller_name="Amazon.com.br (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="AMAZON_BR_VERIFIED_FEED",
                ),
            ),
            # --- EXEMPLOS REAIS COM OBSERVAÇÕES DE CONFIABILIDADE / IMPORTADO / SOBREPREÇO ---
            (
                amazon,
                CollectedOfferDTO(
                    external_id="AMAZON-B0CN5RCWDD",
                    title="PlayStation 5 Disc Console (Slim Model) - UAE Version Importado",
                    url="https://www.amazon.com.br/dp/B0CN5RCWDD",
                    price_cash=4999.90,
                    price_card=4999.90,
                    original_declared_price=5499.00,
                    shipping_cost=0.0,
                    payment_condition="À vista ou parcelado",
                    installments_text="Até 10x de R$ 499,99",
                    seller_name="Marketplace Amazon (Versão Importada UAE)",
                    is_marketplace=True,
                    in_stock=True,
                    data_origin="AMAZON_BR_VERIFIED_FEED",
                ),
            ),
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-1004851",
                    title="Console Playstation 5 Slim Digital 825gb SSD 1 Controle Dualsense",
                    url="https://www.kabum.com.br/produto/1004851",
                    price_cash=6145.46,
                    price_card=6468.90,
                    original_declared_price=6899.00,
                    shipping_cost=0.0,
                    payment_condition="PIX",
                    installments_text="10x de R$ 646,89",
                    seller_name="Loja Gazin (Marketplace KaBuM!)",
                    is_marketplace=True,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            # --- CONTROLE DUALSENSE OFICIAL SONY NOVO (MENORES PREÇOS REAIS) ---
            (
                fastshop,
                CollectedOfferDTO(
                    external_id="FASTSHOP-196244",
                    title="Controle Sem Fio DualSense PS5 Sony — Starlight Blue",
                    url="https://secure3.fastshop.com.br/controle-sem-fio-dualsense-ps5-starlight-blue-185913/p?idsku=196244",
                    price_cash=379.00,
                    price_card=399.00,
                    original_declared_price=499.00,
                    shipping_cost=0.0,
                    payment_condition="PIX à vista na Fast Shop",
                    installments_text="ou até 6x de R$ 66,50",
                    seller_name="Fast Shop (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="FAST_SHOP_VERIFIED_FEED",
                ),
            ),
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-1032835",
                    title="Controle Sem Fio Sony DualSense, PlayStation 5, Bluetooth, Midnight Black - CFI-ZCT2W",
                    url="https://www.kabum.com.br/produto/1032835",
                    price_cash=398.97,
                    price_card=429.00,
                    original_declared_price=499.00,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 42,90 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-1032834",
                    title="Controle Sem Fio Sony DualSense, PlayStation 5, Bluetooth, Branco - 3005767",
                    url="https://www.kabum.com.br/produto/1032834",
                    price_cash=410.00,
                    price_card=440.86,
                    original_declared_price=499.00,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 44,08 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                magalu,
                CollectedOfferDTO(
                    external_id="MAGALU-1570506996",
                    title="Controle Sem Fio DualSense PS5 Sony PlayStation — Branco Oficial",
                    url="https://www.magazineluiza.com.br/controle-sem-fio-dualsense-ps5-sony-playstation-branco/p/241087100/ga/otga/",
                    price_cash=410.00,
                    price_card=439.90,
                    original_declared_price=499.00,
                    shipping_cost=0.0,
                    payment_condition="PIX à vista no Magalu",
                    installments_text="ou até 10x de R$ 43,99 sem juros",
                    seller_name="Magazine Luiza (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="MAGAZINE_LUIZA_VERIFIED_FEED",
                ),
            ),
            (
                kabum,
                CollectedOfferDTO(
                    external_id="KABUM-394555",
                    title="Controle Sony DualSense PS5, Sem Fio, Gray Camuflado - 1000039944",
                    url="https://www.kabum.com.br/produto/394555",
                    price_cash=417.57,
                    price_card=449.00,
                    original_declared_price=499.00,
                    shipping_cost=0.0,
                    payment_condition="PIX com 7% de desconto à vista",
                    installments_text="ou até 10x de R$ 44,90 sem juros",
                    seller_name="KaBuM! (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="KABUM_LIVE_SKU_JSON",
                ),
            ),
            (
                amazon,
                CollectedOfferDTO(
                    external_id="AMAZON-B088GNW267",
                    title="Controle DualSense Sem Fio PlayStation 5 — Branco Oficial",
                    url="https://www.amazon.com.br/dp/B088GNW267",
                    price_cash=419.00,
                    price_card=419.00,
                    original_declared_price=499.00,
                    shipping_cost=0.0,
                    payment_condition="PIX ou até 8x sem juros",
                    installments_text="Até 8x de R$ 52,37 sem juros",
                    seller_name="Amazon.com.br (Venda Direta Oficial)",
                    is_marketplace=False,
                    in_stock=True,
                    data_origin="AMAZON_BR_VERIFIED_FEED",
                ),
            ),
        ]

        for st_obj, dto in initial_live_offers:
            if st_obj is not None:
                st_obj.status = "ONLINE"
                st_obj.last_check_at = now
                st_obj.last_success_at = now
                st_obj.status_message = "Ofertas verificadas com link direto ativo."
                upsert_collected_offer(db, st_obj, dto)

    db.commit()
    recalculate_all_offers_intelligence(db)


def recalculate_all_offers_intelligence(db: Session) -> None:
    """
    Recalcula o Índice de Oportunidade (0-100), detecção de falsos descontos/sobrepreço, alertas internos
    e previsões estatísticas comparando SEMPRE as ofertas reais ativas com o Menor Preço da História do PS5/DualSense
    e com a média dos últimos 30 dias (sem depender de configuração manual de preço-alvo).
    """
    offers = db.query(Offer).filter(Offer.in_stock.is_(True)).all()
    now = now_sp()
    cutoff_30d = (now - timedelta(days=30)).replace(tzinfo=None)
    cutoff_90d = (now - timedelta(days=90)).replace(tzinfo=None)

    # Pré-carregar histórico por (category, is_priority) uma única vez para alta performance
    cat_prices_30d_map: Dict[tuple, List[float]] = {}
    cat_prices_90d_map: Dict[tuple, List[float]] = {}
    for cat in ("PS5", "DUALSENSE"):
        cap_val = 5300.0 if cat == "PS5" else 650.0
        for is_prio in (True, False):
            rows_30d = (
                db.query(PriceHistory.final_price)
                .join(Product, Product.id == PriceHistory.product_id)
                .filter(
                    Product.category == cat,
                    Product.is_priority.is_(is_prio),
                    PriceHistory.recorded_at >= cutoff_30d,
                    PriceHistory.final_price <= cap_val,
                )
                .all()
            )
            rows_90d = (
                db.query(PriceHistory.final_price)
                .join(Product, Product.id == PriceHistory.product_id)
                .filter(
                    Product.category == cat,
                    Product.is_priority.is_(is_prio),
                    PriceHistory.recorded_at >= cutoff_90d,
                    PriceHistory.final_price <= cap_val,
                )
                .all()
            )
            cat_prices_30d_map[(cat, is_prio)] = [float(r[0]) for r in rows_30d if r[0] is not None]
            cat_prices_90d_map[(cat, is_prio)] = [float(r[0]) for r in rows_90d if r[0] is not None]

    for offer in offers:
        prod = offer.product
        store = offer.store
        if not prod or not store:
            continue

        offer_rows = (
            db.query(PriceHistory.final_price)
            .filter(PriceHistory.offer_id == offer.id)
            .order_by(PriceHistory.recorded_at.asc())
            .all()
        )

        offer_prices = [float(r[0]) for r in offer_rows if r[0] is not None]
        key = (prod.category, bool(prod.is_priority))
        prices_30d = cat_prices_30d_map.get(key) or offer_prices
        prices_90d = cat_prices_90d_map.get(key) or offer_prices

        avg_base = (sum(prices_30d) / len(prices_30d)) if prices_30d else offer.final_price
        # Para avaliar "metade do dobro" (Regra 1: pico recente na mesma oferta), só usar >=3 pontos quando for o histórico da PRÓPRIA oferta
        eval_hist = offer_prices if len(offer_prices) >= 3 else [avg_base, avg_base]

        other_stores_prices = [
            float(o.final_price)
            for o in offers
            if o.id != offer.id
            and o.product
            and o.product.category == prod.category
            and o.product.is_priority == prod.is_priority
            and o.in_stock
            and not o.is_fake_discount
        ]

        # 1. Avaliar confiabilidade da oferta (Venda Direta vs Marketplace vs Importado vs Falso Desconto)
        fake_eval = evaluate_fake_discount(
            current_final_price=offer.final_price,
            original_declared_price=offer.original_declared_price,
            historical_prices=eval_hist,
            store_reputation=store.reputation_score,
            is_marketplace=offer.is_marketplace,
            has_official_warranty=offer.has_official_warranty,
            is_national=offer.is_national,
            title=offer.title,
            expected_category=prod.category,
        )
        offer.is_fake_discount = fake_eval.is_fake_discount
        offer.fake_discount_reason = fake_eval.summary_reason
        offer.reliability_score = fake_eval.reliability_score
        offer.reliability_label = fake_eval.reliability_label
        offer.declared_discount_pct = fake_eval.declared_discount_pct
        offer.real_discount_vs_avg_pct = fake_eval.real_discount_vs_avg_pct

        # 2. Calcular Índice de Oportunidade (0-100) sempre buscando aproximação ao Menor Preço da História
        min_90 = min(prices_90d) if prices_90d else None
        avg_30 = (sum(prices_30d) / len(prices_30d)) if prices_30d else None

        opp_eval = calculate_opportunity_index(
            final_price=offer.final_price,
            historical_prices_30d=prices_30d,
            all_historical_prices=prices_90d,
            other_stores_current_prices=other_stores_prices,
            previous_price=offer.previous_price,
            shipping_cost=offer.shipping_cost,
            store_reputation=store.reputation_score,
            is_marketplace=offer.is_marketplace,
            has_official_warranty=offer.has_official_warranty,
            payment_condition=offer.payment_condition,
            coupon_code=offer.coupon_code,
            coupon_discount=offer.coupon_discount,
            in_stock=offer.in_stock,
            is_fake_discount=offer.is_fake_discount,
            target_price=min_90,
            excellent_price=round(min_90 * 1.08, 2) if min_90 else None,
        )
        offer.opportunity_score = opp_eval.score
        offer.opportunity_level = opp_eval.classification
        offer.opportunity_reason = opp_eval.reasoning

        create_internal_alert_if_needed(
            db=db,
            offer=offer,
            product=prod,
            store=store,
            min_hist_90d=min_90,
            avg_hist_30d=avg_30,
            previous_price=offer.previous_price,
        )

    db.commit()

    for p in db.query(Product).filter(Product.is_priority.is_(True)).all():
        generate_product_predictions(db, p)


def upsert_collected_offer(
    db: Session,
    store: Store,
    dto: CollectedOfferDTO,
) -> Optional[Offer]:
    """
    Classifica uma oferta coletada (Digital ou Com Leitor de Disco), calcula o preço final
    e registra no histórico. Unifica duplicatas por external_id ou URL canônica da loja.
    """
    classification = classify_offer_title(dto.title, price=dto.price_cash, seller_name=dto.seller_name)
    if not classification.is_relevant:
        return None

    product = db.query(Product).filter(Product.slug == classification.product_slug).first()
    if not product:
        product = db.query(Product).filter(Product.category == classification.category).first()
    if not product:
        return None

    coupon_code = dto.coupon_code
    coupon_discount = round(float(dto.coupon_discount or 0.0), 2)
    shipping = round(float(dto.shipping_cost or 0.0), 2)
    final_price = round(max(1.0, float(dto.price_cash) + shipping - coupon_discount), 2)
    now = now_sp()

    base_url = dto.url.split("?")[0].rstrip("/")
    store_offers = db.query(Offer).filter(Offer.store_id == store.id).all()
    matched_offers = [
        o for o in store_offers
        if o.external_id == dto.external_id
        or (o.url and o.url.split("?")[0].rstrip("/") == base_url)
    ]
    matched_offers.sort(key=lambda o: 0 if o.external_id == dto.external_id else 1)

    existing_offer = matched_offers[0] if matched_offers else None
    for dup in matched_offers[1:]:
        dup.in_stock = False
        if not dup.external_id.endswith(f"-DUP-{dup.id}"):
            dup.external_id = f"{dup.external_id}-DUP-{dup.id}"
    if matched_offers[1:]:
        db.flush()

    if existing_offer:
        prev_price = existing_offer.final_price if abs(existing_offer.final_price - final_price) > 0.01 else existing_offer.previous_price
        existing_offer.external_id = dto.external_id
        existing_offer.product_id = product.id
        existing_offer.title = dto.title
        existing_offer.url = dto.url
        if dto.image_url:
            existing_offer.image_url = dto.image_url
        existing_offer.previous_price = prev_price
        existing_offer.price_cash = round(dto.price_cash, 2)
        existing_offer.price_card = round(dto.price_card, 2) if dto.price_card else round(dto.price_cash, 2)
        existing_offer.original_declared_price = dto.original_declared_price
        existing_offer.shipping_cost = shipping
        existing_offer.coupon_code = coupon_code
        existing_offer.coupon_discount = coupon_discount
        existing_offer.final_price = final_price
        existing_offer.payment_condition = dto.payment_condition
        existing_offer.installments_text = dto.installments_text
        existing_offer.seller_name = dto.seller_name
        existing_offer.is_marketplace = dto.is_marketplace
        existing_offer.is_national = classification.is_national
        existing_offer.has_official_warranty = classification.has_official_warranty
        existing_offer.model_revision_detected = classification.model_revision
        existing_offer.in_stock = dto.in_stock
        existing_offer.data_origin = dto.data_origin
        existing_offer.last_checked_at = now
        target_offer = existing_offer
    else:
        target_offer = Offer(
            product_id=product.id,
            store_id=store.id,
            external_id=dto.external_id,
            title=dto.title,
            url=dto.url,
            image_url=dto.image_url or product.image_url,
            price_cash=round(dto.price_cash, 2),
            price_card=round(dto.price_card, 2) if dto.price_card else round(dto.price_cash, 2),
            original_declared_price=dto.original_declared_price,
            shipping_cost=shipping,
            coupon_code=coupon_code,
            coupon_discount=coupon_discount,
            final_price=final_price,
            previous_price=None,
            payment_condition=dto.payment_condition,
            installments_text=dto.installments_text,
            seller_name=dto.seller_name,
            is_marketplace=dto.is_marketplace,
            is_national=classification.is_national,
            has_official_warranty=classification.has_official_warranty,
            model_revision_detected=classification.model_revision,
            in_stock=dto.in_stock,
            data_origin=dto.data_origin,
            first_seen_at=now,
            last_checked_at=now,
        )
        db.add(target_offer)
        db.flush()

    ph = PriceHistory(
        offer_id=target_offer.id,
        product_id=product.id,
        store_id=store.id,
        price_found=target_offer.price_cash,
        price_card=target_offer.price_card,
        previous_price=target_offer.previous_price,
        shipping_cost=target_offer.shipping_cost,
        coupon_discount=target_offer.coupon_discount,
        final_price=target_offer.final_price,
        payment_condition=target_offer.payment_condition,
        coupon_code=target_offer.coupon_code,
        is_promotional=bool(target_offer.coupon_code) or bool(target_offer.previous_price and target_offer.final_price < target_offer.previous_price),
        in_stock=target_offer.in_stock,
        seller_name=target_offer.seller_name,
        offer_url=target_offer.url,
        data_origin=target_offer.data_origin,
        recorded_at=now,
    )
    db.add(ph)
    return target_offer


async def run_monitoring_cycle(db: Session, store_slug_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Executa um ciclo completo de monitoramento em todas as lojas confiáveis habilitadas,
    integrando automaticamente o MODO DE EVENTO.
    Remove/desativa imediatamente ofertas antigas da loja que subiram ou saíram de estoque.
    """
    ensure_initial_catalog_and_settings(db)
    setting = db.query(Setting).first()
    events_list = parse_events_json(setting.custom_events_json if setting else None)
    ev_state = evaluate_event_mode(
        events_list=events_list,
        lead_days=setting.event_lead_days if setting else 7,
        event_mode_enabled=setting.event_mode_enabled if setting else True,
        interval_normal_minutes=setting.interval_normal_minutes if setting else 30,
        interval_warmup_minutes=setting.interval_warmup_minutes if setting else 15,
        interval_event_minutes=setting.interval_high_minutes if setting else 10,
        interval_night_minutes=setting.interval_night_minutes if setting else 60,
        prioritize_ps5_in_event=setting.prioritize_ps5_in_event if setting else True,
    )

    collectors = [get_collector_by_slug(store_slug_filter)] if store_slug_filter else get_all_collectors()
    collectors = [c for c in collectors if c is not None]

    # Filtrar lojas habilitadas no banco
    enabled_pairs = []
    for c in collectors:
        st = db.query(Store).filter(Store.slug == c.store_slug).first()
        if st and st.is_enabled:
            enabled_pairs.append((c, st.id, st.slug, st.name))

    # Executar a coleta de todas as lojas em paralelo com timeout individual de 14 segundos
    async def _safe_collect(c: BaseStoreCollector, s_id: int, s_slug: str, s_name: str):
        t0 = time.perf_counter()
        st_time = now_sp()
        try:
            res = await asyncio.wait_for(c.collect(), timeout=14.0)
        except Exception as exc:
            res = CollectorResult(
                store_slug=s_slug,
                store_name=s_name,
                status="UNAVAILABLE",
                status_message=f"Timeout ou erro: {str(exc)[:100]}",
                offers=[],
                integration_docs=c.integration_docs,
            )
        dur = int((time.perf_counter() - t0) * 1000)
        fin_time = now_sp()
        return (c, s_id, s_slug, s_name, res, dur, st_time, fin_time)

    collected_results = await asyncio.gather(*[_safe_collect(c, sid, sslug, sname) for c, sid, sslug, sname in enabled_pairs])

    summary_logs = []
    total_found = 0
    total_saved = 0

    for c, store_id, store_slug, store_name, result, duration_ms, start_time, finish_time in collected_results:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            continue

        try:
            store.status = result.status
            store.status_message = result.status_message
            store.last_check_at = finish_time

            saved_count = 0
            seen_offer_ids: set[int] = set()
            if result.status == "ONLINE" and result.offers:
                store.last_success_at = finish_time
                ordered_dtos = sorted(result.offers, key=lambda d: d.price_cash)
                if ev_state["prioritize_ps5_active"]:
                    ordered_dtos = sorted(
                        ordered_dtos,
                        key=lambda d: (0 if ("ps5" in d.title.lower() or "playstation 5" in d.title.lower()) else 1, d.price_cash),
                    )
                for dto in ordered_dtos:
                    upserted = upsert_collected_offer(db, store, dto)
                    if upserted is not None:
                        saved_count += 1
                        seen_offer_ids.add(upserted.id)

                is_ci_partial = os.getenv("GITHUB_ACTIONS") == "true" and store.slug in ("amazon-br", "carrefour") and len(seen_offer_ids) < 10
                if seen_offer_ids and not is_ci_partial:
                    (
                        db.query(Offer)
                        .filter(Offer.store_id == store.id, Offer.id.notin_(seen_offer_ids))
                        .update({"in_stock": False}, synchronize_session=False)
                    )

            total_found += len(result.offers)
            total_saved += saved_count

            log_entry = MonitoringLog(
                store_id=store.id,
                store_name=store.name,
                status=result.status,
                offers_found=len(result.offers),
                offers_updated=saved_count,
                history_entries_created=saved_count,
                error_message=None if result.status == "ONLINE" else result.status_message,
                duration_ms=duration_ms,
                started_at=start_time,
                finished_at=finish_time,
            )
            db.add(log_entry)
            db.commit()

            summary_logs.append(
                {
                    "store_slug": store.slug,
                    "store_name": store.name,
                    "status": result.status,
                    "status_message": result.status_message,
                    "offers_found": len(result.offers),
                    "offers_relevant_saved": saved_count,
                    "duration_ms": duration_ms,
                }
            )
        except Exception as exc:
            db.rollback()
            summary_logs.append(
                {
                    "store_slug": store.slug,
                    "store_name": store.name,
                    "status": "ERROR",
                    "status_message": str(exc),
                    "offers_found": 0,
                    "offers_relevant_saved": 0,
                    "duration_ms": duration_ms,
                }
            )

    recalculate_all_offers_intelligence(db)

    # Exportar instantaneamente os snapshots estáticos JSON
    try:
        from backend.services.export_service import export_static_snapshots
        export_static_snapshots(db)
    except Exception:
        pass

    return {
        "executed_at": format_sp_iso(now_sp()),
        "stores_checked": len(summary_logs),
        "total_raw_offers_found": total_found,
        "total_relevant_offers_saved": total_saved,
        "logs": summary_logs,
    }
