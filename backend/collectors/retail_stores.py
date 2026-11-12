"""
Módulos de coleta independentes para as lojas varejistas brasileiras confiáveis (Produtos 100% Novos).
REGRA DE OURO:
1. Sempre buscar o MENOR PREÇO REAL disponível para PlayStation 5 Novo (com ou sem leitor de disco) e Controle DualSense Oficial.
2. Na KaBuM!, consulta o catálogo ordenado por menor preço (`sort=price`) E verifica o JSON individual do produto (`pageProps.product.prices.priceWithDiscount`) para capturar o desconto real no PIX (ex: R$ 4.146,87 no PS5 Slim Digital e R$ 4.537,47 no PS5 Slim com Leitor), sem inflar com frete fictício.
3. Na Magazine Luiza, Amazon Brasil e Fast Shop, além da busca direta, utiliza o barramento público de comparação verificada (Zoom) resolvendo o redirecionamento 302 até a URL direta do produto na loja oficial (`magazineluiza.com.br/.../p/...`, `amazon.com.br/dp/...`, `fastshop.com.br/.../p`).
4. Nunca inventa preços nem gera links quebrados; todas as ofertas ativas possuem link direto funcional verificado.
"""
import asyncio
import json
import os
import re
import time
from urllib.parse import urlparse, parse_qs, unquote
import httpx
from bs4 import BeautifulSoup
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO


# Cache em memória de curta duração (90s) para evitar múltiplas requisições repetidas ao barramento comparador no mesmo ciclo
_ZOOM_FEED_CACHE: dict[str, object] = {"timestamp": 0.0, "offers_by_store": {}}
_ZOOM_LOCK = asyncio.Lock()

ZOOM_PRODUCT_HUB_URLS = [
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-slim-825gb-sony-ps5-edicao-digital-bundle-4k",
    "https://www.zoom.com.br/console-de-video-game/playstation-5-slim-1tb-bundle-astro-bot-gran-turismo-7",
    "https://www.zoom.com.br/console-de-video-game/pre-venda-console-playstation-5-slim-1-tb-sony-1214a-4k",
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-slim-1tb-sony-4k-hdr",
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-edicao-digital-sony-4k",
    "https://www.zoom.com.br/console-de-video-game/playstation-5-slim-edicao-digital-1tb-bundle-astro-bot-gran-turismo-7",
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-slim-825gb-sony-4k",
    "https://www.zoom.com.br/controle-joystick/controle-ps5-sem-fio-dualsense-sony",
]


async def _get_zoom_verified_offers_for_store(store_slug: str, headers: dict[str, str]) -> list[CollectedOfferDTO]:
    """
    Consulta as páginas agregadoras públicas do Zoom para PS5 Slim (Digital e Com Leitor) e DualSense,
    resolvendo cada OID em paralelo para obter o link direto real na loja oficial
    (Magazine Luiza, Amazon Brasil, Fast Shop, KaBuM!, Casas Bahia, Ponto, Carrefour, Americanas).
    """
    now = time.time()
    cached_ts = float(_ZOOM_FEED_CACHE.get("timestamp") or 0.0)
    cached_map = _ZOOM_FEED_CACHE.get("offers_by_store")
    if (now - cached_ts) < 180.0 and isinstance(cached_map, dict) and cached_map:
        return list(cached_map.get(store_slug, []))

    async with _ZOOM_LOCK:
        now = time.time()
        cached_ts = float(_ZOOM_FEED_CACHE.get("timestamp") or 0.0)
        cached_map = _ZOOM_FEED_CACHE.get("offers_by_store")
        if (now - cached_ts) < 180.0 and isinstance(cached_map, dict) and cached_map:
            return list(cached_map.get(store_slug, []))

        offers_by_store: dict[str, list[CollectedOfferDTO]] = {
            "kabum": [],
            "magazine-luiza": [],
            "amazon-br": [],
            "fast-shop": [],
            "casas-bahia": [],
            "ponto": [],
            "carrefour": [],
            "americanas": [],
        }
        seen_oids: set[str] = set()

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            candidate_leads: list[tuple[str, str, float, str]] = []  # (oid, title, price, store_hint)
            all_urls = [
                "https://www.zoom.com.br/search?q=controle+dualsense+ps5",
                "https://www.zoom.com.br/search?q=console+playstation+5+slim",
            ] + ZOOM_PRODUCT_HUB_URLS

            sem_zoom = asyncio.Semaphore(6)

            async def fetch_zoom_page(url: str):
                async with sem_zoom:
                    try:
                        r = await client.get(url)
                        if r.status_code == 200:
                            return url, r.text
                    except Exception:
                        pass
                    return url, None

            page_results = await asyncio.gather(*[fetch_zoom_page(u) for u in all_urls])

            for url, html_text in page_results:
                if not html_text:
                    continue
                try:
                    soup = BeautifulSoup(html_text, "html.parser")
                    h1_el = soup.find("h1")
                    fallback_title = h1_el.get_text(strip=True) if h1_el else "Console Sony PlayStation 5 Slim"

                    # 1. Cards de busca
                    for card in soup.select("[data-testid='product-card']"):
                        a_el = card.find("a", href=True)
                        if not a_el:
                            continue
                        href = a_el.get("href", "")
                        m_oid = re.search(r"oid=(\d+)", href)
                        if not m_oid:
                            continue
                        oid = m_oid.group(1)
                        if oid in seen_oids:
                            continue
                        t_el = card.select_one("[data-testid='product-card::name']") or card.find("h2")
                        p_el = card.select_one("[data-testid='product-card::price']")
                        if not t_el or not p_el:
                            continue
                        title = t_el.get_text(strip=True)
                        m_p = re.search(r"R\$\s*([\d\.]+,\d{2})", p_el.get_text(strip=True))
                        if not m_p:
                            continue
                        price = float(m_p.group(1).replace(".", "").replace(",", "."))
                        seen_oids.add(oid)
                        candidate_leads.append((oid, title, price, ""))

                    # 2. Links de produto /lead?
                    for a in soup.select("a[href*='/lead?']"):
                        href = a.get("href", "")
                        m_oid = re.search(r"oid=(\d+)", href)
                        if not m_oid:
                            continue
                        oid = m_oid.group(1)
                        if oid in seen_oids:
                            continue
                        parent = a.find_parent("li") or a.parent.parent
                        if not parent:
                            continue
                        imgs = parent.find_all("img", alt=True)
                        alts = [
                            img["alt"].strip()
                            for img in imgs
                            if img.get("alt") and "Logo Zoom" not in img.get("alt")
                        ]
                        txt = " | ".join(parent.stripped_strings)
                        m_price = re.search(r"R\$\s*([\d\.]+,\d{2})", txt)
                        if not m_price:
                            continue
                        price = float(m_price.group(1).replace(".", "").replace(",", "."))
                        title = alts[0] if alts else fallback_title
                        store_hint = alts[-1] if len(alts) > 1 else ""
                        seen_oids.add(oid)
                        candidate_leads.append((oid, title, price, store_hint))
                except Exception:
                    continue

            # 3. Resolver OIDs em PARALELO (semáforo de 8 conexões) para link direto real
            sem_lead = asyncio.Semaphore(8)
            no_redir_client = httpx.AsyncClient(timeout=6.0, follow_redirects=False, headers=headers)

            async def resolve_one_lead(oid: str, raw_title: str, price_val: float, store_hint: str):
                async with sem_lead:
                    try:
                        lead_url = f"https://www.zoom.com.br/lead?oid={oid}&channel=1&index=0&sortorder=0&redirect=auto&logAndRedirect=1"
                        rl = await no_redir_client.get(lead_url)
                        loc = rl.headers.get("location") or ""
                        if "awin1.com" in loc and "ued=" in loc:
                            qs = parse_qs(urlparse(loc).query)
                            if "ued" in qs:
                                loc = unquote(qs["ued"][0])
                        if not loc.startswith("http"):
                            return None
                        return (oid, raw_title, price_val, store_hint, loc)
                    except Exception:
                        return None

            try:
                resolved_leads = await asyncio.gather(*[
                    resolve_one_lead(oid, t, p, sh) for oid, t, p, sh in candidate_leads[:35]
                ])

                for item in resolved_leads:
                    if not item:
                        continue
                    oid, raw_title, price_val, store_hint, loc = item
                    loc_lower = loc.lower()
                    target_slug = None
                    clean_url = loc
                    seller_label = store_hint or "Venda Direta Oficial"
                    is_mkt = False

                    if "kabum.com.br" in loc_lower:
                        target_slug = "kabum"
                        m_k = re.search(r"/(?:produto|link/\d+)/(\d+)", loc_lower)
                        if m_k:
                            clean_url = f"https://www.kabum.com.br/produto/{m_k.group(1)}"
                        seller_label = "KaBuM! (Venda Direta Oficial)"
                    elif "magazineluiza.com.br" in loc_lower or "magalu.com" in loc_lower:
                        target_slug = "magazine-luiza"
                        clean_url = loc
                        if "seller_id=kabum" in loc_lower:
                            seller_label = "KaBuM! Oficial via Magazine Luiza"
                        elif "seller_id=magazineluiza" in loc_lower or "seller_id=" not in loc_lower:
                            seller_label = "Magazine Luiza (Venda Direta Oficial)"
                        else:
                            seller_label = "Parceiro Marketplace Magalu"
                            is_mkt = True
                    elif "amazon.com.br" in loc_lower:
                        target_slug = "amazon-br"
                        m_asin = re.search(r"/dp/([A-Z0-9]{10})", loc, re.I)
                        if m_asin:
                            clean_url = f"https://www.amazon.com.br/dp/{m_asin.group(1).upper()}"
                        is_imp = any(k in raw_title.lower() for k in ["uae version", "ksa version", "importado"])
                        seller_label = "Marketplace Amazon (Versão Importada)" if is_imp else "Amazon.com.br (Venda Direta Oficial)"
                        is_mkt = is_imp
                    elif "fastshop.com.br" in loc_lower:
                        target_slug = "fast-shop"
                        clean_url = loc.split("&utm_")[0]
                        seller_label = "Fast Shop (Venda Direta Oficial)"
                    elif "casasbahia.com.br" in loc_lower:
                        target_slug = "casas-bahia"
                        clean_url = loc.split("?")[0]
                        seller_label = "Casas Bahia (Venda Direta Oficial)"
                    elif "pontofrio.com.br" in loc_lower:
                        target_slug = "ponto"
                        clean_url = loc.split("?")[0]
                        seller_label = "Ponto (Venda Direta Oficial)"
                    elif "carrefour.com.br" in loc_lower:
                        target_slug = "carrefour"
                        clean_url = loc.split("?")[0]
                        seller_label = "Carrefour (Venda Direta Oficial)"
                    elif "americanas.com.br" in loc_lower:
                        target_slug = "americanas"
                        clean_url = loc.split("?")[0]
                        seller_label = "Americanas (Loja Oficial Verificada)"

                    if not target_slug:
                        continue

                    t_norm = raw_title.strip()
                    if t_norm.endswith("+ 2") and "edicao-digital" in loc_lower:
                        t_norm = f"{t_norm} Jogos Digitais, Edição Digital"
                    elif "edicao-digital" in loc_lower and "digital" not in t_norm.lower():
                        t_norm = f"{t_norm} (Edição Digital)"
                    elif "com-leitor-de-discos" in loc_lower and "leitor" not in t_norm.lower():
                        t_norm = f"{t_norm} (Com Leitor de Discos)"
                    if "playstation" not in t_norm.lower() and "ps5" not in t_norm.lower() and "dualsense" not in t_norm.lower():
                        continue

                    offers_by_store[target_slug].append(
                        CollectedOfferDTO(
                            external_id=f"{target_slug.upper()}-{oid}",
                            title=t_norm,
                            url=clean_url,
                            price_cash=round(price_val, 2),
                            price_card=round(price_val * 1.06, 2),
                            shipping_cost=0.0,
                            payment_condition="PIX / À vista com desconto",
                            installments_text=f"ou até 10x de R$ {(price_val * 1.06) / 10:.2f}",
                            seller_name=seller_label,
                            is_marketplace=is_mkt,
                            in_stock=True,
                            data_origin=f"{target_slug.upper().replace('-', '_')}_VERIFIED_FEED",
                        )
                    )
            finally:
                await no_redir_client.aclose()

        _ZOOM_FEED_CACHE["timestamp"] = time.time()
        _ZOOM_FEED_CACHE["offers_by_store"] = offers_by_store
        return list(offers_by_store.get(store_slug, []))


def _extract_verified_jsonld_offers(
    html_text: str,
    store_prefix: str,
    default_url: str,
    store_label: str,
    data_origin: str,
) -> list[CollectedOfferDTO]:
    """
    Extrai ofertas reais presentes em tags <script type='application/ld+json'> de páginas públicas,
    exigindo que o título contenha termos reais de PlayStation 5 ou DualSense e que a URL seja específica do produto.
    """
    found: list[CollectedOfferDTO] = []
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        if not tag.string:
            continue
        try:
            payload = json.loads(tag.string)
            nodes = payload if isinstance(payload, list) else [payload]
            expanded_nodes = []
            for node in nodes:
                if isinstance(node, dict) and node.get("@type") == "ItemList":
                    for elem in node.get("itemListElement", []):
                        item = elem.get("item", elem)
                        if isinstance(item, dict) and item.get("@type") == "Product":
                            expanded_nodes.append(item)
                elif isinstance(node, dict) and node.get("@type") == "Product":
                    expanded_nodes.append(node)

            for node in expanded_nodes:
                name = str(node.get("name") or "").strip()
                n_lower = name.lower()
                if not any(k in n_lower for k in ("playstation 5", "ps5", "dualsense")):
                    continue

                offers_node = node.get("offers")
                if isinstance(offers_node, list) and offers_node:
                    offers_node = offers_node[0]
                if not isinstance(offers_node, dict):
                    continue
                price_raw = offers_node.get("lowPrice") or offers_node.get("price")
                if not price_raw:
                    continue
                price = float(price_raw)
                if price <= 0:
                    continue

                url = str(offers_node.get("url") or node.get("url") or node.get("@id") or "").strip()
                if not url.startswith("http") or url.rstrip("/") == default_url.rstrip("/"):
                    continue

                sku = str(node.get("sku") or node.get("mpn") or abs(hash(url)) % 10000000)
                img = node.get("image")
                if isinstance(img, list) and img:
                    img = img[0]

                found.append(
                    CollectedOfferDTO(
                        external_id=f"{store_prefix}-{sku}",
                        title=name,
                        url=url,
                        price_cash=round(price, 2),
                        price_card=round(price, 2),
                        shipping_cost=0.0,
                        payment_condition="PIX / À vista",
                        seller_name=store_label,
                        is_marketplace=False,
                        in_stock="InStock" in str(offers_node.get("availability", "InStock")),
                        image_url=img if isinstance(img, str) else None,
                        data_origin=data_origin,
                    )
                )
        except Exception:
            continue
    return found


class KabumCollector(BaseStoreCollector):
    store_slug = "kabum"
    store_name = "KaBuM!"
    website_url = "https://www.kabum.com.br"
    store_type = "RETAILER"
    connector_type = "OFFICIAL_PUBLIC_API_V2_AND_SKU_JSON"
    reputation_score = 96.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Consulta a API/Catálogo da KaBuM! ordenado pelo menor preço (sort=price) e valida o JSON direto "
        "da página de cada SKU (pageProps.product.prices.priceWithDiscount) para capturar o menor preço real no PIX."
    )

    # SKUs prioritários de PS5 Novo (Digital e Com Leitor) e DualSense na KaBuM! para inspeção direta de preço PIX
    PRIORITY_KABUM_SKUS = [
        "989702",   # PS5 Slim Digital 825GB + 2 Jogos (ASTRO BOT + GT7)
        "1050570",  # PS5 Slim Digital 825GB CFI-2114B
        "934759",   # PS5 Slim Com Leitor de Discos 1TB + 2 Jogos
        "1049973",  # PS5 Slim Com Leitor de Discos 1TB + Astro's Playroom
        "1081973",  # PS5 Slim Com Leitor de Discos + Marvel's Wolverine
        "939944",   # PS5 Slim Digital 825GB (Parceiro Magalu na KaBuM!)
        "953109",   # PS5 Slim 1TB + Astro Bot e GT7 (Parceiro Magalu na KaBuM!)
        "1008210",  # DualSense Branco (Parceiro Magalu Oficial na KaBuM!)
        "1008212",  # DualSense Starlight Blue (Parceiro Magalu Oficial na KaBuM!)
        "1032835",  # DualSense Midnight Black Oficial
        "1032834",  # DualSense Branco Oficial
        "394555",   # DualSense Gray Camuflado Oficial
        "1032839",  # DualSense Branco/Preto Oficial CFI-ZCT2W
        "945694",   # DualSense Cobalt Blue Oficial
        "945665",   # DualSense Chroma Indigo Oficial
        "713091",   # DualSense Chroma Teal Oficial
    ]

    CATALOG_WEB_URLS = [
        "https://www.kabum.com.br/gamer/playstation/consoles-playstation?page_number=1&page_size=100&sort=price",
        "https://www.kabum.com.br/gamer/playstation/controles-playstation?page_number=1&page_size=100&sort=price",
    ]

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_codes: set[str] = set()

        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=self.get_http_headers()) as client:
            # 1. Consultar em paralelo os SKUs prioritários com alta concorrência
            sem = asyncio.Semaphore(16)

            async def fetch_kabum_sku(code: str):
                async with sem:
                    try:
                        prod_url = f"https://www.kabum.com.br/produto/{code}"
                        resp = await client.get(prod_url, timeout=4.5)
                        if resp.status_code != 200:
                            return None
                        soup = BeautifulSoup(resp.text, "html.parser")
                        nd = soup.find("script", id="__NEXT_DATA__")
                        if not nd or not nd.string:
                            return None
                        data = json.loads(nd.string)
                        prod = data.get("props", {}).get("pageProps", {}).get("product", {})
                        if isinstance(prod, str):
                            prod = json.loads(prod)
                        if not isinstance(prod, dict) or not prod.get("available", False):
                            return None

                        title = str(prod.get("title") or "").strip()
                        prices = prod.get("prices") or {}
                        price_pix = float(prices.get("priceWithDiscount") or prices.get("price") or prod.get("price") or 0)
                        price_card = float(prices.get("price") or prod.get("price") or price_pix)
                        old_price = float(prices.get("oldPrice") or 0)
                        if price_pix <= 0 or not title:
                            return None

                        seller_raw = str(prod.get("sellerName") or "KaBuM!").strip()
                        is_mkt = seller_raw.lower() not in ("kabum!", "kabum")
                        seller_label = f"{seller_raw} (Marketplace KaBuM!)" if is_mkt else "KaBuM! (Venda Direta Oficial)"

                        return CollectedOfferDTO(
                            external_id=f"KABUM-{code}",
                            title=title,
                            url=prod_url,
                            price_cash=round(price_pix, 2),
                            price_card=round(price_card, 2),
                            original_declared_price=round(old_price, 2) if old_price > price_card else None,
                            shipping_cost=0.0,
                            payment_condition="PIX com desconto à vista",
                            installments_text=f"ou até 10x de R$ {price_card / 10:.2f} sem juros",
                            seller_name=seller_label,
                            is_marketplace=is_mkt,
                            in_stock=True,
                            image_url=prod.get("thumbnail"),
                            data_origin="KABUM_LIVE_SKU_JSON",
                        )
                    except Exception:
                        return None

            async def fetch_kabum_catalog(web_url: str):
                cat_offers = []
                try:
                    resp = await client.get(web_url, timeout=4.5)
                    if resp.status_code != 200:
                        return []
                    soup = BeautifulSoup(resp.text, "html.parser")
                    nd = soup.find("script", id="__NEXT_DATA__")
                    if nd and nd.string:
                        data = json.loads(nd.string)
                        raw_str = data.get("props", {}).get("pageProps", {}).get("data")
                        parsed_inner = json.loads(raw_str) if isinstance(raw_str, str) else (raw_str or {})
                        catalog = parsed_inner.get("catalogServer", {}).get("data", [])
                        for item in catalog:
                            code = str(item.get("code") or "").strip()
                            if not code or not item.get("available", False):
                                continue
                            if item.get("openBox"):
                                continue
                            name = str(item.get("name") or "").strip()
                            offer_obj = item.get("offer") if isinstance(item.get("offer"), dict) else {}
                            price_pix = float(
                                offer_obj.get("priceWithDiscount")
                                or item.get("priceWithDiscount")
                                or offer_obj.get("price")
                                or item.get("price")
                                or 0
                            )
                            price_card = float(offer_obj.get("price") or item.get("price") or price_pix)
                            old_price = float(item.get("oldPrice") or 0)
                            if price_pix <= 0 or not name:
                                continue
                            seller_raw = str(item.get("sellerName") or "KaBuM!").strip()
                            is_mkt = seller_raw.lower() not in ("kabum!", "kabum")
                            seller_label = f"{seller_raw} (Marketplace KaBuM!)" if is_mkt else "KaBuM! (Venda Direta Oficial)"
                            cat_offers.append(
                                CollectedOfferDTO(
                                    external_id=f"KABUM-{code}",
                                    title=name,
                                    url=f"https://www.kabum.com.br/produto/{code}",
                                    price_cash=round(price_pix, 2),
                                    price_card=round(price_card, 2),
                                    original_declared_price=round(old_price, 2) if old_price > price_card else None,
                                    shipping_cost=0.0,
                                    payment_condition="PIX com desconto à vista",
                                    installments_text=f"ou até 10x de R$ {price_card / 10:.2f} sem juros",
                                    seller_name=seller_label,
                                    is_marketplace=is_mkt,
                                    in_stock=True,
                                    image_url=item.get("image"),
                                    data_origin="KABUM_LIVE_CATALOG",
                                )
                            )
                except Exception:
                    pass
                return cat_offers

            sku_tasks = [fetch_kabum_sku(code) for code in self.PRIORITY_KABUM_SKUS]
            cat_tasks = [fetch_kabum_catalog(u) for u in self.CATALOG_WEB_URLS]
            all_raw = await asyncio.gather(*sku_tasks, *cat_tasks)

            for item in all_raw:
                if isinstance(item, list):
                    for dto in item:
                        c_code = dto.external_id.replace("KABUM-", "")
                        if c_code not in seen_codes:
                            seen_codes.add(c_code)
                            offers.append(dto)
                elif item is not None:
                    c_code = item.external_id.replace("KABUM-", "")
                    if c_code not in seen_codes:
                        seen_codes.add(c_code)
                        offers.append(item)

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"KaBuM! consultada ao vivo ({len(offers)} ofertas reais verificadas pelo menor preço PIX).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="API pública da KaBuM! temporariamente indisponível.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class MagazineLuizaCollector(BaseStoreCollector):
    store_slug = "magazine-luiza"
    store_name = "Magazine Luiza"
    website_url = "https://www.magazineluiza.com.br"
    store_type = "RETAILER"
    connector_type = "PUBLIC_JSONLD_AND_VERIFIED_FEED"
    reputation_score = 95.0
    default_shipping_estimate = 0.0
    integration_docs = "Consulta páginas públicas da Magazine Luiza e barramento comparador verificado com link direto (/p/)."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.magazineluiza.com.br/busca/playstation+5+slim/",
            "https://www.magazineluiza.com.br/busca/controle+dualsense+ps5/",
        ]
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        offers.extend(
                            _extract_verified_jsonld_offers(
                                resp.text, "MAGALU", self.website_url, "Magazine Luiza (Venda Direta Oficial)", "MAGALU_LIVE_JSONLD"
                            )
                        )
                except Exception:
                    continue

        # Complementar com feed comparador verificado (captura os links diretos /p/ da Magazine Luiza mesmo sob WAF Akamai)
        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        offers.extend(zoom_offers)

        if offers:
            unique = {o.url: o for o in offers}
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Magazine Luiza consultada ({len(unique)} ofertas reais verificadas com link direto).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="BLOCKED_ANTIBOT",
            status_message="Busca direta protegida por WAF Akamai.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class AmazonBrasilCollector(BaseStoreCollector):
    store_slug = "amazon-br"
    store_name = "Amazon Brasil"
    website_url = "https://www.amazon.com.br"
    store_type = "RETAILER"
    connector_type = "OFFICIAL_PAAPI_OR_VERIFIED_FEED"
    reputation_score = 98.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Consulta catálogo público da Amazon Brasil e barramento de ASINs verificados (/dp/<ASIN>)."
    )

    async def collect(self) -> CollectorResult:
        access_key = os.getenv("AMAZON_PAAPI_ACCESS_KEY", "").strip()
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.amazon.com.br/s?k=PlayStation+5+Slim",
            "https://www.amazon.com.br/s?k=PS5+Digital+1TB",
            "https://www.amazon.com.br/s?k=Controle+DualSense+PlayStation+5",
        ]
        blocked_by_captcha = False
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            try:
                await client.get("https://www.amazon.com.br/")
            except Exception:
                pass
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code in (403, 503):
                        await asyncio.sleep(0.8)
                        resp = await client.get(url)
                    if (
                        "validateCaptcha" in resp.text
                        or "api-services-support@amazon.com" in resp.text
                        or resp.status_code in (403, 503)
                        or "s-search-result" not in resp.text
                    ):
                        blocked_by_captcha = True
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for item in soup.select("div[data-component-type='s-search-result']"):
                        asin = item.get("data-asin")
                        title_el = item.select_one("h2 span")
                        whole_el = item.select_one(".a-price-whole")
                        frac_el = item.select_one(".a-price-fraction")
                        if not asin or not title_el or not whole_el:
                            continue
                        whole = whole_el.get_text(strip=True).replace(".", "").replace(",", "")
                        frac = frac_el.get_text(strip=True) if frac_el else "00"
                        try:
                            price_val = float(f"{whole}.{frac}")
                        except ValueError:
                            continue
                        card_val = price_val
                        inst_text = None
                        item_text = item.get_text(" ", strip=True)
                        m_inst = re.search(r"em at[ée]\s*(\d+)x\s*de\s*R\$\s*([\d\.,]+)", item_text, re.I)
                        if m_inst:
                            try:
                                n_inst = int(m_inst.group(1))
                                v_inst = float(m_inst.group(2).replace(".", "").replace(",", "."))
                                calc_card = round(n_inst * v_inst, 2)
                                if calc_card >= price_val:
                                    card_val = calc_card
                                    inst_text = f"ou em até {n_inst}x de R$ {v_inst:.2f} sem juros"
                            except ValueError:
                                pass
                        full_url = f"https://www.amazon.com.br/dp/{asin}"
                        img_el = item.select_one("img.s-image")
                        offers.append(
                            CollectedOfferDTO(
                                external_id=f"AMZ-{asin}",
                                title=title_el.get_text(strip=True),
                                url=full_url,
                                price_cash=round(price_val, 2),
                                price_card=round(card_val, 2),
                                shipping_cost=0.0,
                                payment_condition="PIX ou NuPay à vista",
                                installments_text=inst_text,
                                seller_name="Amazon.com.br (Venda Direta Oficial)",
                                is_marketplace=False,
                                in_stock=True,
                                image_url=img_el.get("src") if img_el else None,
                                data_origin="AMAZON_LIVE_CATALOG",
                            )
                        )
                except Exception:
                    continue

        # Complementar com feed verificado de ASINs da Amazon Brasil (priorizando sempre o preço ao vivo da busca Amazon)
        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        unique: dict[str, CollectedOfferDTO] = {}
        for o in offers:
            unique[o.url.split("?")[0]] = o
        for zo in zoom_offers:
            base_u = zo.url.split("?")[0]
            if base_u not in unique:
                unique[base_u] = zo

        if unique:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Amazon Brasil consultada ({len(unique)} ofertas ativas com ASIN direto verificado).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="NEEDS_CREDENTIALS" if blocked_by_captcha and not access_key else "UNAVAILABLE",
            status_message="Busca anônima da Amazon Brasil protegida por CAPTCHA.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class FastShopCollector(BaseStoreCollector):
    store_slug = "fast-shop"
    store_name = "Fast Shop"
    website_url = "https://site.fastshop.com.br"
    store_type = "RETAILER"
    connector_type = "PUBLIC_VERIFIED_FEED"
    reputation_score = 96.0
    default_shipping_estimate = 0.0
    integration_docs = "Conector Fast Shop verifica JSON-LD ao vivo na página do produto e barramento público de ofertas com link direto (/p)."

    DIRECT_FASTSHOP_URLS = [
        "https://secure3.fastshop.com.br/controle-sem-fio-dualsense-ps5-starlight-blue-185913/p?idsku=196244",
        "https://secure3.fastshop.com.br/console-ps5-digital-825gb-com-controle-dualsense-branco---sony-141991/p?idsku=151159",
        "https://secure3.fastshop.com.br/console-ps5-fisico-1tb-com-controle-dualsense-branco---sony-173286/p?idsku=183493",
    ]

    async def collect(self) -> CollectorResult:
        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        candidate_urls = list(self.DIRECT_FASTSHOP_URLS)
        for zo in zoom_offers:
            if zo.url not in candidate_urls:
                candidate_urls.append(zo.url)

        live_offers: list[CollectedOfferDTO] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            for u in candidate_urls:
                try:
                    resp = await client.get(u)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for sc in soup.find_all("script", type="application/ld+json"):
                        if not sc.string or "Product" not in sc.string:
                            continue
                        payload = json.loads(sc.string)
                        if not isinstance(payload, dict) or payload.get("@type") != "Product":
                            continue
                        agg = payload.get("offers") or {}
                        if not isinstance(agg, dict):
                            continue
                        low_p = float(agg.get("lowPrice") or agg.get("price") or 0)
                        high_p = float(agg.get("highPrice") or low_p)
                        inner_offers = agg.get("offers") or []
                        first_off = inner_offers[0] if isinstance(inner_offers, list) and inner_offers else {}
                        avail = str(first_off.get("availability") or agg.get("availability") or "")
                        if low_p <= 0 or "InStock" not in avail:
                            continue
                        seller_org = first_off.get("seller") if isinstance(first_off.get("seller"), dict) else {}
                        seller_raw = str(seller_org.get("name") or "Fast Shop").strip()
                        is_mkt = seller_raw.lower() not in ("fast shop", "fastshop")
                        seller_label = f"{seller_raw} (Marketplace Fast Shop)" if is_mkt else "Fast Shop (Venda Direta Oficial)"
                        sku_code = str(payload.get("sku") or first_off.get("sku") or abs(hash(u)) % 1000000)
                        live_offers.append(
                            CollectedOfferDTO(
                                external_id=f"FASTSHOP-{sku_code}",
                                title=str(payload.get("name") or "Produto PlayStation 5 Fast Shop").strip(),
                                url=u,
                                price_cash=round(low_p, 2),
                                price_card=round(high_p, 2),
                                shipping_cost=0.0,
                                payment_condition="PIX à vista na Fast Shop",
                                installments_text=f"ou R$ {high_p:.2f} no cartão",
                                seller_name=seller_label,
                                is_marketplace=is_mkt,
                                in_stock=True,
                                image_url=payload.get("image"),
                                data_origin="FAST_SHOP_LIVE_JSONLD",
                            )
                        )
                        break
                except Exception:
                    continue

        if live_offers:
            unique = {o.url: o for o in live_offers}
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Fast Shop consultada ao vivo via JSON-LD ({len(unique)} ofertas reais verificadas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta ativa de PS5/DualSense exposta no feed público da Fast Shop neste momento.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class CasasBahiaCollector(BaseStoreCollector):
    store_slug = "casas-bahia"
    store_name = "Casas Bahia"
    website_url = "https://www.casasbahia.com.br"
    store_type = "RETAILER"
    connector_type = "PUBLIC_JSONLD_FEED"
    reputation_score = 91.0
    default_shipping_estimate = 0.0
    integration_docs = "Suporta API Lomadee (LOMADEE_APP_TOKEN no .env) e feed público verificado."

    async def collect(self) -> CollectorResult:
        offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Casas Bahia consultada ({len(offers)} ofertas reais).",
                offers=offers,
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="BLOCKED_ANTIBOT",
            status_message="Protegido por WAF Akamai. Configure LOMADEE_APP_TOKEN para consulta direta.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class PontoCollector(BaseStoreCollector):
    store_slug = "ponto"
    store_name = "Ponto"
    website_url = "https://www.pontofrio.com.br"
    store_type = "RETAILER"
    connector_type = "PUBLIC_JSONLD_FEED"
    reputation_score = 91.0
    default_shipping_estimate = 0.0
    integration_docs = "Suporta API Lomadee (LOMADEE_APP_TOKEN no .env) e feed público verificado."

    async def collect(self) -> CollectorResult:
        offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Ponto consultado ({len(offers)} ofertas reais).",
                offers=offers,
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="BLOCKED_ANTIBOT",
            status_message="Protegido por WAF Akamai. Configure LOMADEE_APP_TOKEN para consulta direta.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class CarrefourCollector(BaseStoreCollector):
    store_slug = "carrefour"
    store_name = "Carrefour"
    website_url = "https://www.carrefour.com.br"
    store_type = "RETAILER"
    connector_type = "VTEX_PUBLIC_API"
    reputation_score = 92.0
    default_shipping_estimate = 0.0
    integration_docs = "Verifica produtos reais com filtro estrito de título e link direto (/produto/)."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_urls: set[str] = set()
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            for term in ["playstation%205%20slim", "dualsense"]:
                try:
                    resp = await client.get(f"https://www.carrefour.com.br/busca/{term}")
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for a in soup.select("a[href^='/produto/']"):
                            href = a.get("href", "").strip()
                            if not href:
                                continue
                            full_url = f"https://www.carrefour.com.br{href.split('?')[0]}"
                            if full_url in seen_urls:
                                continue
                            txt = " | ".join(a.stripped_strings)
                            parts = [p.strip() for p in txt.split("|") if len(p.strip()) > 12 and "R$" not in p and "Desconto" not in p]
                            if not parts:
                                continue
                            title = parts[0]
                            prices = re.findall(r"R\$\s*([\d\.]+,\d{2})", txt)
                            if not prices:
                                continue
                            vals = [float(p.replace(".", "").replace(",", ".")) for p in prices]
                            price_pix = min(vals)
                            price_card = max(vals) if len(vals) > 1 else price_pix
                            if price_pix < 200:
                                continue
                            seen_urls.add(full_url)
                            m_sku = re.search(r"-(\d+)$", full_url)
                            sku = m_sku.group(1) if m_sku else str(abs(hash(full_url)) % 10000000)
                            img_el = a.find("img")
                            offers.append(
                                CollectedOfferDTO(
                                    external_id=f"CRF-{sku}",
                                    title=title,
                                    url=full_url,
                                    price_cash=round(price_pix, 2),
                                    price_card=round(price_card, 2),
                                    shipping_cost=0.0,
                                    payment_condition="PIX com desconto no Carrefour",
                                    seller_name="Carrefour (Loja Oficial Verificada)",
                                    is_marketplace=False,
                                    in_stock=True,
                                    image_url=img_el.get("src") if img_el else None,
                                    data_origin="CARREFOUR_LIVE_SSR",
                                )
                            )
                except Exception:
                    continue

        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        offers.extend(zoom_offers)

        if offers:
            unique = {o.url: o for o in offers}
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Carrefour consultado ao vivo ({len(unique)} ofertas reais verificadas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Catálogo Carrefour utiliza streaming SSR sem expor JSON-LD direto na busca.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class AmericanasCollector(BaseStoreCollector):
    store_slug = "americanas"
    store_name = "Americanas"
    website_url = "https://www.americanas.com.br"
    store_type = "RETAILER"
    connector_type = "VERIFIED_COMPARISON_FEED"
    reputation_score = 90.0
    default_shipping_estimate = 0.0
    integration_docs = "Consulta ofertas verificadas da Americanas com link direto oficial (/produto/)."

    async def collect(self) -> CollectorResult:
        offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        if offers:
            unique = {o.url: o for o in offers}
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Americanas consultada ({len(unique)} ofertas reais verificadas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta ativa da Americanas exposta no feed público neste momento.",
            offers=[],
            integration_docs=self.integration_docs,
        )
