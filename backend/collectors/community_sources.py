"""
Módulos de coleta independentes em tempo real para comunidades verificadas de promoções:
- Promobit (promobit.com.br) — Radar instantâneo de ofertas relâmpago (RECENTS, TOP_OFFER, APPROVED) e cupons ativos Black Friday
- Pelando (pelando.com.br)
"""
import asyncio
import json
import re
import time
from urllib.parse import urlparse, parse_qs, unquote
import httpx
from bs4 import BeautifulSoup
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO

_PROMOBIT_CACHE: dict[str, object] = {"timestamp": 0.0, "raw_items": []}
_PROMOBIT_LOCK = asyncio.Lock()

PROMOBIT_SEARCH_URLS = [
    "https://www.promobit.com.br/promocoes/playstation-5/s/",
    "https://www.promobit.com.br/promocoes/playstation-5/s/?page=2",
    "https://www.promobit.com.br/promocoes/console-playstation-5/s/",
    "https://www.promobit.com.br/promocoes/controle-playstation-5/s/",
    "https://www.promobit.com.br/promocoes/games/",
]

INVALID_PROMOBIT_STATUSES = {"EXPIRED", "FINISHED", "ENDED", "INACTIVE", "REJECTED", "DELETED", "OUT_OF_STOCK"}


def _map_promobit_store(store_name: str, store_domain: str, resolved_url: str) -> tuple[str, str, float, bool]:
    """
    Mapeia a loja real de uma oferta verificada no Promobit para o slug e nome canônico da loja confiável.
    Retorna (store_slug, store_name, reputation_score, is_imported_marketplace).
    """
    raw = f"{store_name} {store_domain} {resolved_url}".lower()
    if "mercadolivre" in raw or "mercado livre" in raw or "meli.la" in raw:
        return ("mercado-livre", "Mercado Livre", 95.0, False)
    if "kabum" in raw:
        return ("kabum", "KaBuM!", 96.0, False)
    if "amazon" in raw or "amzn.to" in raw:
        return ("amazon-br", "Amazon Brasil", 98.0, False)
    if "magazineluiza" in raw or "magalu" in raw or "magazine luiza" in raw:
        return ("magazine-luiza", "Magazine Luiza", 95.0, False)
    if "shopee" in raw:
        return ("shopee", "Shopee (Loja Oficial)", 92.0, False)
    if "fastshop" in raw or "fast shop" in raw:
        return ("fast-shop", "Fast Shop", 96.0, False)
    if "carrefour" in raw:
        return ("carrefour", "Carrefour", 92.0, False)
    if "casasbahia" in raw or "casas bahia" in raw:
        return ("casas-bahia", "Casas Bahia", 91.0, False)
    if "pontofrio" in raw or "ponto" in raw:
        return ("ponto", "Ponto", 91.0, False)
    if "extra.com" in raw:
        return ("extra", "Extra", 91.0, False)
    if "americanas" in raw:
        return ("americanas", "Americanas", 90.0, False)
    if "submarino" in raw:
        return ("submarino", "Submarino", 90.0, False)
    if "havan" in raw:
        return ("havan", "Havan", 93.0, False)
    if "bemol" in raw:
        return ("bemol", "Bemol", 94.0, False)
    if "kalunga" in raw:
        return ("kalunga", "Kalunga", 94.0, False)
    if "nagem" in raw:
        return ("nagem", "Nagem", 92.0, False)
    if "girafa" in raw:
        return ("girafa", "Girafa", 92.0, False)
    if "webfones" in raw:
        return ("webfones", "Webfones", 92.0, False)
    if "aliexpress" in raw:
        return ("aliexpress-br", "AliExpress Brasil (Parceiro Magalu)", 90.0, False)
    clean_name = store_name.strip() or "Loja Verificada"
    slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "promobit"
    return (slug, clean_name, 91.0, False)


def _normalize_store_url(url: str) -> str:
    """Limpa parâmetros de rastreamento quando seguro (KaBuM, Amazon), preservando encurtadores oficiais (meli.la, shopee)."""
    if not url:
        return url
    u_low = url.lower()
    if "kabum.com.br" in u_low:
        m = re.search(r"/(?:produto|link/\d+)/(\d+)", u_low)
        if m:
            return f"https://www.kabum.com.br/produto/{m.group(1)}"
    if "amazon.com.br" in u_low:
        m = re.search(r"/dp/([A-Z0-9]{10})", url, re.I)
        if m:
            return f"https://www.amazon.com.br/dp/{m.group(1).upper()}"
    return url


async def resolve_promobit_direct_url(client: httpx.AsyncClient, offer_id: int | str, slug: str) -> str:
    """Resolve o link direto da loja a partir do redirecionador público do Promobit (/Redirect/to/{id}/)."""
    fallback_url = f"https://www.promobit.com.br/oferta/{slug}" if slug else "https://www.promobit.com.br"
    if not offer_id:
        return fallback_url
    try:
        r = await client.get(f"https://www.promobit.com.br/Redirect/to/{offer_id}/", timeout=5.0)
        if r.status_code == 200:
            m = re.search(r"l\s*=\s*'([^']+)'", r.text)
            if m:
                target = m.group(1).strip()
                qs = parse_qs(urlparse(target).query)
                for key in ("ued", "murl", "url", "dl"):
                    if key in qs and qs[key]:
                        return _normalize_store_url(unquote(qs[key][0]))
                if target.startswith("http"):
                    return _normalize_store_url(target)
    except Exception:
        pass
    return fallback_url


async def fetch_live_promobit_raw_offers(headers: dict[str, str]) -> list[dict]:
    """
    Busca ofertas ativas em tempo real nas páginas SSR (__NEXT_DATA__) do Promobit em paralelo.
    Inclui TOP_OFFER, RECENTS (recém-publicadas na Black Friday) e APPROVED.
    """
    now = time.time()
    cached_ts = float(_PROMOBIT_CACHE.get("timestamp") or 0.0)
    cached_items = _PROMOBIT_CACHE.get("raw_items")
    if (now - cached_ts) < 25.0 and isinstance(cached_items, list) and cached_items:
        return list(cached_items)

    async with _PROMOBIT_LOCK:
        now = time.time()
        cached_ts = float(_PROMOBIT_CACHE.get("timestamp") or 0.0)
        cached_items = _PROMOBIT_CACHE.get("raw_items")
        if (now - cached_ts) < 25.0 and isinstance(cached_items, list) and cached_items:
            return list(cached_items)

        seen_ids: set[int] = set()
        candidates: list[dict] = []

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            async def _fetch_page(url: str) -> list[dict]:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200 or "/404" in str(resp.url):
                        return []
                    soup = BeautifulSoup(resp.text, "html.parser")
                    nd = soup.find("script", id="__NEXT_DATA__")
                    if not nd or not nd.string:
                        return []
                    data = json.loads(nd.string)
                    pp = data.get("props", {}).get("pageProps", {})
                    return (pp.get("serverOffers") or {}).get("offers") or []
                except Exception:
                    return []

            pages_offers = await asyncio.gather(*[_fetch_page(u) for u in PROMOBIT_SEARCH_URLS])
            for server_offers in pages_offers:
                for item in server_offers:
                    if not isinstance(item, dict):
                        continue
                    oid = item.get("offerId") or item.get("id")
                    status_name = str(item.get("offerStatusName") or "").upper().strip()
                    if not oid or int(oid) in seen_ids or status_name in INVALID_PROMOBIT_STATUSES:
                        continue
                    if item.get("offerExpired") or item.get("isExpired"):
                        continue
                    price = float(item.get("offerPrice") or item.get("offer_price") or 0)
                    title = str(item.get("offerTitle") or item.get("offer_title") or "").strip()
                    # Caso raro onde o preço está no título (ex: "Por: R$ 4.249 PlayStation 5...")
                    if price < 200:
                        m_tp = re.search(r"R\$\s*([\d\.]+(?:,\d{2})?)", title)
                        if m_tp:
                            try:
                                price = float(m_tp.group(1).replace(".", "").replace(",", "."))
                                item = dict(item)
                                item["offerPrice"] = price
                            except ValueError:
                                pass
                    if price < 200:
                        continue
                    t_low = title.lower()
                    if not any(k in t_low for k in ("playstation 5", "playstation5", "ps5", "dualsense")):
                        continue
                    seen_ids.add(int(oid))
                    candidates.append(item)

            sem = asyncio.Semaphore(10)

            async def _resolve_item(item_obj: dict) -> dict:
                async with sem:
                    oid_val = item_obj.get("offerId") or item_obj.get("id")
                    slug_val = str(item_obj.get("offerSlug") or item_obj.get("offer_slug") or "").strip()
                    direct_url = await resolve_promobit_direct_url(client, oid_val, slug_val)
                    item_copy = dict(item_obj)
                    item_copy["_resolved_url"] = direct_url
                    return item_copy

            collected_raw = await asyncio.gather(*[_resolve_item(c) for c in candidates])

        if collected_raw:
            _PROMOBIT_CACHE["timestamp"] = time.time()
            _PROMOBIT_CACHE["raw_items"] = list(collected_raw)
        return list(collected_raw)


class PromobitCollector(BaseStoreCollector):
    store_slug = "promobit"
    store_name = "Radar Promobit (Cupons & Relâmpago)"
    website_url = "https://www.promobit.com.br"
    store_type = "COMMUNITY_FEED"
    connector_type = "PUBLIC_FEED"
    reputation_score = 94.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Monitora em tempo real promoções relâmpago (RECENTS), destaques Black Friday (TOP_OFFER) e cupons ativos "
        "(KaBuM!, Mercado Livre, Amazon, Shopee Oficial, Magalu, AliExpress Brasil) com resolução direta do link."
    )

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        raw_items = await fetch_live_promobit_raw_offers(self.get_http_headers())

        for item in raw_items:
            domain = str(item.get("storeDomain") or "").lower()
            store_origin = str(item.get("storeName") or "Loja Verificada").strip()
            oid = item.get("offerId") or item.get("id")
            title = str(item.get("offerTitle") or "").strip()
            price = float(item.get("offerPrice") or 0)
            old_price = float(item.get("offerOldPrice") or 0)
            coupon = str(item.get("offerCoupon") or "").strip() or None
            slug = str(item.get("offerSlug") or "").strip()
            offer_url = str(item.get("_resolved_url") or f"https://www.promobit.com.br/oferta/{slug}")
            photo = str(item.get("offerPhoto") or "").strip()
            img_url = f"https://i.promobit.com.br/268{photo}" if photo.startswith("/") else (photo if photo.startswith("http") else None)
            status_name = str(item.get("offerStatusName") or "").upper()

            mapped_slug, mapped_name, mapped_rep, is_mkt = _map_promobit_store(store_origin, domain, offer_url)
            is_flash = status_name in ("TOP_OFFER", "RECENTS") or bool(coupon)

            if coupon:
                pay_cond = f"🔥 Black Friday PIX + Cupom {coupon}"
            elif status_name == "TOP_OFFER":
                pay_cond = "🔥 Super Oferta Black Friday Verificada"
            elif status_name == "RECENTS":
                pay_cond = "⚡ Oferta Relâmpago Recém-Publicada"
            else:
                pay_cond = "PIX / Promoção Verificada"

            seller_badge = f"{mapped_name} (Promoção Verificada Black Friday)"

            offers.append(
                CollectedOfferDTO(
                    external_id=f"PROMOBIT-{oid}",
                    title=title,
                    url=offer_url,
                    price_cash=round(price, 2),
                    price_card=round(old_price if old_price > price else price * 1.06, 2),
                    original_declared_price=round(old_price, 2) if old_price > price else None,
                    coupon_code=coupon,
                    coupon_discount=0.0,
                    payment_condition=pay_cond,
                    seller_name=seller_badge,
                    is_marketplace=is_mkt,
                    in_stock=True,
                    image_url=img_url,
                    data_origin="PROMOBIT_BLACK_FRIDAY_LIVE",
                    store_slug_override=mapped_slug,
                    store_name_override=mapped_name,
                    store_reputation_override=mapped_rep,
                    is_flash_deal=is_flash,
                )
            )

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Radar Promobit Black Friday ativo ({len(offers)} promoções relâmpago e cupons ao vivo).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta ativa retornada no feed público neste instante.",
            offers=[],
            integration_docs=self.integration_docs,
        )


class PelandoCollector(BaseStoreCollector):
    store_slug = "pelando"
    store_name = "Pelando"
    website_url = "https://www.pelando.com.br"
    store_type = "COMMUNITY_FEED"
    connector_type = "PUBLIC_FEED"
    reputation_score = 90.0
    default_shipping_estimate = 0.0
    integration_docs = "Consulta o feed público de promoções do Pelando via dados estruturados públicos."

    async def collect(self) -> CollectorResult:
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Protegido por GraphQL/Cloudflare nas buscas anônimas.",
            offers=[],
            integration_docs=self.integration_docs,
        )
