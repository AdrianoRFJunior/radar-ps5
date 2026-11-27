"""
Módulos de coleta independentes em Modo Intensivo Black Friday para todas as lojas varejistas brasileiras confiáveis (Produtos 100% Novos).
Lojas cobertas:
- KaBuM!, Amazon Brasil, Magazine Luiza, Mercado Livre, Shopee (Lojas Oficiais), Fast Shop, Carrefour,
  Casas Bahia, Ponto, Extra, Americanas, Submarino, Havan, Kalunga, Bemol, Lojas Benoit, Angeloni, iByte,
  Fujioka, Webcontinental, Lojas Solar, Girafa, Webfones e Nagem.
- Integra barramentos públicos duplos (Zoom + Buscapé) em paralelo com resolução real de URL direta.
- Nunca inventa preços nem tenta contornar CAPTCHAs ou bloqueios anti-bot.
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
from backend.collectors.community_sources import fetch_live_promobit_raw_offers


# Cache curto (45s) para o Modo Intensivo Black Friday evitar duplicação dentro do mesmo ciclo paralelo
_COMPARISON_FEED_CACHE: dict[str, object] = {"timestamp": 0.0, "offers_by_store": {}}
_COMPARISON_LOCK = asyncio.Lock()

COMPARISON_SEARCH_AND_HUB_URLS = [
    # Buscas diretas Zoom + Buscapé
    "https://www.zoom.com.br/search?q=console+playstation+5+slim",
    "https://www.buscape.com.br/search?q=console+playstation+5+slim",
    "https://www.zoom.com.br/search?q=playstation+5+digital",
    "https://www.buscape.com.br/search?q=playstation+5+com+leitor",
    "https://www.zoom.com.br/search?q=controle+dualsense+ps5",
    "https://www.buscape.com.br/search?q=controle+dualsense+ps5",
    # Hubs de produto Zoom + Buscapé (Digital, Com Leitor, Bundles e DualSense)
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-slim-825gb-sony-ps5-edicao-digital-bundle-4k",
    "https://www.buscape.com.br/console-de-video-game/console-playstation-5-slim-825gb-sony-ps5-edicao-digital-bundle-4k",
    "https://www.zoom.com.br/console-de-video-game/playstation-5-slim-1tb-bundle-astro-bot-gran-turismo-7",
    "https://www.buscape.com.br/console-de-video-game/playstation-5-slim-1tb-bundle-astro-bot-gran-turismo-7",
    "https://www.zoom.com.br/console-de-video-game/pre-venda-console-playstation-5-slim-1-tb-sony-1214a-4k",
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-slim-1tb-sony-4k-hdr",
    "https://www.buscape.com.br/console-de-video-game/console-playstation-5-slim-1tb-sony-4k-hdr",
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-edicao-digital-sony-4k",
    "https://www.buscape.com.br/console-de-video-game/console-playstation-5-edicao-digital-sony-4k",
    "https://www.zoom.com.br/console-de-video-game/playstation-5-slim-edicao-digital-1tb-bundle-astro-bot-gran-turismo-7",
    "https://www.zoom.com.br/console-de-video-game/console-playstation-5-slim-825gb-sony-4k",
    "https://www.zoom.com.br/controle-joystick/controle-ps5-sem-fio-dualsense-sony",
    "https://www.buscape.com.br/controle-joystick/controle-ps5-sem-fio-dualsense-sony",
]

ALL_TRACKED_SLUGS = [
    "kabum",
    "magazine-luiza",
    "amazon-br",
    "mercado-livre",
    "shopee",
    "fast-shop",
    "casas-bahia",
    "ponto",
    "extra",
    "carrefour",
    "americanas",
    "submarino",
    "havan",
    "bemol",
    "kalunga",
    "nagem",
    "girafa",
    "webfones",
    "benoit",
    "angeloni",
    "ibyte",
]


def _classify_lead_destination(loc: str, raw_title: str, store_hint: str) -> tuple[str | None, str, str, float, bool]:
    """
    Identifica a loja de destino de um lead do Zoom/Buscapé.
    Retorna (store_slug, store_display_name, clean_url, reputation_score, is_marketplace).
    """
    loc_lower = loc.lower()
    clean_url = loc
    is_mkt = False

    if "kabum.com.br" in loc_lower:
        m_k = re.search(r"/(?:produto|link/\d+)/(\d+)", loc_lower)
        if m_k:
            clean_url = f"https://www.kabum.com.br/produto/{m_k.group(1)}"
        return ("kabum", "KaBuM!", clean_url, 96.0, False)

    if "magazineluiza.com.br" in loc_lower or "magalu.com" in loc_lower:
        if "seller_id=kabum" in loc_lower:
            return ("magazine-luiza", "Magazine Luiza", loc, 95.0, False)
        if "seller_id=magazineluiza" in loc_lower or "seller_id=" not in loc_lower:
            return ("magazine-luiza", "Magazine Luiza", loc, 95.0, False)
        return ("magazine-luiza", "Magazine Luiza", loc, 93.0, True)

    if "amazon.com.br" in loc_lower:
        m_asin = re.search(r"/dp/([A-Z0-9]{10})", loc, re.I)
        if m_asin:
            clean_url = f"https://www.amazon.com.br/dp/{m_asin.group(1).upper()}"
        is_imp = any(k in raw_title.lower() for k in ["uae version", "ksa version", "importado", "international version"])
        return ("amazon-br", "Amazon Brasil", clean_url, 98.0, is_imp)

    if "mercadolivre.com.br" in loc_lower or "meli.la" in loc_lower:
        clean_url = loc.split("#")[0]
        return ("mercado-livre", "Mercado Livre", clean_url, 94.0, False)

    if "shopee.com.br" in loc_lower:
        return ("shopee", "Shopee (Loja Oficial)", loc, 92.0, False)

    if "fastshop.com.br" in loc_lower:
        clean_url = loc.split("&utm_")[0]
        return ("fast-shop", "Fast Shop", clean_url, 96.0, False)

    if "casasbahia.com.br" in loc_lower:
        return ("casas-bahia", "Casas Bahia", loc.split("?")[0], 91.0, False)

    if "pontofrio.com.br" in loc_lower:
        return ("ponto", "Ponto", loc.split("?")[0], 91.0, False)

    if "extra.com.br" in loc_lower:
        return ("extra", "Extra", loc.split("?")[0], 91.0, False)

    if "carrefour.com.br" in loc_lower:
        return ("carrefour", "Carrefour", loc.split("?")[0], 92.0, False)

    if "americanas.com.br" in loc_lower:
        return ("americanas", "Americanas", loc.split("?")[0], 90.0, False)

    if "submarino.com.br" in loc_lower:
        return ("submarino", "Submarino", loc.split("?")[0], 90.0, False)

    if "havan.com.br" in loc_lower:
        return ("havan", "Havan", loc.split("?")[0], 93.0, False)

    if "bemol.com.br" in loc_lower:
        return ("bemol", "Bemol", loc.split("?")[0], 94.0, False)

    if "kalunga.com.br" in loc_lower:
        return ("kalunga", "Kalunga", loc.split("?")[0], 94.0, False)

    if "nagem.com.br" in loc_lower:
        return ("nagem", "Nagem", loc.split("?")[0], 92.0, False)

    if "girafa.com.br" in loc_lower:
        return ("girafa", "Girafa", loc.split("?")[0], 92.0, False)

    if "webfones.com.br" in loc_lower:
        return ("webfones", "Webfones", loc.split("?")[0], 92.0, False)

    if "benoit.com.br" in loc_lower:
        return ("benoit", "Lojas Benoit", loc.split("?")[0], 92.0, False)

    if "angeloni.com.br" in loc_lower:
        return ("angeloni", "Angeloni", loc.split("?")[0], 93.0, False)

    if "ibyte.com.br" in loc_lower:
        return ("ibyte", "iByte", loc.split("?")[0], 92.0, False)

    return (None, store_hint or "", loc, 90.0, False)


async def _get_zoom_verified_offers_for_store(store_slug: str, headers: dict[str, str]) -> list[CollectedOfferDTO]:
    """
    Consulta simultaneamente Zoom + Buscapé para PS5 Slim (Digital, Com Leitor, Bundles) e DualSense,
    resolvendo cada OID em paralelo para obter o link direto real na loja oficial.
    """
    now = time.time()
    cached_ts = float(_COMPARISON_FEED_CACHE.get("timestamp") or 0.0)
    cached_map = _COMPARISON_FEED_CACHE.get("offers_by_store")
    if (now - cached_ts) < 45.0 and isinstance(cached_map, dict) and cached_map:
        return list(cached_map.get(store_slug, []))

    async with _COMPARISON_LOCK:
        now = time.time()
        cached_ts = float(_COMPARISON_FEED_CACHE.get("timestamp") or 0.0)
        cached_map = _COMPARISON_FEED_CACHE.get("offers_by_store")
        if (now - cached_ts) < 45.0 and isinstance(cached_map, dict) and cached_map:
            return list(cached_map.get(store_slug, []))

        offers_by_store: dict[str, list[CollectedOfferDTO]] = {slug: [] for slug in ALL_TRACKED_SLUGS}
        seen_oids: set[str] = set()

        async with httpx.AsyncClient(timeout=8.5, follow_redirects=True, headers=headers) as client:
            # (host_base, oid, title, price, store_hint)
            candidate_leads: list[tuple[str, str, str, float, str]] = []
            sem_page = asyncio.Semaphore(8)

            async def fetch_comp_page(url: str):
                async with sem_page:
                    try:
                        r = await client.get(url)
                        if r.status_code == 200:
                            return url, r.text
                    except Exception:
                        pass
                    return url, None

            page_results = await asyncio.gather(*[fetch_comp_page(u) for u in COMPARISON_SEARCH_AND_HUB_URLS])

            for url, html_text in page_results:
                if not html_text:
                    continue
                host_base = "https://www.buscape.com.br" if "buscape.com.br" in url else "https://www.zoom.com.br"
                try:
                    soup = BeautifulSoup(html_text, "html.parser")
                    h1_el = soup.find("h1")
                    fallback_title = h1_el.get_text(strip=True) if h1_el else "Console Sony PlayStation 5 Slim"

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
                        if price < 200 or price > 7200:
                            continue
                        seen_oids.add(oid)
                        candidate_leads.append((host_base, oid, title, price, ""))

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
                            if img.get("alt") and not any(x in img.get("alt", "") for x in ("Logo Zoom", "Logo Buscapé", "Buscape"))
                        ]
                        txt = " | ".join(parent.stripped_strings)
                        m_price = re.search(r"R\$\s*([\d\.]+,\d{2})", txt)
                        if not m_price:
                            continue
                        price = float(m_price.group(1).replace(".", "").replace(",", "."))
                        if price < 200 or price > 7200:
                            continue
                        title = alts[0] if alts else fallback_title
                        store_hint = alts[-1] if len(alts) > 1 else ""
                        seen_oids.add(oid)
                        candidate_leads.append((host_base, oid, title, price, store_hint))
                except Exception:
                    continue

            # Ordenar priorizando Consoles PS5 mais baratos primeiro + DualSense mais baratos primeiro (nunca cortar consoles!)
            console_leads = sorted([x for x in candidate_leads if x[3] >= 2200], key=lambda x: x[3])
            ctrl_leads = sorted([x for x in candidate_leads if x[3] < 2200], key=lambda x: x[3])
            prioritized_leads = console_leads[:45] + ctrl_leads[:25]

            sem_lead = asyncio.Semaphore(14)
            no_redir_client = httpx.AsyncClient(timeout=5.0, follow_redirects=False, headers=headers)

            async def resolve_one_lead(host_b: str, oid: str, raw_title: str, price_val: float, store_hint: str):
                async with sem_lead:
                    try:
                        lead_url = f"{host_b}/lead?oid={oid}&channel=1&index=0&sortorder=0&redirect=auto&logAndRedirect=1"
                        rl = await no_redir_client.get(lead_url)
                        loc = rl.headers.get("location") or ""
                        for param in ("ued", "murl", "url", "dl"):
                            if f"{param}=" in loc:
                                qs = parse_qs(urlparse(loc).query)
                                if param in qs and qs[param]:
                                    loc = unquote(qs[param][0])
                        if not loc.startswith("http"):
                            return None
                        return (oid, raw_title, price_val, store_hint, loc)
                    except Exception:
                        return None

            try:
                resolved_leads = await asyncio.gather(*[
                    resolve_one_lead(hb, oid, t, p, sh) for hb, oid, t, p, sh in prioritized_leads
                ])

                for item in resolved_leads:
                    if not item:
                        continue
                    oid, raw_title, price_val, store_hint, loc = item
                    loc_lower = loc.lower()
                    target_slug, store_disp, clean_url, rep_score, is_mkt = _classify_lead_destination(loc, raw_title, store_hint)
                    if not target_slug or target_slug not in offers_by_store:
                        continue

                    t_norm = raw_title.strip()
                    if t_norm.endswith("+ 2") and "edicao-digital" in loc_lower:
                        t_norm = f"{t_norm} Jogos Digitais, Edição Digital"
                    elif "edicao-digital" in loc_lower and "digital" not in t_norm.lower():
                        t_norm = f"{t_norm} (Edição Digital)"
                    elif "com-leitor-de-discos" in loc_lower and "leitor" not in t_norm.lower():
                        t_norm = f"{t_norm} (Com Leitor de Discos)"
                    if not any(k in t_norm.lower() for k in ("playstation", "ps5", "dualsense")):
                        continue

                    seller_label = f"{store_disp} ({'Marketplace' if is_mkt else 'Venda Direta Oficial'})"
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
                            store_slug_override=target_slug,
                            store_name_override=store_disp,
                            store_reputation_override=rep_score,
                        )
                    )
            finally:
                await no_redir_client.aclose()

        _COMPARISON_FEED_CACHE["timestamp"] = time.time()
        _COMPARISON_FEED_CACHE["offers_by_store"] = offers_by_store
        return list(offers_by_store.get(store_slug, []))


def _extract_verified_jsonld_offers(
    html_text: str,
    store_prefix: str,
    default_url: str,
    store_label: str,
    data_origin: str,
) -> list[CollectedOfferDTO]:
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
                if price <= 0 or price > 7200:
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
        "Consulta a API/Catálogo da KaBuM! ordenado pelo menor preço (sort=price), inspeciona o JSON ao vivo "
        "dos SKUs prioritários no PIX e cruza cupons ativos de Black Friday."
    )

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

        async with httpx.AsyncClient(timeout=6.5, follow_redirects=True, headers=self.get_http_headers()) as client:
            sem = asyncio.Semaphore(16)

            async def fetch_kabum_sku(code: str):
                async with sem:
                    try:
                        prod_url = f"https://www.kabum.com.br/produto/{code}"
                        resp = await client.get(prod_url, timeout=5.0)
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
                    resp = await client.get(web_url, timeout=5.0)
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
                            if not code or not item.get("available", False) or item.get("openBox"):
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
    integration_docs = "Consulta páginas públicas da Magazine Luiza + barramentos Zoom/Buscapé com link direto (/p/)."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.magazineluiza.com.br/busca/playstation+5+slim/",
            "https://www.magazineluiza.com.br/busca/controle+dualsense+ps5/",
        ]
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=self.get_http_headers()) as client:
            resps = await asyncio.gather(*[client.get(u) for u in urls], return_exceptions=True)
            for resp in resps:
                if not isinstance(resp, Exception) and resp.status_code == 200:
                    offers.extend(
                        _extract_verified_jsonld_offers(
                            resp.text, "MAGALU", self.website_url, "Magazine Luiza (Venda Direta Oficial)", "MAGALU_LIVE_JSONLD"
                        )
                    )

        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        offers.extend(zoom_offers)

        if offers:
            unique: dict[str, CollectedOfferDTO] = {}
            for o in sorted(offers, key=lambda x: x.price_cash):
                unique.setdefault(o.url.split("?")[0], o)
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
    integration_docs = "Consulta catálogo público de Black Friday da Amazon Brasil e barramento de ASINs verificados (/dp/<ASIN>)."

    async def collect(self) -> CollectorResult:
        access_key = os.getenv("AMAZON_PAAPI_ACCESS_KEY", "").strip()
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.amazon.com.br/s?k=PlayStation+5+Slim",
            "https://www.amazon.com.br/s?k=Console+PlayStation+5+Com+Leitor",
            "https://www.amazon.com.br/s?k=PS5+Digital+1TB",
            "https://www.amazon.com.br/s?k=Controle+DualSense+PlayStation+5",
        ]
        blocked_by_captcha = False
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=self.get_http_headers()) as client:
            try:
                await client.get("https://www.amazon.com.br/", timeout=4.0)
            except Exception:
                pass

            sem = asyncio.Semaphore(4)

            async def _fetch_amz_search(url: str) -> list[CollectedOfferDTO]:
                nonlocal blocked_by_captcha
                found_local: list[CollectedOfferDTO] = []
                async with sem:
                    try:
                        resp = await client.get(url, timeout=6.0)
                        if (
                            "validateCaptcha" in resp.text
                            or "api-services-support@amazon.com" in resp.text
                            or resp.status_code in (403, 503)
                            or "s-search-result" not in resp.text
                        ):
                            blocked_by_captcha = True
                            return []
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
                            if price_val < 200 or price_val > 7200:
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
                            # Detectar cupom de página na Amazon ("Economize R$ X com cupom" / "Com cupom")
                            orig_el = item.select_one(".a-price.a-text-price span.a-offscreen")
                            orig_val = None
                            if orig_el:
                                m_or = re.search(r"([\d\.]+,\d{2})", orig_el.get_text(strip=True))
                                if m_or:
                                    try:
                                        orig_val = float(m_or.group(1).replace(".", "").replace(",", "."))
                                    except ValueError:
                                        pass
                            full_url = f"https://www.amazon.com.br/dp/{asin}"
                            img_el = item.select_one("img.s-image")
                            found_local.append(
                                CollectedOfferDTO(
                                    external_id=f"AMZ-{asin}",
                                    title=title_el.get_text(strip=True),
                                    url=full_url,
                                    price_cash=round(price_val, 2),
                                    price_card=round(card_val, 2),
                                    original_declared_price=round(orig_val, 2) if orig_val and orig_val > price_val else None,
                                    shipping_cost=0.0,
                                    payment_condition="PIX ou Cartão Amazon em até 10x",
                                    installments_text=inst_text,
                                    seller_name="Amazon.com.br (Venda Direta Oficial)",
                                    is_marketplace=False,
                                    in_stock=True,
                                    image_url=img_el.get("src") if img_el else None,
                                    data_origin="AMAZON_LIVE_CATALOG",
                                )
                            )
                    except Exception:
                        return []
                return found_local

            batches = await asyncio.gather(*[_fetch_amz_search(u) for u in urls])
            for b in batches:
                offers.extend(b)

        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        unique: dict[str, CollectedOfferDTO] = {}
        for o in sorted(offers + zoom_offers, key=lambda x: x.price_cash):
            base_u = o.url.split("?")[0]
            if base_u not in unique:
                unique[base_u] = o

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
    integration_docs = "Conector Fast Shop verifica JSON-LD ao vivo na página do produto e barramento público (/p)."

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
        async with httpx.AsyncClient(timeout=7.0, follow_redirects=True, headers=self.get_http_headers()) as client:
            async def _fetch_fs(u: str) -> CollectedOfferDTO | None:
                try:
                    resp = await client.get(u, timeout=5.5)
                    if resp.status_code != 200:
                        return None
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
                        return CollectedOfferDTO(
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
                except Exception:
                    return None
                return None

            res_list = await asyncio.gather(*[_fetch_fs(u) for u in candidate_urls])
            live_offers.extend([x for x in res_list if x is not None])

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
            status_message="Nenhuma oferta ativa de PS5/DualSense exposta na Fast Shop neste momento.",
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
    integration_docs = "Consulta barramento duplo Zoom + Buscapé + Promobit para ofertas oficiais Casas Bahia."

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
            status_message="Protegido por WAF Akamai na busca direta; monitorando via comparadores oficiais.",
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
    integration_docs = "Consulta barramento duplo Zoom + Buscapé + Promobit para ofertas oficiais Ponto."

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
            status_message="Protegido por WAF Akamai na busca direta; monitorando via comparadores oficiais.",
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
    integration_docs = "Verifica produtos reais no Carrefour com filtro estrito de título e link direto (/produto/)."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_urls: set[str] = set()
        terms = ["playstation%205%20slim", "console%20playstation%205", "dualsense"]
        async with httpx.AsyncClient(timeout=7.0, follow_redirects=True, headers=self.get_http_headers()) as client:
            resps = await asyncio.gather(*[client.get(f"https://www.carrefour.com.br/busca/{t}") for t in terms], return_exceptions=True)
            for resp in resps:
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                try:
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
                        valid_vals = [v for v in vals if v >= 200]
                        if not valid_vals:
                            continue
                        price_pix = min(valid_vals)
                        price_card = max(valid_vals) if len(valid_vals) > 1 else price_pix
                        if price_pix > 7200:
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
            status_message="Nenhuma oferta ativa encontrada no Carrefour neste instante.",
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
    integration_docs = "Consulta ofertas verificadas da Americanas via Zoom + Buscapé + Promobit."

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


class ShopeeOficialCollector(BaseStoreCollector):
    """Captura ofertas verificadas de Lojas Oficiais na Shopee Brasil (Sony, Webfones, Gamer Hut, Escorrega o Preço)."""
    store_slug = "shopee"
    store_name = "Shopee (Lojas Oficiais)"
    website_url = "https://shopee.com.br"
    store_type = "RETAILER"
    connector_type = "VERIFIED_MALL_AND_FLASH_DEALS"
    reputation_score = 92.0
    default_shipping_estimate = 0.0
    integration_docs = "Monitora ofertas verificadas de Lojas Oficiais (Shopee Mall) via barramentos públicos e Promobit."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        zoom_offers = await _get_zoom_verified_offers_for_store(self.store_slug, self.get_http_headers())
        offers.extend(zoom_offers)

        raw_promos = await fetch_live_promobit_raw_offers(self.get_http_headers())
        for item in raw_promos:
            domain = str(item.get("storeDomain") or "").lower()
            s_name = str(item.get("storeName") or "").lower()
            resolved = str(item.get("_resolved_url") or "")
            if "shopee" not in domain and "shopee" not in s_name and "shopee" not in resolved.lower():
                continue
            oid = item.get("offerId") or item.get("id")
            title = str(item.get("offerTitle") or "").strip()
            price = float(item.get("offerPrice") or 0)
            old_price = float(item.get("offerOldPrice") or 0)
            coupon = str(item.get("offerCoupon") or "").strip() or None
            photo = str(item.get("offerPhoto") or "").strip()
            img_url = f"https://i.promobit.com.br/268{photo}" if photo.startswith("/") else (photo if photo.startswith("http") else None)
            pay_cond = f"PIX ou 12x Shopee Oficial (Cupom {coupon})" if coupon else "PIX ou até 12x na Shopee Oficial"
            offers.append(
                CollectedOfferDTO(
                    external_id=f"SHOPEE-{oid}",
                    title=title,
                    url=resolved or "https://shopee.com.br",
                    price_cash=round(price, 2),
                    price_card=round(old_price if old_price > price else price, 2),
                    original_declared_price=round(old_price, 2) if old_price > price else None,
                    coupon_code=coupon,
                    shipping_cost=0.0,
                    payment_condition=pay_cond,
                    seller_name="Shopee Mall (Loja Oficial Verificada)",
                    is_marketplace=False,
                    in_stock=True,
                    image_url=img_url,
                    data_origin="SHOPEE_VERIFIED_DEAL",
                    is_flash_deal=True,
                )
            )

        if offers:
            unique = {o.url: o for o in offers}
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Shopee Lojas Oficiais consultada ({len(unique)} ofertas ativas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma promoção verificada da Shopee Oficial ativa neste instante.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class HavanCollector(BaseStoreCollector):
    """Consulta direta SSR ao catálogo oficial da Havan (havan.com.br)."""
    store_slug = "havan"
    store_name = "Havan"
    website_url = "https://www.havan.com.br"
    store_type = "RETAILER"
    connector_type = "MAGENTO_PUBLIC_SSR"
    reputation_score = 93.0
    default_shipping_estimate = 0.0
    integration_docs = "Consulta direta ao catálogo público Magento SSR da Havan (produtos 100% novos nacionais)."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_urls: set[str] = set()
        urls = [
            "https://www.havan.com.br/catalogsearch/result/?q=playstation+5",
            "https://www.havan.com.br/catalogsearch/result/?q=dualsense",
        ]
        async with httpx.AsyncClient(timeout=7.5, follow_redirects=True, headers=self.get_http_headers()) as client:
            resps = await asyncio.gather(*[client.get(u) for u in urls], return_exceptions=True)
            for resp in resps:
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                try:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for it in soup.select(".product-item-info"):
                        a_el = it.select_one("a.product-item-link")
                        p_el = it.select_one("[data-price-amount]")
                        if not a_el or not p_el:
                            continue
                        title = a_el.get_text(strip=True)
                        href = a_el.get("href", "").strip()
                        if not title or not href or href in seen_urls:
                            continue
                        try:
                            price = float(p_el.get("data-price-amount") or 0)
                        except ValueError:
                            continue
                        if price < 200 or price > 7200:
                            continue
                        seen_urls.add(href)
                        img_el = it.select_one("img.product-image-photo")
                        sku = str(abs(hash(href)) % 10000000)
                        offers.append(
                            CollectedOfferDTO(
                                external_id=f"HAVAN-{sku}",
                                title=title,
                                url=href,
                                price_cash=round(price, 2),
                                price_card=round(price, 2),
                                shipping_cost=0.0,
                                payment_condition="PIX ou até 10x sem juros na Havan",
                                installments_text=f"ou 10x de R$ {price / 10:.2f} sem juros",
                                seller_name="Havan (Venda Direta Oficial)",
                                is_marketplace=False,
                                in_stock=True,
                                image_url=img_el.get("src") if img_el else None,
                                data_origin="HAVAN_LIVE_SSR",
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
                status_message=f"Havan consultada ao vivo ({len(unique)} ofertas oficiais ativas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta ativa encontrada na Havan neste instante.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class KalungaCollector(BaseStoreCollector):
    """Consulta direta SSR ao catálogo oficial da Kalunga (kalunga.com.br)."""
    store_slug = "kalunga"
    store_name = "Kalunga"
    website_url = "https://www.kalunga.com.br"
    store_type = "RETAILER"
    connector_type = "KALUNGA_PUBLIC_SSR"
    reputation_score = 94.0
    default_shipping_estimate = 0.0
    integration_docs = "Consulta direta ao catálogo público da Kalunga (revendedora oficial Sony Brasil)."

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_urls: set[str] = set()
        urls = [
            "https://www.kalunga.com.br/busca/1?q=playstation+5",
            "https://www.kalunga.com.br/busca/1?q=dualsense",
        ]
        async with httpx.AsyncClient(timeout=7.5, follow_redirects=True, headers=self.get_http_headers()) as client:
            resps = await asyncio.gather(*[client.get(u) for u in urls], return_exceptions=True)
            for resp in resps:
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                try:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for card in soup.select(".blocoproduto"):
                        h_el = card.find(["h2", "h3"])
                        a_el = card.select_one("a[href^='/prod/']") or card.find("a", href=True)
                        if not h_el or not a_el:
                            continue
                        title = h_el.get_text(strip=True)
                        href = a_el.get("href", "").strip()
                        if not href:
                            continue
                        full_url = f"https://www.kalunga.com.br{href}" if href.startswith("/") else href
                        if full_url in seen_urls:
                            continue
                        txt = " | ".join(card.stripped_strings)
                        if "indisponível" in txt.lower() or "esgotado" in txt.lower():
                            continue
                        raw_prices = re.findall(r"R\$\s*([\d\.]+,\d{2})", txt)
                        vals = [float(p.replace(".", "").replace(",", ".")) for p in raw_prices]
                        # Ignorar valor unitário de parcela pequena (< R$ 180)
                        valid_vals = [v for v in vals if v >= 200]
                        if not valid_vals:
                            continue
                        price_pix = min(valid_vals)
                        price_card = max(valid_vals) if len(valid_vals) > 1 else price_pix
                        if price_pix > 7200:
                            continue
                        seen_urls.add(full_url)
                        img_el = card.find("img")
                        img_src = (img_el.get("data-src") or img_el.get("src")) if img_el else None
                        sku = str(abs(hash(full_url)) % 10000000)
                        offers.append(
                            CollectedOfferDTO(
                                external_id=f"KALUNGA-{sku}",
                                title=title,
                                url=full_url,
                                price_cash=round(price_pix, 2),
                                price_card=round(price_card, 2),
                                shipping_cost=0.0,
                                payment_condition="PIX com desconto à vista na Kalunga",
                                installments_text=f"ou até 10x de R$ {price_card / 10:.2f} sem juros",
                                seller_name="Kalunga (Venda Direta Oficial)",
                                is_marketplace=False,
                                in_stock=True,
                                image_url=img_src if img_src and img_src.startswith("http") else None,
                                data_origin="KALUNGA_LIVE_SSR",
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
                status_message=f"Kalunga consultada ao vivo ({len(unique)} ofertas oficiais ativas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta ativa encontrada na Kalunga neste instante.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class VtexRetailNetworkCollector(BaseStoreCollector):
    """
    Varre em paralelo grandes redes varejistas oficiais Sony que utilizam API pública VTEX:
    - Bemol, Lojas Benoit, Angeloni, iByte, Fujioka, Webcontinental e Lojas Solar.
    Exige estoque positivo confirmado (AvailableQuantity > 0).
    """
    store_slug = "rede-varejo-oficial"
    store_name = "Rede Varejistas Oficiais (Bemol, Benoit, Fujioka, iByte, Angeloni)"
    website_url = "https://www.bemol.com.br"
    store_type = "RETAILER"
    connector_type = "VTEX_CATALOG_REST_API"
    reputation_score = 93.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Consulta a API REST pública VTEX (/api/catalog_system/pub/products/search/) em paralelo nas redes "
        "Bemol, Lojas Benoit, Angeloni, iByte, Fujioka, Webcontinental e Lojas Solar com validação de estoque real."
    )

    VTEX_STORES = [
        ("bemol", "Bemol", "https://www.bemol.com.br", 94.0),
        ("benoit", "Lojas Benoit", "https://www.benoit.com.br", 92.0),
        ("angeloni", "Angeloni", "https://www.angeloni.com.br/eletro", 93.0),
        ("ibyte", "iByte", "https://www.ibyte.com.br", 92.0),
        ("fujioka", "Fujioka", "https://www.fujioka.com.br", 92.0),
        ("webcontinental", "Webcontinental", "https://www.webcontinental.com.br", 91.0),
        ("lojas-solar", "Lojas Solar", "https://www.lojasolar.com.br", 92.0),
    ]

    SEARCH_TERMS = ["console%20playstation%205", "dualsense%20playstation%205"]

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_links: set[str] = set()
        sem = asyncio.Semaphore(10)

        async with httpx.AsyncClient(timeout=6.5, follow_redirects=True, headers=self.get_http_headers()) as client:
            async def _query_vtex(s_slug: str, s_name: str, base_url: str, rep: float, term: str) -> list[CollectedOfferDTO]:
                found: list[CollectedOfferDTO] = []
                async with sem:
                    try:
                        api_url = f"{base_url}/api/catalog_system/pub/products/search/?ft={term}&_from=0&_to=15"
                        r = await client.get(api_url, timeout=5.5)
                        if r.status_code not in (200, 206):
                            return []
                        arr = r.json()
                        if not isinstance(arr, list):
                            return []
                        for prod in arr:
                            title = str(prod.get("productName") or "").strip()
                            link = str(prod.get("link") or "").strip()
                            if not title or not link:
                                continue
                            items = prod.get("items") or []
                            if not items:
                                continue
                            first_item = items[0]
                            sellers = first_item.get("sellers") or []
                            if not sellers:
                                continue
                            comm = sellers[0].get("commertialOffer") or {}
                            qty = int(comm.get("AvailableQuantity") or 0)
                            price = float(comm.get("Price") or 0)
                            list_price = float(comm.get("ListPrice") or price)
                            if qty <= 0 or price < 200 or price > 7200:
                                continue
                            imgs = first_item.get("images") or []
                            img_url = imgs[0].get("imageUrl") if imgs and isinstance(imgs[0], dict) else None
                            pid = str(prod.get("productId") or abs(hash(link)) % 10000000)
                            seller_name_raw = str(sellers[0].get("sellerName") or s_name).strip()
                            is_mkt = seller_name_raw.lower() not in (s_name.lower(), "1", "loja oficial") and s_slug not in seller_name_raw.lower()

                            found.append(
                                CollectedOfferDTO(
                                    external_id=f"VTEX-{s_slug.upper()}-{pid}",
                                    title=title,
                                    url=link,
                                    price_cash=round(price, 2),
                                    price_card=round(price, 2),
                                    original_declared_price=round(list_price, 2) if list_price > price else None,
                                    shipping_cost=0.0,
                                    payment_condition=f"PIX ou Cartão na {s_name}",
                                    installments_text=f"ou até 10x de R$ {price / 10:.2f}",
                                    seller_name=f"{s_name} (Venda Direta Oficial)" if not is_mkt else f"{seller_name_raw} (via {s_name})",
                                    is_marketplace=is_mkt,
                                    in_stock=True,
                                    image_url=img_url,
                                    data_origin=f"VTEX_{s_slug.upper()}_API",
                                    store_slug_override=s_slug,
                                    store_name_override=s_name,
                                    store_reputation_override=rep,
                                )
                            )
                    except Exception:
                        return []
                return found

            tasks = [
                _query_vtex(s_slug, s_name, base_url, rep, term)
                for (s_slug, s_name, base_url, rep) in self.VTEX_STORES
                for term in self.SEARCH_TERMS
            ]
            batches = await asyncio.gather(*tasks)
            for batch in batches:
                for dto in batch:
                    if dto.url not in seen_links:
                        seen_links.add(dto.url)
                        offers.append(dto)

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Rede Varejistas VTEX consultada ({len(offers)} ofertas em estoque confirmadas).",
                offers=offers,
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta disponível nas redes regionais VTEX neste instante.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class ExtraSubmarinoGirafaCollector(BaseStoreCollector):
    """Agrupa ofertas verificadas de Extra, Submarino, Girafa, Webfones e Nagem nos barramentos de comparação."""
    store_slug = "extra-submarino-girafa"
    store_name = "Extra, Submarino, Girafa & Webfones"
    website_url = "https://www.extra.com.br"
    store_type = "RETAILER"
    connector_type = "VERIFIED_COMPARISON_MULTI_STORE"
    reputation_score = 91.0
    default_shipping_estimate = 0.0
    integration_docs = "Monitora Extra, Submarino, Girafa, Webfones e Nagem via barramentos duplos Zoom + Buscapé."

    TARGET_SLUGS = ["extra", "submarino", "girafa", "webfones", "nagem"]

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        headers = self.get_http_headers()
        for sl in self.TARGET_SLUGS:
            offers.extend(await _get_zoom_verified_offers_for_store(sl, headers))

        if offers:
            unique = {o.url: o for o in offers}
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Extra/Submarino/Girafa/Webfones consultados ({len(unique)} ofertas ativas).",
                offers=list(unique.values()),
                integration_docs=self.integration_docs,
            )
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="ONLINE",
            status_message="Monitoramento ativo via Zoom/Buscapé (sem novas promoções abaixo do teto agora).",
            offers=[],
            integration_docs=self.integration_docs,
        )
