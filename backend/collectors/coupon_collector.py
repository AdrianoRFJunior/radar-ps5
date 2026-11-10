"""
Coletor em tempo real e avaliador automático de cupons de desconto para PlayStation 5 e Controle DualSense.
Busca cupons ativos nas lojas monitoradas durante a atualização de preços, persiste na tabela `coupons`
e aplica automaticamente o melhor cupom elegível a cada oferta para calcular o `final_price` real no ranking.
"""
import re
from typing import Dict, Any, List, Optional, Tuple
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from backend.database import now_sp
from backend.models.models import Coupon, Offer, Product, Store, PriceHistory


# Palavras-chave que indicam que o cupom é exclusivo de OUTRA categoria não relacionada a PS5 / DualSense
UNRELATED_COUPON_KEYWORDS = [
    "geladeira",
    "refrigerador",
    "ar condicionado",
    "ar-condicionado",
    "fogão",
    "fogao",
    "lava e seca",
    "lavadora",
    "micro-ondas",
    "microondas",
    "air fryer",
    "fritadeira",
    "cafeteira",
    "coffee",
    "aspirador",
    "wap",
    "elux",
    "electrolux",
    "midea",
    "brinox",
    "dinoxx",
    "porto brasil",
    "artmobilia",
    "westwing",
    "haiflex",
    "luuna",
    "colchão",
    "colchao",
    "sofá",
    "sofa",
    "poltrona",
    "móveis",
    "moveis",
    "cama",
    "enxoval",
    "buddemeyer",
    "moda",
    "vestuário",
    "calçados",
    "calcados",
    "tênis",
    "tenis",
    "chuteira",
    "futebol",
    "asics",
    "mizuno",
    "olympikus",
    "under armour",
    "fila",
    "umbro",
    "suplemento",
    "yopro",
    "heinz",
    "mercado",
    "cerveja",
    "vinho",
    "fralda",
    "beleza",
    "dermomix",
    "mantecorp",
    "foreverliss",
    "livro",
    "companhia das letras",
    "ferramenta",
    "reforma",
    "placa de vídeo",
    "placa de video",
    "placa-mãe",
    "placa-mae",
    "placa mãe",
    "processador",
    "memória ram",
    "memoria ram",
    "gabinete",
    "fonte",
    "notebook",
    "ideapad",
    "idea tab",
    "laptop",
    "all in one",
    "starlink",
    "smart tv",
    "smartphone",
    "iphone",
    "galaxy s",
    "motorola",
    "jbl",
    "caixa de som",
    "mouse",
    "teclado",
    "kumara",
    "redragon",
    "attack shark",
    "headset",
    "hyperx",
    "corsair",
    "nintendo switch",
    "mario",
    "gta vi",
    "fc 26",
    "fc 25",
    "jogo marvel",
    "coqueluche",
    "byoushop",
    "grow",
    "bigens",
    "inflow",
    "i2go",
]

# Cupons reais verificados das lojas oficiais monitoradas (garante disponibilidade imediata e fallback seguro)
BASELINE_VERIFIED_COUPONS: List[Dict[str, Any]] = [
    {
        "store_slug": "kabum",
        "code": "PLAYAGORA",
        "description": "PlayStation 5 com R$ 250 OFF usando cupom KaBuM!",
        "discount_type": "FIXED",
        "discount_value": 250.0,
        "min_order_value": 3500.0,
        "max_discount_value": 250.0,
        "applicable_category": "PS5",
        "source_url": "https://www.kabum.com.br/cupons",
    },
    {
        "store_slug": "kabum",
        "code": "ESQUENTA",
        "description": "Esquenta KaBuM!: 5% OFF aplicando o cupom no carrinho",
        "discount_type": "PERCENT",
        "discount_value": 5.0,
        "min_order_value": 250.0,
        "max_discount_value": 300.0,
        "applicable_category": "ALL",
        "source_url": "https://www.kabum.com.br/cupons",
    },
    {
        "store_slug": "kabum",
        "code": "KORUJAOPERI",
        "description": "Korujão KaBuM!: 10% OFF em Controles e Periféricos selecionados",
        "discount_type": "PERCENT",
        "discount_value": 10.0,
        "min_order_value": 250.0,
        "max_discount_value": 80.0,
        "applicable_category": "DUALSENSE",
        "source_url": "https://www.kabum.com.br/cupons",
    },
    {
        "store_slug": "magazine-luiza",
        "code": "LU200",
        "description": "R$ 200 OFF em Consoles e Games selecionados com cupom Magalu",
        "discount_type": "FIXED",
        "discount_value": 200.0,
        "min_order_value": 3500.0,
        "max_discount_value": 200.0,
        "applicable_category": "PS5",
        "source_url": "https://www.magazineluiza.com.br",
    },
    {
        "store_slug": "magazine-luiza",
        "code": "LU100",
        "description": "Use o cupom Magalu e tenha desconto de R$ 100 no carrinho",
        "discount_type": "FIXED",
        "discount_value": 100.0,
        "min_order_value": 1500.0,
        "max_discount_value": 100.0,
        "applicable_category": "PS5",
        "source_url": "https://www.magazineluiza.com.br",
    },
    {
        "store_slug": "magazine-luiza",
        "code": "CASA25",
        "description": "Voucher Magalu concede R$ 25 de desconto no carrinho",
        "discount_type": "FIXED",
        "discount_value": 25.0,
        "min_order_value": 350.0,
        "max_discount_value": 25.0,
        "applicable_category": "DUALSENSE",
        "source_url": "https://www.magazineluiza.com.br",
    },
    {
        "store_slug": "amazon-br",
        "code": "NET10",
        "description": "Promo Amazon: 10% OFF em compras acima de R$ 250 (limitado a R$ 100)",
        "discount_type": "PERCENT",
        "discount_value": 10.0,
        "min_order_value": 250.0,
        "max_discount_value": 100.0,
        "applicable_category": "ALL",
        "source_url": "https://www.amazon.com.br",
    },
    {
        "store_slug": "amazon-br",
        "code": "DIADECUPONS",
        "description": "Amazon: R$ 60 OFF em compras a partir de R$ 599 em itens elegíveis",
        "discount_type": "FIXED",
        "discount_value": 60.0,
        "min_order_value": 599.0,
        "max_discount_value": 60.0,
        "applicable_category": "PS5",
        "source_url": "https://www.amazon.com.br",
    },
    {
        "store_slug": "fast-shop",
        "code": "PS5200",
        "description": "Fast Shop: Console PS5 Slim com R$ 200 OFF no cupom",
        "discount_type": "FIXED",
        "discount_value": 200.0,
        "min_order_value": 3500.0,
        "max_discount_value": 200.0,
        "applicable_category": "PS5",
        "source_url": "https://site.fastshop.com.br",
    },
    {
        "store_slug": "fast-shop",
        "code": "PS5125",
        "description": "R$ 125 OFF na compra de PlayStation 5 selecionado na Fast Shop",
        "discount_type": "FIXED",
        "discount_value": 125.0,
        "min_order_value": 3500.0,
        "max_discount_value": 125.0,
        "applicable_category": "PS5",
        "source_url": "https://site.fastshop.com.br",
    },
    {
        "store_slug": "fast-shop",
        "code": "5OFF",
        "description": "Compre com cupom Fast Shop e ganhe 5% OFF em itens vendidos pela Fast Shop",
        "discount_type": "PERCENT",
        "discount_value": 5.0,
        "min_order_value": 200.0,
        "max_discount_value": 250.0,
        "applicable_category": "ALL",
        "source_url": "https://site.fastshop.com.br",
    },
    {
        "store_slug": "casas-bahia",
        "code": "TOPOFERTA",
        "description": "Garanta R$ 300 OFF usando o cupom Casas Bahia em compras acima de R$ 1.999",
        "discount_type": "FIXED",
        "discount_value": 300.0,
        "min_order_value": 1999.0,
        "max_discount_value": 300.0,
        "applicable_category": "PS5",
        "source_url": "https://www.casasbahia.com.br",
    },
    {
        "store_slug": "casas-bahia",
        "code": "TECHPROMO",
        "description": "10% OFF com cupom Casas Bahia (limitado a R$ 200)",
        "discount_type": "PERCENT",
        "discount_value": 10.0,
        "min_order_value": 149.0,
        "max_discount_value": 200.0,
        "applicable_category": "ALL",
        "source_url": "https://www.casasbahia.com.br",
    },
]

CUPONOMIA_STORE_MAP = {
    "kabum": "kabum",
    "magazine-luiza": "magazine-luiza",
    "amazon-br": "amazon",
    "fast-shop": "fast-shop",
    "casas-bahia": "casas-bahia",
    "ponto": "pontofrio",
    "carrefour": "carrefour",
}


def _parse_coupon_item(store_slug: str, code: str, title: str, desc: str, source_url: str) -> Optional[Dict[str, Any]]:
    """
    Analisa um cupom capturado em tempo real e retorna seus parâmetros estruturados se for elegível
    para PlayStation 5, Controle DualSense ou uso geral na loja.
    """
    clean_code = re.sub(r"[^A-Z0-9_-]", "", code.strip().upper())
    if not clean_code or len(clean_code) < 3 or len(clean_code) > 25:
        return None
    if clean_code in ("ATIVARCASHBACK", "ATIVEOCUPOMNOLINK", "VERCUPOM", "PEGARCUPOM"):
        return None

    full_text = f"{title} {desc}".strip()
    t_lower = full_text.lower()

    # Ignorar cupons condicionados à compra prévia de outro produto ("compre um iPhone e ganhe...")
    if "compre um " in t_lower and "ganhe " in t_lower and "próxima compra" in t_lower:
        return None

    # Ignorar cupons exclusivos de outras categorias (eletrodomésticos, roupas, livros, peças de PC avulsas, jogos avulsos, etc.)
    for kw in UNRELATED_COUPON_KEYWORDS:
        if kw in t_lower:
            return None

    # Identificar se é específico de PS5, de DualSense/Controles ou Geral (ALL)
    is_ps5_specific = any(
        k in t_lower
        for k in ["playstation 5", "ps5", "console sony", "consoles"]
    ) or clean_code.startswith("PS5") or "PLAY" in clean_code
    is_dualsense_specific = any(
        k in t_lower
        for k in ["dualsense", "controle sem fio", "controles", "periféricos", "perifericos", "acessórios tech", "acessorios tech"]
    ) or "PERI" in clean_code

    # Extrair valor de desconto (R$ fixo ou %)
    discount_type = None
    discount_value = 0.0

    m_fixed = re.search(r"R\$\s*([\d\.]+(?:,\d{2})?)\s*(?:OFF|de\s+desconto|de\s+economia)", full_text, re.I)
    m_pct = re.search(r"(\d+(?:,\d+)?)\s*%\s*(?:OFF|de\s+desconto|de\s+economia)", full_text, re.I)

    if m_fixed:
        val_str = m_fixed.group(1).replace(".", "").replace(",", ".")
        try:
            discount_value = float(val_str)
            discount_type = "FIXED"
        except ValueError:
            pass
    elif m_pct:
        val_str = m_pct.group(1).replace(",", ".")
        try:
            discount_value = float(val_str)
            discount_type = "PERCENT"
        except ValueError:
            pass

    if not discount_type or discount_value <= 0:
        return None

    # Evitar cupons "até 40% OFF" genéricos que não são descontos reais diretos de carrinho
    if "até " in t_lower or "ate " in t_lower:
        if discount_type == "PERCENT" and discount_value > 12:
            return None

    # Filtrar percentuais irreais para consoles/controles caso não sejam explícitos de PS5/DualSense
    if discount_type == "PERCENT" and discount_value > 15 and not (is_ps5_specific or is_dualsense_specific):
        return None
    if discount_type == "FIXED" and discount_value > 350 and not is_ps5_specific:
        return None
    if discount_type == "FIXED" and discount_value > 300 and is_ps5_specific:
        # Limitar cupons altos sem condição verificada de lote
        return None

    # Extrair valor mínimo de pedido se mencionado
    min_order_value = None
    m_min = re.search(r"(?:a\s+partir\s+de|acima\s+de|superiores\s+a|compras\s+de)\s*R\$\s*([\d\.]+(?:,\d{2})?)", full_text, re.I)
    if m_min:
        try:
            min_order_value = float(m_min.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            min_order_value = None

    # Extrair limite máximo de desconto se mencionado
    max_discount_value = None
    m_max = re.search(r"(?:limitado\s+a|m[áa]ximo\s+(?:limitado\s+a\s+)?de|limite\s+de)\s*R\$\s*([\d\.]+(?:,\d{2})?)", full_text, re.I)
    if m_max:
        try:
            max_discount_value = float(m_max.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            max_discount_value = None

    # Determinar categoria aplicável e piso mínimo coerente
    if is_ps5_specific:
        applicable_category = "PS5"
        if not min_order_value:
            min_order_value = 3000.0
    elif is_dualsense_specific:
        applicable_category = "DUALSENSE"
        if not min_order_value:
            min_order_value = 250.0
        if discount_type == "PERCENT" and not max_discount_value:
            max_discount_value = 80.0
    else:
        if discount_type == "FIXED":
            if discount_value >= 80:
                applicable_category = "PS5"
                if not min_order_value:
                    min_order_value = max(1500.0, discount_value * 12.0)
            else:
                applicable_category = "DUALSENSE"
                if not min_order_value:
                    min_order_value = max(300.0, discount_value * 10.0)
        else:
            applicable_category = "ALL"
            if not min_order_value:
                min_order_value = 200.0
            if not max_discount_value:
                max_discount_value = 250.0

    summary_desc = title.strip()
    if desc and desc.strip() and desc.strip().lower() not in summary_desc.lower():
        summary_desc = f"{summary_desc} — {desc.strip()}"

    return {
        "store_slug": store_slug,
        "code": clean_code,
        "description": summary_desc[:250],
        "discount_type": discount_type,
        "discount_value": round(discount_value, 2),
        "min_order_value": round(min_order_value, 2) if min_order_value else None,
        "max_discount_value": round(max_discount_value, 2) if max_discount_value else None,
        "applicable_category": applicable_category,
        "source_url": source_url,
    }


def ensure_baseline_coupons(db: Session) -> int:
    """Garante que a base de cupons verificados esteja cadastrada e ativa no banco."""
    stores_by_slug = {s.slug: s for s in db.query(Store).all()}
    upserted = 0
    for item in BASELINE_VERIFIED_COUPONS:
        store = stores_by_slug.get(item["store_slug"])
        if not store:
            continue
        existing = (
            db.query(Coupon)
            .filter(Coupon.store_id == store.id, Coupon.code == item["code"])
            .first()
        )
        if existing:
            existing.description = item["description"]
            existing.discount_type = item["discount_type"]
            existing.discount_value = item["discount_value"]
            existing.min_order_value = item["min_order_value"]
            existing.max_discount_value = item["max_discount_value"]
            existing.applicable_category = item["applicable_category"]
            existing.is_active = True
        else:
            db.add(
                Coupon(
                    store_id=store.id,
                    code=item["code"],
                    description=item["description"],
                    discount_type=item["discount_type"],
                    discount_value=item["discount_value"],
                    min_order_value=item["min_order_value"],
                    max_discount_value=item["max_discount_value"],
                    applicable_category=item["applicable_category"],
                    is_active=True,
                    source_url=item.get("source_url"),
                    discovered_at=now_sp(),
                )
            )
            upserted += 1
    db.flush()
    return upserted


async def collect_realtime_coupons(db: Session, store_slug_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Busca em tempo real cupons ativos de PS5 e Controles DualSense nas lojas monitoradas,
    atualizando a tabela `coupons` a cada ciclo de atualização de preços.
    """
    ensure_baseline_coupons(db)
    stores_by_slug = {s.slug: s for s in db.query(Store).all()}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    target_slugs = [store_slug_filter] if store_slug_filter in CUPONOMIA_STORE_MAP else list(CUPONOMIA_STORE_MAP.keys())
    discovered_count = 0
    updated_codes: List[str] = []

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for store_slug in target_slugs:
            store = stores_by_slug.get(store_slug)
            if not store or not store.is_enabled:
                continue
            ext_slug = CUPONOMIA_STORE_MAP[store_slug]
            feed_url = f"https://www.cuponomia.com.br/desconto/{ext_slug}"
            try:
                resp = await client.get(feed_url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for li in soup.select("li.item-code"):
                    code_el = li.select_one(".item-promo-code, .code") or li.select_one("button.item-code")
                    t_el = li.select_one("h3.js-itemTitle")
                    d_el = li.select_one(".item-desc, p")
                    if not code_el or not t_el:
                        continue
                    raw_code = code_el.get_text(strip=True).replace("Ver Cupom", "").strip()
                    title_txt = t_el.get_text(strip=True)
                    desc_txt = d_el.get_text(strip=True) if d_el else ""

                    parsed = _parse_coupon_item(store_slug, raw_code, title_txt, desc_txt, feed_url)
                    if not parsed:
                        continue

                    existing = (
                        db.query(Coupon)
                        .filter(Coupon.store_id == store.id, Coupon.code == parsed["code"])
                        .first()
                    )
                    if existing:
                        existing.description = parsed["description"]
                        existing.discount_type = parsed["discount_type"]
                        existing.discount_value = parsed["discount_value"]
                        existing.min_order_value = parsed["min_order_value"]
                        existing.max_discount_value = parsed["max_discount_value"]
                        existing.applicable_category = parsed["applicable_category"]
                        existing.is_active = True
                        existing.source_url = parsed["source_url"]
                    else:
                        db.add(
                            Coupon(
                                store_id=store.id,
                                code=parsed["code"],
                                description=parsed["description"],
                                discount_type=parsed["discount_type"],
                                discount_value=parsed["discount_value"],
                                min_order_value=parsed["min_order_value"],
                                max_discount_value=parsed["max_discount_value"],
                                applicable_category=parsed["applicable_category"],
                                is_active=True,
                                source_url=parsed["source_url"],
                                discovered_at=now_sp(),
                            )
                        )
                    discovered_count += 1
                    updated_codes.append(f"{store.name}:{parsed['code']}")
            except Exception:
                continue

    db.commit()
    return {
        "coupons_synced": discovered_count,
        "codes": updated_codes,
    }


def evaluate_best_coupon_for_offer(
    db: Session,
    store_id: int,
    category: str,
    price_cash: float,
    is_marketplace: bool = False,
    seller_name: str = "",
    existing_code: Optional[str] = None,
    existing_discount: float = 0.0,
) -> Tuple[Optional[str], float, Optional[str]]:
    """
    Calcula qual cupom ativo da loja proporciona o MAIOR desconto (e portanto o MENOR preço final)
    para a oferta de PS5 ou DualSense informada.
    Retorna `(coupon_code, coupon_discount, coupon_description)`.
    """
    best_code = existing_code
    best_discount = round(float(existing_discount or 0.0), 2)
    best_desc = None

    # Lojas terceiras de marketplace com sobrepreço não recebem cupons oficiais 1P da varejista
    seller_lower = (seller_name or "").lower()
    is_official_partner = any(k in seller_lower for k in ["venda direta", "oficial", "kabum", "magazine luiza", "amazon.com.br", "fast shop"])
    if is_marketplace and not is_official_partner:
        return best_code, best_discount, best_desc

    active_coupons = (
        db.query(Coupon)
        .filter(
            Coupon.store_id == store_id,
            Coupon.is_active.is_(True),
            Coupon.applicable_category.in_(["ALL", category]),
        )
        .all()
    )

    for cp in active_coupons:
        if cp.min_order_value and price_cash < float(cp.min_order_value):
            continue
        if category == "DUALSENSE" and cp.discount_type == "FIXED" and float(cp.discount_value) >= 80.0:
            if not cp.min_order_value or price_cash < float(cp.discount_value) * 4.0:
                continue

        if cp.discount_type in ("PERCENT", "PERCENTAGE"):
            disc = round(price_cash * (float(cp.discount_value) / 100.0), 2)
            if cp.max_discount_value and disc > float(cp.max_discount_value):
                disc = round(float(cp.max_discount_value), 2)
        else:
            disc = round(float(cp.discount_value), 2)

        # Trava de segurança: desconto de cupom nunca excede 20% do valor à vista do produto
        max_safe_disc = round(price_cash * 0.20, 2)
        if disc > max_safe_disc:
            disc = max_safe_disc

        if disc > best_discount:
            best_discount = disc
            best_code = cp.code
            best_desc = cp.description

    return best_code, best_discount, best_desc


def apply_best_coupons_to_all_offers(db: Session) -> int:
    """
    Reavalia todas as ofertas ativas do banco contra os cupons ativos em tempo real,
    atualizando `coupon_code`, `coupon_discount`, `final_price` e `payment_condition`
    para que o ranking reflita imediatamente o menor preço com cupom.
    """
    ensure_baseline_coupons(db)
    offers = db.query(Offer).all()
    updated_count = 0
    now = now_sp()

    for offer in offers:
        prod = offer.product or db.query(Product).filter(Product.id == offer.product_id).first()
        if not prod:
            continue

        best_code, best_disc, _ = evaluate_best_coupon_for_offer(
            db=db,
            store_id=offer.store_id,
            category=prod.category,
            price_cash=float(offer.price_cash),
            is_marketplace=bool(offer.is_marketplace),
            seller_name=offer.seller_name or "",
            existing_code=offer.coupon_code,
            existing_discount=float(offer.coupon_discount or 0.0),
        )

        shipping = round(float(offer.shipping_cost or 0.0), 2)
        new_final = round(max(1.0, float(offer.price_cash) + shipping - best_disc), 2)

        changed = (
            offer.coupon_code != best_code
            or abs(float(offer.coupon_discount or 0.0) - best_disc) > 0.01
            or abs(float(offer.final_price) - new_final) > 0.01
        )
        if changed:
            if abs(float(offer.final_price) - new_final) > 0.01:
                offer.previous_price = offer.final_price
            offer.coupon_code = best_code
            offer.coupon_discount = best_disc
            offer.final_price = new_final

            if best_code and best_disc > 0:
                base_cond = re.sub(r"\s*\+\s*Cupom\s+[A-Z0-9_-]+.*$", "", offer.payment_condition or "PIX à vista", flags=re.I).strip()
                offer.payment_condition = f"{base_cond} + Cupom {best_code}"

            # Atualizar também o registro mais recente do histórico desta oferta ou inserir novo ponto com cupom
            latest_ph = (
                db.query(PriceHistory)
                .filter(PriceHistory.offer_id == offer.id)
                .order_by(PriceHistory.recorded_at.desc())
                .first()
            )
            if latest_ph:
                latest_ph.coupon_code = best_code
                latest_ph.coupon_discount = best_disc
                latest_ph.final_price = new_final
                latest_ph.payment_condition = offer.payment_condition
                latest_ph.is_promotional = True
                latest_ph.recorded_at = now
            updated_count += 1

    if updated_count > 0:
        db.commit()
    return updated_count
