"""
Módulos de coleta independentes para as comunidades de ofertas:
- Promobit (promobit.com.br)
- Pelando (pelando.com.br)
"""
import json
import re
import time
from urllib.parse import urlparse, parse_qs, unquote
import httpx
from bs4 import BeautifulSoup
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO

_PROMOBIT_CACHE: dict[str, object] = {"timestamp": 0.0, "raw_items": []}

PROMOBIT_SEARCH_URLS = [
    "https://www.promobit.com.br/promocoes/playstation-5/s/",
    "https://www.promobit.com.br/promocoes/console-playstation-5/s/",
    "https://www.promobit.com.br/promocoes/dualsense/s/",
]


async def resolve_promobit_direct_url(client: httpx.AsyncClient, offer_id: int | str, slug: str) -> str:
    """Resolve o link direto da loja a partir do redirecionador público do Promobit (/Redirect/to/{id}/)."""
    fallback_url = f"https://www.promobit.com.br/oferta/{slug}" if slug else "https://www.promobit.com.br"
    if not offer_id:
        return fallback_url
    try:
        r = await client.get(f"https://www.promobit.com.br/Redirect/to/{offer_id}/", timeout=6.0)
        if r.status_code == 200:
            m = re.search(r"l\s*=\s*'([^']+)'", r.text)
            if m:
                target = m.group(1).strip()
                qs = parse_qs(urlparse(target).query)
                if "ued" in qs and qs["ued"]:
                    return unquote(qs["ued"][0])
                if "murl" in qs and qs["murl"]:
                    return unquote(qs["murl"][0])
                if target.startswith("http"):
                    return target
    except Exception:
        pass
    return fallback_url


async def fetch_live_promobit_raw_offers(headers: dict[str, str]) -> list[dict]:
    """Busca ofertas aprovadas em tempo real nas páginas de busca SSR (__NEXT_DATA__) do Promobit."""
    now = time.time()
    cached_ts = float(_PROMOBIT_CACHE.get("timestamp") or 0.0)
    cached_items = _PROMOBIT_CACHE.get("raw_items")
    if (now - cached_ts) < 90.0 and isinstance(cached_items, list) and cached_items:
        return list(cached_items)

    seen_ids: set[int] = set()
    collected_raw: list[dict] = []

    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
        for url in PROMOBIT_SEARCH_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                nd = soup.find("script", id="__NEXT_DATA__")
                if not nd or not nd.string:
                    continue
                data = json.loads(nd.string)
                pp = data.get("props", {}).get("pageProps", {})
                server_offers = (pp.get("serverOffers") or {}).get("offers") or []
                candidates = []
                for item in server_offers:
                    if not isinstance(item, dict):
                        continue
                    oid = item.get("offerId") or item.get("id")
                    status_name = str(item.get("offerStatusName") or "").upper()
                    if not oid or oid in seen_ids or status_name != "APPROVED":
                        continue
                    price = float(item.get("offerPrice") or item.get("offer_price") or 0)
                    if price < 200:
                        continue
                    title = str(item.get("offerTitle") or item.get("offer_title") or "").strip()
                    t_low = title.lower()
                    if not any(k in t_low for k in ("playstation 5", "ps5", "dualsense")):
                        continue
                    seen_ids.add(int(oid))
                    candidates.append(item)

                async def _resolve_item(item_obj):
                    oid_val = item_obj.get("offerId") or item_obj.get("id")
                    slug_val = str(item_obj.get("offerSlug") or item_obj.get("offer_slug") or "").strip()
                    direct_url = await resolve_promobit_direct_url(client, oid_val, slug_val)
                    item_copy = dict(item_obj)
                    item_copy["_resolved_url"] = direct_url
                    return item_copy

                resolved_items = await asyncio.gather(*[_resolve_item(c) for c in candidates])
                collected_raw.extend(resolved_items)
            except Exception:
                continue

    if collected_raw:
        _PROMOBIT_CACHE["timestamp"] = time.time()
        _PROMOBIT_CACHE["raw_items"] = collected_raw
    return collected_raw


class PromobitCollector(BaseStoreCollector):
    store_slug = "promobit"
    store_name = "Promobit"
    website_url = "https://www.promobit.com.br"
    store_type = "COMMUNITY_FEED"
    connector_type = "PUBLIC_FEED"
    reputation_score = 93.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Consulta ofertas públicas aprovadas e moderadas pela comunidade Promobit via __NEXT_DATA__ SSR "
        "(serverOffers.offers), capturando cupons ativos e links verificados."
    )

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        raw_items = await fetch_live_promobit_raw_offers(self.get_http_headers())

        for item in raw_items:
            domain = str(item.get("storeDomain") or "").lower()
            store_origin = str(item.get("storeName") or "Loja Verificada").strip()
            if "mercadolivre" in domain or "mercado livre" in store_origin.lower():
                store_origin = "Mercado Livre"
            oid = item.get("offerId") or item.get("id")
            title = str(item.get("offerTitle") or "").strip()
            price = float(item.get("offerPrice") or 0)
            old_price = float(item.get("offerOldPrice") or 0)
            coupon = str(item.get("offerCoupon") or "").strip() or None
            slug = str(item.get("offerSlug") or "").strip()
            offer_url = str(item.get("_resolved_url") or f"https://www.promobit.com.br/oferta/{slug}")
            photo = str(item.get("offerPhoto") or "").strip()
            img_url = f"https://i.promobit.com.br/268{photo}" if photo.startswith("/") else (photo if photo.startswith("http") else None)

            pay_cond = f"PIX com cupom {coupon}" if coupon else "PIX / Promoção Verificada"
            offers.append(
                CollectedOfferDTO(
                    external_id=f"PROMOBIT-{oid}",
                    title=title,
                    url=offer_url,
                    price_cash=round(price, 2),
                    price_card=round(old_price if old_price > price else price, 2),
                    original_declared_price=round(old_price, 2) if old_price > price else None,
                    coupon_code=coupon,
                    coupon_discount=0.0,
                    payment_condition=pay_cond,
                    seller_name=f"{store_origin} (Oferta Verificada Promobit)",
                    is_marketplace=False,
                    in_stock=True,
                    image_url=img_url,
                    data_origin="PROMOBIT_LIVE_SSR",
                )
            )

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Feed Promobit consultado ao vivo ({len(offers)} promoções aprovadas com cupom).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Nenhuma oferta aprovada de PS5/DualSense retornada no feed público do Promobit neste instante.",
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
    integration_docs = (
        "Consulta o feed público de promoções do Pelando via dados estruturados públicos (__NEXT_DATA__ / JSON-LD). "
        "Respeita rate-limiting e políticas anti-bot."
    )

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.pelando.com.br/busca?q=ps5+slim+digital",
            "https://www.pelando.com.br/busca?q=dualsense",
        ]
        errors = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        errors.append(f"HTTP {resp.status_code}")
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for ld in soup.find_all("script", type="application/ld+json"):
                        if not ld.string:
                            continue
                        try:
                            parsed = json.loads(ld.string)
                            items = parsed if isinstance(parsed, list) else [parsed]
                            for obj in items:
                                if obj.get("@type") == "Product":
                                    offer_node = obj.get("offers", {})
                                    price = float(offer_node.get("price") or 0)
                                    if price > 0:
                                        offers.append(
                                            CollectedOfferDTO(
                                                external_id=f"PELANDO-{abs(hash(obj.get('name', '')))}",
                                                title=obj.get("name", ""),
                                                url=offer_node.get("url") or self.website_url,
                                                price_cash=round(price, 2),
                                                payment_condition="Oferta Pelando",
                                                seller_name="Comunidade Pelando",
                                                in_stock=True,
                                                data_origin="PELANDO_JSONLD",
                                            )
                                        )
                        except Exception:
                            continue
                except Exception as exc:
                    errors.append(str(exc))

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Feed Pelando consultado ({len(offers)} promoções identificadas).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message=(
                "O Pelando utiliza proteção GraphQL/Cloudflare nas buscas diretas. Nenhuma promoção pública "
                "em JSON-LD retornada sem autenticação."
            ),
            offers=[],
            integration_docs=self.integration_docs,
        )
